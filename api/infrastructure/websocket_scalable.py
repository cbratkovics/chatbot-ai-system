"""
WebSocket Infrastructure at Scale
Socket.IO with Redis adapter, sticky sessions, message queues, and WebRTC
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import jwt
import redis.asyncio as redis
import socketio
from aiohttp import web

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


class MessageType(Enum):
    CHAT = "chat"
    SYSTEM = "system"
    PRESENCE = "presence"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    TYPING = "typing"
    ACK = "ack"


class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class WebSocketConnection:
    session_id: str
    user_id: str
    socket_id: str
    room: str
    status: ConnectionStatus
    last_seen: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    reconnect_attempts: int = 0
    max_reconnects: int = 5


@dataclass
class QueuedMessage:
    id: str
    session_id: str
    message_type: MessageType
    content: dict[str, Any]
    priority: MessagePriority
    timestamp: datetime
    expires_at: datetime | None = None
    retry_count: int = 0


@dataclass
class PresenceInfo:
    user_id: str
    status: str  # online, away, busy, invisible
    last_activity: datetime
    device_info: dict[str, Any] = field(default_factory=dict)
    custom_status: str | None = None


class ScalableWebSocketManager:
    """
    Production-grade WebSocket manager with horizontal scaling capabilities
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

        # Redis for pub/sub and session management
        self.redis_pool = redis.ConnectionPool.from_url(
            config["redis_url"], max_connections=100, retry_on_timeout=True
        )
        self.redis = redis.Redis(connection_pool=self.redis_pool)

        # Socket.IO server with Redis adapter
        self.sio = socketio.AsyncServer(
            async_mode="aiohttp",
            cors_allowed_origins=config.get("cors_origins", ["*"]),
            logger=logger,
            engineio_logger=logger,
        )

        # Connection tracking
        self.connections: dict[str, WebSocketConnection] = {}
        self.user_sessions: dict[str, set[str]] = {}  # user_id -> session_ids
        self.room_members: dict[str, set[str]] = {}  # room -> session_ids

        # Message queue for guaranteed delivery
        self.message_queue: dict[str, list[QueuedMessage]] = {}
        self.processing_queues: set[str] = set()

        # Presence system
        self.presence_info: dict[str, PresenceInfo] = {}

        # WebRTC signaling support
        self.webrtc_rooms: dict[str, dict[str, Any]] = {}

        # Rate limiting
        self.rate_limiters: dict[str, dict[str, Any]] = {}

        # Setup event handlers
        self._setup_event_handlers()

        # Background tasks
        self.cleanup_task = None
        self.queue_processor_task = None
        self.presence_updater_task = None

    async def initialize(self):
        """Initialize the WebSocket manager"""

        # Start background tasks
        self.cleanup_task = asyncio.create_task(self._cleanup_connections())
        self.queue_processor_task = asyncio.create_task(self._process_message_queues())
        self.presence_updater_task = asyncio.create_task(self._update_presence_info())

        # Subscribe to Redis channels for cross-server communication
        await self._setup_redis_subscriptions()

        logger.info("Scalable WebSocket manager initialized")

    async def shutdown(self):
        """Clean shutdown of WebSocket manager"""

        # Cancel background tasks
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.queue_processor_task:
            self.queue_processor_task.cancel()
        if self.presence_updater_task:
            self.presence_updater_task.cancel()

        # Close Redis connections
        await self.redis.close()

        logger.info("WebSocket manager shut down")

    def _setup_event_handlers(self):
        """Setup Socket.IO event handlers"""

        @self.sio.event
        async def connect(sid, environ, auth):
            """Handle client connection"""
            try:
                # Authenticate user
                user_info = await self._authenticate_connection(auth)
                if not user_info:
                    logger.warning(f"Authentication failed for connection {sid}")
                    await self.sio.disconnect(sid)
                    return False

                # Create connection record
                connection = WebSocketConnection(
                    session_id=str(uuid.uuid4()),
                    user_id=user_info["user_id"],
                    socket_id=sid,
                    room=user_info.get("room", f"user_{user_info['user_id']}"),
                    status=ConnectionStatus.CONNECTED,
                    last_seen=datetime.now(UTC),
                    metadata=user_info.get("metadata", {}),
                )

                # Check rate limits
                if not await self._check_rate_limit(user_info["user_id"]):
                    logger.warning(f"Rate limit exceeded for user {user_info['user_id']}")
                    await self.sio.disconnect(sid)
                    return False

                # Store connection
                self.connections[sid] = connection

                # Track user sessions
                if connection.user_id not in self.user_sessions:
                    self.user_sessions[connection.user_id] = set()
                self.user_sessions[connection.user_id].add(connection.session_id)

                # Join room for sticky sessions
                await self.sio.enter_room(sid, connection.room)

                # Track room membership
                if connection.room not in self.room_members:
                    self.room_members[connection.room] = set()
                self.room_members[connection.room].add(connection.session_id)

                # Update presence
                await self._update_user_presence(
                    connection.user_id, "online", user_info.get("device_info", {})
                )

                # Process queued messages
                await self._process_queued_messages(connection.session_id)

                # Notify other clients
                await self._broadcast_presence_update(connection.user_id, "online")

                logger.info(
                    f"User {connection.user_id} connected with session {connection.session_id}"
                )

                return True

            except Exception as e:
                logger.error(f"Connection error: {e}")
                await self.sio.disconnect(sid)
                return False

        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection"""
            try:
                connection = self.connections.get(sid)
                if not connection:
                    return

                # Update connection status
                connection.status = ConnectionStatus.DISCONNECTED
                connection.last_seen = datetime.now(UTC)

                # Leave room
                await self.sio.leave_room(sid, connection.room)

                # Update room membership
                if connection.room in self.room_members:
                    self.room_members[connection.room].discard(connection.session_id)

                # Update user sessions
                if connection.user_id in self.user_sessions:
                    self.user_sessions[connection.user_id].discard(connection.session_id)

                    # Update presence if no other sessions
                    if not self.user_sessions[connection.user_id]:
                        await self._update_user_presence(connection.user_id, "offline")
                        await self._broadcast_presence_update(connection.user_id, "offline")

                # Store disconnection info for potential reconnection
                await self._store_disconnection_info(connection)

                # Clean up connection
                del self.connections[sid]

                logger.info(f"User {connection.user_id} disconnected")

            except Exception as e:
                logger.error(f"Disconnection error: {e}")

        @self.sio.event
        async def message(sid, data):
            """Handle incoming message"""
            try:
                connection = self.connections.get(sid)
                if not connection:
                    return

                # Validate message format
                if not isinstance(data, dict) or "type" not in data:
                    await self.sio.emit("error", {"message": "Invalid message format"}, room=sid)
                    return

                # Update last seen
                connection.last_seen = datetime.now(UTC)

                # Process message based on type
                message_type = MessageType(data["type"])

                if message_type == MessageType.CHAT:
                    await self._handle_chat_message(connection, data)
                elif message_type == MessageType.PRESENCE:
                    await self._handle_presence_message(connection, data)
                elif message_type == MessageType.VOICE:
                    await self._handle_voice_message(connection, data)
                elif message_type == MessageType.TYPING:
                    await self._handle_typing_message(connection, data)
                elif message_type == MessageType.ACK:
                    await self._handle_ack_message(connection, data)
                else:
                    await self._handle_generic_message(connection, data)

            except Exception as e:
                logger.error(f"Message handling error: {e}")
                await self.sio.emit("error", {"message": "Message processing failed"}, room=sid)

        @self.sio.event
        async def join_room(sid, data):
            """Handle room join request"""
            try:
                connection = self.connections.get(sid)
                if not connection:
                    return

                room_id = data.get("room_id")
                if not room_id:
                    return

                # Validate room access
                if not await self._validate_room_access(connection.user_id, room_id):
                    await self.sio.emit("error", {"message": "Access denied"}, room=sid)
                    return

                # Leave current room
                await self.sio.leave_room(sid, connection.room)
                if connection.room in self.room_members:
                    self.room_members[connection.room].discard(connection.session_id)

                # Join new room
                connection.room = room_id
                await self.sio.enter_room(sid, room_id)

                # Update room membership
                if room_id not in self.room_members:
                    self.room_members[room_id] = set()
                self.room_members[room_id].add(connection.session_id)

                # Notify room members
                await self.sio.emit(
                    "user_joined",
                    {"user_id": connection.user_id, "session_id": connection.session_id},
                    room=room_id,
                    skip_sid=sid,
                )

                logger.info(f"User {connection.user_id} joined room {room_id}")

            except Exception as e:
                logger.error(f"Room join error: {e}")

        @self.sio.event
        async def webrtc_signal(sid, data):
            """Handle WebRTC signaling"""
            try:
                connection = self.connections.get(sid)
                if not connection:
                    return

                await self._handle_webrtc_signaling(connection, data)

            except Exception as e:
                logger.error(f"WebRTC signaling error: {e}")

    async def _authenticate_connection(self, auth: dict[str, Any]) -> dict[str, Any] | None:
        """Authenticate WebSocket connection"""
        try:
            token = auth.get("token")
            if not token:
                return None

            # Verify JWT token
            payload = jwt.decode(token, self.config["jwt_secret"], algorithms=["HS256"])

            user_id = payload.get("user_id")
            if not user_id:
                return None

            # Additional validation can be added here
            # e.g., check user status, permissions, etc.

            return {
                "user_id": user_id,
                "room": auth.get("room"),
                "metadata": auth.get("metadata", {}),
                "device_info": auth.get("device_info", {}),
            }

        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        try:
            current_time = time.time()
            window_size = self.config.get("rate_limit_window", 60)  # 1 minute
            max_connections = self.config.get("max_connections_per_user", 10)

            # Get user's rate limit info
            rate_key = f"rate_limit:{user_id}"
            rate_info = await self.redis.hgetall(rate_key)

            if rate_info:
                window_start = float(rate_info.get("window_start", 0))
                connection_count = int(rate_info.get("count", 0))

                # Check if we're in the same window
                if current_time - window_start < window_size:
                    if connection_count >= max_connections:
                        return False
                    else:
                        # Increment count
                        await self.redis.hincrby(rate_key, "count", 1)
                        await self.redis.expire(rate_key, window_size)
                else:
                    # New window
                    await self.redis.hset(
                        rate_key, mapping={"window_start": current_time, "count": 1}
                    )
                    await self.redis.expire(rate_key, window_size)
            else:
                # First connection in window
                await self.redis.hset(rate_key, mapping={"window_start": current_time, "count": 1})
                await self.redis.expire(rate_key, window_size)

            return True

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True  # Allow connection on error

    async def _handle_chat_message(self, connection: WebSocketConnection, data: dict[str, Any]):
        """Handle chat message"""
        try:
            message_id = str(uuid.uuid4())
            content = data.get("content", "")
            target_room = data.get("room", connection.room)

            # Create message
            message = {
                "id": message_id,
                "type": "chat",
                "content": content,
                "sender_id": connection.user_id,
                "session_id": connection.session_id,
                "room": target_room,
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": data.get("metadata", {}),
            }

            # Broadcast to room
            await self.sio.emit("message", message, room=target_room)

            # Queue for offline users if needed
            await self._queue_message_for_offline_users(target_room, message)

            # Send ACK to sender
            await self.sio.emit(
                "message_ack",
                {"message_id": message_id, "status": "delivered"},
                room=connection.socket_id,
            )

        except Exception as e:
            logger.error(f"Chat message error: {e}")

    async def _handle_typing_message(self, connection: WebSocketConnection, data: dict[str, Any]):
        """Handle typing indicator"""
        try:
            typing_data = {
                "user_id": connection.user_id,
                "typing": data.get("typing", False),
                "room": data.get("room", connection.room),
            }

            # Broadcast typing status (excluding sender)
            await self.sio.emit(
                "typing", typing_data, room=connection.room, skip_sid=connection.socket_id
            )

        except Exception as e:
            logger.error(f"Typing message error: {e}")

    async def _handle_webrtc_signaling(self, connection: WebSocketConnection, data: dict[str, Any]):
        """Handle WebRTC signaling messages"""
        try:
            signal_type = data.get("signal_type")
            target_user = data.get("target_user")
            room_id = data.get("room_id", connection.room)

            if not target_user:
                return

            # Forward signaling message to target user
            target_sessions = self.user_sessions.get(target_user, set())

            for session_id in target_sessions:
                # Find socket ID for session
                target_sid = None
                for sid, conn in self.connections.items():
                    if conn.session_id == session_id:
                        target_sid = sid
                        break

                if target_sid:
                    await self.sio.emit(
                        "webrtc_signal",
                        {
                            "signal_type": signal_type,
                            "data": data.get("data"),
                            "from_user": connection.user_id,
                            "room_id": room_id,
                        },
                        room=target_sid,
                    )

        except Exception as e:
            logger.error(f"WebRTC signaling error: {e}")

    async def _update_user_presence(
        self, user_id: str, status: str, device_info: dict[str, Any] = None
    ):
        """Update user presence information"""
        try:
            presence = PresenceInfo(
                user_id=user_id,
                status=status,
                last_activity=datetime.now(UTC),
                device_info=device_info or {},
            )

            self.presence_info[user_id] = presence

            # Store in Redis for cross-server access
            await self.redis.hset(
                f"presence:{user_id}",
                mapping={
                    "status": status,
                    "last_activity": presence.last_activity.isoformat(),
                    "device_info": json.dumps(device_info or {}),
                },
            )
            await self.redis.expire(f"presence:{user_id}", 3600)  # 1 hour TTL

        except Exception as e:
            logger.error(f"Presence update error: {e}")

    async def _broadcast_presence_update(self, user_id: str, status: str):
        """Broadcast presence update to relevant users"""
        try:
            # Find rooms where this user is a member
            user_rooms = set()
            for room, members in self.room_members.items():
                for session_id in members:
                    for conn in self.connections.values():
                        if conn.session_id == session_id and conn.user_id == user_id:
                            user_rooms.add(room)
                            break

            # Broadcast to all relevant rooms
            for room in user_rooms:
                await self.sio.emit(
                    "presence_update",
                    {
                        "user_id": user_id,
                        "status": status,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    room=room,
                )

        except Exception as e:
            logger.error(f"Presence broadcast error: {e}")

    async def _queue_message_for_offline_users(self, room: str, message: dict[str, Any]):
        """Queue message for offline users in room"""
        try:
            # This would typically query a database to find offline users in the room
            # For now, we'll implement a simple in-memory queue

            queued_message = QueuedMessage(
                id=message["id"],
                session_id=message["session_id"],
                message_type=MessageType.CHAT,
                content=message,
                priority=MessagePriority.NORMAL,
                timestamp=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )

            # Store in Redis for persistence
            await self.redis.lpush(
                f"message_queue:{room}",
                json.dumps(
                    {
                        "id": queued_message.id,
                        "content": queued_message.content,
                        "timestamp": queued_message.timestamp.isoformat(),
                        "expires_at": queued_message.expires_at.isoformat()
                        if queued_message.expires_at
                        else None,
                    }
                ),
            )

            # Set TTL on the queue
            await self.redis.expire(f"message_queue:{room}", 604800)  # 7 days

        except Exception as e:
            logger.error(f"Message queuing error: {e}")

    async def _process_queued_messages(self, session_id: str):
        """Process queued messages for a session"""
        try:
            connection = None
            for conn in self.connections.values():
                if conn.session_id == session_id:
                    connection = conn
                    break

            if not connection:
                return

            # Get queued messages for user's room
            queue_key = f"message_queue:{connection.room}"
            messages = await self.redis.lrange(queue_key, 0, -1)

            for message_data in messages:
                try:
                    message = json.loads(message_data)

                    # Check if message hasn't expired
                    if message.get("expires_at"):
                        expires_at = datetime.fromisoformat(message["expires_at"])
                        if datetime.now(UTC) > expires_at:
                            continue

                    # Send message to user
                    await self.sio.emit(
                        "queued_message", message["content"], room=connection.socket_id
                    )

                    # Remove from queue after successful delivery
                    await self.redis.lrem(queue_key, 1, message_data)

                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.error(f"Queued message processing error: {e}")

    async def _process_message_queues(self):
        """Background task to process message queues"""
        while True:
            try:
                await asyncio.sleep(30)  # Process every 30 seconds

                # Get all queue keys
                queue_keys = await self.redis.keys("message_queue:*")

                for queue_key in queue_keys:
                    # Process expired messages
                    messages = await self.redis.lrange(queue_key, 0, -1)

                    for message_data in messages:
                        try:
                            message = json.loads(message_data)

                            if message.get("expires_at"):
                                expires_at = datetime.fromisoformat(message["expires_at"])
                                if datetime.now(UTC) > expires_at:
                                    await self.redis.lrem(queue_key, 1, message_data)

                        except json.JSONDecodeError:
                            # Remove invalid messages
                            await self.redis.lrem(queue_key, 1, message_data)

            except Exception as e:
                logger.error(f"Message queue processing error: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _cleanup_connections(self):
        """Background task to clean up stale connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute

                current_time = datetime.now(UTC)
                stale_connections = []

                for sid, connection in self.connections.items():
                    # Consider connection stale if no activity for 5 minutes
                    if (current_time - connection.last_seen).seconds > 300:
                        stale_connections.append(sid)

                # Clean up stale connections
                for sid in stale_connections:
                    await self.sio.disconnect(sid)

                logger.debug(f"Cleaned up {len(stale_connections)} stale connections")

            except Exception as e:
                logger.error(f"Connection cleanup error: {e}")

    async def _update_presence_info(self):
        """Background task to update presence information"""
        while True:
            try:
                await asyncio.sleep(30)  # Update every 30 seconds

                current_time = datetime.now(UTC)

                # Update presence for active connections
                for connection in self.connections.values():
                    if connection.status == ConnectionStatus.CONNECTED:
                        # Check if user should be marked as away
                        inactive_time = (current_time - connection.last_seen).seconds

                        if inactive_time > 300:  # 5 minutes
                            await self._update_user_presence(connection.user_id, "away")
                        elif inactive_time > 60:  # 1 minute
                            await self._update_user_presence(connection.user_id, "idle")
                        else:
                            await self._update_user_presence(connection.user_id, "online")

            except Exception as e:
                logger.error(f"Presence update error: {e}")

    async def _setup_redis_subscriptions(self):
        """Setup Redis pub/sub for cross-server communication"""
        try:
            # Subscribe to channels for cross-server messaging
            pubsub = self.redis.pubsub()
            await pubsub.subscribe("websocket_broadcast", "presence_updates")

            # Process messages in background
            asyncio.create_task(self._process_redis_messages(pubsub))

        except Exception as e:
            logger.error(f"Redis subscription setup error: {e}")

    async def _process_redis_messages(self, pubsub):
        """Process Redis pub/sub messages"""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"].decode()
                    data = json.loads(message["data"])

                    if channel == "websocket_broadcast":
                        await self._handle_cross_server_broadcast(data)
                    elif channel == "presence_updates":
                        await self._handle_cross_server_presence(data)

        except Exception as e:
            logger.error(f"Redis message processing error: {e}")

    async def _validate_room_access(self, user_id: str, room_id: str) -> bool:
        """Validate if user has access to room"""
        # This would typically check database for room permissions
        # For now, allow all access
        return True

    async def _store_disconnection_info(self, connection: WebSocketConnection):
        """Store disconnection info for reconnection"""
        try:
            disconnect_info = {
                "user_id": connection.user_id,
                "session_id": connection.session_id,
                "room": connection.room,
                "last_seen": connection.last_seen.isoformat(),
                "metadata": connection.metadata,
            }

            # Store for 1 hour to allow reconnection
            await self.redis.setex(
                f"disconnect:{connection.session_id}", 3600, json.dumps(disconnect_info)
            )

        except Exception as e:
            logger.error(f"Disconnection info storage error: {e}")

    async def _handle_ack_message(self, connection: WebSocketConnection, data: dict[str, Any]):
        """Handle message acknowledgment"""
        try:
            message_id = data.get("message_id")
            if message_id:
                # Update message status in database/cache
                await self.redis.hset(f"message_status:{message_id}", "status", "acknowledged")

        except Exception as e:
            logger.error(f"ACK handling error: {e}")

    async def _handle_presence_message(self, connection: WebSocketConnection, data: dict[str, Any]):
        """Handle presence status change"""
        try:
            status = data.get("status", "online")
            custom_status = data.get("custom_status")

            await self._update_user_presence(
                connection.user_id, status, connection.metadata.get("device_info", {})
            )

            if custom_status:
                self.presence_info[connection.user_id].custom_status = custom_status

            await self._broadcast_presence_update(connection.user_id, status)

        except Exception as e:
            logger.error(f"Presence message error: {e}")

    async def _handle_voice_message(self, connection: WebSocketConnection, data: dict[str, Any]):
        """Handle voice message"""
        try:
            # This would typically process voice data
            # For now, just relay to target users
            target_room = data.get("room", connection.room)

            voice_message = {
                "type": "voice",
                "sender_id": connection.user_id,
                "audio_data": data.get("audio_data"),
                "duration": data.get("duration"),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            await self.sio.emit("voice_message", voice_message, room=target_room)

        except Exception as e:
            logger.error(f"Voice message error: {e}")

    async def _handle_generic_message(self, connection: WebSocketConnection, data: dict[str, Any]):
        """Handle generic message types"""
        try:
            # Generic message relay
            await self.sio.emit(
                "message",
                {
                    "type": data["type"],
                    "content": data.get("content", {}),
                    "sender_id": connection.user_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                room=connection.room,
            )

        except Exception as e:
            logger.error(f"Generic message error: {e}")

    async def _handle_cross_server_broadcast(self, data: dict[str, Any]):
        """Handle cross-server broadcast messages"""
        try:
            message_type = data.get("type")
            target_room = data.get("room")
            content = data.get("content")

            if target_room and content:
                await self.sio.emit(message_type, content, room=target_room)

        except Exception as e:
            logger.error(f"Cross-server broadcast error: {e}")

    async def _handle_cross_server_presence(self, data: dict[str, Any]):
        """Handle cross-server presence updates"""
        try:
            user_id = data.get("user_id")
            status = data.get("status")

            if user_id and status:
                await self._broadcast_presence_update(user_id, status)

        except Exception as e:
            logger.error(f"Cross-server presence error: {e}")


class ConsistentHashingManager:
    """
    Consistent hashing for sticky sessions across multiple servers
    """

    def __init__(self, servers: list[str], replicas: int = 3):
        self.servers = servers
        self.replicas = replicas
        self.ring = {}
        self._build_ring()

    def _build_ring(self):
        """Build the consistent hashing ring"""
        for server in self.servers:
            for i in range(self.replicas):
                key = f"{server}:{i}"
                hash_value = self._hash(key)
                self.ring[hash_value] = server

    def _hash(self, key: str) -> int:
        """Hash function for consistent hashing"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def get_server(self, session_id: str) -> str:
        """Get server for session using consistent hashing"""
        hash_value = self._hash(session_id)

        # Find the first server clockwise
        for ring_key in sorted(self.ring.keys()):
            if hash_value <= ring_key:
                return self.ring[ring_key]

        # If no server found, return the first one
        return self.ring[min(self.ring.keys())]

    def add_server(self, server: str):
        """Add server to the ring"""
        self.servers.append(server)
        for i in range(self.replicas):
            key = f"{server}:{i}"
            hash_value = self._hash(key)
            self.ring[hash_value] = server

    def remove_server(self, server: str):
        """Remove server from the ring"""
        if server in self.servers:
            self.servers.remove(server)

        # Remove from ring
        keys_to_remove = []
        for hash_value, ring_server in self.ring.items():
            if ring_server == server:
                keys_to_remove.append(hash_value)

        for key in keys_to_remove:
            del self.ring[key]


class WebSocketApp:
    """
    WebSocket application with aiohttp integration
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.ws_manager = ScalableWebSocketManager(config)
        self.app = web.Application()

        # Attach Socket.IO to aiohttp app
        self.ws_manager.sio.attach(self.app)

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes"""

        # Health check
        self.app.router.add_get("/health", self._health_check)

        # WebSocket connection info
        self.app.router.add_get("/ws/stats", self._get_connection_stats)

        # Presence API
        self.app.router.add_get("/presence/{user_id}", self._get_user_presence)

        # Room management
        self.app.router.add_post("/rooms/{room_id}/broadcast", self._broadcast_to_room)

    async def _health_check(self, request):
        """Health check endpoint"""
        return web.json_response(
            {
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "connections": len(self.ws_manager.connections),
                "active_rooms": len(self.ws_manager.room_members),
            }
        )

    async def _get_connection_stats(self, request):
        """Get WebSocket connection statistics"""
        stats = {
            "total_connections": len(self.ws_manager.connections),
            "active_rooms": len(self.ws_manager.room_members),
            "presence_info": len(self.ws_manager.presence_info),
            "connections_by_status": {},
            "room_sizes": {},
        }

        # Count connections by status
        for connection in self.ws_manager.connections.values():
            status = connection.status.value
            stats["connections_by_status"][status] = (
                stats["connections_by_status"].get(status, 0) + 1
            )

        # Room sizes
        for room, members in self.ws_manager.room_members.items():
            stats["room_sizes"][room] = len(members)

        return web.json_response(stats)

    async def _get_user_presence(self, request):
        """Get user presence information"""
        user_id = request.match_info["user_id"]

        presence = self.ws_manager.presence_info.get(user_id)
        if not presence:
            return web.json_response({"error": "User not found"}, status=404)

        return web.json_response(
            {
                "user_id": presence.user_id,
                "status": presence.status,
                "last_activity": presence.last_activity.isoformat(),
                "device_info": presence.device_info,
                "custom_status": presence.custom_status,
            }
        )

    async def _broadcast_to_room(self, request):
        """Broadcast message to room via HTTP API"""
        room_id = request.match_info["room_id"]
        data = await request.json()

        message = {
            "type": data.get("type", "broadcast"),
            "content": data.get("content"),
            "timestamp": datetime.now(UTC).isoformat(),
            "sender": "system",
        }

        await self.ws_manager.sio.emit("broadcast", message, room=room_id)

        return web.json_response({"status": "sent"})

    async def start_server(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the WebSocket server"""
        await self.ws_manager.initialize()

        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, host, port)
        await site.start()

        logger.info(f"WebSocket server started on {host}:{port}")

    async def stop_server(self):
        """Stop the WebSocket server"""
        await self.ws_manager.shutdown()

"""
Production WebSocket Infrastructure
Scalable WebSocket system with Redis pub/sub, connection pooling, and presence
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import aioredis
from fastapi import HTTPException, WebSocket
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Metrics
ws_connections = Gauge(
    "websocket_connections_active", "Active WebSocket connections", ["region", "node"]
)
ws_messages = Counter("websocket_messages_total", "Total WebSocket messages", ["direction", "type"])
ws_errors = Counter("websocket_errors_total", "WebSocket errors", ["error_type"])
ws_latency = Histogram("websocket_message_latency_seconds", "Message processing latency")
presence_updates = Counter("presence_updates_total", "Presence system updates", ["action"])


class MessageType(Enum):
    CHAT = "chat"
    SYSTEM = "system"
    PRESENCE = "presence"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class ConnectionState(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


@dataclass
class Connection:
    id: str
    websocket: WebSocket
    user_id: str
    tenant_id: str
    session_id: str
    node_id: str
    region: str
    state: ConnectionState = ConnectionState.CONNECTING
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    subscriptions: set[str] = field(default_factory=set)


@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.CHAT
    content: Any = None
    sender_id: str | None = None
    recipient_id: str | None = None
    channel: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class WebSocketManager:
    """Production-ready WebSocket connection manager with horizontal scaling"""

    def __init__(
        self, redis_url: str, node_id: str, region: str, config: dict[str, Any] | None = None
    ):
        self.redis_url = redis_url
        self.node_id = node_id
        self.region = region
        self.config = config or {}

        # Connection pools
        self.connections: dict[str, Connection] = {}
        self.user_connections: dict[str, set[str]] = {}  # user_id -> connection_ids
        self.session_connections: dict[str, set[str]] = {}  # session_id -> connection_ids

        # Redis clients
        self.redis: aioredis.Redis | None = None
        self.pubsub: aioredis.client.PubSub | None = None

        # Configuration
        self.heartbeat_interval = self.config.get("heartbeat_interval", 30)
        self.heartbeat_timeout = self.config.get("heartbeat_timeout", 60)
        self.max_connections_per_user = self.config.get("max_connections_per_user", 5)
        self.max_message_size = self.config.get("max_message_size", 1024 * 1024)  # 1MB
        self.reconnect_window = self.config.get("reconnect_window", 300)  # 5 minutes

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None
        self._pubsub_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # Message handlers
        self.handlers: dict[MessageType, list[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }

    async def initialize(self):
        """Initialize Redis connections and background tasks"""
        # Create Redis pool
        self.redis = await aioredis.from_url(
            self.redis_url, decode_responses=True, max_connections=100, health_check_interval=30
        )

        # Setup pub/sub
        self.pubsub = self.redis.pubsub()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._pubsub_task = asyncio.create_task(self._pubsub_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Register node
        await self._register_node()

        logger.info(f"WebSocket manager initialized: node={self.node_id}, region={self.region}")

    async def shutdown(self):
        """Gracefully shutdown the manager"""
        # Cancel background tasks
        for task in [self._heartbeat_task, self._pubsub_task, self._cleanup_task]:
            if task:
                task.cancel()

        # Close all connections
        for conn_id in list(self.connections.keys()):
            await self.disconnect(conn_id, reason="Server shutdown")

        # Unregister node
        await self._unregister_node()

        # Close Redis connections
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()

    @asynccontextmanager
    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        tenant_id: str,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ):
        """Context manager for WebSocket connections"""
        conn_id = None
        try:
            conn_id = await self._handle_connection(
                websocket, user_id, tenant_id, session_id, metadata
            )
            yield conn_id
        finally:
            if conn_id:
                await self.disconnect(conn_id)

    async def _handle_connection(
        self,
        websocket: WebSocket,
        user_id: str,
        tenant_id: str,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Handle new WebSocket connection"""
        # Check connection limits
        user_conn_count = len(self.user_connections.get(user_id, set()))
        if user_conn_count >= self.max_connections_per_user:
            await websocket.close(code=1008, reason="Connection limit exceeded")
            raise HTTPException(status_code=429, detail="Too many connections")

        # Accept connection
        await websocket.accept()

        # Create connection object
        conn = Connection(
            id=str(uuid.uuid4()),
            websocket=websocket,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            node_id=self.node_id,
            region=self.region,
            state=ConnectionState.CONNECTED,
            metadata=metadata or {},
        )

        # Store connection
        self.connections[conn.id] = conn

        # Update indexes
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(conn.id)

        if session_id not in self.session_connections:
            self.session_connections[session_id] = set()
        self.session_connections[session_id].add(conn.id)

        # Subscribe to channels
        await self._subscribe_connection(conn)

        # Update presence
        await self._update_presence(user_id, "online")

        # Update metrics
        ws_connections.labels(region=self.region, node=self.node_id).inc()

        # Send welcome message
        await self.send_message(
            conn.id,
            Message(
                type=MessageType.SYSTEM,
                content={
                    "event": "connected",
                    "connection_id": conn.id,
                    "node_id": self.node_id,
                    "region": self.region,
                },
            ),
        )

        logger.info(f"WebSocket connected: {conn.id} (user={user_id})")

        return conn.id

    async def disconnect(self, connection_id: str, reason: str = "Normal closure"):
        """Disconnect a WebSocket connection"""
        conn = self.connections.get(connection_id)
        if not conn:
            return

        try:
            # Send disconnect message
            await self.send_message(
                connection_id,
                Message(
                    type=MessageType.SYSTEM, content={"event": "disconnecting", "reason": reason}
                ),
            )

            # Close WebSocket
            await conn.websocket.close(code=1000, reason=reason)

        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")

        finally:
            # Remove from indexes
            self.user_connections.get(conn.user_id, set()).discard(connection_id)
            self.session_connections.get(conn.session_id, set()).discard(connection_id)

            # Unsubscribe from channels
            await self._unsubscribe_connection(conn)

            # Update presence if no more connections
            if not self.user_connections.get(conn.user_id):
                await self._update_presence(conn.user_id, "offline")

            # Remove connection
            del self.connections[connection_id]

            # Update metrics
            ws_connections.labels(region=self.region, node=self.node_id).dec()

            logger.info(f"WebSocket disconnected: {connection_id} ({reason})")

    async def send_message(self, connection_id: str, message: Message) -> bool:
        """Send message to specific connection"""
        conn = self.connections.get(connection_id)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return False

        try:
            # Serialize message
            data = {
                "id": message.id,
                "type": message.type.value,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            }

            # Send via WebSocket
            await conn.websocket.send_json(data)

            # Update metrics
            ws_messages.labels(direction="outbound", type=message.type.value).inc()

            return True

        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            ws_errors.labels(error_type="send_failed").inc()

            # Mark connection as disconnected
            conn.state = ConnectionState.DISCONNECTED
            asyncio.create_task(self.disconnect(connection_id, "Send error"))

            return False

    async def broadcast_to_user(self, user_id: str, message: Message):
        """Broadcast message to all user connections across nodes"""
        # Local connections
        local_conns = self.user_connections.get(user_id, set())
        for conn_id in local_conns:
            await self.send_message(conn_id, message)

        # Remote connections via Redis pub/sub
        channel = f"user:{user_id}"
        await self._publish_message(channel, message)

    async def broadcast_to_session(self, session_id: str, message: Message):
        """Broadcast message to all session connections"""
        # Local connections
        local_conns = self.session_connections.get(session_id, set())
        for conn_id in local_conns:
            await self.send_message(conn_id, message)

        # Remote connections
        channel = f"session:{session_id}"
        await self._publish_message(channel, message)

    async def broadcast_to_tenant(self, tenant_id: str, message: Message):
        """Broadcast message to all tenant connections"""
        # Local connections
        for conn in self.connections.values():
            if conn.tenant_id == tenant_id:
                await self.send_message(conn.id, message)

        # Remote connections
        channel = f"tenant:{tenant_id}"
        await self._publish_message(channel, message)

    async def handle_incoming_message(self, connection_id: str, data: dict[str, Any]):
        """Handle incoming WebSocket message"""
        start_time = time.time()

        conn = self.connections.get(connection_id)
        if not conn:
            return

        try:
            # Parse message
            message = Message(
                type=MessageType(data.get("type", "chat")),
                content=data.get("content"),
                sender_id=conn.user_id,
                metadata=data.get("metadata", {}),
            )

            # Update metrics
            ws_messages.labels(direction="inbound", type=message.type.value).inc()

            # Handle heartbeat
            if message.type == MessageType.HEARTBEAT:
                conn.last_heartbeat = datetime.now(UTC)
                await self.send_message(
                    connection_id, Message(type=MessageType.HEARTBEAT, content="pong")
                )
                return

            # Process message handlers
            handlers = self.handlers.get(message.type, [])
            for handler in handlers:
                try:
                    await handler(conn, message)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
                    ws_errors.labels(error_type="handler_error").inc()

            # Record latency
            ws_latency.observe(time.time() - start_time)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            ws_errors.labels(error_type="parse_error").inc()

            await self.send_message(
                connection_id,
                Message(type=MessageType.ERROR, content={"error": "Invalid message format"}),
            )

    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register message handler"""
        self.handlers[message_type].append(handler)

    # Presence System

    async def _update_presence(self, user_id: str, status: str):
        """Update user presence status"""
        key = f"presence:{user_id}"

        presence_data = {
            "user_id": user_id,
            "status": status,
            "node_id": self.node_id,
            "region": self.region,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Store in Redis with TTL
        await self.redis.setex(key, self.heartbeat_timeout * 2, json.dumps(presence_data))

        # Publish presence update
        await self._publish_message(
            "presence_updates", Message(type=MessageType.PRESENCE, content=presence_data)
        )

        presence_updates.labels(action=status).inc()

    async def get_presence(self, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Get presence status for multiple users"""
        if not user_ids:
            return {}

        # Batch get from Redis
        keys = [f"presence:{user_id}" for user_id in user_ids]
        values = await self.redis.mget(keys)

        result = {}
        for user_id, value in zip(user_ids, values, strict=False):
            if value:
                result[user_id] = json.loads(value)
            else:
                result[user_id] = {"status": "offline"}

        return result

    # Redis Pub/Sub

    async def _subscribe_connection(self, conn: Connection):
        """Subscribe connection to relevant channels"""
        channels = [
            f"user:{conn.user_id}",
            f"session:{conn.session_id}",
            f"tenant:{conn.tenant_id}",
            f"node:{self.node_id}",
        ]

        for channel in channels:
            conn.subscriptions.add(channel)

        # Subscribe to Redis channels if not already
        current_subs = set(self.pubsub.channels.keys())
        new_channels = [ch for ch in channels if ch not in current_subs]

        if new_channels:
            await self.pubsub.subscribe(*new_channels)

    async def _unsubscribe_connection(self, conn: Connection):
        """Unsubscribe connection from channels"""
        # Check if any other connections need these channels
        all_subscriptions = set()
        for other_conn in self.connections.values():
            if other_conn.id != conn.id:
                all_subscriptions.update(other_conn.subscriptions)

        # Unsubscribe from unused channels
        unused_channels = conn.subscriptions - all_subscriptions
        if unused_channels:
            await self.pubsub.unsubscribe(*unused_channels)

    async def _publish_message(self, channel: str, message: Message):
        """Publish message to Redis channel"""
        data = {
            "id": message.id,
            "type": message.type.value,
            "content": message.content,
            "sender_id": message.sender_id,
            "timestamp": message.timestamp.isoformat(),
            "metadata": message.metadata,
            "node_id": self.node_id,
        }

        await self.redis.publish(channel, json.dumps(data))

    async def _pubsub_loop(self):
        """Process Redis pub/sub messages"""
        while True:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)

                if message and message["type"] == "message":
                    await self._handle_pubsub_message(message["channel"], message["data"])

                await asyncio.sleep(0.01)  # Small delay to prevent busy loop

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pub/sub error: {e}")
                await asyncio.sleep(1)

    async def _handle_pubsub_message(self, channel: str, data: str):
        """Handle message from Redis pub/sub"""
        try:
            message_data = json.loads(data)

            # Skip messages from self
            if message_data.get("node_id") == self.node_id:
                return

            # Create message object
            message = Message(
                id=message_data["id"],
                type=MessageType(message_data["type"]),
                content=message_data["content"],
                sender_id=message_data.get("sender_id"),
                metadata=message_data.get("metadata", {}),
            )

            # Find matching connections
            if channel.startswith("user:"):
                user_id = channel.split(":", 1)[1]
                conn_ids = self.user_connections.get(user_id, set())
            elif channel.startswith("session:"):
                session_id = channel.split(":", 1)[1]
                conn_ids = self.session_connections.get(session_id, set())
            elif channel.startswith("tenant:"):
                tenant_id = channel.split(":", 1)[1]
                conn_ids = [c.id for c in self.connections.values() if c.tenant_id == tenant_id]
            else:
                conn_ids = []

            # Send to matching connections
            for conn_id in conn_ids:
                await self.send_message(conn_id, message)

        except Exception as e:
            logger.error(f"Error handling pub/sub message: {e}")

    # Background Tasks

    async def _heartbeat_loop(self):
        """Send periodic heartbeats and check connection health"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                now = datetime.now(UTC)
                dead_connections = []

                for conn_id, conn in self.connections.items():
                    # Check last heartbeat
                    time_since_heartbeat = (now - conn.last_heartbeat).total_seconds()

                    if time_since_heartbeat > self.heartbeat_timeout:
                        dead_connections.append(conn_id)
                    elif time_since_heartbeat > self.heartbeat_interval:
                        # Send heartbeat ping
                        await self.send_message(
                            conn_id, Message(type=MessageType.HEARTBEAT, content="ping")
                        )

                # Disconnect dead connections
                for conn_id in dead_connections:
                    await self.disconnect(conn_id, "Heartbeat timeout")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")

    async def _cleanup_loop(self):
        """Periodic cleanup tasks"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                # Clean up empty collections
                empty_users = [
                    user_id for user_id, conns in self.user_connections.items() if not conns
                ]
                for user_id in empty_users:
                    del self.user_connections[user_id]

                empty_sessions = [
                    session_id
                    for session_id, conns in self.session_connections.items()
                    if not conns
                ]
                for session_id in empty_sessions:
                    del self.session_connections[session_id]

                # Update node registration
                await self._register_node()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    # Node Management

    async def _register_node(self):
        """Register this node in Redis"""
        node_data = {
            "node_id": self.node_id,
            "region": self.region,
            "connections": len(self.connections),
            "started_at": datetime.now(UTC).isoformat(),
            "last_update": datetime.now(UTC).isoformat(),
        }

        await self.redis.setex(
            f"ws_node:{self.node_id}", 120, json.dumps(node_data)  # 2 minute TTL
        )

    async def _unregister_node(self):
        """Unregister this node from Redis"""
        await self.redis.delete(f"ws_node:{self.node_id}")

    async def get_cluster_status(self) -> dict[str, Any]:
        """Get status of all nodes in cluster"""
        pattern = "ws_node:*"
        nodes = []

        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

            if keys:
                values = await self.redis.mget(keys)
                for _key, value in zip(keys, values, strict=False):
                    if value:
                        nodes.append(json.loads(value))

            if cursor == 0:
                break

        total_connections = sum(node["connections"] for node in nodes)

        return {
            "nodes": nodes,
            "total_nodes": len(nodes),
            "total_connections": total_connections,
            "regions": list(set(node["region"] for node in nodes)),
        }

    # Reconnection Support

    async def handle_reconnection(
        self, websocket: WebSocket, user_id: str, old_connection_id: str
    ) -> str | None:
        """Handle reconnection with session recovery"""
        # Check if old connection exists
        reconnect_key = f"reconnect:{old_connection_id}"
        session_data = await self.redis.get(reconnect_key)

        if not session_data:
            return None

        data = json.loads(session_data)

        # Verify user
        if data["user_id"] != user_id:
            return None

        # Create new connection with same session
        new_conn_id = await self._handle_connection(
            websocket, user_id, data["tenant_id"], data["session_id"], data.get("metadata", {})
        )

        # Send missed messages if any
        missed_messages_key = f"missed_messages:{old_connection_id}"
        missed_messages = await self.redis.lrange(missed_messages_key, 0, -1)

        for msg_data in missed_messages:
            message = Message(**json.loads(msg_data))
            await self.send_message(new_conn_id, message)

        # Clean up
        await self.redis.delete(reconnect_key, missed_messages_key)

        logger.info(f"Reconnection successful: {old_connection_id} -> {new_conn_id}")

        return new_conn_id

    async def enable_reconnection(self, connection_id: str):
        """Enable reconnection for a connection"""
        conn = self.connections.get(connection_id)
        if not conn:
            return

        # Store session data for reconnection
        session_data = {
            "user_id": conn.user_id,
            "tenant_id": conn.tenant_id,
            "session_id": conn.session_id,
            "metadata": conn.metadata,
        }

        await self.redis.setex(
            f"reconnect:{connection_id}", self.reconnect_window, json.dumps(session_data)
        )

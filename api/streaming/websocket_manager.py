"""Enhanced WebSocket manager with reconnection, heartbeat, and room-based broadcasting."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


@dataclass
class ConnectionInfo:
    """WebSocket connection information."""

    websocket: WebSocket
    session_id: str
    tenant_id: str | None
    user_id: str | None
    state: ConnectionState
    connected_at: datetime
    last_heartbeat: datetime
    room_ids: set[str]
    metadata: dict[str, Any]
    message_queue: list[dict[str, Any]]
    reconnect_token: str | None


class WebSocketManager:
    """Enhanced WebSocket connection manager with advanced features."""

    def __init__(
        self,
        heartbeat_interval: int = 30,
        heartbeat_timeout: int = 60,
        max_connections: int = 1000,
        max_queue_size: int = 100,
        enable_rooms: bool = True,
    ):
        """Initialize WebSocket manager.

        Args:
            heartbeat_interval: Heartbeat interval in seconds
            heartbeat_timeout: Heartbeat timeout in seconds
            max_connections: Maximum concurrent connections
            max_queue_size: Maximum message queue size per connection
            enable_rooms: Enable room-based broadcasting
        """
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.max_connections = max_connections
        self.max_queue_size = max_queue_size
        self.enable_rooms = enable_rooms

        # Connection storage
        self.connections: dict[str, ConnectionInfo] = {}
        self.reconnect_tokens: dict[str, str] = {}  # token -> session_id

        # Room management
        self.rooms: dict[str, set[str]] = {}  # room_id -> session_ids

        # Background tasks
        self.heartbeat_task = None
        self.cleanup_task = None

        # Statistics
        self.stats = {
            "total_connections": 0,
            "total_messages_sent": 0,
            "total_messages_received": 0,
            "total_reconnections": 0,
            "total_disconnections": 0,
        }

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
        reconnect_token: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConnectionInfo:
        """Accept WebSocket connection.

        Args:
            websocket: WebSocket instance
            session_id: Session identifier
            tenant_id: Tenant identifier
            user_id: User identifier
            reconnect_token: Token for reconnection
            metadata: Connection metadata

        Returns:
            Connection information
        """
        # Check connection limit
        if len(self.connections) >= self.max_connections:
            await websocket.close(code=1008, reason="Connection limit reached")
            raise Exception("Connection limit reached")

        # Handle reconnection
        if reconnect_token and reconnect_token in self.reconnect_tokens:
            old_session_id = self.reconnect_tokens[reconnect_token]
            if old_session_id in self.connections:
                # Restore connection state
                old_conn = self.connections[old_session_id]
                session_id = old_session_id
                tenant_id = tenant_id or old_conn.tenant_id
                user_id = user_id or old_conn.user_id

                # Send queued messages
                await self._send_queued_messages(websocket, old_conn.message_queue)

                self.stats["total_reconnections"] += 1
                logger.info(f"WebSocket reconnected: {session_id}")

        # Accept connection
        await websocket.accept()

        # Create connection info
        conn_info = ConnectionInfo(
            websocket=websocket,
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            state=ConnectionState.CONNECTED,
            connected_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow(),
            room_ids=set(),
            metadata=metadata or {},
            message_queue=[],
            reconnect_token=self._generate_reconnect_token(),
        )

        # Store connection
        self.connections[session_id] = conn_info
        self.reconnect_tokens[conn_info.reconnect_token] = session_id

        # Send connection confirmation
        await self.send_message(
            session_id,
            {
                "type": "connection",
                "status": "connected",
                "session_id": session_id,
                "reconnect_token": conn_info.reconnect_token,
                "heartbeat_interval": self.heartbeat_interval,
            },
        )

        # Start background tasks if not running
        if not self.heartbeat_task:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if not self.cleanup_task:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        self.stats["total_connections"] += 1
        logger.info(f"WebSocket connected: {session_id}")

        return conn_info

    async def disconnect(self, session_id: str, code: int = 1000, reason: str = "Normal closure"):
        """Disconnect WebSocket connection.

        Args:
            session_id: Session identifier
            code: Close code
            reason: Close reason
        """
        if session_id not in self.connections:
            return

        conn_info = self.connections[session_id]

        # Update state
        conn_info.state = ConnectionState.DISCONNECTED

        # Leave all rooms
        for room_id in list(conn_info.room_ids):
            await self.leave_room(session_id, room_id)

        # Close WebSocket
        try:
            await conn_info.websocket.close(code=code, reason=reason)
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")

        # Remove connection
        del self.connections[session_id]

        # Keep reconnect token for a while
        asyncio.create_task(
            self._cleanup_reconnect_token(conn_info.reconnect_token, delay=300)  # 5 minutes
        )

        self.stats["total_disconnections"] += 1
        logger.info(f"WebSocket disconnected: {session_id}")

    async def send_message(self, session_id: str, message: dict[str, Any]) -> bool:
        """Send message to specific connection.

        Args:
            session_id: Session identifier
            message: Message to send

        Returns:
            True if sent successfully
        """
        if session_id not in self.connections:
            return False

        conn_info = self.connections[session_id]

        try:
            # Add timestamp if not present
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()

            # Send message
            await conn_info.websocket.send_json(message)

            self.stats["total_messages_sent"] += 1
            return True

        except WebSocketDisconnect:
            # Connection lost, queue message
            await self._queue_message(session_id, message)
            conn_info.state = ConnectionState.RECONNECTING
            return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await self._queue_message(session_id, message)
            return False

    async def broadcast(self, message: dict[str, Any], exclude: list[str] | None = None):
        """Broadcast message to all connections.

        Args:
            message: Message to broadcast
            exclude: Session IDs to exclude
        """
        exclude = exclude or []

        tasks = []
        for session_id in self.connections:
            if session_id not in exclude:
                task = asyncio.create_task(self.send_message(session_id, message))
                tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def join_room(self, session_id: str, room_id: str) -> bool:
        """Join a room for broadcasting.

        Args:
            session_id: Session identifier
            room_id: Room identifier

        Returns:
            True if joined successfully
        """
        if not self.enable_rooms:
            return False

        if session_id not in self.connections:
            return False

        # Add to room
        if room_id not in self.rooms:
            self.rooms[room_id] = set()

        self.rooms[room_id].add(session_id)
        self.connections[session_id].room_ids.add(room_id)

        # Notify room members
        await self.room_broadcast(
            room_id,
            {
                "type": "room_event",
                "event": "user_joined",
                "room_id": room_id,
                "session_id": session_id,
            },
            exclude=[session_id],
        )

        logger.info(f"Session {session_id} joined room {room_id}")
        return True

    async def leave_room(self, session_id: str, room_id: str) -> bool:
        """Leave a room.

        Args:
            session_id: Session identifier
            room_id: Room identifier

        Returns:
            True if left successfully
        """
        if not self.enable_rooms:
            return False

        if room_id not in self.rooms:
            return False

        if session_id in self.rooms[room_id]:
            self.rooms[room_id].remove(session_id)

            if session_id in self.connections:
                self.connections[session_id].room_ids.discard(room_id)

            # Clean up empty room
            if not self.rooms[room_id]:
                del self.rooms[room_id]
            else:
                # Notify remaining members
                await self.room_broadcast(
                    room_id,
                    {
                        "type": "room_event",
                        "event": "user_left",
                        "room_id": room_id,
                        "session_id": session_id,
                    },
                )

            logger.info(f"Session {session_id} left room {room_id}")
            return True

        return False

    async def room_broadcast(
        self, room_id: str, message: dict[str, Any], exclude: list[str] | None = None
    ):
        """Broadcast message to all room members.

        Args:
            room_id: Room identifier
            message: Message to broadcast
            exclude: Session IDs to exclude
        """
        if not self.enable_rooms or room_id not in self.rooms:
            return

        exclude = exclude or []

        tasks = []
        for session_id in self.rooms[room_id]:
            if session_id not in exclude:
                task = asyncio.create_task(self.send_message(session_id, message))
                tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_heartbeat(self, session_id: str):
        """Handle heartbeat from client.

        Args:
            session_id: Session identifier
        """
        if session_id in self.connections:
            self.connections[session_id].last_heartbeat = datetime.utcnow()

            # Send pong
            await self.send_message(
                session_id, {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
            )

    async def _heartbeat_loop(self):
        """Background task to send heartbeats and check connection health."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                current_time = datetime.utcnow()
                timeout_threshold = current_time - timedelta(seconds=self.heartbeat_timeout)

                # Send heartbeats and check timeouts
                for session_id, conn_info in list(self.connections.items()):
                    # Check for timeout
                    if conn_info.last_heartbeat < timeout_threshold:
                        logger.warning(f"Heartbeat timeout for session {session_id}")
                        await self.disconnect(session_id, code=1001, reason="Heartbeat timeout")
                        continue

                    # Send ping
                    await self.send_message(
                        session_id, {"type": "ping", "timestamp": current_time.isoformat()}
                    )

            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")

    async def _cleanup_loop(self):
        """Background task to clean up stale connections and data."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                current_time = datetime.utcnow()

                # Clean up stale connections
                for session_id, conn_info in list(self.connections.items()):
                    if conn_info.state == ConnectionState.RECONNECTING:
                        # Check reconnection timeout (5 minutes)
                        if current_time - conn_info.last_heartbeat > timedelta(minutes=5):
                            await self.disconnect(
                                session_id, code=1001, reason="Reconnection timeout"
                            )

                # Clean up message queues
                for conn_info in self.connections.values():
                    if len(conn_info.message_queue) > self.max_queue_size:
                        # Remove oldest messages
                        conn_info.message_queue = conn_info.message_queue[-self.max_queue_size :]

            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _queue_message(self, session_id: str, message: dict[str, Any]):
        """Queue message for later delivery.

        Args:
            session_id: Session identifier
            message: Message to queue
        """
        if session_id in self.connections:
            conn_info = self.connections[session_id]

            # Add to queue with limit
            if len(conn_info.message_queue) < self.max_queue_size:
                conn_info.message_queue.append(message)
            else:
                # Remove oldest and add new
                conn_info.message_queue.pop(0)
                conn_info.message_queue.append(message)

    async def _send_queued_messages(self, websocket: WebSocket, queue: list[dict[str, Any]]):
        """Send queued messages to reconnected client.

        Args:
            websocket: WebSocket connection
            queue: Message queue
        """
        if not queue:
            return

        # Send queue indicator
        await websocket.send_json({"type": "queued_messages", "count": len(queue)})

        # Send all queued messages
        for message in queue:
            try:
                await websocket.send_json(message)
                await asyncio.sleep(0.01)  # Small delay to prevent flooding
            except Exception as e:
                logger.error(f"Error sending queued message: {e}")
                break

        # Clear queue
        queue.clear()

    def _generate_reconnect_token(self) -> str:
        """Generate unique reconnect token.

        Returns:
            Reconnect token
        """
        import secrets

        return secrets.token_urlsafe(32)

    async def _cleanup_reconnect_token(self, token: str, delay: int):
        """Clean up reconnect token after delay.

        Args:
            token: Reconnect token
            delay: Delay in seconds
        """
        await asyncio.sleep(delay)
        if token in self.reconnect_tokens:
            del self.reconnect_tokens[token]

    async def get_connection_info(self, session_id: str) -> dict[str, Any] | None:
        """Get connection information.

        Args:
            session_id: Session identifier

        Returns:
            Connection information
        """
        if session_id not in self.connections:
            return None

        conn_info = self.connections[session_id]

        return {
            "session_id": session_id,
            "tenant_id": conn_info.tenant_id,
            "user_id": conn_info.user_id,
            "state": conn_info.state.value,
            "connected_at": conn_info.connected_at.isoformat(),
            "last_heartbeat": conn_info.last_heartbeat.isoformat(),
            "rooms": list(conn_info.room_ids),
            "queue_size": len(conn_info.message_queue),
            "metadata": conn_info.metadata,
        }

    async def get_stats(self) -> dict[str, Any]:
        """Get manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "active_connections": len(self.connections),
            "max_connections": self.max_connections,
            "total_rooms": len(self.rooms),
            "total_connections": self.stats["total_connections"],
            "total_messages_sent": self.stats["total_messages_sent"],
            "total_messages_received": self.stats["total_messages_received"],
            "total_reconnections": self.stats["total_reconnections"],
            "total_disconnections": self.stats["total_disconnections"],
            "connection_states": {
                state.value: sum(1 for c in self.connections.values() if c.state == state)
                for state in ConnectionState
            },
        }


# Global manager instance
manager = WebSocketManager(
    heartbeat_interval=30,
    heartbeat_timeout=60,
    max_connections=1000,
    max_queue_size=100,
    enable_rooms=True,
)

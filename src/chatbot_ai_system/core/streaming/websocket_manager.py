"""WebSocket connection manager with pooling and heartbeat."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections with pooling and heartbeat."""

    def __init__(
        self,
        max_connections: int = 1000,
        heartbeat_interval: int = 30,
        connection_timeout: int = 300,
    ):
        """Initialize WebSocket manager.

        Args:
            max_connections: Maximum number of connections
            heartbeat_interval: Heartbeat interval in seconds
            connection_timeout: Connection timeout in seconds
        """
        self.max_connections = max_connections
        self.heartbeat_interval = heartbeat_interval
        self.connection_timeout = connection_timeout

        self.connections: dict[str, dict[str, Any]] = {}
        self.user_connections: dict[str, set[str]] = {}
        self.room_connections: dict[str, set[str]] = {}

        self.is_running = False
        self.heartbeat_task: asyncio.Task | None = None

    async def accept_connection(
        self,
        websocket: WebSocket,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Accept WebSocket connection.

        Args:
            websocket: WebSocket connection
            user_id: User identifier
            metadata: Connection metadata

        Returns:
            Connection ID

        Raises:
            ConnectionError: If connection pool is full
        """
        if len(self.connections) >= self.max_connections:
            raise ConnectionError("Connection pool full")

        await websocket.accept()

        connection_id = str(uuid.uuid4())
        self.connections[connection_id] = {
            "websocket": websocket,
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "metadata": metadata or {},
        }

        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)

        logger.info(f"Accepted connection {connection_id} for user {user_id}")

        if not self.is_running:
            await self.start_heartbeat()

        return connection_id

    async def disconnect(self, connection_id: str):
        """Disconnect WebSocket connection.

        Args:
            connection_id: Connection identifier
        """
        if connection_id not in self.connections:
            return

        connection = self.connections[connection_id]
        user_id = connection.get("user_id")

        try:
            await connection["websocket"].close()
        except Exception as e:
            logger.error(f"Error closing websocket: {e}")

        del self.connections[connection_id]

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        for _room_id, connections in self.room_connections.items():
            connections.discard(connection_id)

        logger.info(f"Disconnected connection {connection_id}")

        if not self.connections and self.is_running:
            await self.stop_heartbeat()

    async def send_to_connection(self, connection_id: str, message: dict[str, Any]) -> bool:
        """Send message to specific connection.

        Args:
            connection_id: Connection identifier
            message: Message to send

        Returns:
            Success status
        """
        if connection_id not in self.connections:
            return False

        try:
            websocket = self.connections[connection_id]["websocket"]
            await websocket.send_json(message)
            self.connections[connection_id]["last_activity"] = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            await self.disconnect(connection_id)
            return False

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> int:
        """Send message to all connections of a user.

        Args:
            user_id: User identifier
            message: Message to send

        Returns:
            Number of successful sends
        """
        if user_id not in self.user_connections:
            return 0

        success_count = 0
        for connection_id in list(self.user_connections[user_id]):
            if await self.send_to_connection(connection_id, message):
                success_count += 1

        return success_count

    async def broadcast(self, message: dict[str, Any], exclude: set[str] | None = None) -> int:
        """Broadcast message to all connections.

        Args:
            message: Message to broadcast
            exclude: Connection IDs to exclude

        Returns:
            Number of successful sends
        """
        exclude = exclude or set()
        success_count = 0

        for connection_id in list(self.connections.keys()):
            if connection_id not in exclude:
                if await self.send_to_connection(connection_id, message):
                    success_count += 1

        return success_count

    async def join_room(self, connection_id: str, room_id: str):
        """Add connection to room.

        Args:
            connection_id: Connection identifier
            room_id: Room identifier
        """
        if connection_id not in self.connections:
            return

        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()

        self.room_connections[room_id].add(connection_id)
        self.connections[connection_id]["metadata"]["room_id"] = room_id

        logger.info(f"Connection {connection_id} joined room {room_id}")

    async def leave_room(self, connection_id: str, room_id: str):
        """Remove connection from room.

        Args:
            connection_id: Connection identifier
            room_id: Room identifier
        """
        if room_id in self.room_connections:
            self.room_connections[room_id].discard(connection_id)

            if not self.room_connections[room_id]:
                del self.room_connections[room_id]

        if connection_id in self.connections:
            self.connections[connection_id]["metadata"].pop("room_id", None)

        logger.info(f"Connection {connection_id} left room {room_id}")

    async def send_to_room(
        self, room_id: str, message: dict[str, Any], exclude: set[str] | None = None
    ) -> int:
        """Send message to all connections in room.

        Args:
            room_id: Room identifier
            message: Message to send
            exclude: Connection IDs to exclude

        Returns:
            Number of successful sends
        """
        if room_id not in self.room_connections:
            return 0

        exclude = exclude or set()
        success_count = 0

        for connection_id in list(self.room_connections[room_id]):
            if connection_id not in exclude:
                if await self.send_to_connection(connection_id, message):
                    success_count += 1

        return success_count

    async def start_heartbeat(self):
        """Start heartbeat task."""
        if self.is_running:
            return

        self.is_running = True
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Started heartbeat task")

    async def stop_heartbeat(self):
        """Stop heartbeat task."""
        if not self.is_running:
            return

        self.is_running = False

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None

        logger.info("Stopped heartbeat task")

    async def _heartbeat_loop(self):
        """Heartbeat loop to check connection health."""
        while self.is_running:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                current_time = datetime.utcnow()
                disconnected = []

                for connection_id, connection in list(self.connections.items()):
                    last_activity = connection["last_activity"]
                    time_since_activity = (current_time - last_activity).total_seconds()

                    if time_since_activity > self.connection_timeout:
                        disconnected.append(connection_id)
                    else:
                        await self.send_to_connection(
                            connection_id, {"type": "ping", "timestamp": current_time.isoformat()}
                        )

                for connection_id in disconnected:
                    logger.warning(f"Connection {connection_id} timed out")
                    await self.disconnect(connection_id)

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def get_connection_count(self) -> int:
        """Get current connection count.

        Returns:
            Number of active connections
        """
        return len(self.connections)

    def get_user_count(self) -> int:
        """Get unique user count.

        Returns:
            Number of unique users
        """
        return len(self.user_connections)

    def get_room_count(self) -> int:
        """Get room count.

        Returns:
            Number of active rooms
        """
        return len(self.room_connections)

    def get_statistics(self) -> dict[str, Any]:
        """Get connection statistics.

        Returns:
            Connection statistics
        """
        return {
            "total_connections": self.get_connection_count(),
            "unique_users": self.get_user_count(),
            "active_rooms": self.get_room_count(),
            "max_connections": self.max_connections,
            "capacity_used": self.get_connection_count() / self.max_connections,
            "heartbeat_interval": self.heartbeat_interval,
            "connection_timeout": self.connection_timeout,
        }

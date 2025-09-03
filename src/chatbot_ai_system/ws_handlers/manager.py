"""WebSocket connection management with multi-tenancy support."""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from fastapi import WebSocket, WebSocketDisconnect

from .events import (
    ErrorEvent,
    EventType,
    HeartbeatEvent,
    WebSocketEvent,
    create_connection_event,
)

logger = logging.getLogger(__name__)


@dataclass
class ConnectionStats:
    """Statistics for a WebSocket connection."""

    connected_at: float = field(default_factory=time.time)
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    @property
    def uptime_seconds(self) -> float:
        """Get connection uptime in seconds."""
        return time.time() - self.connected_at

    @property
    def is_stale(self, stale_threshold: float = 300) -> bool:
        """Check if connection is stale (no activity for threshold seconds)."""
        return time.time() - self.last_activity > stale_threshold


@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection with metadata."""

    id: str = field(default_factory=lambda: str(uuid4()))
    websocket: WebSocket = None
    tenant_id: UUID | None = None
    user_id: str | None = None
    conversation_id: UUID | None = None

    # Connection state
    authenticated: bool = False
    subscribed_events: set[EventType] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)

    # Statistics
    stats: ConnectionStats = field(default_factory=ConnectionStats)

    # Rate limiting
    message_timestamps: list[float] = field(default_factory=list)

    def __post_init__(self):
        """Initialize connection after creation."""
        if self.websocket:
            # Add all basic events by default
            self.subscribed_events.update(
                [
                    EventType.CONNECTION_ESTABLISHED,
                    EventType.CONNECTION_CLOSED,
                    EventType.CONNECTION_ERROR,
                    EventType.HEARTBEAT,
                    EventType.SYSTEM_MESSAGE,
                ]
            )

    async def send_event(self, event: WebSocketEvent):
        """Send event through WebSocket connection."""
        if not self.websocket:
            raise RuntimeError("WebSocket is not available")

        # Check if connection is subscribed to this event type
        if event.type not in self.subscribed_events:
            logger.debug(f"Connection {self.id} not subscribed to {event.type}")
            return

        # Add connection context
        event.connection_id = self.id
        event.tenant_id = self.tenant_id
        event.user_id = self.user_id

        try:
            message = event.to_json()
            await self.websocket.send_text(message)

            # Update statistics
            self.stats.messages_sent += 1
            self.stats.bytes_sent += len(message.encode("utf-8"))
            self.stats.last_activity = time.time()

            logger.debug(f"Sent event {event.type} to connection {self.id}")

        except WebSocketDisconnect as e:
            logger.warning(f"Failed to send event to connection {self.id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending event to connection {self.id}: {e}")
            raise

    async def receive_event(self) -> WebSocketEvent | None:
        """Receive and parse event from WebSocket connection."""
        if not self.websocket:
            raise RuntimeError("WebSocket is not available")

        try:
            message = await self.websocket.receive_text()

            # Update statistics
            self.stats.messages_received += 1
            self.stats.bytes_received += len(message.encode("utf-8"))
            self.stats.last_activity = time.time()

            # Parse event
            event = WebSocketEvent.from_json(message)
            event.connection_id = self.id

            logger.debug(f"Received event {event.type} from connection {self.id}")
            return event

        except WebSocketDisconnect:
            logger.info(f"Connection {self.id} disconnected")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from connection {self.id}: {e}")
            # Send error event
            error_event = ErrorEvent(
                error_message="Invalid JSON format", error_code="invalid_json", retryable=True
            )
            await self.send_event(error_event)
            return None
        except Exception as e:
            logger.error(f"Unexpected error receiving from connection {self.id}: {e}")
            return None

    def subscribe_to_event(self, event_type: EventType):
        """Subscribe to an event type."""
        self.subscribed_events.add(event_type)
        logger.debug(f"Connection {self.id} subscribed to {event_type}")

    def unsubscribe_from_event(self, event_type: EventType):
        """Unsubscribe from an event type."""
        self.subscribed_events.discard(event_type)
        logger.debug(f"Connection {self.id} unsubscribed from {event_type}")

    def is_rate_limited(self, max_messages: int = 60, window_seconds: int = 60) -> bool:
        """Check if connection is rate limited."""
        now = time.time()
        # Remove old timestamps outside the window
        self.message_timestamps = [
            ts for ts in self.message_timestamps if now - ts <= window_seconds
        ]

        # Add current timestamp
        self.message_timestamps.append(now)

        return len(self.message_timestamps) > max_messages

    async def close(self, code: int = 1000, reason: str = "Connection closed"):
        """Close WebSocket connection."""
        if self.websocket:
            try:
                await self.websocket.close(code=code, reason=reason)
                logger.info(f"Closed connection {self.id}: {reason}")
            except Exception as e:
                logger.error(f"Error closing connection {self.id}: {e}")


class ConnectionManager:
    """Manages WebSocket connections with multi-tenant support."""

    def __init__(self, heartbeat_interval: int = 30, max_connections_per_tenant: int = 100):
        self.connections: dict[str, WebSocketConnection] = {}
        self.tenant_connections: dict[UUID, set[str]] = {}
        self.user_connections: dict[str, set[str]] = {}
        self.conversation_connections: dict[UUID, set[str]] = {}

        self.heartbeat_interval = heartbeat_interval
        self.max_connections_per_tenant = max_connections_per_tenant

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # Statistics
        self.total_connections = 0
        self.total_messages_sent = 0
        self.total_messages_received = 0

        logger.info(f"Connection manager initialized with {heartbeat_interval}s heartbeat")

    async def start_background_tasks(self):
        """Start background tasks for heartbeat and cleanup."""
        if not self._heartbeat_task or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Started heartbeat task")

        if not self._cleanup_task or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started cleanup task")

    async def stop_background_tasks(self):
        """Stop background tasks."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped heartbeat task")

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped cleanup task")

    async def connect(
        self,
        websocket: WebSocket,
        tenant_id: UUID | None = None,
        user_id: str | None = None,
        conversation_id: UUID | None = None,
    ) -> WebSocketConnection:
        """Accept new WebSocket connection."""

        # Check tenant connection limits
        if tenant_id and tenant_id in self.tenant_connections:
            if len(self.tenant_connections[tenant_id]) >= self.max_connections_per_tenant:
                await websocket.close(code=4008, reason="Too many connections for tenant")
                raise RuntimeError(f"Tenant {tenant_id} has reached connection limit")

        # Accept WebSocket connection
        await websocket.accept()

        # Create connection object
        connection = WebSocketConnection(
            websocket=websocket,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        # Store connection
        self.connections[connection.id] = connection

        # Index by tenant
        if tenant_id:
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = set()
            self.tenant_connections[tenant_id].add(connection.id)

        # Index by user
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection.id)

        # Index by conversation
        if conversation_id:
            if conversation_id not in self.conversation_connections:
                self.conversation_connections[conversation_id] = set()
            self.conversation_connections[conversation_id].add(connection.id)

        self.total_connections += 1

        # Send connection established event
        established_event = create_connection_event(
            EventType.CONNECTION_ESTABLISHED,
            connection.id,
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=user_id,
            conversation_id=str(conversation_id) if conversation_id else None,
            server_time=time.time(),
        )
        await connection.send_event(established_event)

        logger.info(
            f"New connection established: {connection.id} (tenant: {tenant_id}, user: {user_id})"
        )

        # Start background tasks if not running
        await self.start_background_tasks()

        return connection

    async def disconnect(self, connection_id: str, code: int = 1000, reason: str = "Disconnected"):
        """Disconnect and cleanup connection."""
        connection = self.connections.get(connection_id)
        if not connection:
            logger.warning(f"Connection {connection_id} not found for disconnect")
            return

        # Send connection closed event
        try:
            closed_event = create_connection_event(
                EventType.CONNECTION_CLOSED,
                connection_id,
                reason=reason,
                uptime_seconds=connection.stats.uptime_seconds,
                messages_sent=connection.stats.messages_sent,
                messages_received=connection.stats.messages_received,
            )
            await connection.send_event(closed_event)
        except Exception as e:
            logger.debug(f"Could not send close event to {connection_id}: {e}")

        # Close WebSocket
        await connection.close(code=code, reason=reason)

        # Remove from indexes
        if connection.tenant_id and connection.tenant_id in self.tenant_connections:
            self.tenant_connections[connection.tenant_id].discard(connection_id)
            if not self.tenant_connections[connection.tenant_id]:
                del self.tenant_connections[connection.tenant_id]

        if connection.user_id and connection.user_id in self.user_connections:
            self.user_connections[connection.user_id].discard(connection_id)
            if not self.user_connections[connection.user_id]:
                del self.user_connections[connection.user_id]

        if (
            connection.conversation_id
            and connection.conversation_id in self.conversation_connections
        ):
            self.conversation_connections[connection.conversation_id].discard(connection_id)
            if not self.conversation_connections[connection.conversation_id]:
                del self.conversation_connections[connection.conversation_id]

        # Remove main connection
        del self.connections[connection_id]

        logger.info(f"Connection {connection_id} disconnected and cleaned up")

    async def broadcast_to_tenant(self, tenant_id: UUID, event: WebSocketEvent):
        """Broadcast event to all connections for a tenant."""
        connection_ids = self.tenant_connections.get(tenant_id, set())
        await self._broadcast_to_connections(connection_ids, event)

    async def broadcast_to_user(self, user_id: str, event: WebSocketEvent):
        """Broadcast event to all connections for a user."""
        connection_ids = self.user_connections.get(user_id, set())
        await self._broadcast_to_connections(connection_ids, event)

    async def broadcast_to_conversation(self, conversation_id: UUID, event: WebSocketEvent):
        """Broadcast event to all connections for a conversation."""
        connection_ids = self.conversation_connections.get(conversation_id, set())
        await self._broadcast_to_connections(connection_ids, event)

    async def broadcast_to_all(self, event: WebSocketEvent):
        """Broadcast event to all active connections."""
        connection_ids = set(self.connections.keys())
        await self._broadcast_to_connections(connection_ids, event)

    async def _broadcast_to_connections(self, connection_ids: set[str], event: WebSocketEvent):
        """Broadcast event to specific connections."""
        if not connection_ids:
            return

        failed_connections = []

        # Send to all connections concurrently
        async def send_to_connection(connection_id: str):
            connection = self.connections.get(connection_id)
            if connection:
                try:
                    await connection.send_event(event)
                    self.total_messages_sent += 1
                except Exception as e:
                    logger.warning(f"Failed to send to connection {connection_id}: {e}")
                    failed_connections.append(connection_id)

        # Execute sends concurrently
        tasks = [send_to_connection(conn_id) for conn_id in connection_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Cleanup failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id, code=1006, reason="Send failed")

    async def _heartbeat_loop(self):
        """Background task to send heartbeat to all connections."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if not self.connections:
                    continue

                heartbeat_event = HeartbeatEvent()
                await self.broadcast_to_all(heartbeat_event)

                logger.debug(f"Sent heartbeat to {len(self.connections)} connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def _cleanup_loop(self):
        """Background task to cleanup stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Run cleanup every minute

                stale_connections = []

                for connection_id, connection in self.connections.items():
                    if connection.stats.is_stale:
                        stale_connections.append(connection_id)

                # Disconnect stale connections
                for connection_id in stale_connections:
                    await self.disconnect(connection_id, code=1000, reason="Stale connection")

                if stale_connections:
                    logger.info(f"Cleaned up {len(stale_connections)} stale connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def get_connection(self, connection_id: str) -> WebSocketConnection | None:
        """Get connection by ID."""
        return self.connections.get(connection_id)

    def get_connection_stats(self) -> dict:
        """Get overall connection statistics."""
        active_connections = len(self.connections)
        total_uptime = sum(conn.stats.uptime_seconds for conn in self.connections.values())
        avg_uptime = total_uptime / max(active_connections, 1)

        return {
            "active_connections": active_connections,
            "total_connections": self.total_connections,
            "connections_by_tenant": {
                str(tenant_id): len(conn_ids)
                for tenant_id, conn_ids in self.tenant_connections.items()
            },
            "total_messages_sent": self.total_messages_sent,
            "total_messages_received": sum(
                conn.stats.messages_received for conn in self.connections.values()
            ),
            "average_uptime_seconds": avg_uptime,
            "heartbeat_interval": self.heartbeat_interval,
        }

    @asynccontextmanager
    async def connection_context(self, connection_id: str):
        """Context manager for safely working with connections."""
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection {connection_id} not found")

        try:
            yield connection
        except WebSocketDisconnect:
            await self.disconnect(connection_id, reason="Connection lost")
        except Exception as e:
            logger.error(f"Error in connection context for {connection_id}: {e}")
            await self.disconnect(connection_id, code=1011, reason="Server error")
            raise

    async def shutdown(self):
        """Gracefully shutdown connection manager."""
        logger.info("Shutting down connection manager...")

        # Stop background tasks
        await self.stop_background_tasks()

        # Disconnect all connections
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id, code=1001, reason="Server shutdown")

        logger.info("Connection manager shutdown complete")


# Global connection manager instance
connection_manager = ConnectionManager()

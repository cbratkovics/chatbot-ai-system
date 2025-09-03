"""
WebSocket connection manager with connection pooling and heartbeat.
"""

import asyncio
import uuid
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect
from prometheus_client import Gauge, Counter, Histogram
import json

logger = logging.getLogger(__name__)

# Prometheus metrics
ws_connections_active = Gauge('ws_connections_active', 'Number of active WebSocket connections')
ws_connections_total = Counter('ws_connections_total', 'Total number of WebSocket connections')
ws_messages_sent = Counter('ws_messages_sent', 'Total messages sent via WebSocket')
ws_messages_received = Counter('ws_messages_received', 'Total messages received via WebSocket')
ws_connection_duration = Histogram('ws_connection_duration_seconds', 'WebSocket connection duration')
ws_message_latency = Histogram('ws_message_latency_seconds', 'WebSocket message processing latency')


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    
    connection_id: str
    websocket: WebSocket
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    client_info: Dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    is_authenticated: bool = False
    pending_messages: List[Dict[str, Any]] = field(default_factory=list)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def get_connection_duration(self) -> float:
        """Get connection duration in seconds."""
        return (datetime.utcnow() - self.connected_at).total_seconds()
    
    def is_inactive(self, timeout_seconds: int = 300) -> bool:
        """Check if connection is inactive."""
        inactive_duration = (datetime.utcnow() - self.last_activity).total_seconds()
        return inactive_duration > timeout_seconds


class WebSocketManager:
    """Singleton WebSocket connection manager."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize WebSocket manager."""
        if not self._initialized:
            self.active_connections: Dict[str, ConnectionInfo] = {}
            self.user_connections: Dict[str, Set[str]] = defaultdict(set)
            self.max_connections = 100
            self.heartbeat_interval = 30  # seconds
            self.inactive_timeout = 300  # 5 minutes
            self.message_queue_size = 100
            self._heartbeat_task = None
            self._cleanup_task = None
            self._lock = asyncio.Lock()
            self._initialized = True
            
            logger.info("WebSocket manager initialized")
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            user_id: Optional user identifier
            client_info: Optional client information
        
        Returns:
            Connection ID
        
        Raises:
            Exception: If max connections reached
        """
        async with self._lock:
            # Check connection limit
            if len(self.active_connections) >= self.max_connections:
                await websocket.close(code=1008, reason="Max connections reached")
                raise Exception(f"Max connections ({self.max_connections}) reached")
            
            # Accept connection
            await websocket.accept()
            
            # Generate connection ID
            connection_id = str(uuid.uuid4())
            
            # Create connection info
            connection_info = ConnectionInfo(
                connection_id=connection_id,
                websocket=websocket,
                user_id=user_id,
                client_info=client_info or {}
            )
            
            # Register connection
            self.active_connections[connection_id] = connection_info
            
            if user_id:
                self.user_connections[user_id].add(connection_id)
            
            # Update metrics
            ws_connections_active.set(len(self.active_connections))
            ws_connections_total.inc()
            
            # Start background tasks if not running
            if not self._heartbeat_task or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            if not self._cleanup_task or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info(
                "WebSocket connection established",
                extra={
                    "connection_id": connection_id,
                    "user_id": user_id,
                    "total_connections": len(self.active_connections)
                }
            )
            
            # Send welcome message
            await self.send_personal_message(
                connection_id,
                {
                    "type": "connection",
                    "data": {
                        "connection_id": connection_id,
                        "status": "connected",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
            return connection_id
    
    async def disconnect(self, connection_id: str, code: int = 1000, reason: str = "Normal closure"):
        """
        Disconnect and unregister a WebSocket connection.
        
        Args:
            connection_id: Connection ID to disconnect
            code: WebSocket close code
            reason: Disconnect reason
        """
        async with self._lock:
            if connection_id not in self.active_connections:
                return
            
            connection_info = self.active_connections[connection_id]
            
            # Record connection duration
            duration = connection_info.get_connection_duration()
            ws_connection_duration.observe(duration)
            
            # Close WebSocket
            try:
                await connection_info.websocket.close(code=code, reason=reason)
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            
            # Remove from active connections
            del self.active_connections[connection_id]
            
            # Remove from user connections
            if connection_info.user_id:
                self.user_connections[connection_info.user_id].discard(connection_id)
                if not self.user_connections[connection_info.user_id]:
                    del self.user_connections[connection_info.user_id]
            
            # Update metrics
            ws_connections_active.set(len(self.active_connections))
            
            logger.info(
                "WebSocket connection closed",
                extra={
                    "connection_id": connection_id,
                    "user_id": connection_info.user_id,
                    "duration": duration,
                    "message_count": connection_info.message_count,
                    "remaining_connections": len(self.active_connections)
                }
            )
    
    async def send_personal_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Send message to a specific connection.
        
        Args:
            connection_id: Connection ID
            message: Message to send
        
        Returns:
            Success status
        """
        if connection_id not in self.active_connections:
            logger.warning(f"Connection {connection_id} not found")
            return False
        
        connection_info = self.active_connections[connection_id]
        
        try:
            # Convert message to JSON
            message_json = json.dumps(message)
            
            # Send message
            await connection_info.websocket.send_text(message_json)
            
            # Update statistics
            connection_info.message_count += 1
            connection_info.bytes_sent += len(message_json)
            connection_info.update_activity()
            ws_messages_sent.inc()
            
            return True
            
        except WebSocketDisconnect:
            await self.disconnect(connection_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            return False
    
    async def send_user_message(self, user_id: str, message: Dict[str, Any]) -> int:
        """
        Send message to all connections of a user.
        
        Args:
            user_id: User ID
            message: Message to send
        
        Returns:
            Number of successful sends
        """
        if user_id not in self.user_connections:
            return 0
        
        success_count = 0
        failed_connections = []
        
        for connection_id in list(self.user_connections[user_id]):
            if await self.send_personal_message(connection_id, message):
                success_count += 1
            else:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id)
        
        return success_count
    
    async def broadcast(self, message: Dict[str, Any], exclude: Optional[Set[str]] = None) -> int:
        """
        Broadcast message to all connections.
        
        Args:
            message: Message to broadcast
            exclude: Connection IDs to exclude
        
        Returns:
            Number of successful sends
        """
        exclude = exclude or set()
        success_count = 0
        failed_connections = []
        
        for connection_id in list(self.active_connections.keys()):
            if connection_id in exclude:
                continue
            
            if await self.send_personal_message(connection_id, message):
                success_count += 1
            else:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id)
        
        return success_count
    
    async def receive_message(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Receive message from a connection.
        
        Args:
            connection_id: Connection ID
        
        Returns:
            Received message or None
        """
        if connection_id not in self.active_connections:
            return None
        
        connection_info = self.active_connections[connection_id]
        
        try:
            # Receive message
            message_text = await connection_info.websocket.receive_text()
            
            # Parse JSON
            message = json.loads(message_text)
            
            # Update statistics
            connection_info.bytes_received += len(message_text)
            connection_info.update_activity()
            ws_messages_received.inc()
            
            return message
            
        except WebSocketDisconnect:
            await self.disconnect(connection_id)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {connection_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error receiving message from {connection_id}: {e}")
            return None
    
    async def queue_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Queue message for a connection (for reconnection support).
        
        Args:
            connection_id: Connection ID
            message: Message to queue
        
        Returns:
            Success status
        """
        if connection_id not in self.active_connections:
            return False
        
        connection_info = self.active_connections[connection_id]
        
        # Limit queue size
        if len(connection_info.pending_messages) >= self.message_queue_size:
            connection_info.pending_messages.pop(0)  # Remove oldest
        
        connection_info.pending_messages.append(message)
        return True
    
    async def flush_pending_messages(self, connection_id: str) -> int:
        """
        Send all pending messages for a connection.
        
        Args:
            connection_id: Connection ID
        
        Returns:
            Number of messages sent
        """
        if connection_id not in self.active_connections:
            return 0
        
        connection_info = self.active_connections[connection_id]
        sent_count = 0
        
        while connection_info.pending_messages:
            message = connection_info.pending_messages.pop(0)
            if await self.send_personal_message(connection_id, message):
                sent_count += 1
            else:
                # Re-queue on failure
                connection_info.pending_messages.insert(0, message)
                break
        
        return sent_count
    
    async def _heartbeat_loop(self):
        """Background task to send heartbeat pings."""
        while self.active_connections:
            try:
                # Send ping to all connections
                ping_message = {
                    "type": "ping",
                    "data": {
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                
                failed_connections = []
                
                for connection_id in list(self.active_connections.keys()):
                    try:
                        connection_info = self.active_connections[connection_id]
                        await connection_info.websocket.send_json(ping_message)
                    except:
                        failed_connections.append(connection_id)
                
                # Disconnect failed connections
                for connection_id in failed_connections:
                    await self.disconnect(connection_id, code=1001, reason="Heartbeat failed")
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _cleanup_loop(self):
        """Background task to clean up inactive connections."""
        while self.active_connections:
            try:
                # Find inactive connections
                inactive_connections = []
                
                for connection_id, connection_info in self.active_connections.items():
                    if connection_info.is_inactive(self.inactive_timeout):
                        inactive_connections.append(connection_id)
                        logger.info(f"Cleaning up inactive connection: {connection_id}")
                
                # Disconnect inactive connections
                for connection_id in inactive_connections:
                    await self.disconnect(connection_id, code=1001, reason="Inactive timeout")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)
    
    def get_connection_info(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get information about a connection."""
        return self.active_connections.get(connection_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics."""
        total_messages = sum(c.message_count for c in self.active_connections.values())
        total_bytes_sent = sum(c.bytes_sent for c in self.active_connections.values())
        total_bytes_received = sum(c.bytes_received for c in self.active_connections.values())
        
        return {
            "active_connections": len(self.active_connections),
            "max_connections": self.max_connections,
            "total_users": len(self.user_connections),
            "total_messages": total_messages,
            "total_bytes_sent": total_bytes_sent,
            "total_bytes_received": total_bytes_received,
            "heartbeat_interval": self.heartbeat_interval,
            "inactive_timeout": self.inactive_timeout
        }
    
    async def shutdown(self):
        """Gracefully shutdown all connections."""
        logger.info("Shutting down WebSocket manager")
        
        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Close all connections
        for connection_id in list(self.active_connections.keys()):
            await self.disconnect(connection_id, code=1001, reason="Server shutdown")
        
        logger.info("WebSocket manager shutdown complete")
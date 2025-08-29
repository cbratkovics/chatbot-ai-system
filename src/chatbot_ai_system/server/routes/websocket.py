"""WebSocket routes for real-time communication."""

import asyncio
import json
import time
from typing import Dict, Any, Set

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from ...config import settings

logger = structlog.get_logger()
router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_count = 0
    
    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """Accept and register a WebSocket connection."""
        # Check connection limits
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        
        if len(self.active_connections[client_id]) >= settings.WS_MAX_CONNECTIONS_PER_USER:
            logger.warning(
                "WebSocket connection limit exceeded",
                client_id=client_id,
                limit=settings.WS_MAX_CONNECTIONS_PER_USER,
            )
            return False
        
        if self.connection_count >= settings.WS_MAX_CONNECTIONS:
            logger.warning(
                "Global WebSocket connection limit exceeded",
                total_connections=self.connection_count,
                limit=settings.WS_MAX_CONNECTIONS,
            )
            return False
        
        await websocket.accept()
        self.active_connections[client_id].add(websocket)
        self.connection_count += 1
        
        logger.info(
            "WebSocket connected",
            client_id=client_id,
            total_connections=self.connection_count,
        )
        return True
    
    def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
            self.connection_count -= 1
            
            logger.info(
                "WebSocket disconnected",
                client_id=client_id,
                total_connections=self.connection_count,
            )
    
    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message to a specific WebSocket."""
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.send_json(message)
    
    async def broadcast(self, client_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections for a client."""
        if client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                await self.send_message(connection, message)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    client_id = None
    
    try:
        # Extract client ID from query params or headers
        client_id = websocket.query_params.get("client_id", "anonymous")
        
        # Try to connect
        if not await manager.connect(websocket, client_id):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Connection limit exceeded",
            )
            return
        
        # Send welcome message
        await manager.send_message(
            websocket,
            {
                "type": "connection",
                "status": "connected",
                "message": "Welcome to chatbot-ai-system WebSocket",
                "timestamp": time.time(),
            },
        )
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(
            heartbeat(websocket, client_id)
        )
        
        # Message loop
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            logger.debug(
                "WebSocket message received",
                client_id=client_id,
                message_type=data.get("type"),
            )
            
            # Handle different message types
            if data.get("type") == "ping":
                await manager.send_message(
                    websocket,
                    {"type": "pong", "timestamp": time.time()},
                )
            
            elif data.get("type") == "chat":
                # TODO: Process chat message through provider
                await manager.send_message(
                    websocket,
                    {
                        "type": "chat_response",
                        "content": f"Echo: {data.get('content', '')}",
                        "timestamp": time.time(),
                    },
                )
            
            else:
                await manager.send_message(
                    websocket,
                    {
                        "type": "error",
                        "message": f"Unknown message type: {data.get('type')}",
                        "timestamp": time.time(),
                    },
                )
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client", client_id=client_id)
    
    except Exception as e:
        logger.error(
            "WebSocket error",
            client_id=client_id,
            error=str(e),
        )
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR,
                reason="Internal server error",
            )
    
    finally:
        if client_id:
            manager.disconnect(websocket, client_id)
        if 'heartbeat_task' in locals():
            heartbeat_task.cancel()


async def heartbeat(websocket: WebSocket, client_id: str):
    """Send periodic heartbeat messages."""
    try:
        while websocket.application_state == WebSocketState.CONNECTED:
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
            await manager.send_message(
                websocket,
                {"type": "heartbeat", "timestamp": time.time()},
            )
    except Exception as e:
        logger.debug(
            "Heartbeat stopped",
            client_id=client_id,
            reason=str(e),
        )
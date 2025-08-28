"""WebSocket routes for real-time chat functionality."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from api.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Minimal WebSocket endpoint for testing."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


@router.get("/ws/health")
async def websocket_health():
    """Health check for WebSocket system."""
    return {
        "status": "healthy",
        "websocket_manager": {
            "status": "healthy",
            "active_connections": 0,
        },
    }


@router.get("/ws/test", response_class=HTMLResponse)
async def websocket_test_page():
    """Serve a simple HTML page for testing WebSocket functionality."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test</title>
    </head>
    <body>
        <h1>WebSocket Test Page</h1>
        <p>WebSocket endpoint: ws://localhost:{settings.PORT}/ws</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

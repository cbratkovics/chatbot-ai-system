"""
WebSocket API endpoint for real-time chat streaming.
"""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import HTMLResponse
import json

from ..config import get_settings, Settings
from ..websocket.ws_manager import WebSocketManager
from ..websocket.ws_handlers import MessageHandler

logger = logging.getLogger(__name__)

# Create router
ws_router = APIRouter(
    prefix="/ws",
    tags=["websocket"]
)

# Initialize components
ws_manager = WebSocketManager()
message_handler = MessageHandler()

# Provider factory (similar to chat.py)
class ProviderFactory:
    """Factory for creating streaming-capable providers."""
    
    MODEL_PROVIDER_MAP = {
        # OpenAI models
        "gpt-3.5-turbo": "openai",
        "gpt-3.5-turbo-16k": "openai",
        "gpt-4": "openai",
        "gpt-4-turbo-preview": "openai",
        
        # Anthropic models
        "claude-3-opus-20240229": "anthropic",
        "claude-3-sonnet-20240229": "anthropic",
        "claude-3-haiku-20240307": "anthropic",
    }
    
    @classmethod
    def create_streaming_provider(cls, model: str, settings: Settings):
        """Create a streaming-capable provider."""
        provider_name = cls.MODEL_PROVIDER_MAP.get(model)
        
        if not provider_name:
            raise ValueError(f"Model '{model}' not supported for streaming")
        
        if provider_name == "openai":
            if not settings.has_openai_key:
                raise ValueError("OpenAI API key not configured")
            # Import streaming-enhanced provider
            from ..providers.openai_provider import OpenAIProvider
            return OpenAIProvider(
                api_key=settings.openai_api_key,
                timeout=settings.request_timeout,
                max_retries=settings.max_retries
            )
        
        elif provider_name == "anthropic":
            if not settings.has_anthropic_key:
                raise ValueError("Anthropic API key not configured")
            from ..providers.anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                api_key=settings.anthropic_api_key,
                timeout=settings.request_timeout,
                max_retries=settings.max_retries
            )
        
        else:
            raise ValueError(f"Unknown provider: {provider_name}")


@ws_router.websocket("/chat")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Authentication token"),
    client_id: Optional[str] = Query(None, description="Client identifier"),
    settings: Settings = Depends(get_settings)
):
    """
    WebSocket endpoint for streaming chat.
    
    Args:
        websocket: WebSocket connection
        token: Optional authentication token
        client_id: Optional client identifier
        settings: Application settings
    
    WebSocket Protocol:
        Client -> Server:
        {
            "type": "chat",
            "id": "msg-123",
            "data": {
                "message": "Hello",
                "model": "gpt-3.5-turbo",
                "stream": true,
                "temperature": 0.7
            }
        }
        
        Server -> Client (streaming):
        {
            "type": "stream",
            "id": "msg-123",
            "data": {
                "chunk": "Hello",
                "index": 0,
                "finished": false
            }
        }
        
        Server -> Client (complete):
        {
            "type": "complete",
            "id": "msg-123",
            "data": {
                "full_response": "Hello! How can I help?",
                "model": "gpt-3.5-turbo",
                "tokens": 8,
                "cached": false,
                "duration_ms": 1234.5
            }
        }
    """
    connection_id = None
    
    try:
        # Extract user info from token (placeholder for auth)
        user_id = None
        if token:
            # TODO: Validate token and extract user_id
            user_id = f"user_{token[:8]}"  # Mock implementation
        
        # Client info
        client_info = {
            "client_id": client_id,
            "user_agent": websocket.headers.get("user-agent", "unknown"),
            "origin": websocket.headers.get("origin", "unknown")
        }
        
        # Accept connection
        connection_id = await ws_manager.connect(
            websocket=websocket,
            user_id=user_id,
            client_info=client_info
        )
        
        logger.info(f"WebSocket connection established: {connection_id}")
        
        # Message processing loop
        while True:
            try:
                # Receive message
                message = await ws_manager.receive_message(connection_id)
                
                if not message:
                    break
                
                # Handle message
                response = await message_handler.handle_message(
                    websocket=websocket,
                    message=message,
                    connection_id=connection_id,
                    provider_factory=ProviderFactory.create_streaming_provider,
                    settings=settings
                )
                
                # Send response if any
                if response:
                    await ws_manager.send_personal_message(
                        connection_id,
                        response.dict()
                    )
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid message format: {e}")
                error_response = {
                    "type": "error",
                    "data": {
                        "error": "Invalid message format",
                        "code": 4000
                    }
                }
                await ws_manager.send_personal_message(connection_id, error_response)
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                error_response = {
                    "type": "error",
                    "data": {
                        "error": "Internal server error",
                        "code": 5000
                    }
                }
                await ws_manager.send_personal_message(connection_id, error_response)
    
    finally:
        # Clean up
        if connection_id:
            message_handler.cleanup_connection(connection_id)
            await ws_manager.disconnect(connection_id)
            logger.info(f"WebSocket cleanup complete: {connection_id}")


@ws_router.get("/")
async def websocket_info():
    """WebSocket endpoint information and test page."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Chat Test</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            .container { border: 1px solid #ddd; border-radius: 5px; padding: 20px; }
            .messages { height: 400px; overflow-y: auto; border: 1px solid #eee; padding: 10px; margin: 10px 0; background: #f9f9f9; }
            .message { margin: 5px 0; padding: 5px; }
            .message.sent { text-align: right; color: blue; }
            .message.received { text-align: left; color: green; }
            .message.error { color: red; }
            .controls { display: flex; gap: 10px; }
            input, select { flex: 1; padding: 10px; }
            button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .status { margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>WebSocket Chat Test</h1>
            
            <div class="status" id="status">Disconnected</div>
            
            <div class="messages" id="messages"></div>
            
            <div class="controls">
                <input type="text" id="messageInput" placeholder="Type your message..." />
                <select id="modelSelect">
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    <option value="gpt-4">GPT-4</option>
                    <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
                </select>
                <button onclick="sendMessage()">Send</button>
                <button onclick="connect()">Connect</button>
                <button onclick="disconnect()">Disconnect</button>
            </div>
        </div>
        
        <script>
            let ws = null;
            let messageId = 0;
            
            function connect() {
                const wsUrl = `ws://localhost:8000/ws/chat?client_id=test-client`;
                ws = new WebSocket(wsUrl);
                
                ws.onopen = () => {
                    updateStatus('Connected', 'green');
                    addMessage('System', 'WebSocket connected');
                };
                
                ws.onmessage = (event) => {
                    const message = JSON.parse(event.data);
                    handleMessage(message);
                };
                
                ws.onerror = (error) => {
                    updateStatus('Error', 'red');
                    addMessage('Error', 'WebSocket error: ' + error);
                };
                
                ws.onclose = () => {
                    updateStatus('Disconnected', 'gray');
                    addMessage('System', 'WebSocket disconnected');
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                }
            }
            
            function sendMessage() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('Please connect first');
                    return;
                }
                
                const input = document.getElementById('messageInput');
                const model = document.getElementById('modelSelect').value;
                const message = input.value.trim();
                
                if (!message) return;
                
                const msgId = `msg-${++messageId}`;
                const payload = {
                    type: 'chat',
                    id: msgId,
                    data: {
                        message: message,
                        model: model,
                        stream: true,
                        temperature: 0.7
                    }
                };
                
                ws.send(JSON.stringify(payload));
                addMessage('You', message, 'sent');
                input.value = '';
            }
            
            function handleMessage(message) {
                switch (message.type) {
                    case 'stream':
                        if (message.data.chunk) {
                            appendToLastMessage(message.data.chunk);
                        }
                        break;
                    case 'complete':
                        addMessage('AI', `[Complete: ${message.data.tokens} tokens, ${message.data.duration_ms.toFixed(0)}ms]`, 'received');
                        break;
                    case 'error':
                        addMessage('Error', message.data.error, 'error');
                        break;
                    case 'connection':
                        addMessage('System', `Connected with ID: ${message.data.connection_id}`);
                        break;
                }
            }
            
            function addMessage(sender, text, className = '') {
                const messages = document.getElementById('messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message ' + className;
                messageDiv.innerHTML = `<strong>${sender}:</strong> ${text}`;
                messages.appendChild(messageDiv);
                messages.scrollTop = messages.scrollHeight;
            }
            
            let lastAIMessage = null;
            function appendToLastMessage(chunk) {
                const messages = document.getElementById('messages');
                if (!lastAIMessage || lastAIMessage.querySelector('strong').textContent !== 'AI:') {
                    lastAIMessage = document.createElement('div');
                    lastAIMessage.className = 'message received';
                    lastAIMessage.innerHTML = '<strong>AI:</strong> <span></span>';
                    messages.appendChild(lastAIMessage);
                }
                const span = lastAIMessage.querySelector('span');
                span.textContent += chunk;
                messages.scrollTop = messages.scrollHeight;
            }
            
            function updateStatus(text, color) {
                const status = document.getElementById('status');
                status.textContent = text;
                status.style.color = color;
            }
            
            // Enter key to send
            document.getElementById('messageInput').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') sendMessage();
            });
            
            // Auto-connect on load
            window.onload = () => connect();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@ws_router.get("/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    stats = ws_manager.get_stats()
    return {
        "websocket": stats,
        "handler": {
            "active_streams": len(message_handler.active_streams),
            "total_connections": len(message_handler.message_history)
        }
    }
"""
WebSocket message handlers with validation and error handling.
"""

import asyncio
import uuid
import time
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from fastapi import WebSocket, WebSocketDisconnect
import json

from ..providers.base import ChatMessage, ProviderError
from ..config import Settings

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    
    # Client -> Server
    CHAT = "chat"
    PING = "ping"
    PONG = "pong"
    AUTH = "auth"
    CANCEL = "cancel"
    
    # Server -> Client
    STREAM = "stream"
    COMPLETE = "complete"
    ERROR = "error"
    CONNECTION = "connection"
    STATUS = "status"


class ChatRequest(BaseModel):
    """Chat request data model."""
    
    message: str = Field(..., min_length=1, max_length=10000)
    model: str = Field(...)
    stream: bool = Field(True)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0, le=8192)
    system_prompt: Optional[str] = Field(None)
    conversation_history: Optional[List[Dict[str, str]]] = Field(None)
    
    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        """Validate message content."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    
    type: MessageType = Field(..., description="Message type")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Message ID")
    data: Optional[Dict[str, Any]] = Field(None, description="Message data")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    class Config:
        use_enum_values = True


class StreamChunk(BaseModel):
    """Stream chunk data."""
    
    chunk: str = Field(..., description="Text chunk")
    index: int = Field(..., description="Chunk index")
    finished: bool = Field(False, description="Whether streaming is finished")
    tokens_per_second: Optional[float] = Field(None, description="Streaming speed")


class CompleteResponse(BaseModel):
    """Complete response data."""
    
    full_response: str = Field(..., description="Complete response text")
    model: str = Field(..., description="Model used")
    tokens: int = Field(..., description="Total tokens used")
    cached: bool = Field(False, description="Whether response was cached")
    duration_ms: float = Field(..., description="Processing duration in milliseconds")


class ErrorResponse(BaseModel):
    """Error response data."""
    
    error: str = Field(..., description="Error message")
    code: int = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class MessageHandler:
    """WebSocket message handler."""
    
    def __init__(self, settings: Settings = None):
        """
        Initialize message handler.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.handlers: Dict[MessageType, Callable] = {
            MessageType.CHAT: self._handle_chat,
            MessageType.PING: self._handle_ping,
            MessageType.PONG: self._handle_pong,
            MessageType.AUTH: self._handle_auth,
            MessageType.CANCEL: self._handle_cancel,
        }
        self.active_streams: Dict[str, asyncio.Task] = {}
        self.message_history: Dict[str, List[WebSocketMessage]] = {}
    
    async def handle_message(
        self,
        websocket: WebSocket,
        message: Dict[str, Any],
        connection_id: str,
        **kwargs
    ) -> Optional[WebSocketMessage]:
        """
        Handle incoming WebSocket message.
        
        Args:
            websocket: WebSocket connection
            message: Raw message dictionary
            connection_id: Connection identifier
            **kwargs: Additional context
        
        Returns:
            Response message or None
        """
        try:
            # Validate message
            ws_message = WebSocketMessage(**message)
            
            # Log message
            logger.debug(
                f"Handling WebSocket message",
                extra={
                    "connection_id": connection_id,
                    "message_type": ws_message.type,
                    "message_id": ws_message.id
                }
            )
            
            # Store in history
            if connection_id not in self.message_history:
                self.message_history[connection_id] = []
            self.message_history[connection_id].append(ws_message)
            
            # Limit history size
            if len(self.message_history[connection_id]) > 100:
                self.message_history[connection_id] = self.message_history[connection_id][-50:]
            
            # Get handler
            handler = self.handlers.get(ws_message.type)
            if not handler:
                return self._create_error_response(
                    ws_message.id,
                    f"Unknown message type: {ws_message.type}",
                    code=4000
                )
            
            # Handle message
            return await handler(websocket, ws_message, connection_id, **kwargs)
            
        except ValueError as e:
            logger.error(f"Message validation error: {e}")
            return self._create_error_response(
                message.get("id", "unknown"),
                str(e),
                code=4001
            )
        except Exception as e:
            logger.error(f"Message handling error: {e}", exc_info=True)
            return self._create_error_response(
                message.get("id", "unknown"),
                "Internal server error",
                code=5000
            )
    
    async def _handle_chat(
        self,
        websocket: WebSocket,
        message: WebSocketMessage,
        connection_id: str,
        provider_factory: Optional[Callable] = None,
        **kwargs
    ) -> Optional[WebSocketMessage]:
        """
        Handle chat message.
        
        Args:
            websocket: WebSocket connection
            message: Chat message
            connection_id: Connection identifier
            provider_factory: Provider factory function
            **kwargs: Additional context
        
        Returns:
            Response message or None (streaming handled separately)
        """
        try:
            # Validate chat request
            chat_request = ChatRequest(**message.data)
            
            # Cancel any existing stream for this connection
            if connection_id in self.active_streams:
                self.active_streams[connection_id].cancel()
            
            # Start streaming task
            stream_task = asyncio.create_task(
                self._stream_chat_response(
                    websocket,
                    message.id,
                    chat_request,
                    connection_id,
                    provider_factory,
                    **kwargs
                )
            )
            
            # Track active stream
            self.active_streams[connection_id] = stream_task
            
            # Send acknowledgment
            return WebSocketMessage(
                type=MessageType.STATUS,
                id=message.id,
                data={"status": "processing", "message": "Request received"}
            )
            
        except ValueError as e:
            return self._create_error_response(
                message.id,
                f"Invalid chat request: {str(e)}",
                code=4002
            )
        except Exception as e:
            logger.error(f"Chat handling error: {e}", exc_info=True)
            return self._create_error_response(
                message.id,
                "Failed to process chat request",
                code=5001
            )
    
    async def _stream_chat_response(
        self,
        websocket: WebSocket,
        message_id: str,
        chat_request: ChatRequest,
        connection_id: str,
        provider_factory: Optional[Callable] = None,
        **kwargs
    ):
        """
        Stream chat response chunks.
        
        Args:
            websocket: WebSocket connection
            message_id: Original message ID
            chat_request: Chat request data
            connection_id: Connection identifier
            provider_factory: Provider factory function
            **kwargs: Additional context
        """
        start_time = time.time()
        chunk_index = 0
        full_response = ""
        total_tokens = 0
        
        try:
            # Get provider
            if not provider_factory:
                raise ValueError("Provider factory not available")
            
            provider = provider_factory(chat_request.model, self.settings)
            
            # Prepare messages
            messages = []
            
            if chat_request.system_prompt:
                messages.append(ChatMessage(
                    role="system",
                    content=chat_request.system_prompt
                ))
            
            if chat_request.conversation_history:
                for msg in chat_request.conversation_history:
                    messages.append(ChatMessage(
                        role=msg["role"],
                        content=msg["content"]
                    ))
            
            messages.append(ChatMessage(
                role="user",
                content=chat_request.message
            ))
            
            # Stream response
            if chat_request.stream and hasattr(provider, 'stream_chat'):
                # Streaming mode
                async for chunk in provider.stream_chat(
                    messages=messages,
                    model=chat_request.model,
                    temperature=chat_request.temperature,
                    max_tokens=chat_request.max_tokens
                ):
                    # Check if cancelled
                    if connection_id not in self.active_streams:
                        logger.info(f"Stream cancelled for {connection_id}")
                        return
                    
                    # Send chunk
                    chunk_message = WebSocketMessage(
                        type=MessageType.STREAM,
                        id=message_id,
                        data={
                            "chunk": chunk.content,
                            "index": chunk_index,
                            "finished": False,
                            "tokens_per_second": chunk.tokens_per_second if hasattr(chunk, 'tokens_per_second') else None
                        }
                    )
                    
                    await websocket.send_json(chunk_message.dict())
                    
                    full_response += chunk.content
                    chunk_index += 1
                    total_tokens += 1
            else:
                # Non-streaming mode
                response = await provider.chat(
                    messages=messages,
                    model=chat_request.model,
                    temperature=chat_request.temperature,
                    max_tokens=chat_request.max_tokens
                )
                
                full_response = response.content
                total_tokens = response.usage.get("total_tokens", 0) if response.usage else 0
                
                # Send as single chunk
                chunk_message = WebSocketMessage(
                    type=MessageType.STREAM,
                    id=message_id,
                    data={
                        "chunk": full_response,
                        "index": 0,
                        "finished": True
                    }
                )
                
                await websocket.send_json(chunk_message.dict())
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Send completion message
            complete_message = WebSocketMessage(
                type=MessageType.COMPLETE,
                id=message_id,
                data={
                    "full_response": full_response,
                    "model": chat_request.model,
                    "tokens": total_tokens,
                    "cached": False,
                    "duration_ms": duration_ms
                }
            )
            
            await websocket.send_json(complete_message.dict())
            
        except ProviderError as e:
            error_message = self._create_error_response(
                message_id,
                str(e),
                code=5002,
                details={"provider": e.provider}
            )
            await websocket.send_json(error_message.dict())
            
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for message {message_id}")
            raise
            
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            error_message = self._create_error_response(
                message_id,
                "Stream processing failed",
                code=5003
            )
            await websocket.send_json(error_message.dict())
            
        finally:
            # Clean up active stream
            if connection_id in self.active_streams:
                del self.active_streams[connection_id]
    
    async def _handle_ping(
        self,
        websocket: WebSocket,
        message: WebSocketMessage,
        connection_id: str,
        **kwargs
    ) -> WebSocketMessage:
        """Handle ping message."""
        return WebSocketMessage(
            type=MessageType.PONG,
            id=message.id,
            data={"timestamp": datetime.utcnow().isoformat()}
        )
    
    async def _handle_pong(
        self,
        websocket: WebSocket,
        message: WebSocketMessage,
        connection_id: str,
        **kwargs
    ) -> None:
        """Handle pong message (no response needed)."""
        logger.debug(f"Received pong from {connection_id}")
        return None
    
    async def _handle_auth(
        self,
        websocket: WebSocket,
        message: WebSocketMessage,
        connection_id: str,
        **kwargs
    ) -> WebSocketMessage:
        """
        Handle authentication message.
        
        Note: This is a placeholder for future authentication implementation.
        """
        # TODO: Implement actual authentication
        return WebSocketMessage(
            type=MessageType.STATUS,
            id=message.id,
            data={
                "status": "authenticated",
                "message": "Authentication successful (mock)"
            }
        )
    
    async def _handle_cancel(
        self,
        websocket: WebSocket,
        message: WebSocketMessage,
        connection_id: str,
        **kwargs
    ) -> WebSocketMessage:
        """Handle stream cancellation request."""
        if connection_id in self.active_streams:
            self.active_streams[connection_id].cancel()
            del self.active_streams[connection_id]
            
            return WebSocketMessage(
                type=MessageType.STATUS,
                id=message.id,
                data={
                    "status": "cancelled",
                    "message": "Stream cancelled successfully"
                }
            )
        else:
            return WebSocketMessage(
                type=MessageType.STATUS,
                id=message.id,
                data={
                    "status": "no_stream",
                    "message": "No active stream to cancel"
                }
            )
    
    def _create_error_response(
        self,
        message_id: str,
        error: str,
        code: int,
        details: Optional[Dict[str, Any]] = None
    ) -> WebSocketMessage:
        """Create error response message."""
        return WebSocketMessage(
            type=MessageType.ERROR,
            id=message_id,
            data={
                "error": error,
                "code": code,
                "details": details or {}
            }
        )
    
    def cleanup_connection(self, connection_id: str):
        """Clean up resources for a connection."""
        # Cancel active stream
        if connection_id in self.active_streams:
            self.active_streams[connection_id].cancel()
            del self.active_streams[connection_id]
        
        # Clear message history
        if connection_id in self.message_history:
            del self.message_history[connection_id]
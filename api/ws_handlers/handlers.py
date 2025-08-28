"""WebSocket message handlers for chat functionality."""

import logging
import time
from uuid import UUID, uuid4

from api.providers import CompletionRequest, ProviderError, ProviderOrchestrator
from api.providers import Message as ProviderMessage

from .events import (
    AuthFailedEvent,
    AuthSuccessEvent,
    ErrorEvent,
    EventType,
    ResponseEvent,
    StreamChunkEvent,
    StreamEndEvent,
    StreamStartEvent,
    SystemMessageEvent,
    TypingIndicatorEvent,
    WebSocketEvent,
)
from .manager import ConnectionManager, WebSocketConnection

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket events and routes them to appropriate handlers."""

    def __init__(
        self, connection_manager: ConnectionManager, provider_orchestrator: ProviderOrchestrator
    ):
        self.connection_manager = connection_manager
        self.provider_orchestrator = provider_orchestrator

        # Event handlers mapping
        self.handlers: dict[EventType, callable] = {
            EventType.AUTH_REQUEST: self._handle_auth_request,
            EventType.CHAT_MESSAGE: self._handle_chat_message,
            EventType.HEARTBEAT: self._handle_heartbeat,
            EventType.TYPING_INDICATOR: self._handle_typing_indicator,
        }

        logger.info("WebSocket handler initialized")

    async def handle_connection(self, connection: WebSocketConnection):
        """Main connection handler loop."""
        logger.info(f"Handling connection {connection.id}")

        try:
            while True:
                # Receive event from connection
                event = await connection.receive_event()
                if event is None:
                    # Connection closed or error occurred
                    break

                # Route event to appropriate handler
                await self.route_event(connection, event)

        except Exception as e:
            logger.error(f"Error handling connection {connection.id}: {e}")
            # Send error event to client
            error_event = ErrorEvent(
                error_message="Server error occurred", error_code="server_error", retryable=False
            )
            try:
                await connection.send_event(error_event)
            except Exception:
                pass  # Connection may be closed

        finally:
            # Ensure connection is cleaned up
            await self.connection_manager.disconnect(
                connection.id, reason="Connection handler finished"
            )

    async def route_event(self, connection: WebSocketConnection, event: WebSocketEvent):
        """Route event to appropriate handler."""
        handler = self.handlers.get(event.type)

        if handler:
            try:
                await handler(connection, event)
            except Exception as e:
                logger.error(f"Error handling event {event.type} from {connection.id}: {e}")
                # Send error response
                error_event = ErrorEvent(
                    error_message=f"Error processing {event.type.value}",
                    error_code="handler_error",
                    retryable=True,
                )
                await connection.send_event(error_event)
        else:
            logger.warning(f"No handler for event type {event.type} from {connection.id}")
            # Send unsupported event error
            error_event = ErrorEvent(
                error_message=f"Unsupported event type: {event.type.value}",
                error_code="unsupported_event",
                retryable=False,
            )
            await connection.send_event(error_event)

    async def _handle_auth_request(self, connection: WebSocketConnection, event: WebSocketEvent):
        """Handle authentication request."""
        token = event.data.get("token")

        if not token:
            auth_failed = AuthFailedEvent("Authentication token required")
            await connection.send_event(auth_failed)
            return

        # Mock authentication - in production, validate JWT token
        if token == "valid-token":
            # Mock user and tenant data
            user_id = "user_123"
            tenant_id = UUID("550e8400-e29b-41d4-a716-446655440000")

            # Update connection with auth info
            connection.authenticated = True
            connection.user_id = user_id
            connection.tenant_id = tenant_id

            # Subscribe to chat events after authentication
            connection.subscribe_to_event(EventType.CHAT_RESPONSE)
            connection.subscribe_to_event(EventType.CHAT_STREAM_START)
            connection.subscribe_to_event(EventType.CHAT_STREAM_CHUNK)
            connection.subscribe_to_event(EventType.CHAT_STREAM_END)
            connection.subscribe_to_event(EventType.CHAT_ERROR)

            # Send success response
            auth_success = AuthSuccessEvent(
                user_id=user_id, tenant_id=tenant_id, permissions=["chat", "stream"]
            )
            await connection.send_event(auth_success)

            logger.info(f"Connection {connection.id} authenticated as user {user_id}")

        else:
            auth_failed = AuthFailedEvent("Invalid authentication token")
            await connection.send_event(auth_failed)
            logger.warning(f"Authentication failed for connection {connection.id}")

    async def _handle_chat_message(self, connection: WebSocketConnection, event: WebSocketEvent):
        """Handle chat message from user."""

        # Check authentication
        if not connection.authenticated:
            error_event = ErrorEvent(
                error_message="Authentication required for chat",
                error_code="auth_required",
                retryable=False,
            )
            await connection.send_event(error_event)
            return

        # Check rate limiting
        if connection.is_rate_limited(max_messages=10, window_seconds=60):
            error_event = ErrorEvent(
                error_message="Rate limit exceeded", error_code="rate_limit", retryable=True
            )
            await connection.send_event(error_event)
            return

        # Extract message data
        content = event.data.get("content", "").strip()
        if not content:
            error_event = ErrorEvent(
                error_message="Message content is required",
                error_code="empty_message",
                retryable=True,
            )
            await connection.send_event(error_event)
            return

        conversation_id_str = event.data.get("conversation_id")
        conversation_id = UUID(conversation_id_str) if conversation_id_str else uuid4()

        model = event.data.get("model", "model-3.5-turbo")
        temperature = event.data.get("temperature", 0.7)
        max_tokens = event.data.get("max_tokens", 1000)
        stream = event.data.get("stream", True)

        # Create provider message
        provider_message = ProviderMessage(role="user", content=content)

        # Create completion request
        completion_request = CompletionRequest(
            messages=[provider_message],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            conversation_id=conversation_id,
            tenant_id=connection.tenant_id,
            user_id=connection.user_id,
        )

        if stream:
            await self._handle_streaming_request(connection, completion_request, conversation_id)
        else:
            await self._handle_non_streaming_request(
                connection, completion_request, conversation_id
            )

    async def _handle_streaming_request(
        self, connection: WebSocketConnection, request: CompletionRequest, conversation_id: UUID
    ):
        """Handle streaming chat completion."""
        message_id = uuid4()
        start_time = time.time()

        try:
            # Send stream start event
            stream_start = StreamStartEvent(
                model=request.model, conversation_id=conversation_id, message_id=message_id
            )
            await connection.send_event(stream_start)

            # Process streaming response
            full_content = ""
            chunk_index = 0
            total_tokens = 0

            async for chunk in self.provider_orchestrator.complete_stream(request):
                # Send chunk event
                chunk_event = StreamChunkEvent(
                    delta=chunk.delta,
                    chunk_index=chunk_index,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    finish_reason=chunk.finish_reason,
                )
                await connection.send_event(chunk_event)

                full_content += chunk.delta
                chunk_index += 1

                # Check if stream is finished
                if chunk.finish_reason:
                    break

            # Calculate final metrics
            latency_ms = (time.time() - start_time) * 1000
            total_cost = 0.0  # Would calculate from tokens

            # Send stream end event
            stream_end = StreamEndEvent(
                total_tokens=total_tokens,
                total_cost=total_cost,
                latency_ms=latency_ms,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            await connection.send_event(stream_end)

            logger.info(f"Completed streaming response for {connection.id} in {latency_ms:.2f}ms")

        except ProviderError as e:
            error_event = ErrorEvent(
                error_message=e.message, error_code=e.error_code, retryable=e.retryable
            )
            await connection.send_event(error_event)
            logger.error(f"Provider error for connection {connection.id}: {e.message}")

        except Exception as e:
            error_event = ErrorEvent(
                error_message="Internal server error", error_code="server_error", retryable=True
            )
            await connection.send_event(error_event)
            logger.error(f"Unexpected error for connection {connection.id}: {e}")

    async def _handle_non_streaming_request(
        self, connection: WebSocketConnection, request: CompletionRequest, conversation_id: UUID
    ):
        """Handle non-streaming chat completion."""
        message_id = uuid4()

        try:
            # Get completion from provider
            response = await self.provider_orchestrator.complete(request)

            # Send response event
            response_event = ResponseEvent(
                content=response.content,
                model=response.model,
                latency_ms=response.latency_ms,
                cached=response.cached,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            await connection.send_event(response_event)

            logger.info(
                f"Completed non-streaming response for {connection.id} in {response.latency_ms:.2f}ms"
            )

        except ProviderError as e:
            error_event = ErrorEvent(
                error_message=e.message, error_code=e.error_code, retryable=e.retryable
            )
            await connection.send_event(error_event)
            logger.error(f"Provider error for connection {connection.id}: {e.message}")

        except Exception as e:
            error_event = ErrorEvent(
                error_message="Internal server error", error_code="server_error", retryable=True
            )
            await connection.send_event(error_event)
            logger.error(f"Unexpected error for connection {connection.id}: {e}")

    async def _handle_heartbeat(self, connection: WebSocketConnection, event: WebSocketEvent):
        """Handle heartbeat/ping from client."""
        # Update heartbeat timestamp
        connection.stats.last_heartbeat = time.time()

        # Echo heartbeat back (pong)
        heartbeat_response = WebSocketEvent(
            type=EventType.HEARTBEAT,
            data={
                "server_time": time.time(),
                "message": "pong",
                "client_time": event.data.get("client_time"),
            },
        )
        await connection.send_event(heartbeat_response)

    async def _handle_typing_indicator(
        self, connection: WebSocketConnection, event: WebSocketEvent
    ):
        """Handle typing indicator event."""
        if not connection.authenticated:
            return

        is_typing = event.data.get("is_typing", False)
        conversation_id_str = event.data.get("conversation_id")

        if conversation_id_str:
            conversation_id = UUID(conversation_id_str)

            # Broadcast typing indicator to other users in the conversation
            typing_event = TypingIndicatorEvent(
                is_typing=is_typing, conversation_id=conversation_id
            )
            typing_event.user_id = connection.user_id

            # Broadcast to all connections in the conversation except sender
            connection_ids = self.connection_manager.conversation_connections.get(
                conversation_id, set()
            )
            for conn_id in connection_ids:
                if conn_id != connection.id:
                    conn = self.connection_manager.get_connection(conn_id)
                    if conn:
                        try:
                            await conn.send_event(typing_event)
                        except Exception as e:
                            logger.debug(f"Failed to send typing indicator to {conn_id}: {e}")

    async def send_system_message(self, connection_id: str, message: str, level: str = "info"):
        """Send system message to specific connection."""
        connection = self.connection_manager.get_connection(connection_id)
        if connection:
            system_event = SystemMessageEvent(message=message, level=level)
            await connection.send_event(system_event)

    async def broadcast_system_message(
        self, message: str, level: str = "info", tenant_id: UUID | None = None
    ):
        """Broadcast system message to connections."""
        system_event = SystemMessageEvent(message=message, level=level)

        if tenant_id:
            await self.connection_manager.broadcast_to_tenant(tenant_id, system_event)
        else:
            await self.connection_manager.broadcast_to_all(system_event)

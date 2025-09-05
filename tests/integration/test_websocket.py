"""Integration tests for WebSocket connections."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets
from chatbot_ai_system.websocket.ws_manager import WebSocketManager


@pytest.mark.integration
class TestWebSocketIntegration:
    """Test WebSocket integration."""

    @pytest.fixture
    async def ws_manager(self):
        """Create WebSocket manager instance."""
        manager = WebSocketManager(max_connections=100, heartbeat_interval=30)
        yield manager
        # Cleanup
        await manager.shutdown()

    @pytest.fixture
    async def mock_websocket(self):
        """Create mock WebSocket connection."""
        ws = AsyncMock()
        ws.send = AsyncMock()
        ws.recv = AsyncMock()
        ws.close = AsyncMock()
        ws.closed = False
        ws.remote_address = ("127.0.0.1", 12345)
        return ws

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self, ws_manager, mock_websocket):
        """Test WebSocket connection lifecycle."""
        client_id = "test_client_123"

        # Connect
        await ws_manager.connect(mock_websocket, client_id)
        assert client_id in ws_manager.active_connections
        assert ws_manager.get_connection_count() == 1

        # Send message
        message = {"type": "chat", "content": "Hello"}
        await ws_manager.send_message(client_id, message)
        mock_websocket.send.assert_called_once()
        sent_data = mock_websocket.send.call_args[0][0]
        assert json.loads(sent_data) == message

        # Disconnect
        await ws_manager.disconnect(client_id)
        assert client_id not in ws_manager.active_connections
        assert ws_manager.get_connection_count() == 0
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_broadcast_messages(self, ws_manager):
        """Test broadcasting messages to multiple clients."""
        # Create multiple mock connections
        clients = {}
        for i in range(5):
            client_id = f"client_{i}"
            ws = AsyncMock()
            ws.send = AsyncMock()
            ws.closed = False
            clients[client_id] = ws
            await ws_manager.connect(ws, client_id)

        # Broadcast message
        broadcast_message = {"type": "announcement", "content": "System update"}
        await ws_manager.broadcast(broadcast_message)

        # All clients should receive the message
        for client_id, ws in clients.items():
            ws.send.assert_called_once()
            sent_data = ws.send.call_args[0][0]
            assert json.loads(sent_data) == broadcast_message

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, ws_manager, mock_websocket):
        """Test WebSocket error handling."""
        client_id = "error_client"

        # Connect
        await ws_manager.connect(mock_websocket, client_id)

        # Simulate send error
        mock_websocket.send.side_effect = websockets.exceptions.ConnectionClosed(
            None, None
        )

        # Should handle error gracefully
        message = {"type": "chat", "content": "Test"}
        await ws_manager.send_message(client_id, message)

        # Client should be disconnected
        assert client_id not in ws_manager.active_connections

    @pytest.mark.asyncio
    async def test_websocket_heartbeat_mechanism(self, ws_manager, mock_websocket):
        """Test WebSocket heartbeat/ping mechanism."""
        client_id = "heartbeat_client"

        # Connect
        await ws_manager.connect(mock_websocket, client_id)

        # Start heartbeat
        heartbeat_task = asyncio.create_task(
            ws_manager.send_heartbeat(client_id)
        )

        # Wait for heartbeat
        await asyncio.sleep(0.1)

        # Should have sent ping
        mock_websocket.send.assert_called()
        sent_data = mock_websocket.send.call_args[0][0]
        message = json.loads(sent_data)
        assert message["type"] == "ping"

        # Cleanup
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_websocket_max_connections_limit(self, ws_manager):
        """Test maximum connections limit."""
        ws_manager.max_connections = 3

        # Connect maximum allowed clients
        for i in range(3):
            ws = AsyncMock()
            ws.closed = False
            await ws_manager.connect(ws, f"client_{i}")

        assert ws_manager.get_connection_count() == 3

        # Try to connect one more
        extra_ws = AsyncMock()
        extra_ws.close = AsyncMock()
        
        with pytest.raises(ConnectionError) as exc_info:
            await ws_manager.connect(extra_ws, "extra_client")
        
        assert "Maximum connections reached" in str(exc_info.value)
        extra_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_streaming_chat(self, ws_manager, mock_websocket):
        """Test streaming chat responses over WebSocket."""
        client_id = "stream_client"
        await ws_manager.connect(mock_websocket, client_id)

        # Simulate streaming response
        async def stream_response():
            chunks = ["Hello", " there", ", how", " can", " I", " help", "?"]
            for i, chunk in enumerate(chunks):
                await ws_manager.send_message(
                    client_id,
                    {
                        "type": "stream_chunk",
                        "chunk": chunk,
                        "index": i,
                        "is_final": i == len(chunks) - 1,
                    },
                )
                await asyncio.sleep(0.01)  # Simulate delay

        await stream_response()

        # Should have sent all chunks
        assert mock_websocket.send.call_count == 7
        
        # Verify last chunk is marked as final
        last_call = mock_websocket.send.call_args_list[-1]
        last_message = json.loads(last_call[0][0])
        assert last_message["is_final"] is True

    @pytest.mark.asyncio
    async def test_websocket_authentication(self, ws_manager, mock_websocket):
        """Test WebSocket authentication flow."""
        client_id = "auth_client"

        # Mock authentication
        with patch("chatbot_ai_system.websocket.ws_handlers.authenticate_websocket") as mock_auth:
            mock_auth.return_value = {"user_id": "user123", "authenticated": True}

            # Connect with auth token
            auth_token = "valid_token"
            await ws_manager.connect_with_auth(
                mock_websocket, client_id, auth_token
            )

            mock_auth.assert_called_once_with(auth_token)
            assert client_id in ws_manager.authenticated_connections
            assert ws_manager.authenticated_connections[client_id]["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_websocket_room_management(self, ws_manager):
        """Test WebSocket room/channel management."""
        # Create clients
        clients = {}
        for i in range(4):
            client_id = f"client_{i}"
            ws = AsyncMock()
            ws.send = AsyncMock()
            ws.closed = False
            clients[client_id] = ws
            await ws_manager.connect(ws, client_id)

        # Join rooms
        await ws_manager.join_room("client_0", "room_a")
        await ws_manager.join_room("client_1", "room_a")
        await ws_manager.join_room("client_2", "room_b")
        await ws_manager.join_room("client_3", "room_b")

        # Send message to room_a
        room_message = {"type": "room_message", "content": "Message for room A"}
        await ws_manager.send_to_room("room_a", room_message)

        # Only clients in room_a should receive the message
        clients["client_0"].send.assert_called_once()
        clients["client_1"].send.assert_called_once()
        clients["client_2"].send.assert_not_called()
        clients["client_3"].send.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_reconnection_handling(self, ws_manager):
        """Test WebSocket reconnection handling."""
        client_id = "reconnect_client"
        
        # Initial connection
        ws1 = AsyncMock()
        ws1.send = AsyncMock()
        ws1.close = AsyncMock()
        ws1.closed = False
        await ws_manager.connect(ws1, client_id)

        # Store some state
        ws_manager.set_client_state(client_id, {"conversation_id": "conv123"})

        # Simulate disconnection
        await ws_manager.disconnect(client_id)
        ws1.close.assert_called_once()

        # Reconnect with same client_id
        ws2 = AsyncMock()
        ws2.send = AsyncMock()
        ws2.closed = False
        await ws_manager.connect(ws2, client_id)

        # Should restore state
        state = ws_manager.get_client_state(client_id)
        assert state["conversation_id"] == "conv123"

        # Old connection should be closed, new one active
        assert ws_manager.active_connections[client_id] == ws2

    @pytest.mark.asyncio
    async def test_websocket_rate_limiting(self, ws_manager, mock_websocket):
        """Test WebSocket message rate limiting."""
        client_id = "rate_limit_client"
        await ws_manager.connect(mock_websocket, client_id)

        # Configure rate limit
        ws_manager.set_rate_limit(client_id, max_messages=5, window_seconds=1)

        # Send messages within limit
        for i in range(5):
            result = await ws_manager.check_rate_limit(client_id)
            assert result is True

        # Exceed limit
        result = await ws_manager.check_rate_limit(client_id)
        assert result is False

        # Wait for window to reset
        await asyncio.sleep(1.1)
        result = await ws_manager.check_rate_limit(client_id)
        assert result is True
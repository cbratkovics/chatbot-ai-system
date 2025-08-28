"""Unit tests for streaming service."""

import asyncio

import pytest


class TestWebSocketManager:
    """Test suite for WebSocket manager."""

    @pytest.mark.asyncio
    async def test_connection_pool_initialization(self):
        """Test WebSocket connection pool initialization."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager(max_connections=100)
        assert manager.max_connections == 100
        assert len(manager.connections) == 0
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_connection_accept(self, mock_websocket):
        """Test accepting WebSocket connection."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        connection_id = await manager.accept_connection(mock_websocket, "user123")

        assert connection_id is not None
        assert connection_id in manager.connections
        assert manager.connections[connection_id]["websocket"] == mock_websocket
        assert manager.connections[connection_id]["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_connection_limit(self, mock_websocket):
        """Test connection pool limit enforcement."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager(max_connections=2)

        await manager.accept_connection(mock_websocket, "user1")
        await manager.accept_connection(mock_websocket, "user2")

        with pytest.raises(ConnectionError, match="Connection pool full"):
            await manager.accept_connection(mock_websocket, "user3")

    @pytest.mark.asyncio
    async def test_broadcast_message(self, mock_websocket):
        """Test broadcasting message to all connections."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager()

        conn1 = await manager.accept_connection(mock_websocket, "user1")
        conn2 = await manager.accept_connection(mock_websocket, "user2")

        message = {"type": "broadcast", "data": "Hello everyone"}
        await manager.broadcast(message)

        assert mock_websocket.send_json.call_count == 2

    @pytest.mark.asyncio
    async def test_send_to_user(self, mock_websocket):
        """Test sending message to specific user."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        connection_id = await manager.accept_connection(mock_websocket, "user123")

        message = {"type": "direct", "data": "Personal message"}
        await manager.send_to_user("user123", message)

        mock_websocket.send_json.assert_called_with(message)

    @pytest.mark.asyncio
    async def test_connection_heartbeat(self, mock_websocket):
        """Test connection heartbeat mechanism."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1)
        connection_id = await manager.accept_connection(mock_websocket, "user123")

        await manager.start_heartbeat()
        await asyncio.sleep(1.5)
        await manager.stop_heartbeat()

        mock_websocket.send_json.assert_called()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "ping"

    @pytest.mark.asyncio
    async def test_connection_cleanup(self, mock_websocket):
        """Test connection cleanup on disconnect."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        connection_id = await manager.accept_connection(mock_websocket, "user123")

        await manager.disconnect(connection_id)

        assert connection_id not in manager.connections
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_recovery(self, mock_websocket):
        """Test connection recovery after failure."""
        from api.core.streaming.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        connection_id = await manager.accept_connection(mock_websocket, "user123")

        mock_websocket.send_json.side_effect = ConnectionError("Connection lost")

        message = {"type": "test", "data": "test"}
        result = await manager.send_to_connection(connection_id, message)

        assert result is False
        assert connection_id not in manager.connections


class TestStreamHandler:
    """Test suite for stream handler."""

    @pytest.mark.asyncio
    async def test_sse_stream_generation(self):
        """Test Server-Sent Events stream generation."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler()

        async def data_generator():
            for i in range(3):
                yield f"Data chunk {i}"
                await asyncio.sleep(0.01)

        sse_stream = handler.create_sse_stream(data_generator())
        chunks = []

        async for chunk in sse_stream:
            chunks.append(chunk)

        assert len(chunks) == 3
        assert all("data:" in chunk for chunk in chunks)
        assert all("\n\n" in chunk for chunk in chunks)

    @pytest.mark.asyncio
    async def test_chunked_response_handling(self):
        """Test chunked response handling."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler()

        large_data = "x" * 10000
        chunks = list(handler.chunk_response(large_data, chunk_size=1000))

        assert len(chunks) == 10
        assert all(len(chunk) == 1000 for chunk in chunks)

    @pytest.mark.asyncio
    async def test_stream_with_timeout(self):
        """Test stream with timeout handling."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler()

        async def slow_generator():
            await asyncio.sleep(2)
            yield "Data"

        with pytest.raises(asyncio.TimeoutError):
            async for _ in handler.stream_with_timeout(slow_generator(), timeout=1):
                pass

    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        """Test stream error handling."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler()

        async def error_generator():
            yield "First chunk"
            raise ValueError("Stream error")

        chunks = []
        error_caught = False

        try:
            async for chunk in handler.handle_stream(error_generator()):
                chunks.append(chunk)
        except ValueError:
            error_caught = True

        assert len(chunks) == 1
        assert error_caught is True

    @pytest.mark.asyncio
    async def test_stream_buffering(self):
        """Test stream buffering mechanism."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler(buffer_size=3)

        async def data_generator():
            for i in range(10):
                yield f"Data {i}"
                await asyncio.sleep(0.01)

        buffered_stream = handler.buffer_stream(data_generator())
        chunks = []

        async for batch in buffered_stream:
            chunks.append(batch)

        assert len(chunks) == 4
        assert len(chunks[0]) == 3
        assert len(chunks[-1]) == 1

    @pytest.mark.asyncio
    async def test_stream_compression(self):
        """Test stream compression."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler()

        async def data_generator():
            for i in range(5):
                yield "Repetitive data " * 10

        compressed_stream = handler.compress_stream(data_generator())
        chunks = []

        async for chunk in compressed_stream:
            chunks.append(chunk)

        assert all(len(chunk) < len("Repetitive data " * 10) for chunk in chunks)

    @pytest.mark.asyncio
    async def test_stream_rate_limiting(self):
        """Test stream rate limiting."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler()

        async def fast_generator():
            for i in range(10):
                yield f"Data {i}"

        start_time = asyncio.get_event_loop().time()
        chunks = []

        async for chunk in handler.rate_limit_stream(fast_generator(), rate=10):
            chunks.append(chunk)

        elapsed_time = asyncio.get_event_loop().time() - start_time

        assert len(chunks) == 10
        assert elapsed_time >= 0.9

    @pytest.mark.asyncio
    async def test_stream_metrics_collection(self, mock_metrics_collector):
        """Test stream metrics collection."""
        from api.core.streaming.stream_handler import StreamHandler

        handler = StreamHandler(metrics_collector=mock_metrics_collector)

        async def data_generator():
            for i in range(5):
                yield f"Data {i}"
                await asyncio.sleep(0.01)

        async for _ in handler.stream_with_metrics(data_generator(), stream_id="test123"):
            pass

        mock_metrics_collector.record_gauge.assert_called()
        mock_metrics_collector.record_latency.assert_called()

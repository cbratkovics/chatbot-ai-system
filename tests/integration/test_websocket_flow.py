"""Integration tests for WebSocket flow."""

import asyncio
import json

import pytest
from websockets import connect


class TestWebSocketFlow:
    """Test suite for WebSocket communication flow."""

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self):
        """Test complete WebSocket connection lifecycle."""
        uri = "ws://localhost:8000/ws/chat"

        async with connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "ping"}))
            response = await websocket.recv()
            data = json.loads(response)

            assert data["type"] == "pong"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_websocket_authentication(self):
        """Test WebSocket authentication flow."""
        uri = "ws://localhost:8000/ws/chat"
        headers = {"Authorization": "Bearer test-token"}

        async with connect(uri, extra_headers=headers) as websocket:
            await websocket.send(json.dumps({"type": "auth", "token": "test-token"}))

            response = await websocket.recv()
            data = json.loads(response)

            assert data["type"] == "auth_success"
            assert data["authenticated"] is True

    @pytest.mark.asyncio
    async def test_websocket_streaming_response(self):
        """Test streaming response through WebSocket."""
        uri = "ws://localhost:8000/ws/chat"

        async with connect(uri) as websocket:
            await websocket.send(
                json.dumps({"type": "chat", "data": {"message": "Tell me a story", "stream": True}})
            )

            chunks = []
            while True:
                response = await websocket.recv()
                data = json.loads(response)

                if data["type"] == "stream_end":
                    break

                if data["type"] == "stream_chunk":
                    chunks.append(data["content"])

            assert len(chunks) > 0
            full_response = "".join(chunks)
            assert len(full_response) > 0

    @pytest.mark.asyncio
    async def test_websocket_reconnection(self):
        """Test WebSocket reconnection handling."""
        uri = "ws://localhost:8000/ws/chat"
        session_id = "session123"

        async with connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "init", "session_id": session_id}))

            response = await websocket.recv()
            data = json.loads(response)
            assert data["type"] == "session_restored"

            await websocket.close()

        async with connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "reconnect", "session_id": session_id}))

            response = await websocket.recv()
            data = json.loads(response)
            assert data["type"] == "session_restored"
            assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_websocket_concurrent_connections(self):
        """Test handling of concurrent WebSocket connections."""
        uri = "ws://localhost:8000/ws/chat"

        async def create_connection(client_id):
            async with connect(uri) as websocket:
                await websocket.send(json.dumps({"type": "identify", "client_id": client_id}))

                response = await websocket.recv()
                data = json.loads(response)
                return data["client_id"] == client_id

        tasks = [create_connection(f"client_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(results)

    @pytest.mark.asyncio
    async def test_websocket_error_recovery(self):
        """Test WebSocket error recovery."""
        uri = "ws://localhost:8000/ws/chat"

        async with connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "chat", "data": {"invalid": "request"}}))

            response = await websocket.recv()
            data = json.loads(response)

            assert data["type"] == "error"
            assert "message" in data

            await websocket.send(json.dumps({"type": "chat", "data": {"message": "Valid request"}}))

            response = await websocket.recv()
            data = json.loads(response)

            assert data["type"] != "error"

    @pytest.mark.asyncio
    async def test_websocket_rate_limiting(self):
        """Test WebSocket rate limiting."""
        uri = "ws://localhost:8000/ws/chat"

        async with connect(uri) as websocket:
            for i in range(150):
                await websocket.send(
                    json.dumps({"type": "chat", "data": {"message": f"Message {i}"}})
                )

            response = await websocket.recv()
            data = json.loads(response)

            assert data["type"] == "rate_limit"
            assert "retry_after" in data

    @pytest.mark.asyncio
    async def test_websocket_heartbeat(self):
        """Test WebSocket heartbeat mechanism."""
        uri = "ws://localhost:8000/ws/chat"

        async with connect(uri) as websocket:
            heartbeat_count = 0

            async def receive_heartbeats():
                nonlocal heartbeat_count
                while heartbeat_count < 3:
                    response = await websocket.recv()
                    data = json.loads(response)
                    if data["type"] == "heartbeat":
                        heartbeat_count += 1
                        await websocket.send(json.dumps({"type": "heartbeat_ack"}))

            await asyncio.wait_for(receive_heartbeats(), timeout=10)
            assert heartbeat_count >= 3

    @pytest.mark.asyncio
    async def test_websocket_binary_data(self):
        """Test WebSocket binary data transmission."""
        uri = "ws://localhost:8000/ws/chat"

        async with connect(uri) as websocket:
            binary_data = b"Binary test data"
            await websocket.send(binary_data)

            response = await websocket.recv()

            if isinstance(response, bytes):
                assert response == binary_data
            else:
                data = json.loads(response)
                assert data["type"] == "binary_received"

    @pytest.mark.asyncio
    async def test_websocket_broadcast(self):
        """Test WebSocket broadcast functionality."""
        uri = "ws://localhost:8000/ws/chat"

        connections = []
        for i in range(3):
            ws = await connect(uri)
            await ws.send(json.dumps({"type": "join_room", "room": "test_room"}))
            connections.append(ws)

        await connections[0].send(
            json.dumps({"type": "broadcast", "room": "test_room", "message": "Hello everyone"})
        )

        for ws in connections[1:]:
            response = await ws.recv()
            data = json.loads(response)
            assert data["type"] == "broadcast_message"
            assert data["message"] == "Hello everyone"

        for ws in connections:
            await ws.close()

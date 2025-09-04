from typing import Dict, Set, Optional
from fastapi import WebSocket
import asyncio
import uuid


class WebSocketManager:
    def __init__(self, max_connections: int = 100, heartbeat_interval: int = 30):
        self.connections: Dict[str, Dict] = {}
        self.max_connections = max_connections
        self.heartbeat_interval = heartbeat_interval
        self._heartbeat_task = None
        self._is_running = False

    async def accept_connection(self, websocket: WebSocket, user_id: str) -> str:
        if len(self.connections) >= self.max_connections:
            raise ConnectionError("Connection pool full")

        connection_id = str(uuid.uuid4())
        await websocket.accept()

        self.connections[connection_id] = {"websocket": websocket, "user_id": user_id}

        return connection_id

    async def disconnect(self, connection_id: str):
        if connection_id in self.connections:
            conn = self.connections[connection_id]
            await conn["websocket"].close()
            del self.connections[connection_id]

    async def broadcast(self, message: dict):
        for conn_id, conn in self.connections.items():
            await conn["websocket"].send_json(message)

    async def send_to_user(self, user_id: str, message: dict):
        for conn_id, conn in self.connections.items():
            if conn["user_id"] == user_id:
                await conn["websocket"].send_json(message)

    async def send_to_connection(self, connection_id: str, message: dict) -> bool:
        if connection_id not in self.connections:
            return False

        try:
            await self.connections[connection_id]["websocket"].send_json(message)
            return True
        except Exception:
            await self.disconnect(connection_id)
            return False

    async def start_heartbeat(self):
        async def heartbeat_loop():
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                await self.broadcast({"type": "ping"})

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def stop_heartbeat(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    @property
    def is_running(self):
        """Check if manager is running."""
        return self._is_running

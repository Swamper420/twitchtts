import asyncio
import json
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("twitchtts.websocket")


class ConnectionManager:
    """Manages real-time WebSocket connections for Dashboard and OBS Overlays."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_json(self, data: Dict[str, Any]):
        """Broadcast JSON message to all connected clients."""
        if not self.active_connections:
            return

        message = json.dumps(data)
        disconnected = set()

        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket client: {e}")
                disconnected.add(connection)

        for connection in disconnected:
            self.active_connections.discard(connection)


ws_manager = ConnectionManager()

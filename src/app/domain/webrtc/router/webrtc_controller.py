from typing import Dict
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        # Mapping of room -> username -> WebSocket
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room: str, username: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(room, {})
        self.active_connections[room][username] = websocket

    def disconnect(self, room: str, username: str) -> WebSocket | None:
        if room in self.active_connections and username in self.active_connections[room]:
            ws = self.active_connections[room].pop(username)
            if not self.active_connections[room]:
                del self.active_connections[room]
            return ws
        return None

    async def broadcast(self, room: str, message: str, sender: WebSocket) -> None:
        for connection in self.active_connections.get(room, {}).values():
            if connection is not sender:
                await connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/webrtc/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str, username: str | None = None):
    if username is None:
        await websocket.close()
        return
    await manager.connect(room, username, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(room, data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(room, username)
        leave_message = json.dumps({"type": "leave", "from": username})
        await manager.broadcast(room, leave_message, websocket)

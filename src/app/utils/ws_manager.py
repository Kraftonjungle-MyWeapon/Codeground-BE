from typing import Dict
from fastapi import WebSocket
from collections import defaultdict


class WSManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        # self.match_queue: list[int] = []
        self.match_state: Dict[int, Dict[int, bool]] = defaultdict(dict)  # match_id: {user_id: accepted}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        self.active_connections.pop(user_id, None)

    # def add_to_queue(self, user_id: int):
    #     self.match_queue.append(user_id)
    #
    # def pop_from_queue(self):
    #     if len(self.match_queue) >= 2:
    #         return self.match_queue.pop(0), self.match_queue.pop(0)
    #     return None, None
    #
    # def remove_from_queue(self, user_id: int):
    #     if user_id in self.match_queue:
    #         self.match_queue.remove(user_id)

    async def send(self, user_id: int, data: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            await ws.send_json(data)

    async def broadcast(self, user_ids: list[int], data: dict):
        for uid in user_ids:
            await self.send(uid, data)


ws_manager = WSManager()

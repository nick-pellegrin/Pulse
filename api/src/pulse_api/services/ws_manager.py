"""WebSocket connection manager.

A single process-level singleton tracks all active WS connections keyed by
pipeline_id. Broadcasts are fire-and-forget: dead connections are silently
pruned so a stale subscriber never blocks a live one.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, list[WebSocket]] = defaultdict(list)

    async def connect(self, pipeline_id: uuid.UUID, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[pipeline_id].append(ws)

    def disconnect(self, pipeline_id: uuid.UUID, ws: WebSocket) -> None:
        conns = self._connections.get(pipeline_id, [])
        try:
            conns.remove(ws)
        except ValueError:
            pass

    def subscribed_pipeline_ids(self) -> set[uuid.UUID]:
        return {pid for pid, conns in self._connections.items() if conns}

    async def broadcast(self, pipeline_id: uuid.UUID, message: dict) -> None:
        conns = list(self._connections.get(pipeline_id, []))
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(pipeline_id, ws)


manager = ConnectionManager()

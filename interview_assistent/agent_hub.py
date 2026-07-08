from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)

GRAB_WINDOW_SECONDS = 120


@dataclass
class PendingGrab:
    license_id: int
    expires_at: datetime


class LaptopAgentHub:
    """Tracks the laptop screen-capture agent connected to the VPS."""

    def __init__(self) -> None:
        self._socket: WebSocket | None = None
        self._lock = asyncio.Lock()
        self._pending_grab: PendingGrab | None = None

    def is_connected(self) -> bool:
        return self._socket is not None

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            if self._socket is not None:
                try:
                    await self._socket.close()
                except Exception:
                    pass
            self._socket = websocket
        logger.info("Laptop agent connected")

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            if self._socket is websocket:
                self._socket = None
        logger.info("Laptop agent disconnected")

    async def request_grab(self, license_id: int | None = None) -> None:
        async with self._lock:
            socket = self._socket
            if license_id is not None:
                self._pending_grab = PendingGrab(
                    license_id=license_id,
                    expires_at=datetime.now(timezone.utc)
                    + timedelta(seconds=GRAB_WINDOW_SECONDS),
                )
        if socket is None:
            raise RuntimeError(
                "Laptop not connected. Before the exam, run on laptop: ./start_laptop_agent.sh"
            )
        await socket.send_text(json.dumps({"type": "grab"}))

    def consume_pending_grab(self) -> int | None:
        pending = self._pending_grab
        if pending is None:
            return None
        if datetime.now(timezone.utc) > pending.expires_at:
            self._pending_grab = None
            return None
        self._pending_grab = None
        return pending.license_id
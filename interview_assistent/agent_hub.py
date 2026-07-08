from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)

GRAB_WINDOW_SECONDS = 120
DEFAULT_LICENSE_ID = 0


@dataclass
class PendingGrab:
    license_id: int
    expires_at: datetime


class LaptopAgentHub:
    """Tracks laptop agents per license — phone and laptop must share the same key."""

    def __init__(self) -> None:
        self._agents: dict[int, WebSocket] = {}
        self._pending_grabs: dict[int, PendingGrab] = {}
        self._lock = asyncio.Lock()

    def is_connected(self, license_id: int | None = None) -> bool:
        if license_id is None:
            return bool(self._agents)
        return license_id in self._agents

    async def register(self, websocket: WebSocket, license_id: int) -> None:
        await websocket.accept()
        async with self._lock:
            previous = self._agents.get(license_id)
            if previous is not None and previous is not websocket:
                try:
                    await previous.close()
                except Exception:
                    pass
            self._agents[license_id] = websocket
        logger.info("Laptop agent connected for license_id=%s", license_id)

    async def unregister(self, websocket: WebSocket, license_id: int) -> None:
        async with self._lock:
            if self._agents.get(license_id) is websocket:
                del self._agents[license_id]
        logger.info("Laptop agent disconnected for license_id=%s", license_id)

    async def request_grab(self, license_id: int) -> None:
        async with self._lock:
            socket = self._agents.get(license_id)
            self._pending_grabs[license_id] = PendingGrab(
                license_id=license_id,
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=GRAB_WINDOW_SECONDS),
            )
        if socket is None:
            raise RuntimeError(
                "Your laptop is not connected with the same license key. "
                "On laptop run: ./start-laptop-client.sh YOURKEY"
            )
        await socket.send_text(json.dumps({"type": "grab"}))

    def consume_pending_grab(self, license_id: int) -> bool:
        pending = self._pending_grabs.get(license_id)
        if pending is None:
            return False
        if datetime.now(timezone.utc) > pending.expires_at:
            self._pending_grabs.pop(license_id, None)
            return False
        self._pending_grabs.pop(license_id, None)
        return True
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TranscriptEvent:
    text: str
    is_question: bool
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnswerEvent:
    question: str
    answer: str
    options: str = ""
    consensus: str = ""
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StatusEvent:
    state: str
    detail: str = ""
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    """Fan-out events to WebSocket subscribers and optional callbacks."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()
        self.transcripts: list[TranscriptEvent] = []
        self.answers: list[AnswerEvent] = []
        self.status = StatusEvent(state="idle", detail="Waiting to start")

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.add(queue)
        await self._send_snapshot(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def _send_snapshot(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        await queue.put({"type": "status", **self.status.to_dict()})
        for item in self.transcripts[-30:]:
            await queue.put({"type": "transcript", **item.to_dict()})
        for item in self.answers[-10:]:
            await queue.put({"type": "answer", **item.to_dict()})

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        message = {"type": event_type, **payload}
        async with self._lock:
            dead: list[asyncio.Queue[dict[str, Any]]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._subscribers.discard(queue)

    async def set_status(self, state: str, detail: str = "") -> None:
        self.status = StatusEvent(state=state, detail=detail)
        await self.publish("status", self.status.to_dict())

    async def add_transcript(self, text: str, is_question: bool) -> TranscriptEvent:
        event = TranscriptEvent(text=text, is_question=is_question)
        self.transcripts.append(event)
        await self.publish("transcript", event.to_dict())
        return event

    async def add_answer(
        self,
        question: str,
        answer: str,
        options: str = "",
        consensus: str = "",
    ) -> AnswerEvent:
        event = AnswerEvent(
            question=question,
            answer=answer,
            options=options,
            consensus=consensus,
        )
        self.answers.append(event)
        await self.publish("answer", event.to_dict())
        return event
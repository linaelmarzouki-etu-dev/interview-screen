from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from interview_assistent.ai.assistant import InterviewAssistant
from interview_assistent.audio.capture import AudioRecorder, create_audio_recorder
from interview_assistent.audio.transcriber import Transcriber, is_likely_question
from interview_assistent.config import Settings
from interview_assistent.events import EventBus

logger = logging.getLogger(__name__)


class InterviewPipeline:
    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self.settings = settings
        self.bus = bus
        self.transcriber = Transcriber(settings)
        self.assistant = InterviewAssistant(settings)
        self._recorder: AudioRecorder | None = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        self._last_question = ""
        self._recent_lines: list[str] = []

    def _on_audio_chunk(self, chunk: np.ndarray) -> None:
        if not self._loop or not self._running:
            return
        asyncio.run_coroutine_threadsafe(self._process_chunk(chunk), self._loop)

    async def _process_chunk(self, chunk: np.ndarray) -> None:
        await self.bus.set_status("listening", "Transcribing audio chunk...")
        try:
            text = await asyncio.get_running_loop().run_in_executor(
                self._executor, self.transcriber.transcribe_chunk, chunk
            )
        except Exception as exc:
            await self.bus.set_status("error", f"Transcription error: {exc}")
            return

        if not text or len(text.split()) < 2:
            await self.bus.set_status("listening", "Listening...")
            return

        is_question = is_likely_question(text)
        await self.bus.add_transcript(text, is_question)
        self._recent_lines.append(text)
        self._recent_lines = self._recent_lines[-8:]

        if is_question and text != self._last_question:
            self._last_question = text
            if self.settings.auto_answer:
                await self._answer(text)

        await self.bus.set_status("listening", "Listening...")

    async def _answer(self, question: str) -> None:
        await self.bus.set_status("thinking", "Generating suggested answer...")
        context = "\n".join(self._recent_lines[-5:])
        try:
            answer = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                self.assistant.generate_answer,
                question,
                context,
            )
        except Exception as exc:
            await self.bus.set_status("error", f"Answer error: {exc}")
            return

        await self.bus.add_answer(question, answer)
        await self.bus.set_status("listening", "Listening...")

    async def request_answer(self, question: str | None = None) -> None:
        prompt = question or self._last_question or (
            self._recent_lines[-1] if self._recent_lines else ""
        )
        if not prompt:
            await self.bus.set_status("idle", "No question captured yet")
            return
        await self._answer(prompt)

    async def start(self) -> None:
        if self._running:
            return
        self._loop = asyncio.get_running_loop()
        self._running = True
        self._recorder = create_audio_recorder(
            chunk_seconds=self.settings.audio_chunk_seconds,
            device=self.settings.audio_device,
            on_chunk=self._on_audio_chunk,
        )
        try:
            self._recorder.start()
        except Exception as exc:
            self._running = False
            await self.bus.set_status("error", str(exc))
            raise
        await self.bus.set_status("listening", "Capturing audio. Open companion on your phone.")

    async def stop(self) -> None:
        self._running = False
        if self._recorder:
            self._recorder.stop()
            self._recorder = None
        await self.bus.set_status("idle", "Stopped")

    def shutdown(self) -> None:
        if self._recorder:
            self._recorder.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
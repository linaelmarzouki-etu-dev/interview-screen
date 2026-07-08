from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from interview_assistent.ai.mcq_assistant import McqAssistant
from interview_assistent.capture.screenshot import capture_primary_monitor
from interview_assistent.config import Settings
from interview_assistent.events import EventBus

logger = logging.getLogger(__name__)


class McqPipeline:
    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self.settings = settings
        self.bus = bus
        self.assistant = McqAssistant(settings)
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._busy = False

    async def analyze_image(self, image_bytes: bytes, source: str = "upload"):
        if self._busy:
            await self.bus.set_status("thinking", "Already analyzing, please wait...")
            return ""

        self._busy = True
        model_count = len(self.settings.mcq_reasoning_models)
        if model_count > 1:
            await self.bus.set_status(
                "thinking", f"Verifying with {model_count} models..."
            )
        else:
            await self.bus.set_status("thinking", f"Analyzing {source}...")
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                self.assistant.analyze_image,
                image_bytes,
            )
        except Exception as exc:
            await self.bus.set_status("error", str(exc))
            raise
        finally:
            self._busy = False

        await self.bus.add_answer(
            question=result.question,
            answer=result.answer,
            options=result.options,
            consensus=result.consensus,
        )
        await self.bus.set_status("idle", "Ready for next screenshot")
        return result

    async def capture_and_analyze(self) -> str:
        if not self.settings.mcq_allow_desktop_grab:
            raise RuntimeError(
                "Grab desktop screen is disabled on this server. "
                "Use Upload image or Paste image from your phone."
            )
        await self.bus.set_status("thinking", "Capturing screen...")
        try:
            monitor = self.settings.screen_monitor
            image_bytes = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                lambda: capture_primary_monitor(monitor),
            )
        except Exception as exc:
            await self.bus.set_status("error", f"Screenshot error: {exc}")
            raise

        return await self.analyze_image(image_bytes, source="desktop")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
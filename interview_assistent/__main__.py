from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

import uvicorn

from interview_assistent.config import Settings
from interview_assistent.events import EventBus
from interview_assistent.mcq_pipeline import McqPipeline
from interview_assistent.pipeline import InterviewPipeline
from interview_assistent.server.app import create_app, local_ip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("interview_assistent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stealth interview / MCQ assistant — companion UI, no screen-share orb."
    )
    parser.add_argument(
        "--mode",
        choices=["interview", "mcq"],
        default=None,
        help="Assistant mode: interview (audio) or mcq (screenshot vision).",
    )
    parser.add_argument(
        "--hud",
        action="store_true",
        help="Also open a minimal text HUD (interview mode, second monitor).",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List audio input devices and exit (interview mode).",
    )
    return parser.parse_args()


async def run_server(
    settings: Settings,
    bus: EventBus,
    interview_pipeline: InterviewPipeline | None,
    mcq_pipeline: McqPipeline | None,
    hud: bool,
) -> None:
    app = create_app(
        settings,
        bus,
        pipeline=interview_pipeline,
        mcq_pipeline=mcq_pipeline,
    )
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    if hud and interview_pipeline:
        from interview_assistent.ui.hud import StealthHud

        StealthHud(bus).start(asyncio.get_running_loop())

    stop_event = asyncio.Event()

    def _handle_signal(*_args) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    serve_task = asyncio.create_task(server.serve())
    await stop_event.wait()
    server.should_exit = True
    if interview_pipeline:
        await interview_pipeline.stop()
        interview_pipeline.shutdown()
    if mcq_pipeline:
        mcq_pipeline.shutdown()
    await serve_task


def main() -> None:
    args = parse_args()

    if args.list_devices:
        from interview_assistent.audio.capture import list_audio_devices

        for device in list_audio_devices():
            print(f"[{device['index']}] {device['name']} ({device['channels']} ch)")
        return

    settings = Settings.from_env()
    if args.mode:
        object.__setattr__(settings, "mode", args.mode)

    bus = EventBus()
    interview_pipeline: InterviewPipeline | None = None
    mcq_pipeline: McqPipeline | None = None

    if settings.mode == "mcq":
        mcq_pipeline = McqPipeline(settings, bus)
    else:
        interview_pipeline = InterviewPipeline(settings, bus)

    ip = local_ip()
    platform = "Windows" if sys.platform == "win32" else "Linux/macOS"

    if settings.mode == "mcq":
        print("\n=== MCQ Exam Assistant ===")
        print(f"Platform: {platform}")
        print("Stealth mode: open companion on phone or second monitor (not shared screen)")
        print(f"  Local:     http://127.0.0.1:{settings.port}")
        if settings.public_url:
            print(f"  Public:    {settings.public_url}")
        print(f"  Companion: http://{ip}:{settings.port}")
        print("  Input:     upload screenshot, paste image, or grab desktop screen")
        print(f"  OCR:       {settings.vision_model}")
        models = ", ".join(settings.mcq_reasoning_models)
        print(f"  Reasoning: {models} (two-step: {settings.mcq_two_step})")
        if settings.license_required:
            print(f"  Licensing: enabled (login at /login, admin at /admin)")
        else:
            print("  Licensing: disabled")
    else:
        print("\n=== Interview Assistant ===")
        print(f"Platform: {platform}")
        print("Stealth mode: open companion on phone or second monitor (not shared screen)")
        print(f"  Local:     http://127.0.0.1:{settings.port}")
        if settings.public_url:
            print(f"  Public:    {settings.public_url}")
        print(f"  Companion: http://{ip}:{settings.port}")
        if sys.platform == "win32":
            print("  Audio:     WASAPI loopback (system audio from speakers/headphones)")
        else:
            print("  Audio:     PipeWire monitor (system audio)")

    print("No floating orb — answers stay off your shared screen.\n")

    try:
        asyncio.run(
            run_server(settings, bus, interview_pipeline, mcq_pipeline, hud=args.hud)
        )
    except KeyboardInterrupt:
        if interview_pipeline:
            interview_pipeline.shutdown()
        if mcq_pipeline:
            mcq_pipeline.shutdown()


if __name__ == "__main__":
    main()
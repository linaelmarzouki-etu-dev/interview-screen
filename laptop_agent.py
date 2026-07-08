#!/usr/bin/env python3
"""Laptop agent — connect once to VPS, grab screen when phone taps GRAB."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from interview_assistent.capture.screenshot import capture_primary_monitor  # noqa: E402

DEFAULT_VPS = os.getenv("VPS_URL", "https://139-84-130-152.sslip.io")
DEFAULT_MONITOR = os.getenv("SCREEN_MONITOR", "1")


def vps_ws_url(vps_http: str) -> str:
    base = vps_http.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/ws/agent"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/ws/agent"
    return "ws://" + base + "/ws/agent"


async def grab_and_upload(vps_url: str, monitor: str) -> None:
    image = await asyncio.to_thread(capture_primary_monitor, monitor)
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{vps_url.rstrip('/')}/api/mcq/analyze",
            files={"image": ("screen.png", image, "image/png")},
        )
    if response.status_code != 200:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise RuntimeError(detail)
    print("Screen sent to VPS — check answer on phone.")


async def run_agent(vps_url: str, monitor: str) -> None:
    ws_url = vps_ws_url(vps_url)
    print(f"Connecting to VPS agent channel: {ws_url}")
    print("Keep this running during the exam. Phone taps GRAB on VPS page.\n")

    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                print("Connected to VPS. Laptop ready for GRAB requests.")
                async for raw in ws:
                    message = json.loads(raw)
                    if message.get("type") != "grab":
                        continue
                    print("GRAB requested from phone — capturing screen...")
                    try:
                        await grab_and_upload(vps_url, monitor)
                    except Exception as exc:
                        print(f"Grab failed: {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"Disconnected ({exc}). Reconnecting in 3s...")
            await asyncio.sleep(3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Laptop agent for VPS remote grab")
    parser.add_argument("--vps", default=DEFAULT_VPS)
    parser.add_argument("--monitor", default=DEFAULT_MONITOR)
    args = parser.parse_args()

    try:
        asyncio.run(run_agent(args.vps, args.monitor))
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
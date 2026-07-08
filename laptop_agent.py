#!/usr/bin/env python3
"""Laptop agent — must use the SAME 8-letter license key as the phone."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
import websockets

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from interview_assistent.capture.screenshot import capture_primary_monitor  # noqa: E402
from interview_assistent.license.keys import is_valid_key_format, normalize_key  # noqa: E402

DEFAULT_VPS = os.getenv("VPS_URL", "https://139-84-130-152.sslip.io")
DEFAULT_MONITOR = os.getenv("SCREEN_MONITOR", "1")
DEFAULT_KEY = os.getenv("LICENSE_KEY", "")


def vps_ws_url(vps_http: str, license_key: str) -> str:
    base = vps_http.rstrip("/")
    if base.startswith("https://"):
        host = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        host = "ws://" + base[len("http://") :]
    else:
        host = "ws://" + base
    return f"{host}/ws/agent?key={quote(license_key)}"


async def grab_and_upload(vps_url: str, monitor: str, license_key: str) -> None:
    image = await asyncio.to_thread(capture_primary_monitor, monitor)
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{vps_url.rstrip('/')}/api/mcq/analyze",
            files={"image": ("screen.png", image, "image/png")},
            headers={"X-License-Key": license_key},
        )
    if response.status_code != 200:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise RuntimeError(detail)
    print("Screen sent to VPS — check answer on your phone.")


async def run_agent(vps_url: str, monitor: str, license_key: str) -> None:
    ws_url = vps_ws_url(vps_url, license_key)
    print(f"License key: {license_key}")
    print(f"Connecting:  {ws_url}")
    print("Use the SAME key on phone: {}/u/{}".format(vps_url.rstrip("/"), license_key))
    print("Keep this running. Phone taps Grab laptop screen.\n")

    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                print("Laptop paired with your license. Ready for GRAB.")
                async for raw in ws:
                    message = json.loads(raw)
                    if message.get("type") != "grab":
                        continue
                    print("GRAB from your phone — capturing screen...")
                    try:
                        await grab_and_upload(vps_url, monitor, license_key)
                    except Exception as exc:
                        print(f"Grab failed: {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"Disconnected ({exc}). Reconnecting in 3s...")
            await asyncio.sleep(3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Laptop agent for VPS remote grab")
    parser.add_argument("--vps", default=DEFAULT_VPS)
    parser.add_argument("--monitor", default=DEFAULT_MONITOR)
    parser.add_argument("--key", default=DEFAULT_KEY, help="8-letter license key (same as phone)")
    args = parser.parse_args()

    license_key = normalize_key(args.key)
    if not is_valid_key_format(license_key):
        print("Error: --key must be exactly 8 letters (A-Z). Same key as phone URL.", file=sys.stderr)
        print("Example: ./start-laptop-client.sh ABCDEFGH", file=sys.stderr)
        return 1

    try:
        asyncio.run(run_agent(args.vps, args.monitor, license_key))
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
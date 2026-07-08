#!/usr/bin/env python3
"""Grab laptop screen and send to remote VPS for MCQ analysis.

Phone should stay open on the VPS companion URL — answer appears there via WebSocket.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from interview_assistent.capture.screenshot import capture_primary_monitor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture local screen and upload to VPS MCQ server."
    )
    parser.add_argument(
        "--vps",
        default=os.getenv("VPS_URL", "http://139.84.130.152:8765"),
        help="VPS companion base URL",
    )
    parser.add_argument(
        "--monitor",
        default=os.getenv("SCREEN_MONITOR", "1"),
        help="Monitor to capture (1=laptop screen)",
    )
    args = parser.parse_args()

    vps = args.vps.rstrip("/")
    print(f"Capturing monitor {args.monitor}...")
    try:
        image = capture_primary_monitor(args.monitor)
    except Exception as exc:
        print(f"Capture failed: {exc}", file=sys.stderr)
        return 1

    print(f"Uploading {len(image)} bytes to {vps}...")
    try:
        response = httpx.post(
            f"{vps}/api/mcq/analyze",
            files={"image": ("screen.png", image, "image/png")},
            timeout=120.0,
        )
    except Exception as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        return 1

    if response.status_code != 200:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        print(f"Server error ({response.status_code}): {detail}", file=sys.stderr)
        return 1

    print("Sent! Check answer on your phone (VPS companion page).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Laptop grab helper — start once, trigger grabs from your phone.

While the MCQ is on the laptop screen:
  1. Phone tab 1: VPS companion (answer) — http://139.84.130.152:8765
  2. Phone tab 2: Laptop grab button — http://<laptop-ip>:9876
  3. Tap GRAB on phone → captures laptop screen → sends to VPS → answer on tab 1
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from interview_assistent.capture.screenshot import capture_primary_monitor  # noqa: E402

DEFAULT_VPS = os.getenv("VPS_URL", "http://139.84.130.152:8765")
DEFAULT_MONITOR = os.getenv("SCREEN_MONITOR", "1")
DEFAULT_PORT = int(os.getenv("HELPER_PORT", "9876"))

_busy = threading.Lock()

GRAB_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Grab Laptop Screen</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 1rem;
      font-family: system-ui, sans-serif; background: #0b0f14; color: #e8eef7;
      padding: 1rem;
    }
    h1 { font-size: 1.2rem; margin: 0; color: #8b98ab; font-weight: 500; }
    button {
      width: min(280px, 90vw); height: min(280px, 50vh);
      border: none; border-radius: 24px; font-size: 2rem; font-weight: 700;
      background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white;
      cursor: pointer; touch-action: manipulation;
    }
    button:active { transform: scale(0.97); }
    button:disabled { opacity: 0.5; }
    #status { color: #8b98ab; font-size: 0.95rem; text-align: center; max-width: 320px; }
    .ok { color: #2fd39a; }
    .err { color: #ff6b6b; }
  </style>
</head>
<body>
  <h1>MCQ on laptop → answer on VPS tab</h1>
  <button id="grab" onclick="grab()">GRAB</button>
  <p id="status">Tap to capture laptop screen and send to VPS.</p>
  <script>
    async function grab() {
      const btn = document.getElementById("grab");
      const status = document.getElementById("status");
      btn.disabled = true;
      status.className = "";
      status.textContent = "Capturing laptop screen...";
      try {
        const r = await fetch("/grab", { method: "POST" });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || "Failed");
        status.className = "ok";
        status.textContent = data.message || "Sent! Check VPS tab for answer.";
      } catch (e) {
        status.className = "err";
        status.textContent = e.message;
      } finally {
        btn.disabled = false;
      }
    }
  </script>
</body>
</html>
"""


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def grab_and_send(vps_url: str, monitor: str) -> tuple[bool, str]:
    if not _busy.acquire(blocking=False):
        return False, "Already grabbing, please wait..."

    try:
        image = capture_primary_monitor(monitor)
        response = httpx.post(
            f"{vps_url.rstrip('/')}/api/mcq/analyze",
            files={"image": ("screen.png", image, "image/png")},
            timeout=120.0,
        )
        if response.status_code != 200:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            return False, str(detail)
        return True, "Sent! Check your VPS companion tab for the answer."
    except Exception as exc:
        return False, str(exc)
    finally:
        _busy.release()


def make_handler(vps_url: str, monitor: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            return

        def _json(self, code: int, payload: dict) -> None:
            import json

            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/grab.html"}:
                body = GRAB_PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._json(404, {"detail": "Not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/grab":
                self._json(404, {"detail": "Not found"})
                return
            ok, message = grab_and_send(vps_url, monitor)
            if ok:
                self._json(200, {"status": "ok", "message": message})
            else:
                self._json(400, {"detail": message})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Laptop grab helper for VPS MCQ workflow")
    parser.add_argument("--vps", default=DEFAULT_VPS)
    parser.add_argument("--monitor", default=DEFAULT_MONITOR)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    ip = local_ip()
    handler = make_handler(args.vps, args.monitor)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print("\n=== Laptop Grab Helper ===")
    print("Start this ONCE before the exam. Keep it running in background.")
    print(f"  VPS answer tab (phone): {args.vps}")
    print(f"  Grab button (phone):    http://{ip}:{args.port}")
    print("\nWorkflow:")
    print("  1. Phone: open VPS companion for answers")
    print(f"  2. Phone: open http://{ip}:{args.port} and bookmark it")
    print("  3. MCQ on laptop screen → tap GRAB on phone → answer on VPS tab")
    print("\nPress Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
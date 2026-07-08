from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHANNELS = 1
BYTES_PER_SAMPLE = 2


def default_monitor_target() -> str | None:
    try:
        result = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        sink = result.stdout.strip()
        if sink:
            return f"{sink}.monitor"
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        pass
    return None


def list_audio_devices() -> list[dict[str, str | int]]:
    if not shutil.which("pw-cli"):
        return [{"index": 0, "name": "default (pw-record)", "channels": 2}]

    try:
        result = subprocess.run(
            ["pw-cli", "ls", "Node"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return [{"index": 0, "name": "default (pw-record)", "channels": 2}]

    devices: list[dict[str, str | int]] = []
    current_name = "unknown"
    current_id = len(devices)
    for line in result.stdout.splitlines():
        if "object.id" in line:
            try:
                current_id = int(line.split("=", 1)[1].strip().strip('"'))
            except ValueError:
                current_id = len(devices)
        if "node.name" in line:
            current_name = line.split("=", 1)[1].strip().strip('"')
        if "media.class" in line and "Audio" in line:
            devices.append(
                {
                    "index": current_id,
                    "name": current_name,
                    "channels": 2,
                }
            )
    return devices or [{"index": 0, "name": "default (pw-record)", "channels": 2}]


class LinuxAudioRecorder:
    """Capture system audio on Linux using PipeWire pw-record."""

    def __init__(
        self,
        chunk_seconds: float,
        device: str | None,
        on_chunk: Callable[[np.ndarray], None],
    ) -> None:
        if not shutil.which("pw-record"):
            raise RuntimeError(
                "pw-record not found. Install: sudo apt install pipewire-audio-client-libraries"
            )

        self.chunk_seconds = chunk_seconds
        self.device = device or default_monitor_target()
        self.on_chunk = on_chunk
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def _record_command(self) -> list[str]:
        cmd = ["pw-record"]
        if self.device:
            cmd.extend(["--target", self.device])
        cmd.extend(
            [
                "--rate",
                str(SAMPLE_RATE),
                "--channels",
                str(CHANNELS),
                "--format",
                "s16",
                "-",
            ]
        )
        return cmd

    def _capture_loop(self) -> None:
        chunk_bytes = int(SAMPLE_RATE * self.chunk_seconds) * BYTES_PER_SAMPLE
        cmd = self._record_command()

        while not self._stop.is_set():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except OSError as exc:
                logger.error("Failed to start pw-record: %s", exc)
                break

            assert proc.stdout is not None
            raw = proc.stdout.read(chunk_bytes)
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

            if self._stop.is_set():
                break
            if not raw or len(raw) < chunk_bytes // 4:
                continue

            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(np.square(samples))))
            if rms > 0.002:
                self.on_chunk(samples)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
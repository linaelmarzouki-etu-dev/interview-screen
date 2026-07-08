from __future__ import annotations

import logging
import threading
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16_000


def _import_pyaudio():
    try:
        import pyaudiowpatch as pyaudio
    except ImportError as exc:
        raise RuntimeError(
            "pyaudiowpatch is required on Windows. "
            "Run: pip install pyaudiowpatch"
        ) from exc
    return pyaudio


def list_audio_devices() -> list[dict[str, str | int]]:
    pyaudio = _import_pyaudio()
    pa = pyaudio.PyAudio()
    devices: list[dict[str, str | int]] = []
    try:
        for loopback in pa.get_loopback_device_info_generator():
            devices.append(
                {
                    "index": int(loopback["index"]),
                    "name": str(loopback["name"]),
                    "channels": int(loopback["maxInputChannels"]),
                }
            )
        if not devices:
            for index in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(index)
                if info["maxInputChannels"] > 0:
                    devices.append(
                        {
                            "index": index,
                            "name": str(info["name"]),
                            "channels": int(info["maxInputChannels"]),
                        }
                    )
    finally:
        pa.terminate()
    return devices or [{"index": 0, "name": "default WASAPI loopback", "channels": 2}]


def resolve_loopback_device(pa, device: str | None):
    if device is not None:
        if device.isdigit():
            return pa.get_device_info_by_index(int(device))
        for loopback in pa.get_loopback_device_info_generator():
            if device.lower() in loopback["name"].lower():
                return loopback
        raise RuntimeError(f"Audio device not found: {device}")

    wasapi_info = pa.get_host_api_info_by_type(pa.paWASAPI)
    default_speakers = pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    if default_speakers.get("isLoopbackDevice", False):
        return default_speakers

    for loopback in pa.get_loopback_device_info_generator():
        if default_speakers["name"] in loopback["name"]:
            return loopback

    raise RuntimeError(
        "No WASAPI loopback device found. Enable Stereo Mix or update audio drivers."
    )


def resample(samples: np.ndarray, source_rate: int, target_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    if source_rate == target_rate:
        return samples
    target_length = int(len(samples) * target_rate / source_rate)
    if target_length <= 0:
        return np.array([], dtype=np.float32)
    indices = np.linspace(0, len(samples) - 1, target_length)
    return np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)


def to_mono(samples: np.ndarray, channels: int) -> np.ndarray:
    if channels <= 1:
        return samples
    reshaped = samples.reshape(-1, channels)
    return reshaped.mean(axis=1).astype(np.float32)


class WindowsAudioRecorder:
    """Capture system audio on Windows via WASAPI loopback (pyaudiowpatch)."""

    def __init__(
        self,
        chunk_seconds: float,
        device: str | None,
        on_chunk: Callable[[np.ndarray], None],
    ) -> None:
        self.chunk_seconds = chunk_seconds
        self.device = device
        self.on_chunk = on_chunk
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pa = None
        self._stream = None

    def _capture_loop(self) -> None:
        pyaudio = _import_pyaudio()
        pa = pyaudio.PyAudio()
        self._pa = pa

        try:
            device_info = resolve_loopback_device(pa, self.device)
            sample_rate = int(device_info["defaultSampleRate"])
            channels = int(device_info["maxInputChannels"])
            frames_per_buffer = int(sample_rate * 0.25)
            frames_per_chunk = int(sample_rate * self.chunk_seconds)
            buffer: list[np.ndarray] = []
            buffered_frames = {"count": 0}

            def callback(in_data, _frame_count, _time_info, status) -> tuple[None, int]:
                if status:
                    logger.warning("Audio status: %s", status)
                if self._stop.is_set():
                    return None, pyaudio.paComplete

                chunk = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
                mono = to_mono(chunk, channels)
                buffer.append(mono)
                buffered_frames["count"] += len(mono)

                if buffered_frames["count"] >= frames_per_chunk:
                    combined = np.concatenate(buffer)
                    combined = combined[:frames_per_chunk]
                    remainder = combined[frames_per_chunk:]
                    buffer.clear()
                    if len(remainder):
                        buffer.append(remainder)
                    buffered_frames["count"] = len(remainder)

                    resampled = resample(combined, sample_rate, TARGET_SAMPLE_RATE)
                    rms = float(np.sqrt(np.mean(np.square(resampled))))
                    if rms > 0.002:
                        self.on_chunk(resampled)

                return None, pyaudio.paContinue

            self._stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                frames_per_buffer=frames_per_buffer,
                input=True,
                input_device_index=int(device_info["index"]),
                stream_callback=callback,
            )
            self._stream.start_stream()
            while not self._stop.is_set() and self._stream.is_active():
                self._stop.wait(0.2)
        except Exception:
            logger.exception("Windows audio capture failed")
            raise
        finally:
            if self._stream is not None:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            if pa is not None:
                pa.terminate()
            self._pa = None

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
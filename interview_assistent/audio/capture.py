from __future__ import annotations

import sys
from typing import Callable, Protocol

import numpy as np


class AudioRecorder(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


def _platform_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def list_audio_devices() -> list[dict[str, str | int]]:
    if sys.platform == "win32":
        from interview_assistent.audio.windows import list_audio_devices as list_windows

        return list_windows()

    from interview_assistent.audio.linux import list_audio_devices as list_linux

    return list_linux()


def create_audio_recorder(
    chunk_seconds: float,
    device: str | None,
    on_chunk: Callable[[np.ndarray], None],
) -> AudioRecorder:
    if sys.platform == "win32":
        from interview_assistent.audio.windows import WindowsAudioRecorder

        return WindowsAudioRecorder(chunk_seconds, device, on_chunk)

    from interview_assistent.audio.linux import LinuxAudioRecorder

    return LinuxAudioRecorder(chunk_seconds, device, on_chunk)


# Backwards-compatible alias used by the pipeline.
AudioChunkRecorder = create_audio_recorder
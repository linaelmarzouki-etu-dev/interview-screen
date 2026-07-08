from __future__ import annotations

import io
import logging
import re
import wave

import numpy as np
from openai import OpenAI

from interview_assistent.config import Settings

logger = logging.getLogger(__name__)

QUESTION_HINTS = re.compile(
    r"(\?|^(?:what|why|how|when|where|who|which|can you|could you|tell me|describe|explain|walk me)\b)",
    re.IGNORECASE,
)


def is_likely_question(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    if "?" in cleaned:
        return True
    return bool(QUESTION_HINTS.search(cleaned))


def pcm_to_wav_bytes(samples: np.ndarray, sample_rate: int = 16_000) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm16 = (clipped * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm16.tobytes())
    return buffer.getvalue()


class Transcriber:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def transcribe_chunk(self, samples: np.ndarray) -> str:
        audio_bytes = pcm_to_wav_bytes(samples)
        try:
            result = self.client.audio.transcriptions.create(
                model=self.settings.transcribe_model,
                file=("chunk.wav", audio_bytes, "audio/wav"),
                response_format="text",
            )
        except Exception:
            logger.exception("Transcription failed")
            raise

        if isinstance(result, str):
            return result.strip()
        return str(result).strip()
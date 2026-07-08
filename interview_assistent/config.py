from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class Settings:
    mode: str
    openai_api_key: str
    openai_base_url: str
    transcribe_model: str
    chat_model: str
    vision_model: str
    mcq_reasoning_model: str
    mcq_reasoning_models: tuple[str, ...]
    mcq_two_step: bool
    mcq_answer_only: bool
    mcq_allow_desktop_grab: bool
    screen_monitor: str
    role: str
    resume_summary: str
    extra_context: str
    host: str
    port: int
    audio_device: str | None
    audio_chunk_seconds: float
    auto_answer: bool
    license_required: bool
    license_db_path: str
    license_pepper: str
    license_admin_password: str
    gumroad_webhook_secret: str
    public_url: str

    @classmethod
    def from_env(cls) -> Settings:
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        api_key = groq_key or openai_key
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY or OPENAI_API_KEY is required. "
                "Copy .env.example to .env and set your key."
            )

        default_base_url = (
            "https://api.groq.com/openai/v1"
            if groq_key
            else "https://api.openai.com/v1"
        )
        default_transcribe = (
            "whisper-large-v3-turbo" if groq_key else "whisper-1"
        )
        default_chat = (
            "llama-3.3-70b-versatile" if groq_key else "gpt-4o-mini"
        )
        default_vision = (
            "meta-llama/llama-4-scout-17b-16e-instruct"
            if groq_key
            else "gpt-4o-mini"
        )
        default_mcq_reasoning = (
            "llama-3.3-70b-versatile" if groq_key else "gpt-4o-mini"
        )
        default_mcq_models = (
            "llama-3.3-70b-versatile,openai/gpt-oss-120b,qwen/qwen3-32b"
            if groq_key
            else default_mcq_reasoning
        )
        mode = os.getenv("MODE", "interview").strip().lower()
        mcq_reasoning_model = os.getenv(
            "MCQ_REASONING_MODEL", default_mcq_reasoning
        ).strip()
        mcq_reasoning_models = cls._parse_model_list(
            os.getenv("MCQ_REASONING_MODELS", default_mcq_models),
            fallback=mcq_reasoning_model,
        )

        return cls(
            mode=mode,
            openai_api_key=api_key,
            openai_base_url=os.getenv("OPENAI_BASE_URL", default_base_url).strip(),
            transcribe_model=os.getenv("TRANSCRIBE_MODEL", default_transcribe).strip(),
            chat_model=os.getenv("CHAT_MODEL", default_chat).strip(),
            vision_model=os.getenv("VISION_MODEL", default_vision).strip(),
            mcq_reasoning_model=mcq_reasoning_model,
            mcq_reasoning_models=mcq_reasoning_models,
            mcq_two_step=os.getenv("MCQ_TWO_STEP", "true").lower()
            in {"1", "true", "yes"},
            mcq_answer_only=os.getenv("MCQ_ANSWER_ONLY", "true").lower()
            in {"1", "true", "yes"},
            mcq_allow_desktop_grab=os.getenv("MCQ_ALLOW_DESKTOP_GRAB", "true").lower()
            in {"1", "true", "yes"},
            screen_monitor=os.getenv("SCREEN_MONITOR", "auto").strip(),
            role=os.getenv("ROLE", "Software Engineer").strip(),
            resume_summary=os.getenv("RESUME_SUMMARY", "").strip(),
            extra_context=os.getenv("EXTRA_CONTEXT", "").strip(),
            host=os.getenv("HOST", "0.0.0.0").strip(),
            port=int(os.getenv("PORT", "8765")),
            audio_device=os.getenv("AUDIO_DEVICE") or None,
            audio_chunk_seconds=float(os.getenv("AUDIO_CHUNK_SECONDS", "6")),
            auto_answer=os.getenv("AUTO_ANSWER", "true").lower() in {"1", "true", "yes"},
            license_required=os.getenv("LICENSE_REQUIRED", "true").lower()
            in {"1", "true", "yes"},
            license_db_path=os.getenv(
                "LICENSE_DB_PATH", "data/licenses.db"
            ).strip(),
            license_pepper=os.getenv("LICENSE_PEPPER", "change-me-in-production").strip(),
            license_admin_password=os.getenv("LICENSE_ADMIN_PASSWORD", "").strip(),
            gumroad_webhook_secret=os.getenv("GUMROAD_WEBHOOK_SECRET", "").strip(),
            public_url=os.getenv("PUBLIC_URL", "").strip(),
        )

    @staticmethod
    def _parse_model_list(raw: str, fallback: str) -> tuple[str, ...]:
        text = raw.strip() or fallback.strip()
        seen: set[str] = set()
        models: list[str] = []
        for part in text.split(","):
            model = part.strip()
            if model and model not in seen:
                seen.add(model)
                models.append(model)
        return tuple(models or [fallback.strip()])



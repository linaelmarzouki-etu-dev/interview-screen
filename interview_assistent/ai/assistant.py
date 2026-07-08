from __future__ import annotations

import logging

from openai import OpenAI

from interview_assistent.config import Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a discreet interview copilot. The user is in a live job interview.
Your job is to suggest what THEY should say out loud — not meta commentary.

Rules:
- Write in first person as the candidate ("I...", "In my experience...")
- Keep answers concise and speakable (30-90 seconds unless coding)
- For behavioral questions, use STAR format briefly
- For technical questions, be accurate and structured
- Never mention AI, tools, or that you are helping
- If the input is not a clear question, provide a short summary of key points to mention
"""


class InterviewAssistant:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._history: list[dict[str, str]] = []

    def _profile_block(self) -> str:
        parts = [f"Target role: {self.settings.role}"]
        if self.settings.resume_summary:
            parts.append(f"Background: {self.settings.resume_summary}")
        if self.settings.extra_context:
            parts.append(f"Notes: {self.settings.extra_context}")
        return "\n".join(parts)

    def generate_answer(self, question: str, recent_transcript: str = "") -> str:
        user_content = question.strip()
        if recent_transcript:
            user_content = (
                f"Recent conversation context:\n{recent_transcript}\n\n"
                f"Latest prompt to answer:\n{question}"
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": self._profile_block()},
            *self._history[-6:],
            {"role": "user", "content": user_content},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.settings.chat_model,
                messages=messages,
                temperature=0.4,
                max_tokens=700,
            )
        except Exception:
            logger.exception("LLM request failed")
            raise

        answer = (response.choices[0].message.content or "").strip()
        self._history.append({"role": "user", "content": question})
        self._history.append({"role": "assistant", "content": answer})
        return answer
from __future__ import annotations

import base64
import io
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from openai import APIError, OpenAI
from PIL import Image

from interview_assistent.config import Settings

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 3_500_000

EXTRACT_PROMPT = """Transcribe the multiple-choice question from this image.

Return ONLY:
Question: <text>
A) ...
B) ...
(continue for all visible options)

No commentary. No analysis. No thinking tags."""

REASON_PROMPT = """Solve the multiple-choice question.

Reply with exactly one line:
Answer: B

Rules:
- B must be a single letter from the options (A, B, C, D, E, ...)
- pick the one best correct option
- if truly unsolvable, reply: Answer: ?
- no other text
"""

@dataclass(frozen=True)
class McqResult:
    question: str
    options: str
    answer: str
    consensus: str = ""


INVALID_EXTRACTION_MARKERS = (
    "insufficient information",
    "cannot transcribe",
    "unable to discern",
    "completely black",
    "not possible to",
    "no visible text",
)


class McqAssistant:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def _prepare_image(self, image_bytes: bytes) -> tuple[str, str]:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")

        for max_side in (2560, 1920, 1600, 1280, 1024):
            resized = image.copy()
            resized.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=92, optimize=True)
            data = buffer.getvalue()
            if len(data) <= MAX_IMAGE_BYTES:
                encoded = base64.b64encode(data).decode("ascii")
                return encoded, "image/jpeg"

        raise ValueError("Image is too large even after compression (max ~4MB for Groq).")

    @staticmethod
    def _reject_blank_image(image_bytes: bytes) -> None:
        from interview_assistent.capture.screenshot import _is_blank_image

        if _is_blank_image(image_bytes):
            raise ValueError(
                "Screenshot is blank. Use Paste image or Upload image. "
                "If a second monitor was disconnected, avoid Grab desktop screen."
            )

    @staticmethod
    def _strip_model_noise(text: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"</?think>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*\d+\.\s+\*\*.*?\*\*:?\s*", "", cleaned, flags=re.MULTILINE)
        return cleaned.strip()

    def _profile_context(self) -> str:
        parts = []
        if self.settings.role:
            parts.append(f"Subject: {self.settings.role}")
        if self.settings.extra_context:
            parts.append(f"Notes: {self.settings.extra_context}")
        return "\n".join(parts)

    def _vision_request(self, image_bytes: bytes, prompt: str) -> str:
        encoded, mime = self._prepare_image(image_bytes)
        data_url = f"data:{mime};base64,{encoded}"

        response = self.client.chat.completions.create(
            model=self.settings.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0,
            max_tokens=500,
        )
        return self._strip_model_noise(
            (response.choices[0].message.content or "").strip()
        )

    def _validate_extracted_text(self, text: str) -> None:
        lowered = text.lower()
        if len(text.split()) < 4:
            raise ValueError(
                "Could not read the question. Use a clearer screenshot with the full MCQ visible."
            )
        if any(marker in lowered for marker in INVALID_EXTRACTION_MARKERS):
            raise ValueError(
                "Screenshot unreadable. Use Paste/Upload on the monitor showing the exam, "
                "not Grab desktop screen."
            )
        if not re.search(r"[A-E]\)", text, re.IGNORECASE):
            raise ValueError(
                "No answer options found in the image. Capture the full question with A/B/C/D options."
            )

    def _extract_mcq_text(self, image_bytes: bytes) -> str:
        context = self._profile_context()
        prompt = EXTRACT_PROMPT
        if context:
            prompt = f"{context}\n\n{prompt}"

        text = self._vision_request(image_bytes, prompt)
        text = self._clean_extracted_text(text)
        self._validate_extracted_text(text)
        return text

    @staticmethod
    def _clean_extracted_text(text: str) -> str:
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("question:"):
                lines.append(line)
                continue
            if re.match(r"^[A-E]\)", line, re.IGNORECASE):
                lines.append(line.upper() if len(line) > 2 and line[0].isalpha() else line)
                continue
            if lines:
                lines.append(line)
        return "\n".join(lines)

    def _parse_answer_letter(self, raw: str) -> str:
        cleaned = self._strip_model_noise(raw)
        match = re.search(r"Answer:\s*([A-E?])", cleaned, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        match = re.search(r"\b([A-E])\b", cleaned)
        return match.group(1).upper() if match else "?"

    def _reasoning_models(self) -> tuple[str, ...]:
        models = list(self.settings.mcq_reasoning_models)
        if self.settings.chat_model not in models:
            models.append(self.settings.chat_model)
        return tuple(models)

    def _query_reasoning_model(self, model: str, system: str, mcq_text: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": mcq_text},
            ],
            temperature=0.1,
            max_tokens=128,
        )
        raw = (response.choices[0].message.content or "").strip()
        return self._parse_answer_letter(raw)

    @staticmethod
    def _pick_consensus_answer(
        votes: list[tuple[str, str]], model_order: tuple[str, ...]
    ) -> tuple[str, str]:
        counts = Counter(answer for _, answer in votes)
        top_count = max(counts.values())
        leaders = [answer for answer, count in counts.items() if count == top_count]

        if len(leaders) == 1:
            winner = leaders[0]
        else:
            winner = leaders[0]
            for model in model_order:
                for voted_model, answer in votes:
                    if voted_model == model and answer in leaders:
                        winner = answer
                        break
                else:
                    continue
                break

        consensus = f"{counts[winner]}/{len(votes)}"
        return winner, consensus

    def _solve_mcq_text(self, mcq_text: str) -> tuple[str, str]:
        context = self._profile_context()
        system = REASON_PROMPT
        if context:
            system = f"{context}\n\n{REASON_PROMPT}"

        models = self._reasoning_models()
        votes: list[tuple[str, str]] = []
        last_error: Exception | None = None

        with ThreadPoolExecutor(max_workers=min(len(models), 4)) as executor:
            futures = {
                executor.submit(self._query_reasoning_model, model, system, mcq_text): model
                for model in models
            }
            for future in as_completed(futures):
                model = futures[future]
                try:
                    answer = future.result()
                    if answer != "?":
                        votes.append((model, answer))
                        logger.info("MCQ vote from %s: %s", model, answer)
                except APIError as exc:
                    logger.warning("MCQ reasoning API error on %s: %s", model, exc)
                    last_error = exc
                except Exception as exc:
                    logger.warning("MCQ reasoning failed on %s: %s", model, exc)
                    last_error = exc

        if votes:
            return self._pick_consensus_answer(votes, models)

        if last_error:
            raise ValueError(
                "Could not analyze this screenshot. Use Paste image with only the MCQ visible."
            ) from last_error
        raise ValueError(
            "Could not determine the answer. Try a clearer screenshot of the full question."
        )

    @staticmethod
    def _parse_extracted(extracted: str) -> tuple[str, str]:
        question = ""
        option_lines: list[str] = []
        for line in extracted.splitlines():
            if line.lower().startswith("question:"):
                question = line.split(":", 1)[1].strip()
            elif re.match(r"^[A-E]\)", line.strip(), re.IGNORECASE):
                option_lines.append(line.strip())
        if not question and extracted:
            question = extracted.splitlines()[0].strip()
        return question, "\n".join(option_lines)

    def analyze_image(self, image_bytes: bytes) -> McqResult:
        self._reject_blank_image(image_bytes)

        try:
            if self.settings.mcq_two_step:
                extracted = self._extract_mcq_text(image_bytes)
                answer, consensus = self._solve_mcq_text(extracted)
                question, options = self._parse_extracted(extracted)
                return McqResult(
                    question=question,
                    options=options,
                    answer=answer,
                    consensus=consensus,
                )

            raw = self._vision_request(
                image_bytes,
                "Read the MCQ and reply with only one line: Answer: X",
            )
            match = re.search(r"Answer:\s*([A-E])", raw, re.IGNORECASE)
            answer = match.group(1).upper() if match else "?"
            return McqResult(question="", options="", answer=answer)
        except Exception:
            logger.exception("MCQ analysis failed")
            raise
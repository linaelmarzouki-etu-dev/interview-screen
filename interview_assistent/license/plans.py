from __future__ import annotations

PLANS: dict[str, dict[str, int | None]] = {
    "24h": {"hours": 24, "questions": 100},
    "7d": {"hours": 168, "questions": 500},
    "30d": {"hours": 720, "questions": 2000},
}

DEFAULT_PLAN = "24h"
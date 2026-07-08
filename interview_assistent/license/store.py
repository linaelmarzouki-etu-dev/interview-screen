from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from interview_assistent.license.keys import (
    generate_key,
    hash_key,
    hash_token,
    is_valid_key_format,
    key_prefix,
    normalize_key,
)
from interview_assistent.license.plans import DEFAULT_PLAN, PLANS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class LicenseRecord:
    id: int
    key_prefix: str
    plan: str
    status: str
    expires_at: str
    max_sessions: int
    questions_limit: int | None
    questions_used: int
    customer_email: str
    created_at: str
    notes: str


@dataclass(frozen=True)
class SessionRecord:
    id: int
    license_id: int
    expires_at: str
    last_seen: str
    ip: str
    user_agent: str


@dataclass(frozen=True)
class ActivationResult:
    token: str
    plan: str
    expires_at: str
    questions_remaining: int | None
    key_prefix: str


class LicenseStore:
    def __init__(self, db_path: Path, pepper: str) -> None:
        self.db_path = db_path
        self.pepper = pepper
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS licenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    expires_at TEXT NOT NULL,
                    max_sessions INTEGER NOT NULL DEFAULT 1,
                    questions_limit INTEGER,
                    questions_used INTEGER NOT NULL DEFAULT 0,
                    customer_email TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    ip TEXT NOT NULL DEFAULT '',
                    user_agent TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (license_id) REFERENCES licenses(id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_license
                    ON sessions(license_id);
                CREATE INDEX IF NOT EXISTS idx_licenses_prefix
                    ON licenses(key_prefix);
                """
            )

    def _row_to_license(self, row: sqlite3.Row) -> LicenseRecord:
        return LicenseRecord(
            id=row["id"],
            key_prefix=row["key_prefix"],
            plan=row["plan"],
            status=row["status"],
            expires_at=row["expires_at"],
            max_sessions=row["max_sessions"],
            questions_limit=row["questions_limit"],
            questions_used=row["questions_used"],
            customer_email=row["customer_email"],
            created_at=row["created_at"],
            notes=row["notes"],
        )

    def create_license(
        self,
        plan: str = DEFAULT_PLAN,
        *,
        customer_email: str = "",
        notes: str = "",
        max_sessions: int = 1,
        questions_limit: int | None = None,
        hours: int | None = None,
        plain_key: str | None = None,
    ) -> tuple[str, LicenseRecord]:
        if plan not in PLANS:
            raise ValueError(f"Unknown plan '{plan}'. Choose: {', '.join(PLANS)}")

        plan_info = PLANS[plan]
        duration_hours = hours if hours is not None else int(plan_info["hours"])
        if questions_limit is None:
            questions_limit = plan_info["questions"]  # type: ignore[assignment]

        created = _utcnow()
        expires = created + timedelta(hours=duration_hours)

        for _ in range(20):
            key = plain_key or generate_key()
            if not is_valid_key_format(key):
                continue
            key_hash = hash_key(key, self.pepper)
            try:
                with self._connect() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO licenses (
                            key_hash, key_prefix, plan, status, expires_at,
                            max_sessions, questions_limit, questions_used,
                            customer_email, created_at, notes
                        ) VALUES (?, ?, ?, 'active', ?, ?, ?, 0, ?, ?, ?)
                        """,
                        (
                            key_hash,
                            key_prefix(key),
                            plan,
                            _iso(expires),
                            max_sessions,
                            questions_limit,
                            customer_email,
                            _iso(created),
                            notes,
                        ),
                    )
                    license_id = cursor.lastrowid
                    row = conn.execute(
                        "SELECT * FROM licenses WHERE id = ?", (license_id,)
                    ).fetchone()
                assert row is not None
                return key, self._row_to_license(row)
            except sqlite3.IntegrityError:
                if plain_key:
                    raise ValueError("License key already exists") from None
                continue

        raise RuntimeError("Could not generate a unique license key")

    def activate(
        self,
        raw_key: str,
        *,
        ip: str = "",
        user_agent: str = "",
    ) -> ActivationResult:
        if not is_valid_key_format(raw_key):
            raise ValueError("License key must be exactly 8 letters (A-Z)")

        key_hash = hash_key(raw_key, self.pepper)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE key_hash = ?", (key_hash,)
            ).fetchone()
            if row is None:
                raise ValueError("Invalid license key")

            license_row = self._row_to_license(row)
            self.ensure_license_usable(license_row)

            conn.execute(
                "DELETE FROM sessions WHERE license_id = ?",
                (license_row.id,),
            )

            token = secrets.token_urlsafe(32)
            now = _utcnow()
            license_expires = _parse_iso(license_row.expires_at)
            session_expires = min(
                license_expires,
                now + timedelta(hours=24),
            )
            conn.execute(
                """
                INSERT INTO sessions (
                    license_id, token_hash, created_at, expires_at,
                    last_seen, ip, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    license_row.id,
                    hash_token(token, self.pepper),
                    _iso(now),
                    _iso(session_expires),
                    _iso(now),
                    ip,
                    user_agent,
                ),
            )

        remaining = self.questions_remaining(license_row)
        return ActivationResult(
            token=token,
            plan=license_row.plan,
            expires_at=license_row.expires_at,
            questions_remaining=remaining,
            key_prefix=license_row.key_prefix,
        )

    def validate_token(
        self,
        token: str,
        *,
        ip: str = "",
        user_agent: str = "",
        touch: bool = True,
    ) -> tuple[LicenseRecord, SessionRecord]:
        token_hash = hash_token(token, self.pepper)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    s.id AS session_id,
                    s.license_id,
                    s.expires_at AS session_expires,
                    s.last_seen,
                    s.ip,
                    s.user_agent,
                    l.*
                FROM sessions s
                JOIN licenses l ON l.id = s.license_id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                raise ValueError("Session expired or invalid. Enter your license key again.")

            license_row = self._row_to_license(row)
            session_row = SessionRecord(
                id=row["session_id"],
                license_id=row["license_id"],
                expires_at=row["session_expires"],
                last_seen=row["last_seen"],
                ip=row["ip"],
                user_agent=row["user_agent"],
            )

            now = _utcnow()
            if _parse_iso(session_row.expires_at) <= now:
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_row.id,))
                raise ValueError("Session expired. Enter your license key again.")

            self.ensure_license_usable(license_row)

            if touch:
                conn.execute(
                    """
                    UPDATE sessions
                    SET last_seen = ?, ip = ?, user_agent = ?
                    WHERE id = ?
                    """,
                    (_iso(now), ip, user_agent, session_row.id),
                )

        return license_row, session_row

    def lookup_by_key(self, raw_key: str) -> LicenseRecord | None:
        if not is_valid_key_format(raw_key):
            return None
        key_hash = hash_key(normalize_key(raw_key), self.pepper)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE key_hash = ?", (key_hash,)
            ).fetchone()
        return self._row_to_license(row) if row else None

    def record_question(self, license_id: int) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE id = ?", (license_id,)
            ).fetchone()
            if row is None:
                return
            license_row = self._row_to_license(row)
            self.ensure_license_usable(license_row)
            conn.execute(
                "UPDATE licenses SET questions_used = questions_used + 1 WHERE id = ?",
                (license_id,),
            )

    def revoke_by_key(self, raw_key: str) -> bool:
        key_hash = hash_key(normalize_key(raw_key), self.pepper)
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE licenses SET status = 'revoked' WHERE key_hash = ?",
                (key_hash,),
            )
            if cursor.rowcount:
                conn.execute(
                    "DELETE FROM sessions WHERE license_id IN "
                    "(SELECT id FROM licenses WHERE key_hash = ?)",
                    (key_hash,),
                )
            return cursor.rowcount > 0

    def revoke_by_prefix(self, prefix: str) -> int:
        normalized = normalize_key(prefix)[:2]
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM licenses WHERE key_prefix = ? AND status = 'active'",
                (normalized,),
            ).fetchall()
            if not rows:
                return 0
            ids = [row["id"] for row in rows]
            conn.execute(
                f"UPDATE licenses SET status = 'revoked' WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
            conn.execute(
                f"DELETE FROM sessions WHERE license_id IN ({','.join('?' * len(ids))})",
                ids,
            )
            return len(ids)

    def list_licenses(self, *, active_only: bool = False) -> list[LicenseRecord]:
        query = "SELECT * FROM licenses"
        if active_only:
            query += " WHERE status = 'active'"
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
        return [self._row_to_license(row) for row in rows]

    def get_license_by_id(self, license_id: int) -> LicenseRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE id = ?", (license_id,)
            ).fetchone()
        return self._row_to_license(row) if row else None

    def logout(self, token: str) -> None:
        token_hash = hash_token(token, self.pepper)
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    @staticmethod
    def questions_remaining(license_row: LicenseRecord) -> int | None:
        if license_row.questions_limit is None:
            return None
        return max(0, license_row.questions_limit - license_row.questions_used)

    def ensure_license_usable(self, license_row: LicenseRecord) -> None:
        if license_row.status != "active":
            raise ValueError("License key has been revoked")

        if _parse_iso(license_row.expires_at) <= _utcnow():
            raise ValueError("License key has expired")

        if license_row.questions_limit is not None:
            if license_row.questions_used >= license_row.questions_limit:
                raise ValueError("Question limit reached for this license")
from __future__ import annotations

import hashlib
import re
import secrets
import string

KEY_LENGTH = 8
KEY_PATTERN = re.compile(r"^[A-Z]{8}$")
ALPHABET = string.ascii_uppercase


def normalize_key(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def is_valid_key_format(key: str) -> bool:
    return bool(KEY_PATTERN.match(normalize_key(key)))


def generate_key() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(KEY_LENGTH))


def key_prefix(key: str) -> str:
    normalized = normalize_key(key)
    return normalized[:2]


def hash_key(key: str, pepper: str) -> str:
    normalized = normalize_key(key)
    payload = f"{pepper}:{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_token(token: str, pepper: str) -> str:
    payload = f"{pepper}:session:{token}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def share_url(base_url: str, key: str) -> str:
    normalized = normalize_key(key)
    return f"{base_url.rstrip('/')}/u/{normalized}"
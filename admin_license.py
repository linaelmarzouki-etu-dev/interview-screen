#!/usr/bin/env python3
"""CLI for managing 8-letter MCQ license keys."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from interview_assistent.config import Settings  # noqa: E402
from interview_assistent.license.keys import share_url  # noqa: E402
from interview_assistent.license.plans import PLANS  # noqa: E402
from interview_assistent.license.store import LicenseStore  # noqa: E402


def build_store() -> LicenseStore:
    settings = Settings.from_env()
    return LicenseStore(Path(settings.license_db_path), settings.license_pepper)


def cmd_generate(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    store = build_store()
    base = settings.public_url or f"http://127.0.0.1:{settings.port}"
    for _ in range(args.count):
        key, record = store.create_license(
            args.plan,
            customer_email=args.email or "",
            notes=args.notes or "",
            max_sessions=args.max_sessions,
            questions_limit=args.questions,
        )
        print(f"Key:       {key}")
        print(f"Share URL: {share_url(base, key)}")
        print(f"Plan:      {record.plan}  expires={record.expires_at}")
        print(
            f"Limit:     {record.questions_limit}  prefix={record.key_prefix}  "
            f"email={record.customer_email or '-'}"
        )
        print()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    store = build_store()
    for item in store.list_licenses(active_only=args.active_only):
        print(
            f"{item.key_prefix}******\t{item.plan}\t{item.status}\t"
            f"used={item.questions_used}/{item.questions_limit or '∞'}\t"
            f"expires={item.expires_at}\t{item.customer_email}"
        )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    store = build_store()
    if args.key:
        if not store.revoke_by_key(args.key):
            print("License not found", file=sys.stderr)
            return 1
        print("Revoked 1 license")
        return 0
    if args.prefix:
        count = store.revoke_by_prefix(args.prefix)
        print(f"Revoked {count} license(s)")
        return 0
    print("Provide --key or --prefix", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage MCQ license keys")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Create license keys")
    generate.add_argument("--plan", choices=sorted(PLANS), default="24h")
    generate.add_argument("--count", type=int, default=1)
    generate.add_argument("--email", default="")
    generate.add_argument("--notes", default="")
    generate.add_argument("--max-sessions", type=int, default=1)
    generate.add_argument("--questions", type=int, default=None)
    generate.set_defaults(func=cmd_generate)

    list_cmd = sub.add_parser("list", help="List licenses")
    list_cmd.add_argument("--active-only", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    revoke = sub.add_parser("revoke", help="Revoke a license")
    revoke.add_argument("--key", default="")
    revoke.add_argument("--prefix", default="")
    revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
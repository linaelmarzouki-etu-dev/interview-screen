#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi

VPS_URL="${VPS_URL:-https://139-84-130-152.sslip.io}"
SCREEN_MONITOR="${SCREEN_MONITOR:-1}"

exec .venv/bin/python grab_to_vps.py --vps "$VPS_URL" --monitor "$SCREEN_MONITOR"
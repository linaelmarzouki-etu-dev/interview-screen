#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi

export VPS_URL="${VPS_URL:-http://139.84.130.152:8765}"
export SCREEN_MONITOR="${SCREEN_MONITOR:-1}"

exec .venv/bin/python laptop_agent.py --vps "$VPS_URL" --monitor "$SCREEN_MONITOR"
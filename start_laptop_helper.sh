#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi

export VPS_URL="${VPS_URL:-https://139-84-130-152.sslip.io}"
export SCREEN_MONITOR="${SCREEN_MONITOR:-1}"
export HELPER_PORT="${HELPER_PORT:-9876}"

exec .venv/bin/python laptop_helper.py \
  --vps "$VPS_URL" \
  --monitor "$SCREEN_MONITOR" \
  --port "$HELPER_PORT"
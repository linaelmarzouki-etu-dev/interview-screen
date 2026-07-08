#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi

export VPS_URL="${VPS_URL:-https://139-84-130-152.sslip.io}"
export SCREEN_MONITOR="${SCREEN_MONITOR:-1}"
LICENSE_KEY="${1:-${LICENSE_KEY:-}}"

if [[ -z "$LICENSE_KEY" ]]; then
  read -rp "Enter your 8-letter license key: " LICENSE_KEY
fi

exec .venv/bin/python laptop_agent.py --vps "$VPS_URL" --monitor "$SCREEN_MONITOR" --key "$LICENSE_KEY"
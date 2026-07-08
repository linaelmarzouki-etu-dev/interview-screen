#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f client.env ]]; then
  # shellcheck disable=SC1091
  source client.env
fi

if [[ ! -d .venv ]]; then
  echo "Run ./install-linux-client.sh first"
  exit 1
fi

export VPS_URL="${VPS_URL:-http://139.84.130.152:8765}"
export SCREEN_MONITOR="${SCREEN_MONITOR:-1}"

echo "Connecting laptop to $VPS_URL ..."
echo "On phone: open your license URL and tap Grab laptop screen."
echo

exec .venv/bin/python laptop_agent.py --vps "$VPS_URL" --monitor "$SCREEN_MONITOR"
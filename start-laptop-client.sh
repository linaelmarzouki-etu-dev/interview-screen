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

export VPS_URL="${VPS_URL:-https://139-84-130-152.sslip.io}"
export SCREEN_MONITOR="${SCREEN_MONITOR:-1}"

echo "Connecting laptop to $VPS_URL ..."
echo "Laptop: no license key needed — keep this window open."
echo "Phone:  open https://139-84-130-152.sslip.io/u/YOURKEY then tap Grab laptop screen."
echo

exec .venv/bin/python laptop_agent.py --vps "$VPS_URL" --monitor "$SCREEN_MONITOR"
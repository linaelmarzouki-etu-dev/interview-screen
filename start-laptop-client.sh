#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f client.env ]]; then
  # shellcheck disable=SC1091
  source client.env
fi

if [[ ! -d .venv ]]; then
  echo "Run ./install-linux-client.sh YOURKEY first"
  exit 1
fi

export VPS_URL="${VPS_URL:-https://139-84-130-152.sslip.io}"
export SCREEN_MONITOR="${SCREEN_MONITOR:-1}"

LICENSE_KEY="${1:-${LICENSE_KEY:-}}"
if [[ -z "$LICENSE_KEY" ]]; then
  read -rp "Enter your 8-letter license key (same as phone): " LICENSE_KEY
fi
LICENSE_KEY="$(echo "$LICENSE_KEY" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z' | head -c 8)"

if [[ ${#LICENSE_KEY} -ne 8 ]]; then
  echo "Error: license key must be exactly 8 letters A-Z"
  exit 1
fi

echo "Laptop key: $LICENSE_KEY"
echo "Phone URL:  ${VPS_URL%/}/u/${LICENSE_KEY}"
echo

exec .venv/bin/python laptop_agent.py --vps "$VPS_URL" --monitor "$SCREEN_MONITOR" --key "$LICENSE_KEY"
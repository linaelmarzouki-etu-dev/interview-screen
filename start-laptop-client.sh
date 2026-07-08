#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f client.env ]]; then
  # shellcheck disable=SC1091
  source client.env
fi

if [[ ! -d .venv ]]; then
  echo "Not installed. Run:"
  echo "  curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash -s YOURKEY"
  exit 1
fi

# Update client from GitHub
if [[ -d .git ]]; then
  git pull --ff-only origin main 2>/dev/null || true
fi

export VPS_URL="${VPS_URL:-https://139-84-130-152.sslip.io}"
export SCREEN_MONITOR="${SCREEN_MONITOR:-1}"

LICENSE_KEY="${1:-${LICENSE_KEY:-}}"

if [[ -z "$LICENSE_KEY" ]]; then
  if [[ -t 0 ]]; then
    read -rp "Enter your 8-letter license key (same as phone): " LICENSE_KEY
  elif [[ -e /dev/tty ]]; then
    read -rp "Enter your 8-letter license key (same as phone): " LICENSE_KEY < /dev/tty
  else
    echo "Error: pass your license key:"
    echo "  ./start-laptop-client.sh ABCDEFGH"
    exit 1
  fi
fi

LICENSE_KEY="$(echo "$LICENSE_KEY" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z' | head -c 8)"

if [[ ${#LICENSE_KEY} -ne 8 ]]; then
  echo "Error: license key must be exactly 8 letters A-Z"
  echo "Usage: ./start-laptop-client.sh ABCDEFGH"
  exit 1
fi

echo "Laptop key: $LICENSE_KEY"
echo "Phone URL:  ${VPS_URL%/}/u/${LICENSE_KEY}"
echo

exec .venv/bin/python laptop_agent.py --vps "$VPS_URL" --monitor "$SCREEN_MONITOR" --key "$LICENSE_KEY"
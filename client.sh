#!/usr/bin/env bash
# One command: install + start laptop client with your license key
set -euo pipefail

KEY="${1:-}"
if [[ -z "$KEY" ]]; then
  echo "Usage: bash client.sh ZLHUFEAZ"
  echo "       (replace ZLHUFEAZ with your real 8-letter key)"
  exit 1
fi

KEY="$(echo "$KEY" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z' | head -c 8)"
if [[ ${#KEY} -ne 8 ]]; then
  echo "Error: key must be exactly 8 letters A-Z (you passed: $1)"
  exit 1
fi

curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash -s "$KEY"
exec "$HOME/interview-screen-client/start-laptop-client.sh" "$KEY"
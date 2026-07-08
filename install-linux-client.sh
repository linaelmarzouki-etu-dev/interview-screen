#!/usr/bin/env bash
# Install laptop screen-capture client (Linux) — requires same 8-letter key as phone
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/linaelmarzouki-etu-dev/interview-screen.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/interview-screen-client}"
VPS_URL="${VPS_URL:-https://139-84-130-152.sslip.io}"
LICENSE_KEY="${1:-${LICENSE_KEY:-}}"
BRANCH="${BRANCH:-main}"

usage() {
  cat <<'EOF'
License key required (8 letters A-Z, same as phone URL).

Replace XXXXXXXX with your real 8-letter key (e.g. ZLHUFEAZ).

Examples:
  curl -fsSL .../install-linux-client.sh | bash -s ZLHUFEAZ

  LICENSE_KEY=ZLHUFEAZ curl -fsSL .../install-linux-client.sh | bash

  bash install-linux-client.sh ZLHUFEAZ
EOF
}

prompt_for_key() {
  if [[ -n "$LICENSE_KEY" ]]; then
    return
  fi
  if [[ -t 0 ]]; then
    read -rp "Enter your 8-letter license key: " LICENSE_KEY
  elif [[ -e /dev/tty ]]; then
    read -rp "Enter your 8-letter license key: " LICENSE_KEY < /dev/tty
  else
    echo "ERROR: No license key provided."
    usage
    exit 1
  fi
}

normalize_key() {
  echo "$1" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z' | head -c 8
}

echo "=== MCQ Laptop Client (Linux) ==="
echo "Install dir: $INSTALL_DIR"
echo "VPS URL:     $VPS_URL"
echo
echo "Same 8-letter key on laptop AND phone — pairs your devices only."
echo

prompt_for_key
LICENSE_KEY="$(normalize_key "$LICENSE_KEY")"
if [[ ${#LICENSE_KEY} -ne 8 ]]; then
  echo "Error: license key must be exactly 8 letters A-Z"
  usage
  exit 1
fi
echo "License key: $LICENSE_KEY"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install with: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  echo "Installing screenshot helpers (grim, gnome-screenshot) if available..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq grim gnome-screenshot scrot 2>/dev/null || true
fi

mkdir -p "$(dirname "$INSTALL_DIR")"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Updating existing install..."
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  echo "Cloning from GitHub..."
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements-client.txt -q

.venv/bin/python -c "
import numpy
import httpx
import websockets
from interview_assistent.capture.screenshot import capture_primary_monitor
print('Client dependencies OK')
"

cat > client.env <<EOF
VPS_URL=$VPS_URL
SCREEN_MONITOR=1
LICENSE_KEY=$LICENSE_KEY
EOF

chmod +x start-laptop-client.sh

echo
echo "Installed successfully."
echo
echo "=== Start laptop (before exam) ==="
echo "  cd $INSTALL_DIR"
echo "  ./start-laptop-client.sh $LICENSE_KEY"
echo
echo "=== Phone (same key) ==="
echo "  ${VPS_URL%/}/u/$LICENSE_KEY"
echo
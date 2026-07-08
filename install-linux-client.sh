#!/usr/bin/env bash
# Install laptop screen-capture client (Linux)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/linaelmarzouki-etu-dev/interview-screen.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/interview-screen-client}"
VPS_URL="${VPS_URL:-http://139.84.130.152:8765}"
BRANCH="${BRANCH:-main}"

echo "=== MCQ Laptop Client (Linux) ==="
echo "Install dir: $INSTALL_DIR"
echo "VPS URL:     $VPS_URL"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install with: sudo apt install python3 python3-venv python3-pip"
  exit 1
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

cat > client.env <<EOF
VPS_URL=$VPS_URL
SCREEN_MONITOR=1
EOF

chmod +x start-laptop-client.sh

echo
echo "Installed successfully."
echo
echo "Before exam (run once on laptop, leave open):"
echo "  cd $INSTALL_DIR"
echo "  ./start-laptop-client.sh"
echo
echo "On phone, open your license URL:"
echo "  ${VPS_URL%/}/u/YOURKEY"
echo
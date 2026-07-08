#!/usr/bin/env bash
# Push to GitHub — requires PAT with Contents: Read and write on interview-screen
set -euo pipefail
cd "$(dirname "$0")"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Set GITHUB_TOKEN to a fine-grained PAT with Contents read/write for interview-screen"
  exit 1
fi

git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/linaelmarzouki-etu-dev/interview-screen.git
git branch -M main
git push "https://linaelmarzouki-etu-dev:${GITHUB_TOKEN}@github.com/linaelmarzouki-etu-dev/interview-screen.git" main
echo "Pushed to https://github.com/linaelmarzouki-etu-dev/interview-screen"
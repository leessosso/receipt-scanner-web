#!/usr/bin/env bash
# Idempotent monorepo bootstrap for the Cloud Agent environment.
# Installs backend (Python venv) and frontend (npm) dependencies.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# --- System deps: Python venv support (missing from some base images) ---
if ! dpkg -s python3.12-venv >/dev/null 2>&1; then
  echo "Installing python3.12-venv..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# --- Backend ---
echo "Setting up backend..."
cd "$ROOT_DIR/backend"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt

# --- Frontend ---
echo "Setting up frontend..."
cd "$ROOT_DIR/frontend"
npm ci

echo "Setup complete."

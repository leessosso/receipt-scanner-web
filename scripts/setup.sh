#!/usr/bin/env bash
# Idempotent monorepo bootstrap for the Cloud Agent environment.
# Installs backend (Python venv) and frontend (npm) dependencies.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# --- System deps: Python venv support + Tesseract OCR engine ---
# (both may be missing from the base image; install is idempotent)
missing_pkgs=()
dpkg -s python3.12-venv >/dev/null 2>&1 || missing_pkgs+=(python3.12-venv)
dpkg -s tesseract-ocr >/dev/null 2>&1 || missing_pkgs+=(tesseract-ocr)
dpkg -s tesseract-ocr-kor >/dev/null 2>&1 || missing_pkgs+=(tesseract-ocr-kor)
dpkg -s fonts-noto-cjk >/dev/null 2>&1 || missing_pkgs+=(fonts-noto-cjk)
if [ "${#missing_pkgs[@]}" -gt 0 ]; then
  echo "Installing system packages: ${missing_pkgs[*]}"
  sudo apt-get update -qq
  sudo apt-get install -y -qq "${missing_pkgs[@]}"
fi

# --- Backend ---
echo "Setting up backend..."
cd "$ROOT_DIR/backend"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
# requirements-dev.txt includes requirements.txt plus test tooling (pytest, httpx).
.venv/bin/pip install -r requirements-dev.txt

# --- Frontend ---
echo "Setting up frontend..."
cd "$ROOT_DIR/frontend"
npm ci

echo "Setup complete."

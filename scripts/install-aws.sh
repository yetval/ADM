#!/usr/bin/env bash
set -euo pipefail

ADM_HOME="/opt/adm"
ADM_VENV="$ADM_HOME/venv"
ADM_SRC="$ADM_HOME/src"
ADM_BIN="/usr/local/bin/adm"
ADM_BIN_UPPER="/usr/local/bin/ADM"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer with sudo."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install Python 3.10+ first."
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip ca-certificates curl
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Installing with get.docker.com..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker || true
fi

install -d "$ADM_HOME"
rm -rf "$ADM_SRC"
cp -R "$(pwd)" "$ADM_SRC"
python3 -m venv "$ADM_VENV"
"$ADM_VENV/bin/python" -m pip install --upgrade pip
"$ADM_VENV/bin/python" -m pip install "$ADM_SRC"
ln -sf "$ADM_VENV/bin/adm" "$ADM_BIN"
ln -sf "$ADM_VENV/bin/ADM" "$ADM_BIN_UPPER"

if [ "${SUDO_USER:-}" != "" ]; then
  usermod -aG docker "$SUDO_USER" || true
fi

cat <<'MSG'
ADM installed.

Try:
  adm status
  adm list
  adm

If Docker permissions fail, log out and back in so your docker group membership takes effect.
If you just installed Docker for the first time, a new login session is usually required.
You can also run: newgrp docker
MSG

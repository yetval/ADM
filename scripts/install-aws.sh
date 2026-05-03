#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install Python 3.10+ first."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Installing with get.docker.com..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker || true
fi

python3 -m pip install --upgrade pip
python3 -m pip install .

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
MSG

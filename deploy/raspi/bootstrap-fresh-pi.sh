#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-/home/pi/letohry-lode}"
REPO_URL="${2:-${LETOHRY_REPO_URL:-https://github.com/sten-stulda/letohry-lode.git}}"
BRANCH="${3:-${LETOHRY_REPO_BRANCH:-main}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_USER="${RUN_USER:-$(id -un)}"
RUN_GROUP="${RUN_GROUP:-$(id -gn)}"
HOME_DIR="${HOME_DIR:-$(getent passwd "$RUN_USER" | cut -d: -f6)}"

if [[ -z "$HOME_DIR" ]]; then
  echo "Unable to resolve home directory for user $RUN_USER" >&2
  exit 1
fi

echo "[1/8] Installing system packages"
sudo apt update

CHROMIUM_PACKAGE=""
if apt-cache show chromium >/dev/null 2>&1; then
  CHROMIUM_PACKAGE="chromium"
elif apt-cache show chromium-browser >/dev/null 2>&1; then
  CHROMIUM_PACKAGE="chromium-browser"
else
  echo "Unable to find a Chromium package (expected chromium or chromium-browser)" >&2
  exit 1
fi

sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  "$CHROMIUM_PACKAGE" \
  imagemagick \
  fonts-dejavu-core \
  xdotool \
  unclutter \
  x11-xserver-utils

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  echo "[2/8] Cloning repository into $PROJECT_DIR"
  rm -rf "$PROJECT_DIR"
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$PROJECT_DIR"
else
  echo "[2/8] Repository already exists in $PROJECT_DIR"
fi

cd "$PROJECT_DIR"

echo "[3/8] Configuring Raspberry Pi desktop autologin"
if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_boot_behaviour B4 || true
fi

echo "[4/8] Creating virtual environment"
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

echo "[5/8] Installing Python dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt

echo "[6/8] Ensuring helper scripts are executable"
chmod +x deploy/systemd/install-kiosk.sh
chmod +x deploy/kiosk/start-kiosk.sh
chmod +x deploy/raspi/update-from-github.sh
chmod +x scripts/collect_pm3_diagnostics.sh
chmod +x scripts/generate_manual_pdfs.py || true

echo "[7/8] Installing systemd services"
./deploy/systemd/install-kiosk.sh "$PROJECT_DIR" "$RUN_USER" "$RUN_GROUP" "$HOME_DIR"

echo "[8/8] Final checks"
systemctl --no-pager --full status letohry-lode.service || true
systemctl --no-pager --full status letohry-lode-kiosk.service || true

cat <<EOF

Bootstrap finished.

Recommended next checks:
  1. Open http://127.0.0.1:8000 on the Raspberry Pi
  2. Verify kiosk mode starts after reboot
  3. Connect PM3 monitors and check:
     curl http://127.0.0.1:8000/api/status
     curl http://127.0.0.1:8000/api/diagnostics/status

If PM3 ports are not detected automatically, set:
  export ROWING_PORT_1=/dev/ttyUSB0
  export ROWING_PORT_2=/dev/ttyUSB1

For persistent local overrides outside Git:
  sudo cp deploy/raspi/letohry-lode.env.example /etc/letohry-lode.env
  sudo nano /etc/letohry-lode.env

For future updates from GitHub:
  ./deploy/raspi/update-from-github.sh "$PROJECT_DIR"

EOF
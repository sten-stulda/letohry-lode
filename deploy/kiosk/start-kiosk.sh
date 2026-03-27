#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority

URL="${1:-http://127.0.0.1:8000}"

chromium-browser \
  --kiosk \
  --incognito \
  --disable-restore-session-state \
  --disable-infobars \
  --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 \
  --autoplay-policy=no-user-gesture-required \
  --noerrdialogs \
  "$URL"
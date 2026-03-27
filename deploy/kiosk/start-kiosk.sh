#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

URL="${1:-http://127.0.0.1:8000}"

if command -v chromium >/dev/null 2>&1; then
  CHROMIUM_BIN="chromium"
elif command -v chromium-browser >/dev/null 2>&1; then
  CHROMIUM_BIN="chromium-browser"
else
  echo "Chromium executable not found (expected chromium or chromium-browser)" >&2
  exit 1
fi

"$CHROMIUM_BIN" \
  --kiosk \
  --incognito \
  --disable-restore-session-state \
  --disable-infobars \
  --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 \
  --autoplay-policy=no-user-gesture-required \
  --noerrdialogs \
  "$URL"
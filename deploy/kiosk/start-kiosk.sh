#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

URL="${1:-http://127.0.0.1:8000}"
GPU_MODE="${ROWING_KIOSK_GPU_MODE:-auto}"

if command -v chromium >/dev/null 2>&1; then
  CHROMIUM_BIN="chromium"
elif command -v chromium-browser >/dev/null 2>&1; then
  CHROMIUM_BIN="chromium-browser"
else
  echo "Chromium executable not found (expected chromium or chromium-browser)" >&2
  exit 1
fi

resolve_gpu_mode() {
  case "$GPU_MODE" in
    on|off)
      printf '%s\n' "$GPU_MODE"
      return
      ;;
    auto)
      ;;
    *)
      echo "Unknown ROWING_KIOSK_GPU_MODE=$GPU_MODE (expected auto, on, or off)" >&2
      exit 1
      ;;
  esac

  if [[ -r /proc/device-tree/model ]]; then
    local device_model
    device_model="$(tr -d '\0' < /proc/device-tree/model)"
    if [[ "$device_model" == *"Raspberry Pi 4"* || "$device_model" == *"Raspberry Pi 5"* ]]; then
      printf '%s\n' "on"
      return
    fi
  fi

  printf '%s\n' "off"
}

GPU_EFFECTIVE_MODE="$(resolve_gpu_mode)"

CHROMIUM_FLAGS=(
  --kiosk
  --incognito
  --disable-dev-shm-usage
  --disable-restore-session-state
  --disable-infobars
  --check-for-update-interval=31536000
  --overscroll-history-navigation=0
  --autoplay-policy=no-user-gesture-required
  --noerrdialogs
)

if [[ "$GPU_EFFECTIVE_MODE" == "off" ]]; then
  CHROMIUM_FLAGS+=(
    --disable-gpu
    --disable-gpu-compositing
    --disable-features=UseSkiaRenderer,Vulkan
  )
else
  CHROMIUM_FLAGS+=(
    --ignore-gpu-blocklist
    --enable-gpu-rasterization
    --enable-zero-copy
    --disable-features=Vulkan
  )
fi

"$CHROMIUM_BIN" \
  "${CHROMIUM_FLAGS[@]}" \
  "$URL"
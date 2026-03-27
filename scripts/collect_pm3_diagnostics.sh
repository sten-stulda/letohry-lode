#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
OUTPUT_DIR="${2:-./data/pm3-capture}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET_DIR="$OUTPUT_DIR/$STAMP"

mkdir -p "$TARGET_DIR"

echo "Collecting PM3 diagnostics into $TARGET_DIR"

curl -fsS "$BASE_URL/api/status" -o "$TARGET_DIR/status.json"
curl -fsS "$BASE_URL/api/diagnostics/status" -o "$TARGET_DIR/diagnostics-status.json"
curl -fsS "$BASE_URL/api/diagnostics/events?limit=200" -o "$TARGET_DIR/diagnostics-events.json"
curl -fsS "$BASE_URL/api/diagnostics/export" -o "$TARGET_DIR/pm3-diagnostics.log"

cat <<EOF
Saved files:
  $TARGET_DIR/status.json
  $TARGET_DIR/diagnostics-status.json
  $TARGET_DIR/diagnostics-events.json
  $TARGET_DIR/pm3-diagnostics.log
EOF
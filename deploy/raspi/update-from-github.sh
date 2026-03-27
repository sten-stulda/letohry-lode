#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-/home/pi/letohry-lode}"
BRANCH="${2:-${LETOHRY_REPO_BRANCH:-}}"
INSTALL_DEV_REQUIREMENTS="${INSTALL_DEV_REQUIREMENTS:-0}"
RUN_TESTS="${RUN_TESTS:-0}"

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  echo "Project directory $PROJECT_DIR is not a git repository." >&2
  exit 1
fi

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  echo "Virtual environment is missing in $PROJECT_DIR/.venv" >&2
  exit 1
fi

RUN_USER="${RUN_USER:-$(stat -c '%U' "$PROJECT_DIR")}"
RUN_GROUP="${RUN_GROUP:-$(stat -c '%G' "$PROJECT_DIR")}"
HOME_DIR="${HOME_DIR:-$(getent passwd "$RUN_USER" | cut -d: -f6)}"

if [[ -z "$HOME_DIR" ]]; then
  echo "Unable to resolve home directory for user $RUN_USER" >&2
  exit 1
fi

cd "$PROJECT_DIR"

if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
fi

echo "[1/6] Fetching latest changes from origin/$BRANCH"
git fetch origin "$BRANCH" --tags

CURRENT_COMMIT="$(git rev-parse HEAD)"

echo "[2/6] Updating working tree"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "[3/6] Updating Python dependencies"
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ "$INSTALL_DEV_REQUIREMENTS" == "1" && -f requirements-dev.txt ]]; then
  python -m pip install -r requirements-dev.txt
fi

if [[ "$RUN_TESTS" == "1" ]]; then
  if [[ -f requirements-dev.txt ]]; then
    python -m pip install -r requirements-dev.txt
  fi
  echo "[4/6] Running test suite"
  pytest
else
  echo "[4/6] Skipping tests"
fi

echo "[5/6] Reinstalling systemd service definitions"
./deploy/systemd/install-kiosk.sh "$PROJECT_DIR" "$RUN_USER" "$RUN_GROUP" "$HOME_DIR"

UPDATED_COMMIT="$(git rev-parse HEAD)"

echo "[6/6] Update finished"
echo "Previous commit: $CURRENT_COMMIT"
echo "Current commit:  $UPDATED_COMMIT"
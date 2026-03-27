#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-/home/pi/letohry-lode}"
RUN_USER="${2:-$(id -un)}"
RUN_GROUP="${3:-$(id -gn)}"
HOME_DIR="${4:-$(getent passwd "$RUN_USER" | cut -d: -f6)}"
SERVICE_DIR=/etc/systemd/system

if [[ -z "$HOME_DIR" ]]; then
	echo "Unable to resolve home directory for user $RUN_USER" >&2
	exit 1
fi

render_service() {
	local source_file="$1"
	local target_file="$2"
	local temp_file

	temp_file="$(mktemp)"
	sed \
		-e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
		-e "s|__RUN_USER__|$RUN_USER|g" \
		-e "s|__RUN_GROUP__|$RUN_GROUP|g" \
		-e "s|__HOME_DIR__|$HOME_DIR|g" \
		"$source_file" > "$temp_file"
	sudo install -m 0644 "$temp_file" "$target_file"
	rm -f "$temp_file"
}

render_service "$PROJECT_DIR/deploy/systemd/letohry-lode.service" "$SERVICE_DIR/letohry-lode.service"
render_service "$PROJECT_DIR/deploy/systemd/letohry-lode-kiosk.service" "$SERVICE_DIR/letohry-lode-kiosk.service"
sudo chmod +x "$PROJECT_DIR/deploy/kiosk/start-kiosk.sh"
sudo systemctl daemon-reload
sudo systemctl enable letohry-lode.service letohry-lode-kiosk.service
sudo systemctl restart letohry-lode.service
sudo systemctl restart letohry-lode-kiosk.service
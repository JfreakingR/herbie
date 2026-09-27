#!/bin/sh
set -eu

SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TARGET_DIR="/home/jfreakingr/pal-pi-bridge"
UNIT_PATH="/etc/systemd/system/pal-pi-bridge.service"

install -d -o jfreakingr -g jfreakingr -m 755 "$TARGET_DIR"
install -o jfreakingr -g jfreakingr -m 700 "$SOURCE_DIR/pal_pi_bridge.py" "$TARGET_DIR/pal_pi_bridge.py"
install -o root -g root -m 644 "$SOURCE_DIR/pal-pi-bridge.service" "$UNIT_PATH"

systemctl daemon-reload
systemctl enable --now pal-pi-bridge.service
systemctl is-active pal-pi-bridge.service
systemctl is-enabled pal-pi-bridge.service

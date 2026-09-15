#!/bin/sh
set -eu
chmod 700 /home/jfreakingr/pal-pi-bridge/pal_pi_bridge.py
chmod 755 /home/jfreakingr/pal-pi-bridge/herbie-face-kiosk.sh
chmod 644 /home/jfreakingr/pal-pi-bridge/herbie-face-kiosk.service
chmod 644 /home/jfreakingr/pal-pi-bridge/face/index.html
sudo cp /home/jfreakingr/pal-pi-bridge/herbie-face-kiosk.service /etc/systemd/system/herbie-face-kiosk.service
sudo systemctl daemon-reload
sudo systemctl restart pal-pi-bridge.service
sleep 1
systemctl is-active pal-pi-bridge.service
python3 - <<'PY'
import json, urllib.request
health = json.loads(urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=3).read())
print("HEALTH", json.dumps(health, sort_keys=True))
face = urllib.request.urlopen("http://127.0.0.1:8766/face/?kiosk=1", timeout=3).read()
print("FACE_LEN", len(face), "HAS_BOTFACE", b"BotFace" in face)
assert health["ready"] is True
assert health["motor_authority"] is False
assert health["safe_motion_state"] == "STOP"
assert health["face"] is True
assert b"BotFace" in face
print("OK")
PY
ls -l /home/jfreakingr/pal-pi-bridge /home/jfreakingr/pal-pi-bridge/face
systemctl is-enabled herbie-face-kiosk.service || true
systemctl is-active herbie-face-kiosk.service || true

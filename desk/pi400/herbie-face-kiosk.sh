#!/bin/sh
# Herbie's face, fullscreen, on the Pi 400's screen. Started by the desktop's
# autostart; Alt+F4 closes it. Waits for the desk server first.
set -u

PORT="${HERBIE_DESK_PORT:-8766}"
# HERBIE_FACE_PAGE=index.html shows the older 2D face instead of the 3D spirit.
URL="http://127.0.0.1:$PORT/face/${HERBIE_FACE_PAGE:-spirit.html}?kiosk=1"

for _ in $(seq 1 60); do
    python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/health', timeout=1)" \
        >/dev/null 2>&1 && break
    sleep 1
done

BROWSER=$(command -v chromium || command -v chromium-browser)
exec "$BROWSER" --kiosk "$URL" \
    --user-data-dir="$HOME/.herbie/face-browser" \
    --noerrdialogs --disable-infobars --no-first-run \
    --password-store=basic \
    --autoplay-policy=no-user-gesture-required \
    --check-for-update-interval=31536000 \
    --ignore-gpu-blocklist --enable-gpu-rasterization

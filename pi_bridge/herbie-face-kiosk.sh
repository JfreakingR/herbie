#!/bin/sh
# Fullscreen BMO face on Melba's HDMI panel.
set -eu

FACE_URL="${HERBIE_FACE_URL:-http://127.0.0.1:8766/face/?kiosk=1}"
LOG="${HERBIE_FACE_LOG:-/home/jfreakingr/pal-pi-bridge/face-kiosk.log}"
XINITRC="/home/jfreakingr/pal-pi-bridge/face-xinit.sh"

{
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) kiosk starting"
  python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=2).read()" >/dev/null 2>&1 || echo "face server not ready yet"

  if command -v cog >/dev/null 2>&1; then
    echo "using cog drm"
    exec cog --platform=drm "$FACE_URL"
  fi

  if command -v chromium >/dev/null 2>&1 && command -v xinit >/dev/null 2>&1; then
    echo "using chromium via xinit"
    export DISPLAY=:0
    exec xinit "$XINITRC" -- /usr/bin/X :0 vt7 -nocursor
  fi

  echo "no kiosk browser installed"
  exit 1
} >>"$LOG" 2>&1

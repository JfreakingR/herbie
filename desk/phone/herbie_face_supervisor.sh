#!/data/data/com.termux/files/usr/bin/sh
# Keeps Herbie's face server running on the Galaxy (port 8767), next to his
# brain (8765). Started at boot by ~/.termux/boot/boot_herbie_face.sh.
# It only serves his face; his brain, memory and voice are untouched.
set -u

HOME_DIR="$HOME/herbie-desk"
TOKEN="$HOME/pal-phone-brain/herbie-api-token"
PORT=8767
LOG="$HOME_DIR/herbie-face.log"
PIDFILE="$HOME_DIR/herbie-face-supervisor.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    echo "Herbie's face is already being kept running."
    exit 0
fi
echo $$ >"$PIDFILE"

healthy() {
    python -c "import urllib.request,sys; urllib.request.urlopen(sys.argv[1], timeout=3)" "$1" \
        >/dev/null 2>&1
}

while true; do
    # His face is only useful once his brain is up.
    until healthy "http://127.0.0.1:8765/health"; do sleep 5; done
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') starting face server" >>"$LOG"
    python "$HOME_DIR/desk/herbie_desk.py" --brain http://127.0.0.1:8765 \
        --token-file "$TOKEN" --port "$PORT" >>"$LOG" 2>&1
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') face server stopped; restarting in 5 s" >>"$LOG"
    sleep 5
done

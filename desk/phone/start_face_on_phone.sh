#!/data/data/com.termux/files/usr/bin/sh
# Herbie's face on the Galaxy itself, shown on the 7" screen over HDMI.
# Run inside Termux:  sh /sdcard/Download/herbie-desk/desk/phone/start_face_on_phone.sh
# The desk server talks to the brain on the same phone (127.0.0.1:8765) and
# serves the spirit on port 8767 (8766 belongs to the Herbie Brain app).
DIR=$(cd "$(dirname "$0")/../.." && pwd)
TOKEN="$HOME/pal-phone-brain/herbie-api-token"
PORT=8767

if [ ! -s "$TOKEN" ]; then
    echo "Herbie's brain token is missing at $TOKEN. Is the phone brain installed?"
    exit 1
fi
pkill -f herbie_desk.py 2>/dev/null
nohup python "$DIR/desk/herbie_desk.py" --brain http://127.0.0.1:8765 \
    --token-file "$TOKEN" --port "$PORT" >"$HOME/herbie-desk.log" 2>&1 &
sleep 2
if ! python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/health', timeout=3)" 2>/dev/null; then
    echo "The face server did not start. Its log:"
    cat "$HOME/herbie-desk.log"
    exit 1
fi
echo "Herbie's face is running. Opening it in the browser..."
termux-open-url "http://127.0.0.1:$PORT/face/spirit.html?kiosk=1"
echo "Tap his face once to make it fill the screen."

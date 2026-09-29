#!/data/data/com.termux/files/usr/bin/sh
# One-time setup, run inside Termux:
#   sh /sdcard/Download/herbie-desk/desk/phone/install_face_autostart.sh
# Copies Herbie's face into Termux's own storage (so Android's file rules
# can't hide it), starts it now, and starts it again after every reboot.
set -eu

SRC=$(cd "$(dirname "$0")/../.." && pwd)
DEST="$HOME/herbie-desk"

for need in "$SRC/desk/herbie_desk.py" "$SRC/pi_bridge/face/spirit.html"; do
    if [ ! -f "$need" ]; then
        echo "Missing $need - copy Herbie's face to the phone again first."
        exit 1
    fi
done

echo "Copying Herbie's face into Termux..."
mkdir -p "$DEST/desk" "$DEST/pi_bridge"
rm -rf "$DEST/desk/phone" "$DEST/pi_bridge/face"
cp "$SRC/desk/herbie_desk.py" "$DEST/desk/"
cp -r "$SRC/desk/phone" "$DEST/desk/phone"
cp -r "$SRC/pi_bridge/face" "$DEST/pi_bridge/face"
# Files from a Windows PC may carry CRLF line endings.
for f in "$DEST"/desk/phone/*.sh; do sed -i 's/\r$//' "$f"; chmod 700 "$f"; done

echo "Setting him to start when the phone starts..."
mkdir -p "$HOME/.termux/boot"
cp "$DEST/desk/phone/boot_herbie_face.sh" "$HOME/.termux/boot/boot_herbie_face.sh"
chmod 700 "$HOME/.termux/boot/boot_herbie_face.sh"

echo "Starting him now..."
pkill -f herbie_desk.py 2>/dev/null || true
nohup "$DEST/desk/phone/herbie_face_supervisor.sh" >/dev/null 2>&1 &
sleep 4
if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8767/health', timeout=3)" 2>/dev/null; then
    echo "Done. Herbie's face is running and will start by itself after a reboot."
else
    echo "Set up, but his face isn't answering yet. Is his brain running? Log: $DEST/herbie-face.log"
fi
termux-open-url "http://127.0.0.1:8767/face/spirit.html?kiosk=1" 2>/dev/null || true
echo "In Chrome: menu > Add to Home screen, to get a Herbie icon."

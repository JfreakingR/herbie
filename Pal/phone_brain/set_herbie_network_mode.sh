#!/data/data/com.termux/files/usr/bin/bash
# Select whether Herbie listens only inside the phone or on trusted local Wi-Fi.
set -eu

BRAIN_DIR="$HOME/pal-phone-brain"
MODE_FILE="$BRAIN_DIR/herbie-network-mode"
requested="${1:-status}"

current_mode() {
    if [ -f "$MODE_FILE" ]; then
        head -n 1 "$MODE_FILE"
    else
        echo device
    fi
}

if [ "$requested" = status ]; then
    echo "Herbie network mode: $(current_mode)"
    exit 0
fi

case "$requested" in
    device|usb) mode=device ;;
    wifi) mode=wifi ;;
    *)
        echo "Usage: $0 status|device|wifi" >&2
        exit 2
        ;;
esac

umask 077
temporary="$MODE_FILE.tmp.$$"
printf '%s\n' "$mode" >"$temporary"
mv "$temporary" "$MODE_FILE"

if [ -x "$BRAIN_DIR/stop_pal_brain.sh" ]; then
    "$BRAIN_DIR/stop_pal_brain.sh" >/dev/null 2>&1 || true
fi
nohup "$BRAIN_DIR/herbie_supervisor.sh" >/dev/null 2>&1 &
sleep 3

if ! pidof python >/dev/null 2>&1; then
    echo "Herbie failed to restart; inspect $BRAIN_DIR/herbie-supervisor.log" >&2
    exit 1
fi

if [ "$mode" = wifi ]; then
    echo "Herbie now accepts authenticated requests from private local networks on port 8765."
else
    echo "Herbie is device-only; use USB ADB forwarding for access."
fi

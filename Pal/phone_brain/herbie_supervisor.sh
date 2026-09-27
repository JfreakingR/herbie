#!/data/data/com.termux/files/usr/bin/bash
# Keeps Herbie's brain alive.
#
# Why this exists: start_pal_brain.sh launches the service once with nohup.
# Nothing restarted it after an Android battery-optimisation kill, a Termux
# stop, or a phone reboot - so the brain could die silently and Herbie would
# lose continuity without anyone noticing. This supervises it instead.
#
# Run directly, or let ~/.termux/boot/start-herbie.sh start it at boot
# (requires the Termux:Boot addon).

set -u

BRAIN_DIR="$HOME/pal-phone-brain"
BRAIN_LOG="$BRAIN_DIR/pal-phone-brain.log"
SUPERVISOR_LOG="$BRAIN_DIR/herbie-supervisor.log"
SUPERVISOR_PID="$BRAIN_DIR/herbie-supervisor.pid"
NETWORK_MODE_FILE="$BRAIN_DIR/herbie-network-mode"

MIN_BACKOFF=5
MAX_BACKOFF=60
HEALTHY_RUN_SECONDS=120

log() {
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') $*" >>"$SUPERVISOR_LOG"
}

# Refuse to run twice - two supervisors would fight over port 8765.
if [ -f "$SUPERVISOR_PID" ]; then
    existing="$(cat "$SUPERVISOR_PID" 2>/dev/null || true)"
    if [ -n "$existing" ] && kill -0 "$existing" 2>/dev/null; then
        echo "Herbie supervisor already running as PID $existing."
        exit 0
    fi
    rm -f "$SUPERVISOR_PID"
fi

# Stop a manually started brain so the port is free.
if [ -x "$BRAIN_DIR/stop_pal_brain.sh" ]; then
    "$BRAIN_DIR/stop_pal_brain.sh" >/dev/null 2>&1 || true
fi

# Ask Android not to doze the CPU. Without this the service is suspended and
# heartbeats stop even though the process is technically alive.
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    log "wake lock acquired"
else
    log "WARNING: termux-wake-lock unavailable; install termux-api"
fi

echo $$ >"$SUPERVISOR_PID"

cleanup() {
    log "supervisor stopping"
    command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
    rm -f "$SUPERVISOR_PID"
    exit 0
}
trap cleanup TERM INT

cd "$BRAIN_DIR"
log "supervisor started as PID $$"

network_mode="device"
if [ -f "$NETWORK_MODE_FILE" ]; then
    network_mode="$(head -n 1 "$NETWORK_MODE_FILE" 2>/dev/null || true)"
fi
case "$network_mode" in
    wifi) bind_host="0.0.0.0" ;;
    device|usb|"") bind_host="127.0.0.1" ;;
    *)
        bind_host="127.0.0.1"
        log "WARNING: invalid network mode '$network_mode'; using device-only"
        ;;
esac
log "network mode=$network_mode bind=$bind_host"

backoff="$MIN_BACKOFF"
while true; do
    started_at="$(date +%s)"
    log "starting phone brain"

    HERBIE_PHONE_HOST="$bind_host" HERBIE_PHONE_PORT=8765 \
        python "$BRAIN_DIR/pal_phone_brain.py" >>"$BRAIN_LOG" 2>&1
    exit_code=$?

    ran_for=$(( $(date +%s) - started_at ))
    log "phone brain exited code=$exit_code after ${ran_for}s"

    # A run that lasted a while was healthy; only a fast crash loop backs off,
    # so a genuine one-off kill is recovered from promptly.
    if [ "$ran_for" -ge "$HEALTHY_RUN_SECONDS" ]; then
        backoff="$MIN_BACKOFF"
    fi

    log "restarting in ${backoff}s"
    sleep "$backoff"

    if [ "$backoff" -lt "$MAX_BACKOFF" ]; then
        backoff=$(( backoff * 2 ))
        [ "$backoff" -gt "$MAX_BACKOFF" ] && backoff="$MAX_BACKOFF"
    fi
done

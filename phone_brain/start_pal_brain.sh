#!/data/data/com.termux/files/usr/bin/bash
# Start the brain once, unsupervised.
#
# Prefer herbie_supervisor.sh for normal use: this script does not restart the
# service if Android kills it. Kept for one-off manual runs and debugging.
set -eu

PAL_BRAIN_DIR="$HOME/pal-phone-brain"
PAL_BRAIN_PID="$PAL_BRAIN_DIR/pal-phone-brain.pid"
PAL_BRAIN_LOG="$PAL_BRAIN_DIR/pal-phone-brain.log"
SUPERVISOR_PID="$PAL_BRAIN_DIR/herbie-supervisor.pid"

if [ -f "$SUPERVISOR_PID" ]; then
    sup_pid="$(cat "$SUPERVISOR_PID" 2>/dev/null || true)"
    if [ -n "$sup_pid" ] && kill -0 "$sup_pid" 2>/dev/null; then
        echo "Herbie supervisor is running as PID $sup_pid; it owns the brain."
        echo "Use stop_pal_brain.sh first if you really want an unsupervised run."
        exit 0
    fi
fi

if [ -f "$PAL_BRAIN_PID" ]; then
    old_pid="$(cat "$PAL_BRAIN_PID" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "Herbie phone brain is already running as PID $old_pid."
        exit 0
    fi
    rm -f "$PAL_BRAIN_PID"
fi

# Without a wake lock Android suspends the CPU and heartbeats stop even though
# the process is still alive.
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi

cd "$PAL_BRAIN_DIR"
HERBIE_PHONE_HOST=127.0.0.1 HERBIE_PHONE_PORT=8765 \
    nohup python "$PAL_BRAIN_DIR/pal_phone_brain.py" >"$PAL_BRAIN_LOG" 2>&1 &
new_pid=$!
echo "$new_pid" >"$PAL_BRAIN_PID"
sleep 1

if ! kill -0 "$new_pid" 2>/dev/null; then
    echo "Herbie phone brain failed to start."
    tail -n 20 "$PAL_BRAIN_LOG" || true
    exit 1
fi

echo "Herbie phone brain started as PID $new_pid on 127.0.0.1:8765."
if [ -f "$PAL_BRAIN_DIR/herbie-api-token" ]; then
    echo "Callers must send: Authorization: Bearer \$(cat $PAL_BRAIN_DIR/herbie-api-token)"
fi

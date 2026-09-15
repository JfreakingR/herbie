#!/data/data/com.termux/files/usr/bin/bash
set -eu

PAL_BRAIN_DIR="$HOME/pal-phone-brain"
PAL_BRAIN_PID="$PAL_BRAIN_DIR/pal-phone-brain.pid"
SUPERVISOR_PID="$PAL_BRAIN_DIR/herbie-supervisor.pid"

stopped_something=0

# Stop the supervisor first, or it would immediately restart the brain.
if [ -f "$SUPERVISOR_PID" ]; then
    sup_pid="$(cat "$SUPERVISOR_PID" 2>/dev/null || true)"
    if [ -n "$sup_pid" ] && kill -0 "$sup_pid" 2>/dev/null; then
        kill "$sup_pid"
        echo "Herbie supervisor stopped (PID $sup_pid)."
        stopped_something=1
    fi
    rm -f "$SUPERVISOR_PID"
fi

if [ -f "$PAL_BRAIN_PID" ]; then
    pid="$(cat "$PAL_BRAIN_PID" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "Herbie phone brain stopped (PID $pid)."
        stopped_something=1
    fi
    rm -f "$PAL_BRAIN_PID"
fi

# The supervisor runs python as a child, so catch anything it left behind.
if pkill -f "pal_phone_brain.py" 2>/dev/null; then
    echo "Stopped remaining pal_phone_brain.py process(es)."
    stopped_something=1
fi

if [ "$stopped_something" -eq 0 ]; then
    echo "Herbie phone brain is not running."
fi

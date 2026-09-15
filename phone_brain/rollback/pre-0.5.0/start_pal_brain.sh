#!/data/data/com.termux/files/usr/bin/bash
set -eu

PAL_BRAIN_DIR="$HOME/pal-phone-brain"
PAL_BRAIN_PID="$PAL_BRAIN_DIR/pal-phone-brain.pid"
PAL_BRAIN_LOG="$PAL_BRAIN_DIR/pal-phone-brain.log"

if [ -f "$PAL_BRAIN_PID" ]; then
    old_pid="$(cat "$PAL_BRAIN_PID" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "Herbie phone brain is already running as PID $old_pid."
        exit 0
    fi
    rm -f "$PAL_BRAIN_PID"
fi

cd "$PAL_BRAIN_DIR"
PAL_PHONE_HOST=127.0.0.1 PAL_PHONE_PORT=8765 \
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


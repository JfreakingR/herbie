#!/data/data/com.termux/files/usr/bin/bash
set -eu

SOURCE_DIR="/sdcard/Download/PalBrain"
TARGET_DIR="$HOME/pal-phone-brain"

if [ -x "$TARGET_DIR/stop_pal_brain.sh" ]; then
    "$TARGET_DIR/stop_pal_brain.sh"
fi

mkdir -p "$TARGET_DIR"
cp "$SOURCE_DIR/pal_phone_brain.py" "$TARGET_DIR/"
cp "$SOURCE_DIR/herbie_memory.py" "$TARGET_DIR/"
cp "$SOURCE_DIR/herbie_voice.py" "$TARGET_DIR/"
cp "$SOURCE_DIR/start_pal_brain.sh" "$TARGET_DIR/"
cp "$SOURCE_DIR/stop_pal_brain.sh" "$TARGET_DIR/"
chmod 700 "$TARGET_DIR/pal_phone_brain.py"
chmod 600 "$TARGET_DIR/herbie_memory.py"
chmod 600 "$TARGET_DIR/herbie_voice.py"
chmod 700 "$TARGET_DIR/start_pal_brain.sh"
chmod 700 "$TARGET_DIR/stop_pal_brain.sh"
"$TARGET_DIR/start_pal_brain.sh"

#!/data/data/com.termux/files/usr/bin/bash
set +e

OUT="/sdcard/Download/herbie-sense-help.txt"
{
    printf '%s\n' '--- TTS ---'
    termux-tts-speak -h 2>&1
    printf '%s\n' '--- MICROPHONE ---'
    termux-microphone-record -h 2>&1
    printf '%s\n' '--- CAMERA PHOTO ---'
    termux-camera-photo -h 2>&1
} >"$OUT"

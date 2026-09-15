#!/data/data/com.termux/files/usr/bin/bash
set -u

OUT="/sdcard/Download/herbie-senses-probe.txt"
{
    printf 'timestamp=%s\n' "$(date -Iseconds)"
    for command_name in \
        python \
        termux-tts-speak \
        termux-tts-engines \
        termux-microphone-record \
        termux-speech-to-text \
        termux-camera-info \
        termux-sensor \
        termux-battery-status \
        termux-vibrate
    do
        if command -v "$command_name" >/dev/null 2>&1; then
            printf '%s=available\n' "$command_name"
        else
            printf '%s=missing\n' "$command_name"
        fi
    done
} >"$OUT"

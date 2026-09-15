#!/data/data/com.termux/files/usr/bin/bash
set +e

OUT="/sdcard/Download/herbie-voice-mic-test.txt"
AUDIO="/sdcard/Download/herbie-mic-test.m4a"
rm -f "$AUDIO"

{
    printf 'started=%s\n' "$(date -Iseconds)"
    termux-tts-speak -s MUSIC -l en -n US -p 0.9 -r 0.92 \
        "Hello. I am Herbie. This is only my temporary voice, but I can remember now."
    printf 'tts_exit=%s\n' "$?"
    sleep 3
    termux-microphone-record -f "$AUDIO" -l 3 -e aac
    printf 'microphone_start_exit=%s\n' "$?"
    sleep 5
    termux-microphone-record -q >/dev/null 2>&1
    if [ -s "$AUDIO" ]; then
        printf 'microphone_audio_bytes=%s\n' "$(wc -c <"$AUDIO")"
        printf '%s\n' 'microphone_test=passed'
    else
        printf '%s\n' 'microphone_test=failed'
    fi
    rm -f "$AUDIO"
    printf 'temporary_audio_retained=%s\n' "$(test -e "$AUDIO" && echo yes || echo no)"
    printf 'finished=%s\n' "$(date -Iseconds)"
} >"$OUT" 2>&1

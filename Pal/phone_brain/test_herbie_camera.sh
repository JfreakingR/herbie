#!/data/data/com.termux/files/usr/bin/bash
set +e

OUT="/sdcard/Download/herbie-camera-test.txt"
INFO="/sdcard/Download/herbie-camera-info.json"
PHOTO="/sdcard/Download/herbie-camera-test.jpg"
rm -f "$INFO" "$PHOTO"

{
    printf 'started=%s\n' "$(date -Iseconds)"
    termux-camera-info >"$INFO" 2>&1
    printf 'camera_info_exit=%s\n' "$?"
    termux-camera-photo -c 0 "$PHOTO"
    printf 'camera_photo_exit=%s\n' "$?"
    if [ -s "$PHOTO" ]; then
        printf 'camera_photo_bytes=%s\n' "$(wc -c <"$PHOTO")"
        printf '%s\n' 'camera_test=passed'
    else
        printf '%s\n' 'camera_test=failed'
    fi
    rm -f "$PHOTO" "$INFO"
    printf 'temporary_photo_retained=%s\n' "$(test -e "$PHOTO" && echo yes || echo no)"
    printf 'finished=%s\n' "$(date -Iseconds)"
} >"$OUT" 2>&1

"""Send one CONTROL_SERVO frame straight to Herbie's /dev/ttyMT1.

This is the ONLY path that actually drives him. The factory app's REST
interface on port 1666 looks equivalent and is not: it stamps every frame
with sequence 0, and the STM32 silently discards those - no ack, no beep,
no attempt. See HERBIE_HANDOFF_2026-09-18_SEQUENCE_AND_IR.md.

Usage:
    python tools/Send-Herbie-Frame.py <direction> <duration_ms> [sequence]

    direction    forward | backward | left | right  (see vava.DRIVE_ACTIONS)
    duration_ms  1..2000, capped by the protocol module
    sequence     0x01..0xFF; omit for a time-derived one. NEVER 0.

    Set HERBIE_ADB_TARGET to an `adb -s` target to use Wi-Fi ADB
    (`adb tcpip 5555`, then `adb connect <board-ip>:5555`); it defaults
    to the USB serial. Wi-Fi drops often - retry rather than diagnosing.

Read back what the board says with:
    adb -s <target> shell 'cat /sdcard/com.sego.toy.ctl/log/log.txt' \
        | grep -a UART | tail
A `<=UART: AA5500 0901 <seq> <ours> 22 00000000 <crc>` line is the ack.
A `<=UART: AA5500 0525 <seq> 0B 01 <crc>` line is an infrared_led key event,
which means his IR sensing blocked the move - clear the space around him
and resend. Six for six on 2026-09-18: IR event present = he refuses.
"""
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "phone_brain"))
import herbie_vava_protocol as vava  # noqa: E402

ADB = os.path.join(REPO, ".tools", "platform-tools", "adb.exe")
STAGING = "/sdcard/.herbie_console_frame.bin"
USB_SERIAL = "0123456789ABCDEF"


def main(argv: list) -> int:
    if not 3 <= len(argv) <= 4:
        print(__doc__)
        return 2
    direction = argv[1]
    duration_ms = int(argv[2])
    sequence = int(argv[3], 0) if len(argv) > 3 else (int(time.time()) & 0xFF)
    if sequence == 0:
        # A zero sequence is not an error the board reports; it is simply
        # ignored. Refusing here is the whole point of this script.
        print("sequence 0 is discarded by the STM32 - pick 0x01..0xFF")
        return 2

    target = os.environ.get("HERBIE_ADB_TARGET", USB_SERIAL)
    frame = vava.to_wire(vava.move(direction, duration_ms, sequence))
    print(f"target {target}  seq 0x{sequence:02X}  {frame.hex(' ').upper()}")

    local = os.path.join(REPO, "tools", ".frame.bin")
    with open(local, "wb") as fh:
        fh.write(frame)

    push = subprocess.run([ADB, "-s", target, "push", local, STAGING],
                          capture_output=True, timeout=30)
    if push.returncode != 0:
        print("push failed:", push.stderr.decode(errors="replace").strip())
        return 1
    write = subprocess.run([ADB, "-s", target, "shell",
                            f"cat {STAGING} > /dev/ttyMT1"],
                           capture_output=True, timeout=30)
    if write.returncode != 0:
        print("write failed:", write.stderr.decode(errors="replace").strip())
        return 1
    print("sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

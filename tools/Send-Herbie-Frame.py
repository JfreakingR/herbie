"""Send one CONTROL_SERVO frame straight to Herbie's /dev/ttyMT1.

This is the ONLY path that actually drives him. The factory app's REST
interface on port 1666 looks equivalent and is not: it stamps every frame
with sequence 0, and the STM32 silently discards those - no ack, no beep,
no attempt. See HERBIE_HANDOFF_2026-09-18_SEQUENCE_AND_IR.md.

Usage:
    python tools/Send-Herbie-Frame.py <direction> <duration_ms> [sequence]
    python tools/Send-Herbie-Frame.py treat [sequence]
    python tools/Send-Herbie-Frame.py feed <portions> [sequence]

    treat        turn the treat wheel one step - the factory self-test's own
                 `toggle_peripheral,0,0,4,1,0` (peripheral 4, snack_lattices)
    feed         the app's scheduled-feed command instead: peripheral 7,
                 instant_feeding, 1..3 portions. Try `treat` first.

    direction    forward | backward | left | right  (see vava.DRIVE_ACTIONS)
                 Only `forward` is physically confirmed as of 2026-09-19.
    duration_ms  1..2000, capped by the protocol module
    sequence     0x01..0xFF; omit for a time-derived one. NEVER 0.

    Set HERBIE_ADB_TARGET to an `adb -s` target to use Wi-Fi ADB
    (`adb tcpip 5555`, then `adb connect <board-ip>:5555`); it defaults
    to the USB serial.

After sending it prints the board's reply, which is the real result:

    <=UART: AA5500 0901 <seq> <ours> 22 00000000 <crc>
        the ack. src_command 0x22, result 0 means he accepted it.
    <=UART: AA5500 0525 <seq> 0B 01 <crc>
        an infrared_led key event - his IR sensing vetoed the move. Clear the
        space around him and resend. Six for six on 2026-09-18: IR event
        present = he refuses, absent = he drives.

Wi-Fi note: his radio leaves the channel to scan about every 20 s for about a
second, and adb turns that into a dead session it never recovers from. Every
read-only step here reconnects and retries. The write to /dev/ttyMT1 does NOT
retry, on purpose: a re-sent drive command would move a real robot twice. If
that write's outcome is unclear this script says so and leaves it to a human.
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
APP_LOG = "/sdcard/com.sego.toy.ctl/log/log.txt"
USB_SERIAL = "0123456789ABCDEF"


def adb(target, *args, timeout=30):
    return subprocess.run([ADB, "-s", target, *args],
                          capture_output=True, timeout=timeout)


def link_ok(target):
    """True when adb lists this target as `device` (not `offline`/absent)."""
    try:
        out = subprocess.run([ADB, "devices"], capture_output=True, timeout=15)
    except subprocess.TimeoutExpired:
        return False
    for line in out.stdout.decode(errors="replace").splitlines():
        if line.startswith(target):
            return line.split()[-1].strip() == "device"
    return False


def ensure_link(target, attempts=4):
    """Reconnect a dropped Wi-Fi target. USB targets are left alone.

    adb marks a scanned-away device `offline` and never recovers by itself,
    so a plain `connect` is not enough - the stale entry has to go first.
    """
    if ":" not in target:          # USB serial: nothing to reconnect
        return link_ok(target)
    def quietly(*args, timeout=20):
        # `adb connect` itself blocks and times out when he is mid-scan, so
        # every recovery step has to survive its own timeout.
        try:
            subprocess.run([ADB, *args], capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            pass

    for attempt in range(attempts):
        if link_ok(target):
            return True
        quietly("disconnect", target, timeout=15)
        quietly("connect", target)
        if link_ok(target):
            return True
        if attempt == attempts - 2:   # last resort before giving up
            quietly("kill-server", timeout=15)
            quietly("start-server")
        time.sleep(1.5)
    return link_ok(target)


def uart_lines(target, count=6):
    """Last few UART lines from the app's log. Read-only, safe to retry."""
    for _ in range(3):
        if not ensure_link(target):
            continue
        try:
            out = adb(target, "shell", f"cat {APP_LOG}", timeout=45)
        except subprocess.TimeoutExpired:
            continue
        if out.returncode != 0:
            continue
        lines = [ln.split("SerialIoThread: ")[-1].strip()
                 for ln in out.stdout.decode(errors="replace").splitlines()
                 if "UART:" in ln]
        if lines:
            return lines[-count:]
    return []


def main(argv):
    verb = argv[1] if len(argv) > 1 else ""
    nargs = {"treat": 0, "feed": 1}.get(verb, 1)   # args before [sequence]
    if not 2 + nargs <= len(argv) <= 3 + nargs:
        print(__doc__)
        return 2
    seq_arg = argv[2 + nargs] if len(argv) > 2 + nargs else None
    sequence = int(seq_arg, 0) if seq_arg else (int(time.time()) & 0xFF)
    if sequence == 0:
        # Not an error the board reports; it is simply ignored. Refusing to
        # send it is the entire point of this script.
        print("sequence 0 is discarded by the STM32 - pick 0x01..0xFF")
        return 2

    target = os.environ.get("HERBIE_ADB_TARGET", USB_SERIAL)
    if not ensure_link(target):
        print(f"cannot reach {target} - check he is powered and on the network")
        return 1

    try:
        if verb == "treat":
            frame = vava.treat_wheel(sequence)
        elif verb == "feed":
            frame = vava.feed(int(argv[2]), sequence)
        else:
            frame = vava.move(verb, int(argv[2]), sequence)
        frame = vava.to_wire(frame)
    except ValueError as exc:
        print(f"{exc} - directions: {', '.join(sorted(vava.DRIVE_ACTIONS))}; "
              f"duration 1..{vava.MAX_DURATION_MS} ms; "
              f"feed portions 1..{vava.MAX_FEED_PORTIONS}")
        return 2
    print(f"target {target}  seq 0x{sequence:02X}  {frame.hex(' ').upper()}")
    print("   ", vava.describe(vava.parse_frame(frame)))

    local = os.path.join(REPO, "tools", ".frame.bin")
    with open(local, "wb") as fh:
        fh.write(frame)

    # Pushing a file is idempotent, so retrying it cannot move anything.
    for attempt in range(3):
        push = adb(target, "push", local, STAGING)
        if push.returncode == 0:
            break
        if not ensure_link(target):
            print("lost him while staging the frame")
            return 1
    else:
        print("push failed:", push.stderr.decode(errors="replace").strip())
        return 1

    # The actuation. Exactly one attempt, whatever happens.
    try:
        write = adb(target, "shell", f"cat {STAGING} > /dev/ttyMT1")
    except subprocess.TimeoutExpired:
        print("AMBIGUOUS: the write timed out. He may or may not have moved.")
        print("Not retrying - that could drive him twice. Check the log:")
        for line in uart_lines(target):
            print("   ", line)
        return 3
    if write.returncode != 0:
        print("AMBIGUOUS: the write failed after the frame was staged.")
        print("stderr:", write.stderr.decode(errors="replace").strip())
        for line in uart_lines(target):
            print("   ", line)
        return 3

    print("sent.")
    for line in uart_lines(target):
        print("   ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

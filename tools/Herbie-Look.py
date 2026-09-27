"""Turn Herbie's neck - the treat wheel with a camera on it.

Usage:
    python tools/Herbie-Look.py              where is he facing?
    python tools/Herbie-Look.py home         call the way he faces now 0 degrees
                                             (moves nothing; do this first)
    python tools/Herbie-Look.py <degrees>    turn to face that angle, e.g. 90
    python tools/Herbie-Look.py step [n]     turn n steps (default 1)

One step is 40 degrees; 9 steps is a full turn (owner-measured 2026-09-27).
180 is not a whole number of steps: it rounds to 160 (4 steps).
The wheel is only known to turn one way, so asking for an angle "behind"
him goes forward the long way round. Angles count in that direction.

He remembers where he is facing in %USERPROFILE%\\.herbie\\neck_step.txt,
updated after every step that is sent. If anything turns the wheel without
this tool (a hand, the factory app, a restart that re-centres it), or a step
comes back AMBIGUOUS, point him forward again and run `home`.

Each step is two wheel frames: the wheel only visibly moves on every other
one. Every frame is followed by HERBIE_NECK_PAUSE seconds (default 5), as
frames sent too close together are dropped. About 10 s per 40 degrees.

Uses the same link as Send-Herbie-Frame.py (USB by default,
HERBIE_ADB_TARGET for Wi-Fi) and its exactly-once write per step.
"""
import importlib.util
import os
import sys
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "send_herbie_frame", os.path.join(HERE, "Send-Herbie-Frame.py"))
sender = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sender)
vava = sender.vava

STATE = Path.home() / ".herbie" / "neck_step.txt"
# The wheel makes a visible move on every OTHER frame (2026-09-27: at 6.5 s
# and 14 s spacing, and with an "off" frame between), so each 40-degree step
# is NECK_FRAMES_PER_STEP frames. Frames too close together are dropped
# (~2-3 s apart lost most of them), so every frame is followed by a pause.
# Override with HERBIE_NECK_PAUSE (seconds).
STEP_PAUSE_S = float(os.environ.get("HERBIE_NECK_PAUSE", "5"))


def read_step():
    try:
        return int(STATE.read_text().strip()) % vava.NECK_STEPS_PER_TURN
    except (OSError, ValueError):
        return None


def write_step(step):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(str(step % vava.NECK_STEPS_PER_TURN))


def facing(step):
    return f"facing {step * vava.NECK_DEGREES_PER_STEP} degrees (step {step} of {vava.NECK_STEPS_PER_TURN})"


def turn(steps, current):
    """Turn `steps` 40-degree steps, NECK_FRAMES_PER_STEP frames each. 0 = ok."""
    if steps == 0:
        print("already there -", facing(current))
        return 0
    target = os.environ.get("HERBIE_ADB_TARGET", sender.USB_SERIAL)
    if not sender.ensure_link(target):
        print(f"cannot reach {target} - check he is powered and connected")
        return 1
    sequence = int(time.time()) & 0xFF
    for i in range(steps):
        for f in range(vava.NECK_FRAMES_PER_STEP):
            sequence = sequence % 0xFF + 1      # 1..255, never 0
            frame = vava.to_wire(vava.treat_wheel(sequence))
            print(f"step {i + 1}/{steps}  frame {f + 1}/{vava.NECK_FRAMES_PER_STEP}"
                  f"  seq 0x{sequence:02X}  ", end="")
            result = sender.send_frame(target, frame, show_log=False)
            if result != 0:
                break
            if not (i + 1 == steps and f + 1 == vava.NECK_FRAMES_PER_STEP):
                time.sleep(STEP_PAUSE_S)
        if result != 0:
            if result == 3:
                print("Stopped. That frame may or may not have happened, so his "
                      "heading is unknown: face him forward and run `home`.")
            else:
                print("Stopped before sending that frame. If it was frame 2 of a "
                      "step, the heading may be off: face him forward and run `home`.")
            print("last known:", facing(current))
            return result
        current = (current + 1) % vava.NECK_STEPS_PER_TURN
        write_step(current)
    print("now", facing(current))
    return 0


def main(argv):
    args = argv[1:]
    current = read_step()

    if not args:
        print(facing(current) if current is not None
              else "heading unknown - face him forward and run `home`")
        return 0
    if args[0] == "home":
        write_step(0)
        print("home set:", facing(0))
        return 0
    if current is None:
        print("heading unknown - face him forward and run `home` first")
        return 2
    try:
        if args[0] == "step":
            steps = int(args[1]) if len(args) > 1 else 1
            if not 1 <= steps <= vava.NECK_STEPS_PER_TURN:
                raise ValueError
        else:
            steps = vava.neck_steps_to(current, int(args[0]))
    except (ValueError, IndexError):
        print(__doc__)
        return 2
    return turn(steps, current)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

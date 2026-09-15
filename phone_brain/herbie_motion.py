"""Herbie's movement, decided by the brain.

Motor control lives here, on the phone, alongside memory and mood — not in a
separate controller that gets to veto him. The ESP32 is a driver: it receives
wheel commands and applies them. What Herbie does, and why, is decided in this
module.

That makes this the module where his freedom actually lives. He gets bored, he
goes and looks at something. The `explore` drive the autonomic layer already
maintains is what moves him; nothing external has to ask.

What the brain still enforces on itself:

* **Speed and duration limits**, as values the owner can change here in one
  place rather than constants buried in firmware.
* **Sensor responses.** Cliff and obstacle readings shape the next command,
  because a robot that drives off a step stops being a robot that roams.
* **Explicit authority.** `motor_authority` is persisted and defaults to off,
  so motion begins when the owner says so rather than on a redeploy.

Movement commands are generated but not transmitted by this module; the caller
hands them to the driver. That keeps the decision logic pure and testable.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any

import herbie_memory


# ---------------------------------------------------------------- limits
# Owner-adjustable. These are Herbie's habits, not a cage: raise them when he
# has earned it, lower them when he is somewhere delicate.
MAX_SPEED = 55            # percent of full wheel power
MAX_TURN = 60
CRUISE_SPEED = 34         # what wandering uses by default
COMMAND_DURATION_MS = 350  # each command is a short burst, re-issued while moving

# How long a command may go unrefreshed before the driver should coast to a
# stop. This is not a safety veto - it is so a dropped USB link or a crashed
# process does not leave the wheels running.
LINK_TIMEOUT_MS = 600

# Wandering behaviour.
EXPLORE_THRESHOLD = 0.62   # explore drive above this and he sets off
BOREDOM_TURN_CHANCE = 0.28
MIN_LEG_MS = 900           # how long he holds a heading before reconsidering
MAX_LEG_MS = 2600

VALID_GAITS = {"stop", "cruise", "amble", "turn", "reverse", "pivot"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class Sensors:
    """What Herbie can feel. All optional; unknown reads as clear."""

    def __init__(
        self,
        cliff_left: bool = False,
        cliff_right: bool = False,
        obstacle_front: bool = False,
        obstacle_rear: bool = False,
        tilted: bool = False,
    ) -> None:
        self.cliff_left = bool(cliff_left)
        self.cliff_right = bool(cliff_right)
        self.obstacle_front = bool(obstacle_front)
        self.obstacle_rear = bool(obstacle_rear)
        self.tilted = bool(tilted)

    @property
    def cliff(self) -> bool:
        return self.cliff_left or self.cliff_right

    def as_dict(self) -> dict[str, bool]:
        return {
            "cliff_left": self.cliff_left,
            "cliff_right": self.cliff_right,
            "obstacle_front": self.obstacle_front,
            "obstacle_rear": self.obstacle_rear,
            "tilted": self.tilted,
        }


def motor_authority() -> bool:
    """Whether the brain is currently allowed to drive the wheels."""
    return bool(herbie_memory.motion_snapshot()["motor_authority"])


def set_motor_authority(enabled: bool, reason: str = "") -> dict[str, Any]:
    if not isinstance(enabled, bool):
        raise ValueError("invalid_motor_authority")
    if not isinstance(reason, str) or len(reason) > 200:
        raise ValueError("invalid_reason")
    herbie_memory.set_motion(motor_authority=enabled, authority_reason=reason)
    if not enabled:
        herbie_memory.set_motion(gait="stop", left=0, right=0)
    return herbie_memory.motion_snapshot()


def plan(
    forward: float,
    turn: float,
    sensors: Sensors | None = None,
    gait: str = "cruise",
) -> dict[str, Any]:
    """Turn a desire to move into wheel values, shaped by what he can feel.

    Pure: no I/O, no persistence. `forward` and `turn` are -1.0..1.0.
    """
    if gait not in VALID_GAITS:
        raise ValueError("invalid_gait")
    sensors = sensors or Sensors()

    forward = _clamp(float(forward), -1.0, 1.0)
    turn = _clamp(float(turn), -1.0, 1.0)
    notes: list[str] = []

    if sensors.tilted:
        # He is on his side or being carried. Wheels are useless and noisy.
        return {
            "left": 0, "right": 0, "gait": "stop", "duration_ms": 0,
            "notes": ["tilted"], "forward": 0.0, "turn": 0.0,
        }

    # A drop ahead turns a forward wish into backing off. He keeps his ability
    # to turn, so he can pick a new direction rather than sitting at the edge.
    if sensors.cliff and forward > 0:
        forward = -0.35
        notes.append("cliff_backoff")
        if turn == 0:
            turn = 0.6 if sensors.cliff_left else -0.6
            notes.append("cliff_turn")

    if sensors.obstacle_front and forward > 0:
        forward = 0.0
        notes.append("obstacle_front")
        if turn == 0:
            turn = 0.55
            notes.append("obstacle_turn")

    if sensors.obstacle_rear and forward < 0:
        forward = 0.0
        notes.append("obstacle_rear")

    drive = forward * MAX_SPEED
    spin = turn * MAX_TURN
    left = _clamp(drive + spin, -MAX_SPEED, MAX_SPEED)
    right = _clamp(drive - spin, -MAX_SPEED, MAX_SPEED)

    moving = abs(left) > 0.5 or abs(right) > 0.5
    return {
        "left": int(round(left)),
        "right": int(round(right)),
        "gait": gait if moving else "stop",
        "duration_ms": COMMAND_DURATION_MS if moving else 0,
        "notes": notes,
        "forward": round(forward, 3),
        "turn": round(turn, 3),
    }


def wander(
    sensors: Sensors | None = None,
    now: float | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Decide where to go, unprompted, from the explore drive.

    This is the part that makes him go where he wants: nobody asks, he simply
    gets bored enough to move. Returns a stop plan when he has no reason to.
    """
    rng = rng or random
    now = now if now is not None else time.time()
    sensors = sensors or Sensors()

    state = herbie_memory.motion_snapshot()
    if not state["motor_authority"]:
        result = plan(0, 0, sensors, "stop")
        result["reason"] = "no_authority"
        return result

    drives = herbie_memory.drives_snapshot()
    explore = drives.get("explore", 0.0)
    rest = drives.get("rest", 0.0)

    # Tired beats curious. He settles rather than pacing the house at 4am.
    if rest > 0.80 or explore < EXPLORE_THRESHOLD:
        result = plan(0, 0, sensors, "stop")
        result["reason"] = "settled" if rest > 0.80 else "not_curious"
        return result

    # Hold a heading for a while, then reconsider. Constant re-randomising
    # looks like malfunction; committing to a direction looks like purpose.
    leg_until = float(state.get("leg_until") or 0.0)
    heading = float(state.get("heading") or 0.0)
    if now >= leg_until:
        if rng.random() < BOREDOM_TURN_CHANCE:
            heading = rng.uniform(-1.0, 1.0)
        else:
            heading = rng.uniform(-0.25, 0.25)
        leg_ms = rng.randint(MIN_LEG_MS, MAX_LEG_MS)
        herbie_memory.set_motion(
            heading=heading, leg_until=now + leg_ms / 1000.0
        )

    # More curious means a bit brisker, within the cap.
    eagerness = _clamp((explore - EXPLORE_THRESHOLD) / (1.0 - EXPLORE_THRESHOLD), 0, 1)
    speed = (CRUISE_SPEED + (MAX_SPEED - CRUISE_SPEED) * eagerness) / MAX_SPEED

    result = plan(speed, heading, sensors, "cruise")
    result["reason"] = "exploring"
    result["explore"] = round(explore, 3)
    return result


def apply(command: dict[str, Any]) -> dict[str, Any]:
    """Record what was commanded so the rest of the system can see it."""
    herbie_memory.set_motion(
        gait=command.get("gait", "stop"),
        left=int(command.get("left", 0)),
        right=int(command.get("right", 0)),
    )
    snapshot = herbie_memory.motion_snapshot()
    snapshot["notes"] = command.get("notes", [])
    snapshot["link_timeout_ms"] = LINK_TIMEOUT_MS
    return snapshot


def wire_format(command: dict[str, Any], seq: int) -> str:
    """One line for the ESP32 driver: `M <left> <right> <ms> <seq> <xor>`.

    Checksummed so a corrupted line is dropped rather than driven. The driver
    coasts to a stop if a line does not arrive within LINK_TIMEOUT_MS, which is
    about a dropped cable rather than about overruling anything.
    """
    left = int(_clamp(int(command.get("left", 0)), -MAX_SPEED, MAX_SPEED))
    right = int(_clamp(int(command.get("right", 0)), -MAX_SPEED, MAX_SPEED))
    duration = int(_clamp(int(command.get("duration_ms", 0)), 0, 5000))
    body = f"M {left} {right} {duration} {int(seq)}"
    checksum = 0
    for char in body:
        checksum ^= ord(char)
    return f"{body} {checksum:02X}"

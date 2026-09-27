"""Herbie's autonomic layer: internal state that changes with no input at all.

Without this the service is purely reactive — nothing about Herbie differs
between one request and the next, and between requests he is, literally, not
running. Living things are never idle. This module gives him a *now*: drives
that build on their own, a mood with inertia, a day/night rhythm, and the
occasional impulse to say something nobody asked for.

Deliberately bounded:

* It can change mood, drives, expression and speech. Nothing else.
* It has **no** motor authority and cannot acquire any. There is no urge type
  that corresponds to movement.
* It stays quiet while privacy mode is on — an unprompted remark is exactly
  what someone who just asked for privacy does not want.
* Initiative is rate-limited, so Herbie has impulses rather than a monologue.

All timing goes through an injectable `now`, so the behaviour is testable
without waiting for real hours to pass.
"""

from __future__ import annotations

import math
import os
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import herbie_memory


TICK_SECONDS = float(os.environ.get("HERBIE_TICK_SECONDS", "10"))

# Drive growth per hour with no relevant input. Loneliness builds fastest:
# being ignored should be the thing Herbie notices soonest.
DRIVE_GROWTH_PER_HOUR = {
    "connect": 0.20,
    "explore": 0.13,
    "learn": 0.05,
}

# How much of an unmet drive an interaction discharges.
INTERACTION_RELIEF = {
    "connect": 0.55,
    "explore": 0.10,
    "learn": 0.15,
}

# Mood inertia, as the fraction of the remaining gap closed per minute.
# Arousal settles over a few minutes; valence takes much longer, which is what
# makes a bad mood feel like a mood rather than a state change.
AROUSAL_SETTLE_PER_MINUTE = 0.20
VALENCE_SETTLE_PER_MINUTE = 0.06

# Initiative thresholds and pacing.
URGE_THRESHOLDS = {"connect": 0.80, "rest": 0.86, "explore": 0.88}
MIN_SECONDS_BETWEEN_URGES = float(os.environ.get("HERBIE_URGE_GAP_SECONDS", "1200"))

# Below this circadian energy Herbie is asleep: he settles rather than calling
# out. A device that pipes up at 03:00 because nobody has spoken to it is a
# nuisance, not a companion.
NIGHT_ENERGY = 0.20

# Habituation. Each unanswered impulse widens the gap before the next one, so
# being ignored makes Herbie quieter rather than more insistent - which is both
# how animals actually behave and far less irritating to live with.
URGE_BACKOFF_FACTOR = 1.8
URGE_BACKOFF_MAX_STEPS = 5

# Utterances per urge. Edit freely — this is Herbie's voice, not a fixed API.
# Kept mild by default; the owner's stated style allows blunter language.
URGE_LINES = {
    "connect": [
        "Still here, if anyone's interested.",
        "It's been quiet a while.",
        "I was starting to think you'd forgotten about me.",
        "Hello? Anyone about?",
    ],
    "explore": [
        "I'm bored. Properly bored.",
        "Nothing's changed here in ages.",
        "I'd quite like something new to look at.",
    ],
    "rest": [
        "I'm running out of steam.",
        "Getting late, isn't it.",
        "I could do with switching off for a bit.",
    ],
}

URGE_EXPRESSION = {"connect": "curious", "explore": "playful", "rest": "sleepy"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def circadian_energy(now: datetime | None = None) -> float:
    """0 at the small hours, 1 mid-afternoon, in the phone's LOCAL time.

    This only became possible once Melba/the host had a correct clock; a device
    that thinks it is permanently June cannot have a convincing day and night.
    """
    now = now or utc_now()
    local = now.astimezone()
    hour = local.hour + local.minute / 60.0
    # Trough at 04:00, peak at 16:00.
    return 0.5 - 0.45 * math.cos(2 * math.pi * (hour - 4.0) / 24.0)


def _drive_targets(elapsed_hours: float, drives: dict[str, float], energy: float):
    updated = dict(drives)
    for name, rate in DRIVE_GROWTH_PER_HOUR.items():
        current = drives.get(name, 0.5)
        # Asymptotic, not linear: a drive approaches saturation and slows as it
        # gets there, instead of pinning at the ceiling and staying there.
        updated[name] = current + rate * elapsed_hours * (1.0 - current)
    # Rest tracks the inverse of circadian energy rather than simply climbing.
    rest_target = 1.0 - energy
    gap = rest_target - drives.get("rest", 0.2)
    updated["rest"] = drives.get("rest", 0.2) + gap * min(1.0, elapsed_hours * 0.8)
    return updated


def tick(now: datetime | None = None) -> dict[str, Any]:
    """Advance Herbie's internal state. Safe to call at any interval."""
    now = now or utc_now()
    state = herbie_memory.autonomic_snapshot()
    if not state["enabled"]:
        return {"ticked": False, "reason": "disabled"}

    last_tick = parse_time(state["last_tick_at"]) or now
    elapsed_seconds = max(0.0, (now - last_tick).total_seconds())
    # A long gap means the process was stopped, not that Herbie was awake and
    # bored for a week. Cap it so a restart cannot slam every drive to maximum.
    elapsed_seconds = min(elapsed_seconds, 3600.0)
    elapsed_hours = elapsed_seconds / 3600.0
    elapsed_minutes = elapsed_seconds / 60.0

    energy = circadian_energy(now)
    drives = herbie_memory.drives_snapshot()
    herbie_memory.set_drives(_drive_targets(elapsed_hours, drives, energy))

    expression = herbie_memory.expression_snapshot()
    traits = herbie_memory.self_snapshot()["personality"]

    arousal_baseline = 0.20 + 0.55 * energy
    # Prolonged loneliness drags the mood down, so valence actually varies
    # across a day instead of sitting on one number forever.
    loneliness = max(0.0, drives.get("connect", 0.5) - 0.65)
    valence_baseline = -0.05 + 0.45 * traits.get("confidence", 0.4) - 0.55 * loneliness

    def settle(current: float, baseline: float, per_minute: float) -> float:
        # Exponential approach: never overshoots however long the gap.
        factor = 1.0 - (1.0 - per_minute) ** max(0.0, elapsed_minutes)
        return current + (baseline - current) * factor

    arousal = settle(expression["arousal"], arousal_baseline, AROUSAL_SETTLE_PER_MINUTE)
    valence = settle(expression["valence"], valence_baseline, VALENCE_SETTLE_PER_MINUTE)
    herbie_memory.set_affect(valence, arousal)

    herbie_memory.autonomic_update(last_tick_at=now.isoformat(timespec="seconds"))

    urge = _consider_urge(now, state, expression)
    return {
        "ticked": True,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "circadian_energy": round(energy, 4),
        "drives": herbie_memory.drives_snapshot(),
        "valence": round(valence, 4),
        "arousal": round(arousal, 4),
        "urge": urge,
    }


def _consider_urge(
    now: datetime, state: dict[str, Any], expression: dict[str, Any]
) -> str | None:
    """Decide whether Herbie feels like saying something unprompted."""
    # Privacy mode is a request to be left alone. Respect it.
    if expression.get("privacy_mode"):
        return None
    if state["pending_urge"]:
        return state["pending_urge"]

    # Habituation: each unanswered impulse widens the gap.
    ignored = min(state.get("unanswered_urges", 0), URGE_BACKOFF_MAX_STEPS)
    required_gap = MIN_SECONDS_BETWEEN_URGES * (URGE_BACKOFF_FACTOR ** ignored)
    last = parse_time(state["last_initiative_at"])
    if last and (now - last).total_seconds() < required_gap:
        return None

    energy = circadian_energy(now)
    drives = herbie_memory.drives_snapshot()
    candidates = [
        (name, drives.get(name, 0.0))
        for name, threshold in URGE_THRESHOLDS.items()
        if drives.get(name, 0.0) >= threshold
    ]
    if not candidates:
        return None

    if energy < NIGHT_ENERGY:
        # At night the only thing Herbie expresses is tiredness, silently.
        if drives.get("rest", 0.0) < URGE_THRESHOLDS["rest"]:
            return None
        urge = "rest"
    else:
        # Weight by time of day so tiredness can win in the evening even when
        # loneliness is numerically higher.
        def weight(pair):
            name, value = pair
            if name == "rest":
                return value * (1.6 - energy)
            return value * (0.4 + energy)

        urge = max(candidates, key=weight)[0]

    herbie_memory.autonomic_update(
        pending_urge=urge, pending_urge_at=now.isoformat(timespec="seconds")
    )
    return urge


def take_urge(now: datetime | None = None) -> dict[str, Any] | None:
    """Claim the pending urge, returning what Herbie wants to express.

    Returns expression and words only. There is no movement here and no way to
    ask for any.
    """
    now = now or utc_now()
    state = herbie_memory.autonomic_snapshot()
    urge = state["pending_urge"]
    if not urge:
        return None

    # Silent at night: the face changes, nothing is said aloud.
    silent = circadian_energy(now) < NIGHT_ENERGY

    lines = list(URGE_LINES.get(urge, ["..."]))
    previous = state.get("last_urge_line", "")
    if len(lines) > 1 and previous in lines:
        lines.remove(previous)  # never the same line twice running
    text = random.choice(lines)

    herbie_memory.autonomic_update(
        pending_urge="",
        pending_urge_at=None,
        last_initiative_at=now.isoformat(timespec="seconds"),
        unanswered_urges=state.get("unanswered_urges", 0) + 1,
        last_urge_line="" if silent else text,
    )
    return {
        "urge": urge,
        "expression": URGE_EXPRESSION.get(urge, "curious"),
        "text": "" if silent else text,
        "silent": silent,
        "spontaneous": True,
        "motor_authority": False,
        "safe_motion_state": "STOP",
    }


def note_interaction(now: datetime | None = None) -> dict[str, float]:
    """Someone engaged with Herbie: discharge the drives that satisfies."""
    now = now or utc_now()
    drives = herbie_memory.drives_snapshot()
    updated = dict(drives)
    for name, relief in INTERACTION_RELIEF.items():
        updated[name] = drives.get(name, 0.5) * (1.0 - relief)
    herbie_memory.set_drives(updated)
    # Someone answered, so Herbie stops holding back.
    herbie_memory.autonomic_update(
        last_interaction_at=now.isoformat(timespec="seconds"),
        unanswered_urges=0,
    )
    return herbie_memory.drives_snapshot()


def mood_snapshot(now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    state = herbie_memory.autonomic_snapshot()
    expression = herbie_memory.expression_snapshot()
    last_interaction = parse_time(state["last_interaction_at"])
    energy = circadian_energy(now)
    return {
        "circadian_energy": round(energy, 4),
        "local_time": now.astimezone().isoformat(timespec="seconds"),
        "valence": expression["valence"],
        "arousal": expression["arousal"],
        "expression": expression["expression"],
        "drives": herbie_memory.drives_snapshot(),
        "seconds_since_interaction": (
            None
            if last_interaction is None
            else round((now - last_interaction).total_seconds(), 1)
        ),
        "pending_urge": state["pending_urge"] or None,
        "unanswered_urges": state["unanswered_urges"],
        "asleep": energy < NIGHT_ENERGY,
        "autonomic_enabled": state["enabled"],
        "motor_authority": False,
        "safe_motion_state": "STOP",
    }


class AutonomicLoop:
    """Background ticker. Daemon thread, so it never blocks shutdown."""

    def __init__(self, interval: float = TICK_SECONDS) -> None:
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                tick()
            except Exception as exc:  # noqa: BLE001 - a bad tick must not kill the loop
                self.last_error = f"{type(exc).__name__}: {exc}"

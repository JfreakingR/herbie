"""Herbie's neck, as the brain sees it.

The neck is the old treat wheel on top of his head with a camera on it. It
turns one way only, in 22.5-degree steps, about ten seconds a step. The wheel
itself is driven from the Windows computer (the only machine with a link to
the VAVA motor board); this module is the phone's side of that arrangement:

* Any brain - cloud, computer or phone-local - asks to turn by writing a tag
  such as ``[look 90]`` in its reply. ``extract_look`` removes every such tag
  before the reply is stored or spoken and returns the last angle asked for.
* ``NeckState`` holds that one pending request until the computer's neck
  controller claims it, and remembers which way the controller last reported
  facing.
* The skill is only offered to the brains while a controller has checked in
  recently (``available``), so Herbie is never told he can look when nothing
  would happen.

It covers the neck only. The wheels stay under motor_authority, which is off.
Pure logic, no I/O: the service and the controller do the talking.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

DEGREES_PER_STEP = 22.5
CONTROLLER_TIMEOUT_S = 30.0     # no check-in for this long = no neck
REQUEST_TTL_S = 120.0           # an unclaimed wish to look goes stale

NECK_SKILL = (
    "Your wheels stay off, but you can turn your head: a camera on a wheel on "
    "top of you. It turns only one way, slowly, about ten seconds per 22.5 "
    "degrees, so a full look behind you takes over a minute. To turn it, put "
    "[look N] anywhere in your reply, where N is 0 to 359 degrees from straight "
    "ahead in the direction it turns (0 faces forward again). Use it when you "
    "actually want to see something or someone asks you to look; at most one "
    "per reply. The tag is removed before you speak, so don't read it out."
)

_LOOK = re.compile(
    r"\[\s*look\s+(-?\d{1,4})\s*(?:°|deg(?:rees)?)?\s*\]", re.IGNORECASE
)


def extract_look(text: str) -> tuple[str, int | None]:
    """Strip every [look N] tag; return the cleaned text and the last N (0-359)."""
    matches = _LOOK.findall(text)
    if not matches:
        return text, None
    cleaned = _LOOK.sub(" ", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.!?;:])", r"\1", cleaned).strip()
    return cleaned, int(matches[-1]) % 360


def facing_text(facing: float | None) -> str:
    if facing is None:
        return "Your head's direction is unknown."
    if facing == 0:
        return "Your head is facing straight ahead."
    return f"Your head is turned {facing:g} degrees from straight ahead."


class NeckState:
    """The one pending look request, and what the controller last reported."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, Any] | None = None
        self._next_id = 1
        self._facing: float | None = None
        self._busy = False
        self._last_checkin: float | None = None

    def available(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            return (self._last_checkin is not None
                    and now - self._last_checkin <= CONTROLLER_TIMEOUT_S)

    def request(self, degrees: int, now: float | None = None) -> int:
        """Queue a look; a newer wish replaces an unclaimed older one."""
        if isinstance(degrees, bool) or not isinstance(degrees, int):
            raise ValueError("invalid_degrees")
        now = time.monotonic() if now is None else now
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._pending = {"id": request_id, "degrees": degrees % 360, "at": now}
            return request_id

    def claim(self, facing: Any = None, busy: bool = False,
              now: float | None = None) -> dict[str, Any] | None:
        """The controller checks in. Hands over the pending look unless busy."""
        if facing is not None and (isinstance(facing, bool)
                                   or not isinstance(facing, (int, float))
                                   or not 0 <= facing < 360):
            raise ValueError("invalid_facing")
        if not isinstance(busy, bool):
            raise ValueError("invalid_busy")
        now = time.monotonic() if now is None else now
        with self._lock:
            self._last_checkin = now
            self._facing = facing
            self._busy = busy
            pending = self._pending
            if pending is not None and now - pending["at"] > REQUEST_TTL_S:
                self._pending = pending = None
            if busy or pending is None:
                return None
            self._pending = None
            return {"id": pending["id"], "degrees": pending["degrees"]}

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        available = self.available(now)
        with self._lock:
            return {
                "available": available,
                "facing": self._facing,
                "turning": self._busy,
                "pending": None if self._pending is None
                else {"id": self._pending["id"], "degrees": self._pending["degrees"]},
            }

    def context_line(self, now: float | None = None) -> str | None:
        """A fact for the brain's context, or None when there is no neck."""
        if not self.available(now):
            return None
        with self._lock:
            line = facing_text(self._facing)
            if self._busy:
                line += " It is turning right now."
            return line

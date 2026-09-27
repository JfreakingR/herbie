"""Herbie's tracks, as the brain sees them.

Driving works like the neck (see herbie_neck): the motor board is only
reachable from the Windows computer, so the phone keeps the wish and the
computer's controller carries it out.

* A brain asks to move by writing tags such as ``[drive forward 1]`` in its
  reply: forward, backward, left or right (left and right spin him in place),
  for 0.2 to 2 seconds each. ``extract_drive`` removes every such tag before
  the reply is stored or spoken and returns at most MAX_MOVES of them.
* ``DriveState`` hands the controller one move per check-in, so "stop" can
  drop whatever has not started yet. A single move is at most two seconds,
  and the protocol module caps it again before any byte reaches the board.
* The skill is only offered while a controller has checked in recently, and
  the controller only runs when the owner starts it with ``-Drive``.
* Only replies to a person drive him. His own urges never do (autonomic).

Pure logic, no I/O: the service and the controller do the talking.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

CONTROLLER_TIMEOUT_S = 30.0     # no check-in for this long = no driving
REQUEST_TTL_S = 20.0            # a move not started by then is dropped: stale
MAX_MOVES = 3                   # per reply
MIN_MS, MAX_MS, DEFAULT_MS = 200, 2000, 1000
DIRECTIONS = ("forward", "backward", "left", "right")

DRIVE_SKILL = (
    "You can drive on your tracks, in short bursts. Put [drive forward N], "
    "[drive backward N], [drive left N] or [drive right N] in your reply, where "
    "N is 0.2 to 2 seconds; left and right spin you on the spot. Up to three "
    "tags per reply, carried out in order, a second or two after you speak. "
    "Only drive when someone asks you to or agrees to it, and keep moves short: "
    "you can't see where you're going unless you look first. If anyone says "
    "stop, don't drive. The tags are removed before you speak, so don't read "
    "them out."
)

_DRIVE = re.compile(
    r"\[\s*drive\s+(forwards?|backwards?|back|left|right)"
    r"(?:\s+(\d{1,2}(?:\.\d+)?)\s*(?:s|secs?|seconds?)?)?\s*\]",
    re.IGNORECASE,
)
# Said by the person, these cancel anything not yet started and any new tags.
_STOP = re.compile(r"\b(stop|halt|freeze|whoa|don'?t move|stay still)\b", re.IGNORECASE)


def _direction(word: str) -> str:
    word = word.lower()
    if word.startswith("forward"):
        return "forward"
    if word.startswith("back"):
        return "backward"
    return word


def extract_drive(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Strip every [drive ...] tag; return the text and up to MAX_MOVES moves."""
    moves = []
    for word, seconds in _DRIVE.findall(text):
        ms = DEFAULT_MS if not seconds else round(float(seconds) * 1000)
        moves.append({"direction": _direction(word),
                      "ms": max(MIN_MS, min(MAX_MS, ms))})
    if not moves:
        return text, []
    cleaned = _DRIVE.sub(" ", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.!?;:])", r"\1", cleaned).strip()
    return cleaned, moves[:MAX_MOVES]


def says_stop(message: str) -> bool:
    return bool(_STOP.search(message))


class DriveState:
    """The moves waiting to be driven, and whether a controller is there."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: list[dict[str, Any]] = []
        self._next_id = 1
        self._busy = False
        self._last_checkin: float | None = None

    def available(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            return (self._last_checkin is not None
                    and now - self._last_checkin <= CONTROLLER_TIMEOUT_S)

    def request(self, moves: list[dict[str, Any]], now: float | None = None) -> int:
        """Queue a reply's moves; they replace anything not yet started."""
        if not moves or len(moves) > MAX_MOVES:
            raise ValueError("invalid_moves")
        for move in moves:
            if (move.get("direction") not in DIRECTIONS
                    or isinstance(move.get("ms"), bool)
                    or not isinstance(move.get("ms"), int)
                    or not MIN_MS <= move["ms"] <= MAX_MS):
                raise ValueError("invalid_moves")
        now = time.monotonic() if now is None else now
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._pending = [{"id": request_id, "step": i + 1,
                              "direction": m["direction"], "ms": m["ms"], "at": now}
                             for i, m in enumerate(moves)]
            return request_id

    def stop(self) -> int:
        """Drop every move not yet handed out. Returns how many were dropped."""
        with self._lock:
            dropped = len(self._pending)
            self._pending = []
            return dropped

    def claim(self, busy: bool = False, now: float | None = None) -> dict[str, Any] | None:
        """The controller checks in; hands over the next move unless busy."""
        if not isinstance(busy, bool):
            raise ValueError("invalid_busy")
        now = time.monotonic() if now is None else now
        with self._lock:
            self._last_checkin = now
            self._busy = busy
            self._pending = [m for m in self._pending if now - m["at"] <= REQUEST_TTL_S]
            if busy or not self._pending:
                return None
            move = self._pending.pop(0)
            return {"id": move["id"], "step": move["step"],
                    "direction": move["direction"], "ms": move["ms"]}

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        available = self.available(now)
        with self._lock:
            return {"available": available, "driving": self._busy,
                    "pending": [{"direction": m["direction"], "ms": m["ms"]}
                                for m in self._pending]}

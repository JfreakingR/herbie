"""Herbie's shape on the desk screen: spirit, sun, moon, football, or just a face.

Every conversation, spoken to the Galaxy or typed at the desk, reaches the
brain's /v1/chat, so the brain is where "turn into the moon" is noticed. The
current form rides along in /v1/expression, which the desk face polls.
It is display state only: it touches no motor, memory or identity.
"""

from __future__ import annotations

import re
import threading

FORMS = ("spirit", "sun", "moon", "football", "face")

_ASKS_TO_CHANGE = re.compile(
    r"\b(turn|turning|become|change|changing|shift|transform|morph|be)\b"
)
_FORM_WORDS = (
    (re.compile(r"\b(sun|sunshine)\b"), "sun"),
    (re.compile(r"\bmoon\b"), "moon"),
    (re.compile(r"\b(football|foot ball)\b"), "football"),
    (re.compile(r"\b(just|only) (a|your) face\b|\bjust (eyes|your eyes)\b"), "face"),
    (re.compile(r"\b(spirit|ghost|yourself|normal|back to you)\b"), "spirit"),
)


def requested(message: str) -> str | None:
    """The form a message asks for, or None when it asks for no change."""
    lower = str(message or "").lower()
    if not _ASKS_TO_CHANGE.search(lower):
        return None
    for pattern, form in _FORM_WORDS:
        if pattern.search(lower):
            return form
    return None


def context_line(form: str) -> str:
    if form == "spirit":
        return "On the desk screen you just returned to your usual glowing spirit form."
    shape = {"face": "just your glowing eyes and mouth"}.get(form, f"the {form}")
    return (
        f"On the desk screen you just transformed into {shape}. "
        "Say so briefly and playfully if it fits."
    )


class FormState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._form = "spirit"

    @property
    def current(self) -> str:
        with self._lock:
            return self._form

    def set(self, form: str) -> None:
        if form not in FORMS:
            raise ValueError("invalid_form")
        with self._lock:
            self._form = form

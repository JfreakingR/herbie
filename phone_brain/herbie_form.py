"""Herbie's face on the desk screen: its shape and the expression he asks for.

Shapes: spirit, sun, moon, football, or just a face.

Every conversation, spoken to the Galaxy or typed at the desk, reaches the
brain's /v1/chat, so the brain is where "turn into the moon" is noticed. The
current form rides along in /v1/expression, which the desk face polls.
It is display state only: it touches no motor, memory or identity.
"""

from __future__ import annotations

import re
import threading
import time

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


# How long after the face last asked for his expression it still counts as
# connected. The desk face polls every second.
FACE_TIMEOUT_SECONDS = 15.0

# Words people use for a face, mapped to the brain's expression names.
_EXPRESSION_WORDS = (
    (re.compile(r"\b(angry|mad|annoyed|furious|grumpy|cross)\b"), "angry"),
    (re.compile(r"\b(happy|smile|smiling|glad|joyful|cheerful)\b"), "happy"),
    (re.compile(r"\b(sad|unhappy|worried|concerned|upset)\b"), "concerned"),
    (re.compile(r"\b(surprised|shocked|amazed|astonished)\b"), "surprised"),
    (re.compile(r"\b(sleepy|tired|bored)\b"), "sleepy"),
    (re.compile(r"\b(thinking|thoughtful|puzzled|confused)\b"), "thinking"),
    (re.compile(r"\b(curious|interested)\b"), "curious"),
    (re.compile(r"\b(playful|silly|cheeky|goofy|funny)\b"), "playful"),
    (re.compile(r"\b(calm|neutral|normal|relaxed)\b"), "calm"),
)
_ASKS_FOR_FACE = re.compile(
    r"\b(make|pull|show|give|do)\b.*\bface\b|\blook\b|\bface\b"
)
_FACE_TAG = re.compile(r"\s*\[face\s+([a-z]+)\]", re.IGNORECASE)

FACE_SKILL = (
    "You have a face: a glowing spirit shown on a 7-inch screen on the desk, "
    "which people in the room can see. It shows your mood, listens when you "
    "listen and moves when you talk. To change your expression, put a tag "
    "like [face angry] anywhere in your reply; the tag is removed before "
    "anyone hears it. Expressions: calm, curious, happy, playful, thinking, "
    "surprised, concerned, sleepy, angry. You can also change shape into the "
    "sun, the moon, a football or just your eyes and mouth when asked."
)


def requested_expression(message: str) -> str | None:
    """The expression a message asks his face to make, or None."""
    lower = str(message or "").lower()
    if not _ASKS_FOR_FACE.search(lower):
        return None
    for pattern, expression in _EXPRESSION_WORDS:
        if pattern.search(lower):
            return expression
    return None


def extract_face(text: str) -> tuple[str, str | None]:
    """Remove [face NAME] tags; return the cleaned text and the last valid name."""
    found = None
    for match in _FACE_TAG.finditer(text or ""):
        name = match.group(1).lower()
        for pattern, expression in _EXPRESSION_WORDS:
            if pattern.fullmatch(name):
                found = expression
                break
        else:
            if name in ("calm", "curious", "happy", "playful", "thinking",
                        "surprised", "concerned", "sleepy", "angry"):
                found = name
    cleaned = _FACE_TAG.sub("", text or "").strip()
    return cleaned, found


def expression_line(expression: str) -> str:
    return (
        f"On the desk screen your face just changed to look {expression}, "
        "because you were asked to. Acknowledge it briefly if it fits."
    )


class FaceWatch:
    """Remembers when a desk face last checked in, so the brain knows it has one."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._seen = None

    def seen(self) -> None:
        with self._lock:
            self._seen = self._clock()

    def connected(self) -> bool:
        with self._lock:
            return self._seen is not None and self._clock() - self._seen < FACE_TIMEOUT_SECONDS

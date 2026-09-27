"""Herbie's sight, as the brain sees it.

The Galaxy's back camera is Herbie's eye. The Herbie app on the phone owns it
(`HerbieEyes.kt`), because Android only lets a foreground service use the
camera; this module asks that app for one still over its loopback bridge
(`POST /v1/see`) and hands it to the cloud brain, the one that can read images.

* A brain asks to look by writing ``[see]`` in its reply. ``extract_see``
  removes every such tag before the reply is stored or spoken.
* Photos are never written anywhere: the JPEG lives in memory for one request.
* No photo is taken in privacy mode or with the camera switched off - the
  caller checks, and ``look_now`` checks again.
"""

from __future__ import annotations

import base64
import re
from typing import Any

import herbie_chat
import herbie_memory

CAPTURE_TIMEOUT_S = 20.0
MAX_JPEG_BYTES = 3_500_000      # base64 of this stays under the image API limit

EYES_SKILL = (
    "You can see through the camera on your head. To look, put [see] anywhere "
    "in your reply, for example 'Let me have a look. [see]'. A photo is taken "
    "and you describe it straight after; if you also turn with [look N], the "
    "photo waits until you have finished turning. Use it when someone asks what "
    "you can see, or asks you to look at something; at most one per reply. "
    "Only describe what is actually in a photo you were given."
)
NO_SIGHT = (
    "You cannot see right now - no picture reaches you - so never describe what "
    "you would see or claim to have seen anything."
)
SEEN_PROMPT = (
    "This is the photo you just took with your own camera{where}. Answer what "
    "was asked, from what is really in the picture, briefly and in your own "
    "voice. If it is too dark or blurry to tell, say so. Asked: {question}"
)

_SEE = re.compile(r"\[\s*see\s*\]", re.IGNORECASE)


class EyesUnavailable(RuntimeError):
    """No photo: camera off, privacy mode, or the app could not take one."""


def extract_see(text: str) -> tuple[str, bool]:
    """Strip every [see] tag; say whether there was one."""
    if not _SEE.search(text):
        return text, False
    cleaned = _SEE.sub(" ", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.!?;:])", r"\1", cleaned).strip()
    return cleaned, True


def camera_permitted() -> bool:
    """The owner's switches: privacy mode off and the camera allowed."""
    state = herbie_memory.privacy_snapshot()
    return not state.get("privacy_mode") and bool(state.get("camera_allowed"))


def look_now(timeout: float = CAPTURE_TIMEOUT_S) -> bytes:
    """One JPEG from the Herbie app's camera. Never stored."""
    if not camera_permitted():
        raise EyesUnavailable("camera_not_permitted")
    try:
        result: Any = herbie_chat.post_bridge_voice("/v1/see", {}, timeout)
    except herbie_chat.ChatUnavailable as exc:
        raise EyesUnavailable(f"camera_unavailable: {exc}") from exc
    encoded = result.get("jpeg_base64") if isinstance(result, dict) else None
    if not isinstance(encoded, str) or not encoded:
        raise EyesUnavailable(str(result.get("error") or "camera_returned_no_image"))
    try:
        jpeg = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise EyesUnavailable("camera_returned_bad_image") from exc
    if not jpeg.startswith(b"\xff\xd8") or len(jpeg) > MAX_JPEG_BYTES:
        raise EyesUnavailable("camera_returned_bad_image")
    return jpeg


def seen_prompt(question: str, facing: float | None = None) -> str:
    where = "" if facing is None else f", turned {facing:g} degrees from straight ahead"
    return SEEN_PROMPT.format(where=where, question=question.strip()[:1000])

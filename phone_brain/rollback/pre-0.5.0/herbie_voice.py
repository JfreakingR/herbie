"""Free local speech output for Herbie through Android's installed TTS engine."""

from __future__ import annotations

import shutil
import subprocess
import threading
from typing import Any

import herbie_memory


MAX_SPEECH_TEXT = 1000
VOICE_LOCK = threading.Lock()


def _speak_worker(text: str, pitch: float, rate: float, expression: str) -> None:
    with VOICE_LOCK:
        herbie_memory.set_expression(
            {"expression": expression, "speaking": True, "listening": False}
        )
        try:
            subprocess.run(
                [
                    "termux-tts-speak",
                    "-s",
                    "MUSIC",
                    "-l",
                    "en",
                    "-n",
                    "US",
                    "-p",
                    str(pitch),
                    "-r",
                    str(rate),
                    text,
                ],
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            herbie_memory.set_expression({"expression": expression, "speaking": False})


def speak(request: dict[str, Any]) -> dict[str, Any]:
    text = request.get("text")
    pitch = request.get("pitch", 0.9)
    rate = request.get("rate", 0.92)
    expression = request.get("expression", "calm")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_SPEECH_TEXT:
        raise ValueError("invalid_speech_text")
    if not isinstance(pitch, (int, float)) or not 0.5 <= float(pitch) <= 2:
        raise ValueError("invalid_pitch")
    if not isinstance(rate, (int, float)) or not 0.5 <= float(rate) <= 2:
        raise ValueError("invalid_rate")
    if expression not in herbie_memory.EXPRESSIONS:
        raise ValueError("invalid_expression")
    if shutil.which("termux-tts-speak") is None:
        raise RuntimeError("tts_unavailable")
    thread = threading.Thread(
        target=_speak_worker,
        args=(text.strip(), float(pitch), float(rate), expression),
        daemon=True,
    )
    thread.start()
    return {"queued": True, "expression": expression, "local_only": True}

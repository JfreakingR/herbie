"""Herbie's voice: free, local, and shaped by how he currently feels.

Speech goes through Android's own TTS engine via `termux-tts-speak`. That is
already on the phone, costs nothing, needs no account, and never leaves the
device. No API key exists anywhere in this project and none is required.

What makes a voice sound alive is not fidelity, it is variation:

* **Prosody follows mood.** Pitch tracks valence, rate tracks arousal, and a
  small random jitter means no two utterances are acoustically identical. A
  voice that says everything at exactly the same pitch and speed is the most
  machine-like thing a talking device can do.
* **A beat before answering.** Instant replies feel like a lookup table. The
  pause is longer when Herbie is calm, shorter when he is alert.
* **Occasional imperfection.** A filler, or trailing off — rarely. Flawlessness
  reads as machine. Kept infrequent on purpose: overused disfluency is far worse
  than none at all.
* **He can be interrupted.** A creature you cannot tell to be quiet is an
  appliance.

The shaping functions are pure and take an injectable RNG, so all of this is
testable without a speaker.
"""

from __future__ import annotations

import random
import shutil
import subprocess
import threading
import time
from typing import Any

import herbie_memory


MAX_SPEECH_TEXT = 1000
VOICE_LOCK = threading.Lock()

# Bounds for termux-tts-speak. Staying inside them keeps Herbie recognisably
# himself however extreme the mood gets.
PITCH_RANGE = (0.78, 1.12)
RATE_RANGE = (0.74, 1.16)
JITTER = 0.028

# How long he appears to think before speaking, in seconds.
LATENCY_RANGE = (0.18, 1.15)

# Chance of a filler or a trailing off. Deliberately low.
DISFLUENCY_CHANCE = 0.16

OPENERS = ["Hm.", "Well.", "Right.", "Ah."]
TRAILERS = ["...", ", I suppose.", ", anyway."]

# The process currently speaking, so that it can be stopped.
_CURRENT: Any = None
_CURRENT_LOCK = threading.Lock()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def voice_params(
    valence: float | None = None,
    arousal: float | None = None,
    rng: random.Random | None = None,
) -> dict[str, float]:
    """Derive pitch, rate and pre-speech latency from mood.

    Reads live mood when not given explicitly, so an ordinary call to speak()
    automatically sounds like however Herbie currently is.
    """
    if valence is None or arousal is None:
        state = herbie_memory.expression_snapshot()
        valence = state["valence"] if valence is None else valence
        arousal = state["arousal"] if arousal is None else arousal

    rng = rng or random
    valence = _clamp(float(valence), -1.0, 1.0)
    arousal = _clamp(float(arousal), 0.0, 1.0)

    # Low mood speaks lower; high arousal speaks faster.
    pitch_span = PITCH_RANGE[1] - PITCH_RANGE[0]
    rate_span = RATE_RANGE[1] - RATE_RANGE[0]
    pitch = PITCH_RANGE[0] + pitch_span * ((valence + 1.0) / 2.0)
    rate = RATE_RANGE[0] + rate_span * arousal

    # Jitter is the difference between a voice and a recording.
    pitch = _clamp(pitch + rng.uniform(-JITTER, JITTER), *PITCH_RANGE)
    rate = _clamp(rate + rng.uniform(-JITTER, JITTER), *RATE_RANGE)

    # Calm means an unhurried beat before answering; alert means a quick one.
    low, high = LATENCY_RANGE
    latency = high - (high - low) * arousal
    latency = _clamp(latency * rng.uniform(0.75, 1.25), low * 0.6, high * 1.3)

    return {
        "pitch": round(pitch, 3),
        "rate": round(rate, 3),
        "latency_seconds": round(latency, 3),
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
    }


def add_imperfection(
    text: str, arousal: float = 0.5, rng: random.Random | None = None
) -> str:
    """Occasionally rough the edges. Never changes what was actually said."""
    rng = rng or random
    if rng.random() > DISFLUENCY_CHANCE:
        return text

    # Hesitation belongs to low arousal; trailing off suits either.
    if arousal < 0.45 and rng.random() < 0.6:
        return f"{rng.choice(OPENERS)} {text}"

    stripped = text.rstrip()
    if stripped.endswith((".", "!", "?")):
        stripped = stripped[:-1]
    return f"{stripped}{rng.choice(TRAILERS)}"


def stop() -> dict[str, Any]:
    """Interrupt whatever Herbie is currently saying."""
    stopped = False
    with _CURRENT_LOCK:
        process = _CURRENT
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                stopped = True
            except OSError:
                pass
    try:
        herbie_memory.set_expression({"speaking": False})
    except ValueError:
        pass
    return {"stopped": stopped, "motor_authority": False, "safe_motion_state": "STOP"}


def _speak_worker(
    text: str, pitch: float, rate: float, expression: str, latency: float
) -> None:
    global _CURRENT
    with VOICE_LOCK:
        # The pause happens before the face changes, so the beat looks like
        # consideration rather than lag.
        if latency > 0:
            time.sleep(latency)
        try:
            herbie_memory.set_expression(
                {"expression": expression, "speaking": True, "listening": False}
            )
        except ValueError:
            pass
        try:
            process = subprocess.Popen(
                [
                    "termux-tts-speak",
                    "-s", "MUSIC",
                    "-l", "en",
                    "-n", "US",
                    "-p", str(pitch),
                    "-r", str(rate),
                    text,
                ]
            )
            with _CURRENT_LOCK:
                _CURRENT = process
            process.wait(timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            with _CURRENT_LOCK:
                _CURRENT = None
            try:
                herbie_memory.set_expression(
                    {"expression": expression, "speaking": False}
                )
            except ValueError:
                pass


def speak(request: dict[str, Any]) -> dict[str, Any]:
    text = request.get("text")
    expression = request.get("expression", "calm")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_SPEECH_TEXT:
        raise ValueError("invalid_speech_text")
    if expression not in herbie_memory.EXPRESSIONS:
        raise ValueError("invalid_expression")

    natural = request.get("natural", True)
    if not isinstance(natural, bool):
        raise ValueError("invalid_natural")

    params = voice_params()

    # An explicit pitch/rate still wins, so a caller can override the mood.
    pitch = request.get("pitch", params["pitch"])
    rate = request.get("rate", params["rate"])
    if not isinstance(pitch, (int, float)) or not 0.5 <= float(pitch) <= 2:
        raise ValueError("invalid_pitch")
    if not isinstance(rate, (int, float)) or not 0.5 <= float(rate) <= 2:
        raise ValueError("invalid_rate")

    spoken = text.strip()
    latency = 0.0
    if natural:
        spoken = add_imperfection(spoken, params["arousal"])
        latency = params["latency_seconds"]

    if shutil.which("termux-tts-speak") is None:
        raise RuntimeError("tts_unavailable")

    threading.Thread(
        target=_speak_worker,
        args=(spoken, float(pitch), float(rate), expression, latency),
        daemon=True,
    ).start()

    return {
        "queued": True,
        "expression": expression,
        "pitch": round(float(pitch), 3),
        "rate": round(float(rate), 3),
        "latency_seconds": round(latency, 3),
        "local_only": True,
        "cost": "none",
    }

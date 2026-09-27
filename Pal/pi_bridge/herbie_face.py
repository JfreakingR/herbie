"""Render Herbie's validated expression state as an SVG face.

This module does not talk to displays, install drivers, or command motors.
It only turns the same expression schema the Galaxy brain stores into a
picture that a later, identified screen can show.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


IDENTITY_NAME = "Herbie"
EXPRESSIONS = {
    "calm",
    "curious",
    "happy",
    "playful",
    "thinking",
    "surprised",
    "concerned",
    "sleepy",
}

DEFAULT_STATE: dict[str, Any] = {
    "expression": "curious",
    "valence": 0.3,
    "arousal": 0.45,
    "attention": "",
    "listening": False,
    "speaking": False,
    "privacy_mode": False,
    "camera_allowed": True,
    "microphone_allowed": True,
    "camera_active": False,
    "updated_at": None,
}

# Eye height, pupil offset, mouth kind, and brow tilt for each named face.
FACE_SHAPES = {
    "calm": {"eye_h": 18, "pupil_x": 0, "pupil_y": 4, "mouth": "smile", "mouth_w": 42, "brow": 0},
    "curious": {"eye_h": 28, "pupil_x": 8, "pupil_y": -6, "mouth": "oh", "mouth_w": 18, "brow": -8},
    "happy": {"eye_h": 14, "pupil_x": 0, "pupil_y": 2, "mouth": "grin", "mouth_w": 58, "brow": 4},
    "playful": {"eye_h": 24, "pupil_x": 6, "pupil_y": 0, "mouth": "grin", "mouth_w": 50, "brow": 10, "wink": True},
    "thinking": {"eye_h": 20, "pupil_x": 0, "pupil_y": -10, "mouth": "flat", "mouth_w": 28, "brow": -4},
    "surprised": {"eye_h": 34, "pupil_x": 0, "pupil_y": 0, "mouth": "oh", "mouth_w": 26, "brow": -12},
    "concerned": {"eye_h": 22, "pupil_x": 0, "pupil_y": 6, "mouth": "frown", "mouth_w": 36, "brow": 10},
    "sleepy": {"eye_h": 8, "pupil_x": 0, "pupil_y": 6, "mouth": "flat", "mouth_w": 22, "brow": 6},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _require_bool(value: Any, error: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(error)
    return value


def merge_expression(current: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    state = dict(DEFAULT_STATE)
    state.update(current)
    expression = request.get("expression", state["expression"])
    valence = request.get("valence", state["valence"])
    arousal = request.get("arousal", state["arousal"])
    attention = request.get("attention", state["attention"])
    listening = request.get("listening", state["listening"])
    speaking = request.get("speaking", state["speaking"])
    privacy_mode = request.get("privacy_mode", state["privacy_mode"])
    camera_allowed = request.get("camera_allowed", state["camera_allowed"])
    microphone_allowed = request.get("microphone_allowed", state["microphone_allowed"])
    camera_active = request.get("camera_active", state["camera_active"])
    if expression not in EXPRESSIONS:
        raise ValueError("invalid_expression")
    if not isinstance(valence, (int, float)) or not -1 <= float(valence) <= 1:
        raise ValueError("invalid_valence")
    if not isinstance(arousal, (int, float)) or not 0 <= float(arousal) <= 1:
        raise ValueError("invalid_arousal")
    if not isinstance(attention, str) or len(attention) > 120:
        raise ValueError("invalid_attention")
    listening = _require_bool(listening, "invalid_activity_state")
    speaking = _require_bool(speaking, "invalid_activity_state")
    privacy_mode = _require_bool(privacy_mode, "invalid_privacy_mode")
    camera_allowed = _require_bool(camera_allowed, "invalid_camera_allowed")
    microphone_allowed = _require_bool(microphone_allowed, "invalid_microphone_allowed")
    camera_active = _require_bool(camera_active, "invalid_camera_active")
    if privacy_mode:
        camera_allowed = False
        microphone_allowed = False
        if listening or camera_active:
            raise ValueError("privacy_blocks_senses")
        if attention == "":
            attention = "privacy"
    if not camera_allowed:
        camera_active = False
    if not microphone_allowed:
        listening = False
    state.update(
        {
            "expression": expression,
            "valence": round(float(valence), 4),
            "arousal": round(float(arousal), 4),
            "attention": attention,
            "listening": listening,
            "speaking": speaking,
            "privacy_mode": privacy_mode,
            "camera_allowed": camera_allowed,
            "microphone_allowed": microphone_allowed,
            "camera_active": camera_active,
            "updated_at": utc_now(),
        }
    )
    return state


def set_privacy(current: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    privacy_mode = request.get("privacy_mode")
    if not isinstance(privacy_mode, bool):
        raise ValueError("invalid_privacy_mode")
    update: dict[str, Any] = {
        "privacy_mode": privacy_mode,
        "camera_allowed": not privacy_mode,
        "microphone_allowed": not privacy_mode,
        "camera_active": False,
        "listening": False,
    }
    if privacy_mode:
        update["attention"] = "privacy"
        update["expression"] = "calm"
    elif current.get("attention") == "privacy":
        update["attention"] = ""
    return merge_expression(current, update)


def _mouth_path(kind: str, width: int) -> str:
    left = 240 - width
    right = 240 + width
    if kind == "grin":
        return f"M {left} 198 Q 240 238 {right} 198"
    if kind == "smile":
        return f"M {left} 202 Q 240 222 {right} 202"
    if kind == "frown":
        return f"M {left} 214 Q 240 194 {right} 214"
    if kind == "oh":
        return f"M 240 198 m -{max(8, width // 3)} 0 a {max(8, width // 3)} {max(10, width // 2)} 0 1 0 {2 * max(8, width // 3)} 0 a {max(8, width // 3)} {max(10, width // 2)} 0 1 0 -{2 * max(8, width // 3)} 0"
    return f"M {left} 206 L {right} 206"


def _indicator(x: int, label: str, active: bool, blocked: bool, active_color: str) -> str:
    if blocked:
        fill = "#3a2430"
        stroke = "#c45c6a"
        mark = f'<path d="M {x + 14} 286 L {x + 34} 306 M {x + 34} 286 L {x + 14} 306" stroke="#c45c6a" stroke-width="3" fill="none"/>'
    elif active:
        fill = active_color
        stroke = "#f4f0e6"
        mark = ""
    else:
        fill = "#243044"
        stroke = "#7d8ba0"
        mark = ""
    return (
        f'<rect x="{x}" y="278" width="88" height="34" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        f'<text x="{x + 44}" y="300" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="13" font-weight="700" fill="#f4f0e6">{label}</text>'
        f"{mark}"
    )


def render_svg(state: dict[str, Any]) -> str:
    expression = state.get("expression", "curious")
    if expression not in FACE_SHAPES:
        expression = "curious"
    shape = FACE_SHAPES[expression]
    privacy = bool(state.get("privacy_mode"))
    listening = bool(state.get("listening"))
    speaking = bool(state.get("speaking"))
    camera_active = bool(state.get("camera_active"))
    camera_allowed = bool(state.get("camera_allowed", True))
    microphone_allowed = bool(state.get("microphone_allowed", True))
    attention = xml_escape(str(state.get("attention") or ""))
    head_fill = "#8a93a3" if privacy else "#f0c27a"
    panel_fill = "#10161f" if privacy else "#151c2e"
    glow = "#5aa7c8" if listening else "#2a3348"
    eye_h = int(shape["eye_h"])
    pupil_x = int(shape["pupil_x"])
    pupil_y = int(shape["pupil_y"])
    brow = int(shape["brow"])
    wink = bool(shape.get("wink"))
    left_eye = (
        f'<line x1="156" y1="148" x2="204" y2="148" stroke="#2a1d12" stroke-width="7" stroke-linecap="round"/>'
        if wink
        else (
            f'<ellipse cx="180" cy="150" rx="28" ry="{eye_h}" fill="#f7f3ea" stroke="#2a1d12" stroke-width="4"/>'
            f'<circle cx="{180 + pupil_x}" cy="{150 + pupil_y}" r="9" fill="#1b2433"/>'
        )
    )
    right_eye = (
        f'<ellipse cx="300" cy="150" rx="28" ry="{eye_h}" fill="#f7f3ea" stroke="#2a1d12" stroke-width="4"/>'
        f'<circle cx="{300 + pupil_x}" cy="{150 + pupil_y}" r="9" fill="#1b2433"/>'
    )
    mouth = _mouth_path(str(shape["mouth"]), int(shape["mouth_w"]))
    speak_ring = (
        '<ellipse cx="240" cy="206" rx="78" ry="34" fill="none" stroke="#e7b45a" stroke-width="3" opacity="0.85"/>'
        if speaking
        else ""
    )
    caption = attention if attention else expression
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320" role="img" aria-label="{xml_escape(IDENTITY_NAME)} {xml_escape(expression)}">
  <rect width="480" height="320" fill="{panel_fill}"/>
  <rect x="18" y="16" width="444" height="288" rx="28" fill="#1c2538" stroke="{glow}" stroke-width="6"/>
  <circle cx="240" cy="148" r="108" fill="{head_fill}" stroke="#2a1d12" stroke-width="6"/>
  <path d="M 160 {118 + brow} Q 180 {108 + brow} 200 {118 + brow}" stroke="#2a1d12" stroke-width="6" fill="none" stroke-linecap="round"/>
  <path d="M 280 {118 + brow} Q 300 {108 + brow} 320 {118 + brow}" stroke="#2a1d12" stroke-width="6" fill="none" stroke-linecap="round"/>
  {left_eye}
  {right_eye}
  {speak_ring}
  <path d="{mouth}" stroke="#2a1d12" stroke-width="7" fill="none" stroke-linecap="round"/>
  <text x="240" y="54" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="22" font-weight="700" fill="#f4f0e6">{xml_escape(IDENTITY_NAME)}</text>
  <text x="240" y="268" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="14" fill="#c9d3e0">{caption}</text>
  {_indicator(24, "CAM", camera_active, privacy or not camera_allowed, "#c45c6a")}
  {_indicator(122, "MIC", listening, privacy or not microphone_allowed, "#5aa7c8")}
  {_indicator(220, "TALK", speaking, False, "#e7b45a")}
  {_indicator(368, "PRIV", privacy, False, "#8a93a3")}
</svg>
"""


def render_html(state: dict[str, Any]) -> str:
    svg = render_svg(state)
    title = xml_escape(f"{IDENTITY_NAME} face")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="1"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    html, body {{ margin: 0; background: #0b1020; height: 100%; }}
    body {{ display: flex; align-items: center; justify-content: center; }}
    svg {{ width: 100vw; height: 100vh; }}
  </style>
</head>
<body>
{svg}
</body>
</html>
"""

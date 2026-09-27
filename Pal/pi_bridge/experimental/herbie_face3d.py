"""A dimensional, glossy face for Herbie.

Drop-in alternative to `herbie_face.render_svg`: same validated state in, SVG
out. The difference is purely presentational — volume from radial gradients,
wet-looking eyes with real speculars, a mouth with interior depth, and rim
light along the silhouette.

Chosen over real-time 3D deliberately. A Pi 3B's VideoCore IV would labour to
run WebGL at a sensible frame rate, and pre-rendered frames cannot blend
continuously from valence/arousal the way the autonomic layer needs. Everything
here is plain SVG: no GPU, no dependencies, no build step.

The design is original. It is not a rendering of any existing character.
"""

from __future__ import annotations

import math
from typing import Any

import herbie_face


IDENTITY_NAME = herbie_face.IDENTITY_NAME
EXPRESSIONS = herbie_face.EXPRESSIONS
DEFAULT_STATE = herbie_face.DEFAULT_STATE
merge_expression = herbie_face.merge_expression
set_privacy = herbie_face.set_privacy
xml_escape = herbie_face.xml_escape

WIDTH, HEIGHT = 480, 400

# Per-expression geometry. Values are deliberately exaggerated: a face read
# from across a room needs more shape than a naturalistic one.
SHAPES: dict[str, dict[str, Any]] = {
    "calm":      {"lid": 0.30, "brow": -2, "brow_y": 0,  "gaze": (0, 2),   "mouth": "smile",  "open": 0.22, "wide": 0.78},
    "curious":   {"lid": 0.05, "brow": -13, "brow_y": -8, "gaze": (10, -5), "mouth": "small",  "open": 0.34, "wide": 0.40},
    "happy":     {"lid": 0.42, "brow": -6, "brow_y": -5, "gaze": (0, 0),   "mouth": "grin",   "open": 0.62, "wide": 1.00},
    "playful":   {"lid": 0.20, "brow": -9, "brow_y": -6, "gaze": (12, -2), "mouth": "grin",   "open": 0.50, "wide": 0.92, "wink": True},
    "thinking":  {"lid": 0.34, "brow": -7, "brow_y": -3, "gaze": (-11, -9), "mouth": "flat",  "open": 0.14, "wide": 0.52},
    "surprised": {"lid": 0.00, "brow": -20, "brow_y": -14, "gaze": (0, 0),  "mouth": "small", "open": 0.72, "wide": 0.46},
    "concerned": {"lid": 0.26, "brow": 14, "brow_y": 4,  "gaze": (0, 5),   "mouth": "frown",  "open": 0.20, "wide": 0.66},
    "sleepy":    {"lid": 0.82, "brow": 6,  "brow_y": 6,  "gaze": (0, 7),   "mouth": "flat",   "open": 0.10, "wide": 0.42},
}

# Hue shifts with mood: warmer when content, cooler and greyer when low.
SKIN_WARM = (232, 96, 186)
SKIN_COOL = (150, 112, 196)


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _rgb(c):
    return "#%02x%02x%02x" % c


def _shade(c, factor):
    return _rgb(tuple(max(0, min(255, round(v * factor))) for v in c))


def _eye(cx, cy, shape, gaze, closed_extra=0.0):
    """One glossy eye. Lids are drawn as overlays so blinking is a lid change."""
    rx, ry = 46.0, 52.0
    lid = min(1.0, shape["lid"] + closed_extra)
    gx, gy = gaze
    pupil_r = 20.0
    iris_r = 30.0

    parts = [
        # Socket shadow gives the eye somewhere to sit.
        f'<ellipse cx="{cx}" cy="{cy + 3}" rx="{rx + 7}" ry="{ry + 7}" '
        f'fill="url(#socket)" opacity="0.55"/>',
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#sclera)"/>',
        # Iris and pupil track the gaze.
        f'<circle cx="{cx + gx}" cy="{cy + gy}" r="{iris_r}" fill="url(#iris)"/>',
        f'<circle cx="{cx + gx}" cy="{cy + gy}" r="{pupil_r}" fill="#0b0710"/>',
        # Two speculars: a hard one and a soft one. This is what reads as "wet".
        f'<ellipse cx="{cx + gx - 10}" cy="{cy + gy - 13}" rx="8.5" ry="10" '
        f'fill="#ffffff" opacity="0.95"/>',
        f'<circle cx="{cx + gx + 11}" cy="{cy + gy + 10}" r="4.5" '
        f'fill="#ffffff" opacity="0.45"/>',
        # Contact shadow under the upper lid.
        f'<ellipse cx="{cx}" cy="{cy - ry * 0.5}" rx="{rx * 0.92}" ry="{ry * 0.42}" '
        f'fill="url(#lidshadow)" opacity="0.5"/>',
    ]

    if lid > 0.01:
        drop = ry * 2 * lid
        parts.append(
            f'<path d="M {cx - rx - 2} {cy - ry - 2} H {cx + rx + 2} '
            f'V {cy - ry + drop} Q {cx} {cy - ry + drop + 14} {cx - rx - 2} {cy - ry + drop} Z" '
            f'fill="url(#skin)"/>'
        )
        parts.append(
            f'<path d="M {cx - rx - 2} {cy - ry + drop} Q {cx} {cy - ry + drop + 14} '
            f'{cx + rx + 2} {cy - ry + drop}" fill="none" stroke="#3a1030" '
            f'stroke-width="4" stroke-linecap="round" opacity="0.75"/>'
        )

    parts.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" '
        f'stroke="#3a1030" stroke-width="3" opacity="0.35"/>'
    )
    return "".join(parts)


def _brow(cx, cy, angle, lift):
    w, h = 62.0, 15.0
    y = cy - 74 + lift
    return (
        f'<g transform="rotate({angle} {cx} {y})">'
        f'<rect x="{cx - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="{h / 2}" '
        f'fill="url(#brow)"/>'
        f'<rect x="{cx - w / 2}" y="{y - h / 2}" width="{w}" height="{h * 0.42}" rx="{h / 2}" '
        f'fill="#ffffff" opacity="0.13"/>'
        f"</g>"
    )


def _mouth(cx, cy, shape, skin):
    kind = shape["mouth"]
    open_amount = shape["open"]
    wide = shape["wide"]
    half = 118.0 * wide
    depth = 96.0 * open_amount

    if kind == "flat":
        return (
            f'<path d="M {cx - half * 0.7} {cy} H {cx + half * 0.7}" fill="none" '
            f'stroke="{_shade(skin, 0.42)}" stroke-width="11" stroke-linecap="round"/>'
        )

    if kind == "frown":
        return (
            f'<path d="M {cx - half * 0.8} {cy + 26} Q {cx} {cy - 20} '
            f'{cx + half * 0.8} {cy + 26}" fill="none" stroke="{_shade(skin, 0.42)}" '
            f'stroke-width="12" stroke-linecap="round"/>'
        )

    if kind == "small":
        rx, ry = 34.0 * max(0.5, wide), max(16.0, depth * 0.62)
        return (
            f'<ellipse cx="{cx}" cy="{cy + 6}" rx="{rx}" ry="{ry}" fill="url(#maw)"/>'
            f'<ellipse cx="{cx}" cy="{cy + 6 + ry * 0.45}" rx="{rx * 0.72}" ry="{ry * 0.45}" '
            f'fill="#c8446b" opacity="0.85"/>'
            f'<ellipse cx="{cx}" cy="{cy + 6}" rx="{rx}" ry="{ry}" fill="none" '
            f'stroke="{_shade(skin, 0.45)}" stroke-width="5" opacity="0.6"/>'
        )

    # smile / grin: an open curve with interior depth, teeth and tongue.
    lip = cy - 6
    bottom = lip + depth
    outline = (
        f"M {cx - half} {lip} "
        f"Q {cx} {lip - 26} {cx + half} {lip} "
        f"Q {cx} {bottom} {cx - half} {lip} Z"
    )
    parts = [f'<path d="{outline}" fill="url(#maw)"/>']

    if open_amount > 0.28:
        # Upper teeth follow the lip line.
        parts.append(
            f'<path d="M {cx - half * 0.93} {lip + 2} Q {cx} {lip - 20} '
            f'{cx + half * 0.93} {lip + 2} Q {cx} {lip + 30} {cx - half * 0.93} {lip + 2} Z" '
            f'fill="url(#teeth)"/>'
        )
        # Tongue sits low in the mouth.
        parts.append(
            f'<ellipse cx="{cx}" cy="{bottom - depth * 0.30}" rx="{half * 0.50}" '
            f'ry="{depth * 0.30}" fill="#d2496f"/>'
            f'<ellipse cx="{cx}" cy="{bottom - depth * 0.36}" rx="{half * 0.30}" '
            f'ry="{depth * 0.14}" fill="#ffffff" opacity="0.18"/>'
        )

    parts.append(
        f'<path d="{outline}" fill="none" stroke="{_shade(skin, 0.40)}" '
        f'stroke-width="6" stroke-linejoin="round" opacity="0.75"/>'
    )
    return "".join(parts)


def render_svg(state: dict[str, Any]) -> str:
    expression = state.get("expression", "curious")
    if expression not in EXPRESSIONS:
        raise ValueError("invalid_expression")
    shape = SHAPES[expression]

    valence = float(state.get("valence", 0.0))
    arousal = float(state.get("arousal", 0.5))
    listening = bool(state.get("listening"))
    speaking = bool(state.get("speaking"))
    privacy = bool(state.get("privacy_mode"))

    skin = _mix(SKIN_COOL, SKIN_WARM, (valence + 1.0) / 2.0)
    light = _shade(skin, 1.22)
    dark = _shade(skin, 0.52)

    cx, cy = WIDTH / 2, HEIGHT / 2
    eye_y = cy - 44
    eye_dx = 96

    # Arousal widens the eyes a little; it is a subtle but strong "alive" cue.
    lid_relief = -0.12 * (arousal - 0.5)
    left_shape = dict(shape)
    right_shape = dict(shape)
    left_shape["lid"] = max(0.0, shape["lid"] + lid_relief)
    right_shape["lid"] = max(0.0, shape["lid"] + lid_relief)
    if shape.get("wink"):
        right_shape["lid"] = 0.92

    mouth_shape = dict(shape)
    if speaking:
        mouth_shape["open"] = min(1.0, shape["open"] + 0.25)

    badges = []
    if listening:
        badges.append(
            f'<g transform="translate({WIDTH - 74} 30)">'
            f'<rect x="-30" y="-16" width="60" height="32" rx="16" fill="#0d1b24" '
            f'stroke="#5aa7c8" stroke-width="2"/>'
            f'<text x="0" y="6" font-family="monospace" font-size="15" fill="#5aa7c8" '
            f'text-anchor="middle">MIC</text></g>'
        )
    if privacy:
        badges.append(
            f'<g transform="translate(74 30)">'
            f'<rect x="-34" y="-16" width="68" height="32" rx="16" fill="#241018" '
            f'stroke="#d2738f" stroke-width="2"/>'
            f'<text x="0" y="6" font-family="monospace" font-size="15" fill="#d2738f" '
            f'text-anchor="middle">PRIV</text></g>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}"
     role="img" aria-label="{xml_escape(IDENTITY_NAME)} looking {xml_escape(expression)}">
  <defs>
    <radialGradient id="skin" cx="36%" cy="26%" r="82%">
      <stop offset="0%" stop-color="{light}"/>
      <stop offset="58%" stop-color="{_rgb(skin)}"/>
      <stop offset="100%" stop-color="{dark}"/>
    </radialGradient>
    <radialGradient id="sclera" cx="38%" cy="30%" r="78%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="72%" stop-color="#f3e9f2"/>
      <stop offset="100%" stop-color="#cbb6c8"/>
    </radialGradient>
    <radialGradient id="iris" cx="40%" cy="32%" r="72%">
      <stop offset="0%" stop-color="#6b4a2f"/>
      <stop offset="70%" stop-color="#33200f"/>
      <stop offset="100%" stop-color="#150c05"/>
    </radialGradient>
    <radialGradient id="socket" cx="50%" cy="50%" r="50%">
      <stop offset="60%" stop-color="{dark}" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="{dark}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="lidshadow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#2a0c22" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#2a0c22" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="brow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#5a2148"/>
      <stop offset="100%" stop-color="#2a0c22"/>
    </linearGradient>
    <radialGradient id="maw" cx="50%" cy="22%" r="88%">
      <stop offset="0%" stop-color="#71182f"/>
      <stop offset="100%" stop-color="#2d0512"/>
    </radialGradient>
    <linearGradient id="teeth" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#dcc9d6"/>
    </linearGradient>
    <filter id="soften" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="9"/>
    </filter>
  </defs>

  <rect width="{WIDTH}" height="{HEIGHT}" fill="#120a12"/>

  <ellipse cx="{cx}" cy="{cy + 22}" rx="205" ry="178" fill="#000000"
           opacity="0.55" filter="url(#soften)"/>
  <ellipse cx="{cx}" cy="{cy}" rx="200" ry="172" fill="url(#skin)"/>
  <ellipse cx="{cx - 52}" cy="{cy - 78}" rx="92" ry="58" fill="#ffffff"
           opacity="0.13" filter="url(#soften)"/>
  <path d="M {cx - 196} {cy + 42} A 200 172 0 0 0 {cx + 196} {cy + 42}"
        fill="none" stroke="#ffd9f0" stroke-width="7" opacity="0.20"
        filter="url(#soften)"/>

  {_brow(cx - eye_dx, eye_y, shape["brow"], shape["brow_y"])}
  {_brow(cx + eye_dx, eye_y, -shape["brow"], shape["brow_y"])}
  {_eye(cx - eye_dx, eye_y, left_shape, shape["gaze"])}
  {_eye(cx + eye_dx, eye_y, right_shape, shape["gaze"])}
  {_mouth(cx, cy + 96, mouth_shape, skin)}

  {"".join(badges)}
</svg>"""

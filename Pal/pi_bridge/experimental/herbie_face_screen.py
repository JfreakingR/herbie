"""Herbie's screen face: hairline features on a flat panel.

A handheld-console look. Almost all of the panel is empty; the face is a few
thin dark strokes with a lot of air around them. Restraint is the whole point —
sparse line-work reads as calm and characterful, where heavy filled shapes read
as a cartoon sticker.

This style also suits the hardware best. Thin strokes on a flat ground redraw
cheaply on a Pi 3B, stay legible on a small panel, and animate by moving a
handful of paths rather than reshading anything.

Same contract as the other renderers: validated state in, standalone SVG out.
`animate=True` adds idle life — irregular blinking, a slow breath, and a drift
of gaze — using CSS inside the SVG, so it needs no JavaScript and no GPU.

The design is original; the references informed the *style* only.
"""

from __future__ import annotations

from typing import Any

import herbie_face


IDENTITY_NAME = herbie_face.IDENTITY_NAME
EXPRESSIONS = herbie_face.EXPRESSIONS
DEFAULT_STATE = herbie_face.DEFAULT_STATE
merge_expression = herbie_face.merge_expression
set_privacy = herbie_face.set_privacy
xml_escape = herbie_face.xml_escape

# Landscape, like a small console panel.
WIDTH, HEIGHT = 480, 270
INK = "#20302a"
STROKE = 4.4

PANEL_WARM = (200, 230, 192)
PANEL_COOL = (178, 200, 196)

# Eye kinds: "arc" (content, ∩), "open" (a small ring), "dot", "line" (shut),
# "wide" (a larger ring). Mouth kinds: "smile", "flat", "o", "frown".
SHAPES: dict[str, dict[str, Any]] = {
    "calm":      {"eye": "arc",  "er": 15, "gaze": (0, 0),   "mouth": "smile", "mw": 46, "md": 13},
    "curious":   {"eye": "open", "er": 13, "gaze": (5, -3),  "mouth": "o",     "mw": 11, "md": 11},
    "happy":     {"eye": "arc",  "er": 17, "gaze": (0, 0),   "mouth": "smile", "mw": 62, "md": 20},
    "playful":   {"eye": "wink", "er": 14, "gaze": (4, 0),   "mouth": "smile", "mw": 54, "md": 17},
    "thinking":  {"eye": "open", "er": 12, "gaze": (-7, -5), "mouth": "flat",  "mw": 26, "md": 0},
    "surprised": {"eye": "wide", "er": 18, "gaze": (0, 0),   "mouth": "o",     "mw": 16, "md": 17},
    "concerned": {"eye": "open", "er": 12, "gaze": (0, 3),   "mouth": "frown", "mw": 42, "md": 11},
    "sleepy":    {"eye": "line", "er": 14, "gaze": (0, 2),   "mouth": "flat",  "mw": 22, "md": 0},
}


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _rgb(c):
    return "#%02x%02x%02x" % c


def _shade(c, factor):
    return _rgb(tuple(max(0, min(255, round(v * factor))) for v in c))


def _eye_path(cx, cy, kind, r):
    """A single eye as thin stroke geometry."""
    if kind == "line":
        return (
            f'<path d="M {cx - r} {cy} H {cx + r}" fill="none" stroke="{INK}" '
            f'stroke-width="{STROKE}" stroke-linecap="round"/>'
        )
    if kind == "arc":
        # Content, closed-eye arc: opens downward.
        return (
            f'<path d="M {cx - r} {cy + r * 0.42} Q {cx} {cy - r * 0.62} '
            f'{cx + r} {cy + r * 0.42}" fill="none" stroke="{INK}" '
            f'stroke-width="{STROKE}" stroke-linecap="round"/>'
        )
    if kind == "dot":
        return f'<circle cx="{cx}" cy="{cy}" r="{STROKE * 0.9}" fill="{INK}"/>'
    # "open" / "wide": a thin ring.
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{INK}" '
        f'stroke-width="{STROKE}"/>'
    )


def _mouth_path(cx, cy, kind, width, depth):
    half = width / 2
    if kind == "flat":
        return (
            f'<path d="M {cx - half} {cy} H {cx + half}" fill="none" stroke="{INK}" '
            f'stroke-width="{STROKE}" stroke-linecap="round"/>'
        )
    if kind == "o":
        return (
            f'<ellipse cx="{cx}" cy="{cy}" rx="{half}" ry="{depth}" fill="none" '
            f'stroke="{INK}" stroke-width="{STROKE}"/>'
        )
    if kind == "frown":
        return (
            f'<path d="M {cx - half} {cy + depth} Q {cx} {cy - depth * 1.1} '
            f'{cx + half} {cy + depth}" fill="none" stroke="{INK}" '
            f'stroke-width="{STROKE}" stroke-linecap="round"/>'
        )
    return (
        f'<path d="M {cx - half} {cy - depth * 0.30} Q {cx} {cy + depth * 1.5} '
        f'{cx + half} {cy - depth * 0.30}" fill="none" stroke="{INK}" '
        f'stroke-width="{STROKE}" stroke-linecap="round"/>'
    )


IDLE_CSS = """
    /* Irregular blink: even spacing reads as clockwork, so the gaps differ. */
    @keyframes blink {
      0%,      100% { opacity: 0; }
      13.0%, 13.7%  { opacity: 1; }
      13.8%         { opacity: 0; }
      41.0%, 41.6%  { opacity: 1; }
      41.7%         { opacity: 0; }
      44.0%, 44.7%  { opacity: 1; }
      44.8%         { opacity: 0; }
      78.0%, 78.8%  { opacity: 1; }
      78.9%         { opacity: 0; }
    }
    @keyframes unblink {
      0%,      100% { opacity: 1; }
      13.0%, 13.7%  { opacity: 0; }
      13.8%         { opacity: 1; }
      41.0%, 41.6%  { opacity: 0; }
      41.7%         { opacity: 1; }
      44.0%, 44.7%  { opacity: 0; }
      44.8%         { opacity: 1; }
      78.0%, 78.8%  { opacity: 0; }
      78.9%         { opacity: 1; }
    }
    /* A slow breath: barely perceptible, but stillness is what reads as dead. */
    @keyframes breathe {
      0%, 100% { transform: translateY(0px); }
      50%      { transform: translateY(2.2px); }
    }
    /* Gaze drift, so the eyes are never locked in place. */
    @keyframes drift {
      0%, 100% { transform: translate(0px, 0px); }
      22%      { transform: translate(3.5px, -1.2px); }
      55%      { transform: translate(-2.8px, 1.4px); }
      78%      { transform: translate(1.6px, 0.6px); }
    }
    .breathe { animation: breathe 5.5s ease-in-out infinite; }
    .drift   { animation: drift 13s ease-in-out infinite; }
    .lid     { animation: blink 11s steps(1, end) infinite; }
    .eye     { animation: unblink 11s steps(1, end) infinite; }
"""


def render_svg(state: dict[str, Any], animate: bool = False) -> str:
    expression = state.get("expression", "curious")
    if expression not in EXPRESSIONS:
        raise ValueError("invalid_expression")
    shape = SHAPES[expression]

    valence = float(state.get("valence", 0.0))
    arousal = float(state.get("arousal", 0.5))
    listening = bool(state.get("listening"))
    speaking = bool(state.get("speaking"))
    privacy = bool(state.get("privacy_mode"))

    panel = _mix(PANEL_COOL, PANEL_WARM, (valence + 1.0) / 2.0)

    cx, cy = WIDTH / 2, HEIGHT / 2
    eye_y = cy - 14
    eye_dx = 62
    gx, gy = shape["gaze"]

    # Arousal opens the eyes a little; alert versus half-asleep.
    r = shape["er"] * (1.0 + 0.18 * (arousal - 0.5))

    left_kind = right_kind = shape["eye"]
    if shape["eye"] == "wink":
        left_kind, right_kind = "open", "arc"

    mouth_width, mouth_depth = shape["mw"], shape["md"]
    if speaking:
        mouth_width = max(mouth_width * 0.7, 22)
        mouth_depth = max(mouth_depth, 12) * 1.5

    eyes = (
        _eye_path(cx - eye_dx + gx, eye_y + gy, left_kind, r)
        + _eye_path(cx + eye_dx + gx, eye_y + gy, right_kind, r)
    )

    # The blink overlay: the same eyes drawn shut, cross-faded by CSS.
    lids = (
        _eye_path(cx - eye_dx + gx, eye_y + gy, "line", r)
        + _eye_path(cx + eye_dx + gx, eye_y + gy, "line", r)
    )

    eye_class = ' class="eye"' if animate else ""
    lid_markup = f'<g class="lid" opacity="0">{lids}</g>' if animate else ""
    drift_open = '<g class="drift">' if animate else "<g>"
    breathe_open = '<g class="breathe">' if animate else "<g>"
    style_block = f"<style>{IDLE_CSS}</style>" if animate else ""

    badges = []
    if listening:
        badges.append(
            f'<circle cx="{WIDTH - 40}" cy="{HEIGHT - 32}" r="6" fill="#2f7d8c"/>'
        )
    if privacy:
        badges.append(
            f'<circle cx="40" cy="{HEIGHT - 32}" r="6" fill="#a4525f"/>'
            f'<path d="M 34 {HEIGHT - 38} L 46 {HEIGHT - 26}" stroke="#a4525f" '
            f'stroke-width="3" stroke-linecap="round"/>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}"
     role="img" aria-label="{xml_escape(IDENTITY_NAME)} looking {xml_escape(expression)}">
  {style_block}
  <rect width="{WIDTH}" height="{HEIGHT}" rx="10" fill="{_rgb(panel)}"/>
  {breathe_open}
    {drift_open}
      <g{eye_class}>{eyes}</g>
      {lid_markup}
    </g>
    {_mouth_path(cx, cy + 46, shape["mouth"], mouth_width, mouth_depth)}
  </g>
  {"".join(badges)}
</svg>"""

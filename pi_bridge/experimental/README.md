# Parked: face style explorations

Two alternative renderers for Herbie's face, written 2026-09-09 and parked the
same session because the owner is handling the face art themselves.

- `herbie_face3d.py` — glossy, dimensional style (gradients, speculars, mouth depth)
- `herbie_face_screen.py` — flat hairline style on a console panel, with an
  optional CSS idle-animation layer (irregular blinking, breath, gaze drift)
- `test_herbie_face_contract.py` — runs both against the same contract

Both are drop-in replacements for `herbie_face.render_svg`. Nothing imports
them; they are here in case the styling question comes back. Delete freely.

Two genuine findings about the live `herbie_face.py` came out of writing these,
and still stand:

1. `render_svg` does not validate `expression` — only `merge_expression` does,
   so calling it directly with a bad value renders a KeyError rather than a
   clean `invalid_expression`.
2. It ignores `valence` and `arousal` entirely. The autonomic layer now produces
   continuously varying mood, and the live renderer cannot show any of it.

# Herbie desk mode

Date: 2026-09-27. Herbie is a **stationary desk bot** for now: a face on a 7"
HD LCD, his brain on the Galaxy. The VAVA pet body is parked, not abandoned —
see "Getting back to the body" below.

## What runs where

| Part | Where | Status |
|---|---|---|
| Brain, memory, identity | Galaxy S21 (`phone_brain`, Herbie Brain app) | unchanged |
| Bigger model | Windows PC Ollama via the coordinator | unchanged, optional |
| Voice | Galaxy TTS (Monster speaker when paired), or the screen | new choice |
| Ears | Galaxy (Herbie Brain app, wake word "Herbie") | unchanged |
| Eyes / neck | Galaxy camera, `Herbie-Look.py` | unchanged, optional |
| **Face** | **7" LCD plugged into the Windows PC as a second monitor** | **new** |
| Motors, drive, battery | VAVA body | **parked** |

## Start him

1. Plug the 7" LCD into the PC (HDMI + its USB power). Windows should treat it
   as an extra display — "Extend", not "Duplicate".
2. Plug in the Galaxy with ADB authorized and the phone brain running (same as
   `Start Herbie Presence.cmd` needs; token from `tools/Export-Herbie-Token.ps1`).
3. Double-click **`Start Herbie Desk.cmd`**.

That starts `desk/herbie_desk.py` in the background on `127.0.0.1:8766` and
opens his face fullscreen on the smallest non-primary monitor. To talk to him,
type on the keyboard (a text box pops up; Enter sends, Esc hides it) or tap the
face if the LCD is a touchscreen. Alt+F4 on the face closes it;
`tools/Stop-Herbie-Desk.ps1` stops the server.

Options (pass after the `.cmd` or to the `.ps1`):

- `-List` — print the monitors Windows sees, with their numbers.
- `-Monitor 2` — use that monitor instead of guessing.
- `-Voice screen` — the face speaks through the PC/LCD audio with lip sync from
  the words. The default, `galaxy`, speaks from the phone (Herbie's real voice),
  and the mouth moves for the estimated length of the reply.

If the Galaxy isn't connected the face still comes up; the corner reads
"Herbie · brain offline" and he says so when you talk to him.

## How the face is wired

`pi_bridge/face/index.html` is the same animated face as before. The desk
server answers its three calls from the Galaxy brain:

- `GET /status` — tells the face its brain is the Galaxy (not Grok) and which voice.
- `GET /v1/expression` — polled every 2 s; the Galaxy's expression, listening
  and speaking flags drive the face.
- `POST /v1/chat` — typed text to the Galaxy's `/v1/chat`; the reply is shown
  as a caption and spoken.

Every Galaxy reply is checked for `motor_authority=false` and
`safe_motion_state=STOP`. The desk server has no path to COM7, the ESP32, J21,
the STM32 UART, or any motor. Tests: `cd desk && python -m unittest -v`.

## Known gaps

- **Conversations started by voice on the Galaxy don't animate the face yet.**
  The Herbie Brain app's ears and voice (`HerbieEars.kt`, `HerbieVoice.kt`)
  speak directly and never set the brain's `listening`/`speaking` flags, so the
  face can't tell. Fix: have the app `POST /v1/expression` with
  `listening`/`speaking` around recognition and speech. Typed conversations
  through the face already animate.
- Galaxy-voice lip movement is timed from word count, not the real audio.
- `Start-Herbie-Desk.ps1` was written without a Windows machine to run it on;
  the Python server and the face were tested at 1024×600 and 1280×800 in Chromium.

## Getting back to the body

Nothing in the body's code was changed or removed. When the desk phase is over,
start from `HERBIE_HANDOFF_2026-09-18_SEQUENCE_AND_IR.md` (drive needs a
non-zero sequence; IR vetoes moves) and the other `HERBIE_HANDOFF_*` files.
The same face can move onto the body later — it is one web page.

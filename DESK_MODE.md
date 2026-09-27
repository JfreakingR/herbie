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
| **Face** | **7" LCD on the Pi 400 (or the Windows PC as a second monitor)** | **new** |
| Motors, drive, battery | VAVA body | **parked** |

## Start him from the Windows PC

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

## Pi 400 as his always-on body (recommended)

The Pi 400 drives the 7" LCD and holds the Galaxy on USB, so the PC can be
off. When the PC is on, the Galaxy still reaches its bigger model over Wi-Fi
through the coordinator, as before.

1. Flash **Raspberry Pi OS (64-bit, with desktop)** onto a 128 GB card with
   Raspberry Pi Imager. In Imager's settings, set your user and Wi-Fi.
2. Screen to the Pi 400's **HDMI0** port (the one next to the power jack),
   with the screen's own USB cable for power and touch.
3. On the PC, pull this branch, then copy onto a USB stick:
   - the whole `herbie` folder
   - `%USERPROFILE%\.herbie\api-token`
   - `%USERPROFILE%\.android\adbkey` and `adbkey.pub` (the Galaxy already
     trusts this key; a new one would need a tap on the phone's screen)
4. On the Pi: copy `herbie` to your home folder, `api-token` into `~/.herbie/`,
   and both `adbkey` files into `~/.android/`.
5. Plug the Galaxy into the Pi 400 by USB, then in a terminal:

   ```sh
   cd ~/herbie && sh desk/pi400/install.sh
   sudo reboot
   ```

After the reboot his face comes up on its own. Type on the Pi 400's keyboard
to talk to him. If the phone is unplugged, the server redoes the ADB link
within 15 seconds of it coming back. `HERBIE_VOICE=screen sh
desk/pi400/install.sh` switches his voice to the screen's audio.

Checks: `adb devices` should list `R5CR11QCHPY  device`;
`journalctl --user -u herbie-desk -f` shows the server's log.

## His face: the spirit

Herbie's face is `pi_bridge/face/spirit.html`, a glowing, wispy spirit drawn
in real-time 3D (three.js, bundled under `pi_bridge/face/vendor/three` so he
works with no internet). The older 2D face is still `index.html`: use
`-Look classic` on the PC, or `HERBIE_FACE_PAGE=index.html` on the Pi.

- **Voice conversation** runs on the Galaxy (say "Herbie…"). The spirit
  brightens and leans in while he listens, and pulses while he talks.
- **Typing** anywhere opens a box; his reply shows as a glowing caption.
- **Moods** follow the brain's expression (calm, curious, happy, playful,
  thinking, surprised, concerned, sleepy).
- **Shapeshifting**: "turn into the sun / the moon / a football / just your
  face", and "back to normal". Works from typed messages, or when his own
  reply says it.
- `?controls=1` adds mood and shape buttons for trying him out; `?lite=1`
  drops the bloom and some sparks (the Pi 400 picks this automatically).

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

- **Voice conversations need the rebuilt Herbie Brain app.** `HerbieEars.kt`
  now posts `listening`/`speaking` to the brain's `/v1/expression` (listening
  while awake, speaking while he talks), which the face follows. Rebuild and
  install with `tools/Build-Herbie-Brain.ps1`; until then only typed
  conversations animate the face.
- Galaxy-voice lip movement is timed from word count, not the real audio.
- `Start-Herbie-Desk.ps1` was written without a Windows machine to run it on;
  the Python server and the face were tested at 1024×600 and 1280×800 in Chromium.

## Getting back to the body

Nothing in the body's code was changed or removed. When the desk phase is over,
start from `HERBIE_HANDOFF_2026-09-18_SEQUENCE_AND_IR.md` (drive needs a
non-zero sequence; IR vetoes moves) and the other `HERBIE_HANDOFF_*` files.
The same face can move onto the body later — it is one web page.

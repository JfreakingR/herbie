# Herbie presence checkpoint

Double-click `Start Herbie Presence.cmd` on the Windows PC, or run
`python tools/herbie_presence.py` from this repository if Python is on PATH.
This is a text input and spoken reply path through Herbie's **existing** Galaxy
brain: Galaxy local model and autobiographical memory, then Android local TTS.
When Monster Mag Flux is the Galaxy's active Bluetooth media output, replies
play there. The Galaxy's screen and speaker are not used. The tool opens an
ADB port forward, reads the existing private API token, and checks that the
phone brain reports motor authority disabled. It does not access COM7, J21,
the controller board, sensors, or motors.

The Galaxy must be connected and authorized in ADB, its phone brain and model
bridge must be running, and its API token must already have been exported by
`tools/Export-Herbie-Token.ps1`. An empty line or Ctrl+C exits. This checkpoint
uses typing; hands-free listening still needs an explicit choice of speech
recognition and its privacy/network behavior. The Pi face link remains a
separate integration step once Melba is reachable again.

On 2026-09-20 the local session saw COM7 but no ADB devices, and could not
reach Melba's SSH port. Therefore this tool was verified offline only; no
spoken reply or Pi face response is claimed for this session.

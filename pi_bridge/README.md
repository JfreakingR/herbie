# Pal Pi bridge

Safety-bounded coordinator service for the Raspberry Pi 3B (`Melba`). It uses Python's standard library and listens on loopback until a separately verified transport exists.

Endpoints:

- `GET /health` reports readiness, uptime, heartbeat state, and safety state.
- `POST /v1/heartbeat` accepts a small JSON object such as `{"source":"phone-brain"}` and acknowledges it.

The service cannot command motors or actuators. Every response reports `motor_authority: false` and `safe_motion_state: STOP`. Motor authority belongs only in the future ESP32 layer.

This service is not installed until SSH to Melba is verified.

## Face on the Pi screen

`face/index.html` is the BMO-style animated face. The bridge serves it at `http://127.0.0.1:8766/face/?kiosk=1`.

`herbie-face-kiosk.sh` waits until DRM reports an HDMI or DSI panel as `connected`, then opens that URL fullscreen. It will not guess a GPIO/SPI overlay. Identify the panel connector before enabling `herbie-face-kiosk.service`.

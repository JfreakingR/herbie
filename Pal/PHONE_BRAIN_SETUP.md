# Pal Phone Brain Setup

## Verified state — 2026-09-05

- Phone: Samsung Galaxy S21 Ultra, model `SM-G998U`
- Android: 15
- USB connection: Samsung composite device and file transfer detected
- USB debugging: enabled and authorized for this Windows computer
- Remote display/control: verified through scrcpy at `1080x2400`
- Recovery launcher: `Start Pal Phone.cmd`
- Recovery identity: launcher pins ADB to the existing Windows user key so reconnects do not silently create a different computer identity
- Battery snapshot during the test: Android health `GOOD`, approximately 51%, 3.875 V, and 30 C
- Lock state during the test: unlocked
- Wi-Fi recovery: authenticated ADB-over-LAN verified at `1080x2400`; saved endpoint is local-only and may need updating if the router changes the phone's address
- Pal phone brain: installed in Termux and verified running as `pal-phone-brain 0.1.0` on the phone's loopback interface
- Brain link test: `/health` and `/v1/heartbeat` passed through an authenticated USB ADB tunnel
- Safety response: `motor_authority` is `false` and `safe_motion_state` is `STOP`

The battery snapshot is a momentary software report, not a capacity test. The user's report that runtime is poor still stands. Replace the battery before permanent enclosed installation, and do not use it if it swells, separates the phone, overheats, or develops an odor.

## Normal recovery

1. Double-click `Start Pal Phone.cmd` in the Pal folder.
2. The launcher prefers the authorized USB connection when it is present.
3. If USB is absent, it tries the saved authenticated local Wi-Fi endpoint.
4. Confirm that the `Pal-S21-Ultra` window opens.

Wi-Fi recovery is intentionally limited to the local network and Android still requires the saved ADB key. It is not forwarded through the router. Legacy TCP mode normally ends after a phone reboot, so USB or DeX remains the cold-start recovery path.

The launcher does not remove the screen lock, expose ADB to the internet, activate the camera or microphone, or modify robot power settings. Its `--stay-awake` behavior applies only while the control session is running and the phone is plugged in.

## Before phone disassembly

- Verify control after an ordinary USB disconnect/reconnect.
- Keep Samsung DeX over USB-C/HDMI as a cold-start fallback even though authenticated local Wi-Fi recovery has been verified.
- Verify camera, microphone, speaker, Wi-Fi, Bluetooth, and USB-C operation.
- Back up any data that matters.
- Replace the worn battery with the correct protected S21 Ultra battery before enclosed use.
- Design a ventilated, reversible mount that retains the phone midframe, antennas, camera alignment, shielding, and heat spreading.
- Keep phone power electrically isolated from the VAVA motor supply; use a verified regulated USB supply.

## Brain division

- Galaxy S21 Ultra: camera, microphones, speaker, speech, conversational AI, and high-level decisions.
- Raspberry Pi 3B: onboard coordination, networking, logging, and the bridge to robot electronics.
- ESP32: bounded real-time motor and actuator control with a hardware cutoff and loss-of-heartbeat stop.

High-level AI output must never drive motors directly.

## Verified phone-brain recovery test

1. Make sure the phone is connected and USB debugging is authorized.
2. Double-click `Test Pal Phone Brain.cmd`.
3. A passing result reports `Ready: True`, `Heartbeat acknowledged: True`, `Motor authority: False`, and `Safe motion state: STOP`.

The service currently listens only inside the phone at `127.0.0.1:8765`. The test reaches it through an authenticated ADB tunnel on the connected computer. It is deliberately not exposed directly to the Wi-Fi network. Pi installation and authenticated Pi-to-phone transport remain separate, unverified steps.

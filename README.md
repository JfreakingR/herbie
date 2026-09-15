# Pal — AI Robot Friend

Pal is a mobile companion robot built by preserving and extending as much of the disassembled VAVA pet camera as practical—not merely reusing its shell.

## Proposed roles

- **Galaxy S21 Ultra:** primary camera, microphone, speaker, touch interface, speech recognition, and AI conversation.
- **Raspberry Pi 3B:** onboard coordinator, touchscreen face/status display, networking, and high-level motion requests.
- **ESP32:** real-time motor control, watchdog, emergency stop behavior, and future sensors.
- **Original VAVA electronics:** retain the battery/charging system, drivetrain, motors, camera mechanisms, audio hardware, sensors, LEDs, and control boards wherever inspection proves they can be safely reused or interfaced.
- **L298N boards:** fallback motor power stages only if the original VAVA motor controller cannot be safely commanded.
- **Raspberry Pi 400:** development, recovery, testing, and optional home-base services.
- **3.5-inch display:** onboard face/status panel.
- **7-inch HDMI display:** initial bench console or larger face if its size and power needs suit the chassis.

## Current status

**DESIGN / INSPECTION — no electrical connections approved yet.**

The VAVA model, battery chemistry and voltage, motor ratings, connector pinouts, original control interfaces, and ESP32 board variant must be identified before a wiring diagram can be finalized.

Start with [BUILD_PLAN.md](BUILD_PLAN.md), review the first [PHOTO_AUDIT.md](PHOTO_AUDIT.md), and record new measurements in [HARDWARE_INVENTORY.md](HARDWARE_INVENTORY.md).

The next controlled hardware gate is [FIRST_POWER_TEST.md](FIRST_POWER_TEST.md); do not perform it with the old battery connected.

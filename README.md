# Pal — AI Robot Friend

Pal is a mobile companion robot built by preserving and extending as much of the disassembled VAVA pet camera as practical—not merely reusing its shell.

## Current computing roles

- **Windows computer:** primary local language model through Ollama (`qwen3.5:9b`) whenever the computer is reachable over the private network.
- **Galaxy S21 Ultra:** owns Herbie's identity and memory, routes conversation, supplies camera/microphone/speaker access, and runs a fully offline Qwen3 1.7B fallback model.
- **ESP32:** real-time motor control, watchdog, emergency stop behavior, and future sensors.
- **Original VAVA electronics:** retain the battery/charging system, drivetrain, motors, camera mechanisms, audio hardware, sensors, LEDs, and control boards wherever inspection proves they can be safely reused or interfaced.
- **L298N boards:** fallback motor power stages only if the original VAVA motor controller cannot be safely commanded.

## Current status

**The local AI handoff is live; physical motion remains safety-locked.**

The computer-primary/phone-fallback conversation path is authenticated, local-only, and free to run. The phone fallback uses `Qwen3-1.7B-Q4_K_M.gguf`; measured warm two-turn replies were 2.28 s and 1.80 s. The Android foreground service keeps the model available and starts it again after phone boot. Herbie's phone service remains the only writer of identity and memory.

Motor authority is still `false` and the required motion state is `STOP`. A factory-board version exchange over UART has been proven, but movement has not. Do not infer that the working AI path authorizes motor or battery work.

The battery condition, motor ratings, connector pinouts, and remaining control interfaces still require evidence before a final wiring design or powered movement test.

Start with [BUILD_PLAN.md](BUILD_PLAN.md), review the first [PHOTO_AUDIT.md](PHOTO_AUDIT.md), and record new measurements in [HARDWARE_INVENTORY.md](HARDWARE_INVENTORY.md).

The next controlled hardware gate is [FIRST_POWER_TEST.md](FIRST_POWER_TEST.md); do not perform it with the old battery connected.

Software entry points:

- [Phone brain](phone_brain/README.md)
- [Computer brain](computer_brain/README.md)
- [Android model bridge](android_brain/README.md)

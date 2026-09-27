# Pal Build Plan

## Target version 1

A safe, drivable companion that can:

1. see and hear through the Galaxy S21 Ultra;
2. hold a spoken conversation;
3. display an animated face or status on the 3.5-inch screen;
4. accept deliberate forward, reverse, left, right, and stop commands;
5. stop automatically if communication with the ESP32 is lost;
6. be manually stopped without relying on software.

Autonomous roaming and charging come only after the supervised version is reliable.

## System architecture

```text
Galaxy S21 Ultra
camera / mic / speaker / AI UI
          |
       Wi-Fi or USB
          |
Raspberry Pi 3B -------- 3.5-inch face/status display
high-level coordinator
          |
      USB serial
          |
ESP32 motor safety controller
watchdog + command limits
          |
   control signals only
          |
Original VAVA motor controller OR L298N fallback -------- VAVA motors
          |
separate measured motor supply
```

The Raspberry Pi 400 is the build station and can also host heavier local services while the robot is on the same network. Original VAVA subsystems remain in place whenever they pass identification and interface tests.

## Preservation-first rule

Do not remove, cut, or replace a VAVA subsystem merely because a replacement part is available. Evaluate components in this order:

1. preserve it unchanged and command it through the original VAVA control board;
2. preserve the component and interface its existing connector through the ESP32 or Pi;
3. preserve its mechanical assembly but substitute only the unsupported controller;
4. replace it only when it is damaged, unsafe, undocumented beyond practical testing, or incompatible with the robot's required functions.

Likely preservation candidates include the chassis, wheels/tracks, gearboxes, drive motors, pan/tilt assembly, battery pack, protection board, charging contacts or dock, power switch, speakers, microphones, camera module, LEDs, buttons, and internal wiring harnesses. Each candidate must be proven individually; its presence does not establish its voltage, pinout, or compatibility.

Before further disassembly, label connectors and take photographs. Do not cut original connectors. Adapter harnesses should plug into them so the robot can be returned to its prior configuration.

## Safety rules

- Do not connect the VAVA battery to a Pi, ESP32, display, or L298N until its label and measured voltage are recorded.
- Do not power motors from a Raspberry Pi or ESP32 power pin.
- Do not connect an unknown VAVA wire directly to GPIO.
- Disconnect the battery while tracing continuity or resistance.
- Insulate the battery terminals during mechanical work.
- Add an accessible physical motor-power switch and an inline fuse before powered movement tests.
- Keep the robot raised so its wheels cannot touch the bench during first motion tests.
- The ESP32 must stop all motors when commands stop arriving, the serial link fails, or it resets.
- Begin with a low PWM limit and one motor at a time.

## Stage 0 — identify the hardware

Before designing connections, capture:

- VAVA product label and exact model number;
- full overhead photo of the open chassis;
- close photo of every circuit board, connector, motor label, and battery label;
- wire colors and connector destinations before unplugging anything else;
- battery voltage measured with a multimeter;
- resistance across each disconnected motor pair;
- exact marking on the ESP32 board;
- model/controller marking of both displays;
- available power adapters, USB cables, microSD cards, switches, fuses, and voltage converters.
- every reusable VAVA subsystem, its original connections, and whether its controller exposes identifiable UART, USB, I2C, SPI, PWM, analog, or button/contact interfaces.

Record all results in `HARDWARE_INVENTORY.md`.

## Stage 1 — bench-test logic only

1. Prepare the Pi 3B with Raspberry Pi OS Lite or Desktop, depending on the 3.5-inch display driver.
2. Power the Pi from a known-good regulated USB supply.
3. Connect the ESP32 by USB only; leave both L298N boards and all motors unpowered.
4. Implement a serial command protocol: `STOP`, `DRIVE left right`, heartbeat, and status.
5. Confirm the ESP32 returns to STOP after a short heartbeat timeout.
6. Test the touchscreen and render a simple face/status screen.

**Gate:** logic passes repeated watchdog tests with no motor power present.

## Stage 2 — test original subsystems

1. Inspect and identify the original VAVA main board, motor driver, power/charging board, camera board, audio board, and sensors.
2. Test original functions with the factory wiring intact whenever that can be done safely.
3. Observe control signals non-invasively before attempting to command them.
4. Prefer sending commands to the original controller over bypassing it.
5. Create reversible adapter harnesses; do not cut the factory loom.

**Gate:** every retained subsystem has a documented connector, supply voltage, interface, and safe test result.

## Stage 3 — characterize one motor only if the original controller cannot be reused

Use a current-limited bench source if available. If not, pause and obtain a safe test supply appropriate to the measured motor rating.

1. Identify one motor pair by continuity and physical tracing.
2. Determine its safe operating voltage without assuming it matches the battery label.
3. Connect one L298N channel with motor power off.
4. Establish a common signal ground between ESP32 and driver.
5. Apply motor power, start at low PWM, verify direction, current, heat, and mechanical motion.
6. Disconnect and inspect before adding another motor.

**Gate:** each motor has a documented pair, function, polarity convention, voltage, no-load current, and tested PWM limit.

## Stage 4 — supervised driving

- Mount electronics temporarily with nonconductive spacers.
- Add the physical motor-power cutoff and fuse.
- Drive from a local web control or gamepad-style screen.
- Verify STOP from the UI, STOP on network loss, STOP on Pi shutdown, and STOP on ESP32 reset.
- Run short sessions and log battery voltage, driver temperature, and motor temperature.

**Gate:** ten supervised tests end safely, including deliberate communications failures.

## Stage 5 — phone senses and conversation

- Mount the S21 Ultra securely with unobstructed cameras, microphones, speakers, buttons, and charging port.
- Use the phone for conversational UI and live audio/video.
- Send only bounded high-level motion intents to the Pi, such as “turn toward the person”; the ESP32 retains final timeout and speed enforcement.
- Provide a visible listening/camera indicator and a privacy mode.

## Stage 6 — personality and behavior

- Animated face and emotional state.
- Name, voice, preferred phrases, and local memory with a delete/reset control.
- Wake word or push-to-talk.
- Person-following only after obstacle and edge/fall protection are added.
- Charging behavior only after the original VAVA charge circuitry is understood and proven safe.

## Likely additional low-cost parts

These are not chosen until inspection confirms ratings:

- regulated buck converter(s) for Pi/display and possibly phone charging;
- inline fuse and holder;
- latching motor-power switch or emergency-stop button;
- screw terminals/connectors, wire, heat-shrink, and nonconductive standoffs;
- current-limited bench supply or suitable test supply;
- multimeter if one is not available;
- obstacle and cliff sensors before autonomous movement.

The L298N is usable for early testing but wastes voltage and can run hot. A modern MOSFET motor driver may later improve battery life and low-voltage motor performance.

## Acceptance test for version 1

- Physical cutoff stops the motors.
- Software STOP works every time.
- Removing the Pi-to-ESP32 link stops the motors automatically.
- Robot drives in all four requested directions at a limited speed.
- Touchscreen visibly reports connected, listening, moving, stopped, and fault states.
- Phone supports a complete listen/respond cycle.
- Motors cannot be activated directly by unconstrained AI text.
- Wiring, voltages, software versions, and recovery steps are documented.

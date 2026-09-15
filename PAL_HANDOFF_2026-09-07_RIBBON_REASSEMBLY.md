# PAL / VAVApet VP-SPR001 Handoff — Ribbon Reassembly Checkpoint

**Date:** 2026-09-07  
**Status:** Factory ribbons reconnected; factory computer boots and requests network configuration.  
**This file supersedes the hardware-layout and camera statements in `PAL_HANDOFF_2026-09-07.md`.** Keep that older handoff only for its earlier UART, ESP32, phone, and Melba history.

## Goal

Preserve and reuse PAL's original VAVA electronics wherever practical. Restore the factory wiring first, establish a repeatable factory baseline, and only then add an ESP32, Raspberry Pi, or Galaxy S21 interface. No new controller receives motor authority until the command protocol and an independent safety stop have been verified.

## Device identity

- Product: VAVApet Pet Cam
- Model: `VP-SPR001`
- FCC ID: `2AFDGVP-SPR001`
- Exact FCC internal-photo filing: <https://fccid.io/2AFDGVP-SPR001/Internal-Photos/09-VP-SPR001-IntPho-4338414>
- Original app name: `VAVA Pet Cam`
- Android package reported by archival listings: `com.vava.pet`
- Original networking: Bluetooth-assisted provisioning to 2.4 GHz Wi-Fi; 5 GHz is not supported by the FCC grant/manual.

## Critical correction: PAL has two electronics halves

PAL does **not** have one green board containing every connector. The opened robot has two shell halves with different green boards and different subsystems.

1. One half contains the blue compute board, a green I/O/interconnect board, the treat mechanism, camera wiring, speaker-related wiring, and other factory peripherals.
2. The other half contains a separate green controller/motion board, motors/mechanisms, sensors, and its own connectors.
3. Connector designators such as `J18` can be reused on different boards. Never say only “J18.” Always use the board/half plus the printed designator.

This correction invalidates the older handoff statement: **“One green distribution board. J18, J21, and J22 are all on that board.”** That statement described only one photographed board and must not be used as a map of the entire robot.

## Boards and assemblies photographed

### Blue compute board

- Silkscreen: `A8002_MB80_D3_V1.0`, dated `20180704`.
- Visible factory labels include `USB`, `UART`, `SPK`, `RESET`, `VIB`, `TF`, `CAM`, `MIC`, `PWR`, and `LCD`.
- A black flex marked `R8097G23-C` runs between the blue board's `CAM` connector and the small camera module.
- **The black camera flex was already connected at both ends. It is not the missing inter-half cable and must not be unplugged.**
- A separate thin coaxial lead is the antenna path; do not confuse it with the camera flex.

### Green I/O/interconnect board in the compute/treat half

- Photo-visible date: `2018.12.24`.
- Carries many white wire connectors and one long FFC/ZIF socket marked `J1` in the photographed view.
- This is a separate PCB from the motion/controller board in the other half.

### Green controller/motion board in the other half

- Upright board with many factory wire harnesses, motors/mechanisms, sensors, and a long FFC/ZIF socket.
- Nearby photo-visible markings around the long connector include `J4` and `J16`; the exact designator for the long socket must be read from an unobstructed board photo before it is entered into a pinout.
- Earlier project notes identify a live 3.3 V UART labelled `J21` on a controller board and an STM32-family motion controller. Retain those as prior measured findings, but do not use them to rename connectors on the other green PCB.

## Ribbon-cable findings

### Wide inter-half ribbon

- Marking: `AWM 20861 105C 60V VW-1`.
- The exposed copper contacts and the blue printing are visible in the photographs.
- Its width matched the two long inter-half sockets.
- It was first placed loosely only to verify physical fit; it was subsequently fully inserted and latched.
- Current user report: **all ribbons are now connected**.
- Leading factory-path identification: the wide ribbon joins the long `J1` socket on the green I/O board to the long socket on the separate controller/motion board.
- The `AWM 20861` text is only a UL cable style/rating; it does not define the signal pinout.

### Narrow ribbons

- Marking: `AWM 20624 80C 60V VW-1`.
- These were also reported connected at the current checkpoint.
- Their individual functions and pinouts remain undocumented.
- The `AWM 20624` text is only a UL cable style/rating; it does not identify the circuit.

### Connector handling

- Long connectors use fragile locking actuators. Do not pull a ribbon while its lock is closed.
- Do not pry locks with metal tools.
- Before closing the shell, confirm each ribbon is square, equally deep at both edges, has no exposed contact fingers beyond the normal insertion line, and is not pinched or sharply folded.

## Factory boot result after reconnection

The robot was powered after all ribbons were connected.

**Observed:**

- PAL powered on.
- PAL played startup music.
- PAL announced: **“waiting for network config.”**

**What this verifies:**

- The blue compute board is booting far enough to run its startup/configuration software.
- The speaker/audio-output path works.
- The firmware reached network-provisioning mode.
- At least the power path and essential compute-board startup connections are functional.

**What this does not yet verify:**

- Camera video.
- Microphone input.
- Every inter-half ribbon conductor.
- Controller-board communication.
- Track motors, treat dispenser, laser/toy mechanism, LEDs, or safety sensors.
- Successful connection to the current home network.

## Network/app checkpoint

- PAL has never been provisioned to the user's current Wi-Fi network.
- No PAL Wi-Fi SSID appeared in the phone's normal Wi-Fi list.
- That is not presently treated as a hardware failure: the spoken prompt says PAL is waiting to receive network configuration.
- The manual describes Bluetooth-assisted pairing and recommends completing pairing within five minutes of startup.
- Do **not** reset PAL again at this checkpoint. A reset may erase useful retained configuration and does not solve the missing-app problem.
- An Android phone/tablet is available.
- The original app no longer appeared in current official-store searches performed during this session.
- Archival listings report Android app `VAVA Pet Cam`, package `com.vava.pet`, version `1.0.0` from 2019. An iOS archive listing reports version `1.0.2`.
- Only a third-party APK archive was found. An attempted download for offline inspection was blocked by a Cloudflare challenge, so **no APK was obtained, hashed, signature-checked, permission-audited, or installed**.
- Do not install a random similarly named “Vava” app. Confirm exact package `com.vava.pet` and original publisher before considering installation.
- Even an authentic old APK may depend on discontinued vendor cloud services. Successful installation does not guarantee pairing or control.

Reference manual: <https://www.manualslib.es/manual/657876/Vava-Vp-Spr001.html>

## Prior controller UART work to retain

Earlier project work reported the following on the controller-side debug header:

- `J21`: `TX`, `GND`, `RX`, `3.3V`.
- Measured rail: approximately 3.33 V.
- ESP32 passive listener used controller `TX` to ESP32 `GPIO23` and common `GND`, with ESP32 powered from USB.
- Valid 115200 8N1 frames and controller version text were captured.
- Files: `VAVA_UART_PROTOCOL_NOTES.md`, `firmware\vava_listen_capture.txt`, `firmware\vava_listen_buttons.txt`, and `firmware\vava_uart_listener\`.

Safety status for that work:

- Passive listening is supported by prior evidence.
- Sending commands to controller `RX` is **not authorized or verified**.
- Do not connect VAVA `3.3V` to the ESP32.
- Do not connect any UART until the exact board/header is visually re-confirmed after reassembly.

## Battery and power safety

- Original battery pack remains quarantined and out of service. Do not charge or reconnect it.
- Use only the known original center-positive adapter for factory testing.
- Keep tracks/wheels raised during any open-shell powered test.
- Do not touch boards, exposed contacts, or connector locks while powered.
- Unplug PAL before changing a ribbon, attaching test leads, or moving boards.
- Do not command motion, the treat mechanism, or other actuators while the two halves are open.
- `motor_authority=false` and safe state `STOP` remain mandatory for new software.

## Recommended next steps

### 1. Preserve the successful baseline

1. Power PAL down and unplug it.
2. Photograph both sides of every now-connected ribbon and one overall routing view.
3. Check that no ribbon or wire will be trapped by screw posts, shell edges, gears, the hopper, or the moving head/mechanism.
4. Do not close the shell permanently until the basic peripheral checks below are complete.

### 2. Try the least-invasive factory provisioning path

1. On the Android device, check Google Play **Manage apps and device → Manage → Not installed** under any Google account that may previously have installed VAVA Pet Cam.
2. Accept only the exact app identity `VAVA Pet Cam` / `com.vava.pet` from the original VAVA/Sunvalley publisher.
3. If it is unavailable, do not install a third-party APK directly on a primary phone.
4. If an APK is obtained, copy it to the Windows project first and inspect its SHA-256, Android manifest, requested permissions, embedded endpoints, native libraries, and signing certificate before installation.
5. Prefer a spare Android device with no personal accounts or sensitive data.
6. Use a temporary isolated 2.4 GHz test network, not the main household credentials, if pairing is attempted.
7. Never write the Wi-Fi password into this repository, screenshots, logs, or the handoff.

### 3. If the factory app/cloud path fails

Proceed with read-only discovery rather than flashing:

1. Capture the blue board's labelled `UART` boot output after confirming its voltage and ground with a meter.
2. Inspect the blue board's labelled `USB` connection from Windows and record only how it enumerates.
3. Do not use SP Flash Tool's Download, Format, Firmware Upgrade, or erase functions.
4. If storage backup becomes possible, make and verify a read-only image before changing firmware.
5. Resume passive capture of controller `J21 TX` only after re-confirming the exact header and keeping its `RX` disconnected.
6. Correlate messages with safe, non-motion events first: startup, power button, LEDs, network prompt, and peripheral detection.

### 4. Functional testing order

After wiring/routing inspection and with PAL mechanically secured:

1. Startup audio and status lights.
2. Network provisioning on an isolated 2.4 GHz network.
3. Camera and microphone.
4. Passive controller communication capture.
5. Non-motion LEDs/speaker.
6. Safety sensors.
7. Treat/laser mechanisms only with the area clear.
8. Track motors last, raised off the surface, one brief low-speed action at a time, with immediate power removal available.

## Do not do next

- Do not reset PAL merely because no SSID appears.
- Do not install an unverified APK on a primary phone.
- Do not flash or format the MediaTek board.
- Do not attach the ESP32 to an unverified connector.
- Do not connect the ESP32 to VAVA `3.3V`.
- Do not transmit into controller UART `RX` yet.
- Do not reconnect the quarantined battery.
- Do not test motors while the robot is open or resting on its tracks.
- Do not unplug the black `R8097G23-C` camera flex.

## Immediate continuation question

Choose the next path:

1. **Factory-app recovery:** obtain and inspect the exact archived `com.vava.pet` APK, then attempt Bluetooth provisioning on a spare Android device and isolated 2.4 GHz network.
2. **Read-only hardware discovery:** skip the obsolete app for now and capture the blue board's UART/USB behavior without writing or flashing anything.

The preservation-first recommendation is to attempt option 1 only if the APK can be authenticated and isolated. Otherwise use option 2.


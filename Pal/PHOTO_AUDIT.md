# Photo Audit — 2026-08-29

Source: `attachments.zip`, extracted to `photos/`.

This audit records what is actually visible. “Candidate,” “appears,” and “likely” are not wiring approvals.

## Confirmed from labels and construction

- Robot: VAVApet Pet Cam, model `VP-SPR001`.
- Robot base rating: 48 W; input `DC 16.8 V, 2000 mA`.
- Battery label: 18650 pack, `11.1 V`, `4400 mAh`, `48.84 Wh`, `3S2P`, dated `2018-12-27`.
- Main controller PCB: `SG_802_TD_V1.2_CTL`, dated `2018-12-21`.
- Blue daughterboard: `AB002_D3.01 O-FLASH`.
- One internal actuator is labeled `28BYJ4 5V DC NO:1812 WKX`.
- An ESP-32U development board and at least one L298N dual H-bridge module are present.

## High-value reusable VAVA hardware

1. Complete molded chassis, wheel sets, removable rubber tracks, shafts and motor mounts.
2. Multiple original geared motors and their connectors.
3. Front camera/optical assembly and its enclosure.
4. Original controller, daughterboard, connector/distribution PCB and factory harnesses.
5. Electret microphone, buzzer, power button, front indicators and likely speaker connection.
6. Original battery bay and connector. The battery itself remains conditional on electrical safety tests.
7. The 5 V labeled actuator and another coil/solenoid-like actuator.
8. Any charging contacts, original adapter and docking hardware once photographed and tested.

## Promising original interfaces

The controller/distribution assembly exposes:

- `J18`: six unpopulated pads. A sharp phone photo confirms the left-to-right order shown in that photo as `VCC`, `RXD`, `TXD`, `SET`, `CS`, `GND`;
- `J4`: four pads labeled `SDA`, `SCL`, `GND`, `VCC`;
- `J2`: marked `BATTER`;
- a printed connector legend for multiple factory peripherals.

These headers make preserving the original control electronics plausible. They do **not** establish signal voltage or protocol. Never attach the ESP32 until ground and idle signal levels are measured.

## Proposed preservation path

1. Reassemble enough of the original wiring to perform a factory-function test, without attaching the Pi, ESP32 or L298N.
2. Check the battery mechanically and electrically; do not charge it first.
3. If the original adapter is available and correctly labeled, test the robot with the wheels raised and battery decision made.
4. Observe the `J18` serial header non-invasively. Determine whether the original controller emits boot/status data.
5. If serial commands can be identified, keep the factory controller as the motor/actuator layer.
6. If it cannot be commanded, keep all original motors, mechanisms and connectors, then use reversible adapter harnesses to the ESP32 and external driver boards.
7. Preserve the original camera if its stream can be accessed locally. The Galaxy S21 Ultra can supply AI vision/audio while camera compatibility is investigated.

## Required next evidence

- Multimeter reading across the disconnected battery connector, including polarity.
- Original 16.8 V adapter label and connector.
- Photos of any charging dock and underside charging contacts.
- Straight, close, well-lit photo of the entire component side of B1 with cables moved aside but not disconnected unnecessarily.
- Macro photos of every large IC marking on B1 and both sides of the blue `AB002` daughterboard.
- Close photos showing where each geared motor cable terminates.
- Photo of the actual speaker and its connector.
- Exact model/labels of the 3.5-inch and 7-inch displays.
- Confirmation whether the original VAVA robot operated before disassembly.

## Battery stop conditions

Do not charge or use the pack if it is swollen, punctured, hot, smells unusual, has corroded wiring, measures below a safe recoverable range, or shows severe cell imbalance. The pack is dated 2018, so visible condition alone is not sufficient evidence of safety or useful capacity.

### Battery test result — 2026-08-29

- Pack-output voltage: **UNVERIFIED**. The initial 0.45 V report was later described as an individual-cell attempt rather than a validated connector measurement; a later near-4 V individual-cell claim was also not safely documented.
- Physical state: photographs show the original protective wrap removed, exposing cells, nickel connections and the BMS. Prior verbal condition reports were withdrawn as unreliable.
- Gate result: **QUARANTINE — DO NOT CHARGE OR USE.** The pack's age, exposed construction and unknown cell-group balance require professional evaluation.
- Preserve the robot's battery bay, connector and charging circuitry for characterization, but do not use this pack for powered robot testing.

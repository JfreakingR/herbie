# Hardware Inventory and Measurement Log

Do not infer missing values. Photograph labels and enter measurements.

## VAVA unit

- Product name: VAVApet Pet Cam
- Exact model number: VP-SPR001 (confirmed from base label in photo 3261)
- FCC ID, if shown:
- Rated power: 48 W (base label)
- Original power input: DC 16.8 V, 2000 mA (base label; this is the product input, not a Pi supply)
- Input polarity: center-positive, supported by user-reported ~0 ohm continuity from the power socket outer sleeve to the robot battery-negative contact on 2026-08-29; user reconfirmed this test was actually performed
- Chassis dimensions:
- Original functions that should be preserved: drivetrain, camera/front optics, audio, original controller/driver boards, battery bay and charging path, dispenser/launcher actuators, buttons/LEDs, wiring and connectors

## Battery

- Label text: `18650-2200mAh 11.1V 4400mAh 48.84Wh`; `HL-3S2P-44/2018-12-27`
- Chemistry: likely lithium-ion 18650 pack; chemistry still to be confirmed from documentation or pack construction
- Configuration: label identifies 3S2P
- Nominal voltage: 11.1 V
- Rated capacity: 4400 mAh / 48.84 Wh
- Manufacturing/date marking: 2018-12-27
- Connector and wire colors: two-pin white locking connector; red positive and black negative by conventional color only—polarity must be measured
- Measured disconnected voltage: **UNVERIFIED**. The reported 0.45 V was later clarified as an individual-cell attempt rather than a validated pack-output measurement, and subsequent electrical claims were withdrawn as unreliable.
- Condition: no obvious swelling or puncture visible in photos 3263/3264; electrical condition and cell balance unknown; pack is more than seven years old
- Decision: **QUARANTINED — DO NOT CHARGE OR USE.** The pack is more than seven years old, its protective wrap has been removed, its cell-group balance and BMS state are unknown, and no trustworthy output measurement exists. Evaluation requires a qualified battery technician or properly insulated pack-test equipment.
- Replacement target (not yet purchased or connected): protected **3S lithium-ion**, 11.1 V nominal / 12.6 V full, approximately 4400 mAh, with a discharge rating suitable for the robot's measured motor current. The original lead is a two-wire white locking connector, but connector family, contact pitch, and polarity are not yet measured. Use a reversible adapter; do not cut the factory loom or identify the connector by appearance alone.
- Power-path finding (2026-09-09): with the battery absent and the 16.8 V adapter attached, Android reports `mPlugType=2`, the factory Android board runs, and the STM32 returns valid version and heartbeat frames. This proves logic/STM32 power only. It does **not** prove that the motor-driver rail is powered or that movement is permitted while the charge/external-power input is present. Battery-required or charging-interlock behavior remains a live hypothesis.

## Motors and actuators

| ID | Physical function | Label | Wire pair/connector | Resistance | Test voltage | No-load current | Notes |
|---|---|---|---|---:|---:|---:|---|
| M1 | Left/right drivetrain candidate | Unreadable | Original harness |  |  |  | Two horizontal geared motors are visible in photo 3267; exact left/right mapping unverified |
| M2 | Left/right drivetrain candidate | Unreadable | Original harness |  |  |  | Two horizontal geared motors are visible in photo 3267; exact left/right mapping unverified |
| M3 | Center mechanism candidate | Unreadable | Original harness |  |  |  | One vertically oriented geared motor is visible in photo 3267; function unverified |
| M4 | Internal actuator | `28BYJ4`, `5V DC`, `NO:1812`, `WKX` | Blue leads/connected harness |  |  |  | Visually resembles a small geared stepper, but winding count and function must be traced |
| A1 | Internal solenoid/electromagnet candidate | No readable label | Two blue leads |  |  |  | Yellow coil in metal frame visible in photo 3260; function and rating unverified |

## Original VAVA boards

| ID | Board markings | Connected devices | Connector notes | Keep/remove/unknown |
|---|---|---|---|---|
| B1 | `SG_802_TD_V1.2_CTL`, `2018-12-21`; component-side text also includes `13QD3ES` | Camera/front assembly, audio parts, multiple actuators and sensors through factory harnesses | Sharp photo confirms `J18` left-to-right order: `VCC`, `RXD`, `TXD`, `SET`, `CS`, `GND`. A separate `J4` header appears labeled `SDA`, `SCL`, `GND`, `VCC`. Voltages and protocols remain unverified. | Preserve and characterize |
| B2 | `AB002_D3.01 O-FLASH` | Camera/network subsystem candidate | Board-to-board/FFC connections; exact role unverified | Preserve and characterize |
| B3 | Connector/distribution board dated `2018.12.24` | Battery and original peripheral harnesses | Silkscreen includes `BATTERY J2`. Visible legend in `J18_HEADER_MARKED.png`: `J5 DL-T`, `J6 DL-L`, `J7 DL-B`, `J8 DL-R`, `J9 SMJC-T`, `J10 P2-B`, `J11 P2-A`, `J12 B2`, `J18 SMJC-T`, `J19 SMJC-B`. Meanings unverified. Nearby headers `J17`, `J21`, `J22` are populated. | Preserve and map |
| B4 | Small narrow sensor/contact board, markings unreadable | Mounted near lower front of shell | Multi-wire connector | Preserve and identify |

## Original VAVA subsystem preservation decisions

| Subsystem | Present | Works in original configuration | Supply/interface identified | Planned use | Evidence |
|---|---|---|---|---|---|
| Chassis/drivetrain | Yes | Unknown | No | Preserve | Tracks/wheels/shafts visible in 3261/3263 |
| Drive motors/gearboxes | Yes | Unknown | No | Preserve | Multiple geared motors visible in 3267 |
| Pan/tilt mechanism | Unconfirmed | Unknown | No | Inspect | Front camera enclosure visible, mechanism not sufficiently exposed |
| Battery/protection board | Battery yes; protection board internal/unconfirmed | Unknown | Pack label identified; live voltage unknown | Test before deciding | 3263/3264 |
| Charging contacts/dock | Unconfirmed | Unknown | No | Inspect | Need dock, adapter and underside contact photos |
| Main control board | Yes | Unknown | Candidate UART/I2C headers found; voltages unknown | Preserve and reverse-engineer | 3265/3266/3267 |
| Motor driver board | Possibly integrated into main board | Unknown | No | Preserve if commandable | Driver IC markings need close photos |
| Camera module | Yes | Unknown | No | Preserve; test original stream | 3260/3262 |
| Microphone(s) | At least one visible | Unknown | No | Preserve | Electret microphone visible on B1 in 3266 |
| Speaker/amplifier | Connector labeled `SPK`; speaker itself not confirmed | Unknown | No | Preserve if present | 3265 |
| LEDs/buttons | Yes | Partial pass: red and blue LEDs plus beep observed during adapter test | No | Preserve | Power button/front indicators visible in 3261/3262; live response reported 2026-08-29 |
| Other sensors | Several candidate boards/connectors | Unknown | No | Preserve and map | 3260/3265/3267/3268 |

## New controllers

- Raspberry Pi 3B exact revision:
- Raspberry Pi 400 available power supply:
- ESP32 exact board name and module marking: ESP-32U development board with external-antenna connector; exact module revision/regulatory text needs a sharper close-up
- L298N board 1 markings/jumper positions: standard red `HW-095`-style dual H-bridge module visible; terminals marked `+12V`, `GND`, `+5V` and `OUT1`–`OUT4`; installed jumpers need to be recorded before use
- L298N board 2 markings/jumper positions:

## Displays

- 3.5-inch display brand/model:
- 3.5-inch interface (GPIO/HDMI/other):
- 3.5-inch touch controller:
- 7-inch display brand/model:
- 7-inch power input:
- 7-inch native resolution:

## Available build supplies

- Multimeter:
- Current-limited bench supply:
- Soldering iron:
- Heat-shrink:
- Inline fuse/fuse holder:
- Physical power switch or emergency stop:
- Buck converter(s), with model/rating:
- microSD card(s), with capacities:
- USB cables/adapters:

## Red USB power bank

- Internal cell label: `1260110-10000mAh`, 3.7 V, 37 Wh; other printed code appears as `202601816` but its meaning is unverified
- Construction: one large lithium-polymer pouch cell connected to a USB power-bank controller/display board
- Visible ports: USB-C, Lightning-labeled input, Micro-USB, and four USB-A ports; the exact input/output role and rating of every port remain unverified
- Display: percentage-style numeric display visible
- Physical condition from photos: pouch appears flat; housing is open, so the board and cell wiring require enclosure before mobile use
- Approved provisional role: candidate isolated 5 V source for Pi/display/phone logic only after output voltage, current rating and load stability are verified
- Not approved for: VAVA 16.8 V input, original 11.1 V motor-battery replacement, or direct L298N motor power

## External adjustable adapter

- Type: adjustable universal AC/DC adapter with interchangeable barrel tips
- Label input: 100-240 V AC, 50/60 Hz
- Label output: DC 3-24 V, 3 A maximum
- Selected setting shown in photo: display appears to show 16.8 V; actual output is unverified
- Measured output: 16.8 V reported with red probe at barrel center and black probe at outer sleeve; no minus sign reported, indicating center-positive; user reconfirmed this test was actually performed
- Capacity gate: label rating passes the VAVA 16.8 V DC, 2 A requirement on paper only
- Plug fit: snug, user reconfirmed
- Live robot test: logic-power pass on 2026-08-29 with battery removed. After the power button, red/blue LEDs and a repeated pattern of two fast beeps were observed. No camera, wheel or other actuator movement was noticed. No unusual heat or odor was reported. User reconfirmed these observations were genuine. Motor functionality remains unverified because no motion command was issued.
- J18 power/serial measurements: **PERFORMED 2026-09-07**, battery out, 16.8 V adapter, robot on. Unpowered: `GND` continuity to barrel outer sleeve **PASS** (beep); `VCC` not shorted to `GND` **PASS** (no beep). Powered: `VCC` **0 V**, `TXD` **0.01 V**, `RXD` **0.01 V**. Silkscreen confirmed left-to-right: `VCC`, `RXD`, `TXD`, `SET`, `CS`, `GND`. Header is unpowered. Do not attach Pi/ESP32/L298N to J18.
- J21 serial interface: populated four-pin header labeled left-to-right `TX`, `GND`, `RX`, `3.3V`. Fitted two-wire cable: red on `TX`, black on `GND`. `TX` to `GND` **3.333 V** (2026-09-02). `3.3V` pin to `GND` **3.33 V** (2026-09-07) while J18 `VCC` was 0 V, proving the robot was powered. Approved for passive ESP32 receive on `TX`/`GND` only; VAVA `RX` and `3.3V` remain disconnected.
- J22 interface: populated four-pin header labeled `GND`, `CLK`, `DIO`, `3.3V`. User measured `3.3V` vs `GND` as the same rail as J21 (**~3.33 V**, 2026-09-07). Candidate STM32 SWD (`SWCLK`/`SWDIO`) or similar debug bus; not approved for attach. Leave disconnected.

## Photo checklist

- [ ] VAVA product label
- [ ] Battery label and connector
- [ ] Entire open chassis from directly above
- [ ] Each circuit board, front and back
- [ ] Each motor and its wires
- [ ] Connector locations before further disassembly
- [ ] ESP32 top and bottom
- [ ] Display controller markings

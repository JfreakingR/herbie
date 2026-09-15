# First VAVA Power Test — Battery Removed

Do not perform this test until every prerequisite is satisfied.

## Prerequisites

- [ ] Failed/exposed battery is disconnected and physically away from the robot.
- [ ] Adapter label supports 16.8 V DC at 2 A or more.
- [ ] Adapter output measures approximately +16.8 V with red at center and black at outer sleeve.
- [ ] Robot socket outer sleeve has continuity to system/battery negative, confirming center-positive polarity.
- [ ] Selected barrel tip fits snugly without force or wobble.
- [ ] All original factory connectors needed for the test are returned to their photographed positions; no loose connector can touch a board or chassis metal.
- [ ] No Pi, ESP32, L298N, display, or phone is connected.
- [ ] Wheels/tracks and moving mechanisms are raised clear of the bench.
- [ ] Robot sits on a clean, nonconductive, nonflammable surface with ventilation.
- [ ] A quick way to unplug AC power is within reach.

## Test

1. Set the robot's physical power control to OFF, if it has an OFF state.
2. Set the adapter to 16.8 V and verify the display before connection.
3. Plug the barrel connector into the unpowered robot.
4. Plug the adapter into AC power.
5. For 10 seconds, do not turn the robot on. Watch, listen and smell for heat, smoke, arcing, buzzing, clicking, or odor.
6. If normal, activate the robot's power button once.
7. Observe for no more than 15 seconds: LEDs, sounds, camera movement, wheel movement, dispenser movement, or fault behavior.
8. Unplug AC power regardless of the result.
9. Wait two minutes, then check for unusual warmth without touching exposed conductors.
10. Record exactly what happened.

## Immediate stop conditions

Unplug AC power immediately for smoke, unusual odor, sparking, rapid heating, continuous stalled-motor noise, severe vibration, or unexpected movement that could contact the bench.

## Result

- Date/time:
- Plug fit: snug, user reconfirmed
- Standby behavior: no behavior reported before the power button
- Power-button behavior: red/blue indicator response and repeated audible pattern occurred after pressing the power button
- LEDs: red and blue observed
- Sounds: two fast beeps repeated several times
- Camera/front assembly movement: no movement noticed
- Wheels/tracks movement: no movement noticed
- Other actuator movement: no movement noticed
- Unusual heat/odor/noise: none reported after the short test
- Overall gate: **PASS FOR LOGIC POWER** — the user clarified that the adapter, continuity and live VAVA tests were genuine; only the later nonexistent USB-ground/J18 step was not performed. Camera, motors and actuators remain functionally unverified.

## Next measurement — J18 voltages only

Do not attach a Pi, ESP32, L298N, phone, or USB-serial adapter to J18 until `VCC` versus `GND` is recorded. J18 `VCC` might be 3.3 V, 5 V, or a higher rail.

This is **not** J21. J21 is the 4-pin header already fitted with the red/black pigtail (`TX` / `GND`). Leave that cable alone.

### Which holes

Use the green distribution board over the drive motors, the same view as `J18_HEADER_MARKED.png`: kettle/AIFEEL in the background, motors in the middle, green board along the far edge.

J18 is the row of **six empty round holes** at the left end of that green board, circled in red in that photo. It sits just left of a white 6-pin plug that already has wires in it. Do not probe that white plug.

With the board in that same view, left-to-right the empty holes are:

| Hole | Closest landmark | Label |
|---:|---|---|
| 1 | leftmost, at the board edge, under the printed `J18` | `VCC` |
| 2 | next inward | `RXD` |
| 3 | middle-left | `TXD` |
| 4 | middle-right | `SET` — skip |
| 5 | next | `CS` — skip |
| 6 | rightmost empty hole, closest to the white 6-pin plug | `GND` |

If the silkscreen in front of you does not match that order, stop and photograph the labels before probing.

### Meter

- Continuity / ohms only with AC unplugged.
- Live work: DC volts, 20 V range, or auto-range.
- Black probe = ground. Red probe = the hole being tested.
- Touch only the metal rim of one hole at a time. Do not let the tip bridge two holes.

### Unpowered continuity — AC unplugged

1. Battery out. Adapter unplugged from the wall.
2. Black on the barrel **outer sleeve** (already known as battery-negative). Red on J18 hole 6 (`GND`). Expect continuity / near 0 Ω. Write the reading.
3. Black on J18 hole 6 (`GND`). Red on J18 hole 1 (`VCC`). Expect **no** continuity (open / no beep). If it beeps, stop; `VCC` is shorted to ground.

### Powered voltages — battery still out

1. Set the adapter to 16.8 V. Plug it into the robot, then into the wall, as in the logic-power test.
2. Press the robot power button once. You should get the same red/blue LEDs and double-beep as before. If not, unplug and stop.
3. Keep black on J18 hole 6 (`GND`). Move red to:
   - hole 1 `VCC`
   - hole 3 `TXD`
   - hole 2 `RXD`
4. Write each voltage, including the sign. Then unplug AC.

Do not probe holes 4 or 5 (`SET`, `CS`) this round.

### How to read the numbers

- `VCC` about **3.2–3.4 V**: 3.3 V logic. Safe to discuss an ESP32 listen later.
- `VCC` about **4.8–5.2 V**: 5 V. Do not connect a Pi/ESP32 pin until a level shifter is chosen.
- `VCC` about **16–17 V**, or anything above **6 V**: stop. That is not a logic pin. Do not attach the Pi or ESP32.
- `VCC` about **0 V**: the header is unpowered or the robot is off.
- `TXD` near the same voltage as a 3.3 V `VCC` is normal UART idle-high. `TXD` stuck at 0 V with a good `VCC` may still be usable, but note it.

Stop and unplug for smoke, odor, sparking, heat, or unexpected motion. Send the three voltages and the two continuity results.

## Result — J18 / J21, 2026-09-07

- Unpowered `GND` to barrel sleeve: continuity **PASS** (beep).
- Unpowered `VCC` to `GND`: open **PASS** (no beep).
- Powered J18: `VCC` **0 V**, `TXD` **0.01 V**, `RXD` **0.01 V**.
- Powered J21 `3.3V` to `GND`: **3.33 V** (robot was on; J18 is simply unpowered).

Gate: **J18 is not a live supply or UART. Do not attach Pi, ESP32, or L298N to J18.** Keep serial on **J21 `TX`/`GND` only**, passive listen. Do not connect J21 `RX` or J21 `3.3V`. Motor authority stays off.

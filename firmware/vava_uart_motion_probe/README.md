# Herbie direct UART motion probe

This is a deliberately narrow, one-shot motion test for the original STM32 controller with the blue Android board removed. The earlier `vava_uart_version_probe` received a checksum-valid `0xA6` board-version response over J21, proving direct two-way communication. This probe uses the same GPIO34 receive / GPIO17 transmit path.

The only motion frame is `00 AA 55 00 07 22 50 01 03 F4 01 7D`: original `CONTROL_SERVO` protocol, sequence `0x50`, drive servo 1, action 3, 500 ms duration. Action 3 is factory "backward", but since the track motor plugs were swapped on 2026-09-26 it drives Herbie forward (confirmed through the Android board the same day). The 09-20 tests below used the old frame (sequence `0x48`, action 4). No other direction or duration is available. It requires `ARM` followed by `DRIVE` within 15 seconds over USB serial. The frame is sent at most once per ESP32 boot; an uncertain result must never be retried automatically. GPIO17 returns to input after 1.5 seconds. The ESP32 reports checksum-checked replies and IR events but never bypasses STM32 sensing.

Before the physical test: original blue board absent, old battery disconnected, 16.8 V adapter and unplug point confirmed, Herbie on a clear level floor, original sensor harnesses intact, and a person watching the robot. Turn off the adapter immediately for unexpected motion, heat, odor, smoke, or sparking. A board acknowledgement alone does not prove physical movement; record both the UART frames and what the owner sees.

This probe does not implement autonomous movement or a motor safety controller. The USB connection powers only the ESP32. J21 `3.3V` and J22 remain unconnected.

## First direct test, 2026-09-20

With the blue Android board absent and J21 connected to the ESP32, the command was sent exactly once:

```text
DRIVE_SENT_ONCE: forward 500 ms seq 0x48
FRAME VALID: AA 55 00 07 22 48 01 04 F4 01 62
FRAME VALID: AA 55 00 09 01 80 48 22 00 00 00 00 1D
FRAME VALID: AA 55 00 05 25 81 0B 01 54
FRAME VALID: AA 55 00 07 02 82 00 5A 00 00 22
```

The controller acknowledged the motion command (`src_sequence=0x48`, `src_command=0x22`, `result=0`) and then emitted infrared key event `0x0B`. A heartbeat followed. The owner reported two beeps and no track movement. The key event and beeps are consistent with the earlier IR safety refusal. Do not infer movement from the acknowledgement and do not retry automatically.

## Second direct test, same day

After an explicit owner request to repeat the test, the ESP32 was reset through USB and sent the same 500 ms command once. The STM32 again returned a checksum-valid `0x01` acknowledgement with `src_sequence=0x48`, `src_command=0x22`, and `result=0`, then a checksum-valid `0x25` infrared key event with key `0x0B`, followed by a heartbeat. The board reply sequence advanced (`0xD4`/`0xD5`/`0xD6`), so this was a distinct second exchange. The owner reported no track movement. No further automatic retry.

## Rear board button observation, same day

With the upper half and some sensor connections absent, the owner pressed the button on the rear of the controller board. Herbie repeatedly drove forward and backward under his own power. The ESP32 only listened; it sent no motion command during this observation. It captured a checksum-valid key event `AA 55 00 05 25 A0 01 01 7F`, followed by `AA 55 00 05 25 A1 0B 01 74` and heartbeats. This establishes that the original motor power path and controller can move the tracks in the current partial assembly. It also corrects the overly broad inference above: key `0x0B` is not, by itself, proof that all movement is vetoed, since the built-in forward/backward cycle continued after that event. Why the external `CONTROL_SERVO` command was acknowledged but produced no movement remains unresolved.

## Third direct test, 2026-09-27 (blue Android board installed)

With the blue board still installed and running, the updated frame (`0x50`, action 3, forward 500 ms) was sent once after a `QUERY` from the version probe. The controller acknowledged it (`src_sequence=0x50`, `result=0`), then emitted infrared key event `0x0B`. The owner heard one beep and saw no movement.

Side effect: after the ESP32 transmitted on J21, the controller stopped answering the blue board. The factory app's routine `0x24`/`0x25` frames and a direct `0x51` drive through `tools/Send-Herbie-Frame.py` all went unanswered, even with J21 `RX` moved back to input-only GPIO35. In the controller's reply counter, the blue board's last reply (`0x1C`) comes right before the ESP32's version reply (`0x20`). A full power-cycle of Herbie restored the blue board's link. Assume that **one ESP32 transmit on J21 leaves the Android path dead until Herbie is power-cycled.**

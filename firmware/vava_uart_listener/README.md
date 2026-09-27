# Passive two-channel VAVA UART listener

This sketch listens to both original VAVA UART signals without sending commands back to the robot. GPIO34 and GPIO35 are input-only in hardware on the classic ESP32, so the listener cannot drive either line.

## Verified electrical fact

The user measured `3.333 V` from `J21 TX` to `J21 GND`, using the fitted red/black two-wire connector. This is compatible with an ESP32 3.3 V GPIO input.

## Wiring

Make all connections with both devices powered off:

| VAVA J21 | Cable | ESP32 |
|---|---|---|
| TX | identify from J21 label/pinout | GPIO34 |
| RX | identify from J21 label/pinout | GPIO35 |
| GND | identify from J21 label/pinout | GND |

Leave VAVA `3.3V` disconnected. Do not connect any ESP32 TX/output pin to J21. Power the ESP32 only through USB. Use only Herbie's already-verified power arrangement.

## Operation

1. Flash the sketch to the ESP32 while the VAVA cable is disconnected.
2. Disconnect USB power after flashing.
3. Connect VAVA `TX` to ESP32 `GPIO34`, VAVA `RX` to ESP32 `GPIO35`, and VAVA `GND` to ESP32 `GND`.
4. Reconnect ESP32 USB and open the serial monitor at 115200 baud.
5. Select a candidate VAVA baud rate using keys `1` through `7`.
6. Power-cycle the VAVA and capture the displayed byte lines.
7. Repeat with another baud rate if output is absent or consistently garbled.

Each byte line ends with `J21_TX_REPLY` or `J21_RX_COMMAND`. The hexadecimal bytes remain in the middle column so the existing Herbie console can decode them. The most likely successful output will show repeatable binary frames after startup or an input event.

## Safety boundary

This firmware passes `-1` as the transmit pin for both hardware UARTs and uses GPIO34/35, which have no output drivers. VAVA `3.3V` and every ESP32 output pin must remain disconnected. This listener does not authorize or implement motor control.

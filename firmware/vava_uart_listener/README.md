# Passive VAVA UART Listener

This sketch listens to the original VAVA `J21 TX` signal without sending commands back to the robot.

## Verified electrical fact

The user measured `3.333 V` from `J21 TX` to `J21 GND`, using the fitted red/black two-wire connector. This is compatible with an ESP32 3.3 V GPIO input.

## Wiring

Make all connections with both devices powered off:

| VAVA J21 | Cable | ESP32 |
|---|---|---|
| TX | red | GPIO23 |
| GND | black | GND adjacent to GPIO23 |

Leave VAVA `RX` and `3.3V` disconnected. Power the ESP32 only through USB. Power the VAVA only through the previously verified 16.8 V center-positive adapter, with the old battery removed.

## Operation

1. Flash the sketch to the ESP32 while the VAVA cable is disconnected.
2. Disconnect USB power after flashing.
3. Install the two-wire cable between VAVA `TX/GND` and ESP32 `GPIO23/GND`.
4. Reconnect ESP32 USB and open the serial monitor at 115200 baud.
5. Select a candidate VAVA baud rate using keys `1` through `7`.
6. Power-cycle the VAVA and capture the displayed byte lines.
7. Repeat with another baud rate if output is absent or consistently garbled.

The most likely successful output will show repeatable bytes or readable text after each VAVA startup. Random-looking data at every same pattern may still be a binary protocol; inconsistent noise usually indicates the wrong baud rate.

## Safety boundary

This firmware never configures an ESP32 transmit pin for the VAVA connection. Do not add the VAVA `RX` wire until the captured protocol and safety behavior are understood.

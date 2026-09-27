# VAVA UART Protocol Notes

Device: VAVA Pet Cam VP-SPR001  
Interface observed: J21 `TX` and `GND` only  
Listener: ESP32 GPIO23, passive receive-only  
Serial settings: 115200 baud, 8 data bits, no parity, 1 stop bit

## Confirmed framing

Observed packets begin with:

```text
00 AA 55
```

## Idle/status packet

A 13-byte packet was observed approximately every 22 seconds while the VAVA
was powered and idle:

```text
00 AA 55 00 07 02 08 00 5A 00 00 A8 00
00 AA 55 00 07 02 09 00 5A 00 00 A9 00
00 AA 55 00 07 02 0A 00 5A 00 00 AA 00
```

The seventh byte increments. Its exact meaning is not yet confirmed.

For the observed framed packets, the checksum byte equals the XOR of all
preceding bytes in the frame. For example:

```text
00 XOR AA XOR 55 XOR 00 XOR 07 XOR 02 XOR 08 XOR 00 XOR 5A XOR 00 XOR 00 = A8
```

## Recapture — 2026-09-07

Passive listen on J21 `TX` → ESP32 GPIO23, J21 `GND` → ESP32 GND, 115200 8N1. Robot on 16.8 V adapter, battery out.

Idle frames matched the known 13-byte status packet, counter incrementing:

```text
00 AA 55 00 07 02 11 00 5A 00 00 B1
00 AA 55 00 07 02 12 00 5A 00 00 B2
00 AA 55 00 07 02 13 00 5A 00 00 B3 00
```

XOR checksum still holds. A power-button press again produced the version-text burst, plus shorter frames of the form `00 AA 55 00 05 25 ...` around that event. No transmit to J21 `RX` was performed.

## Button recapture — 2026-09-07 (~120 s)

Idle `00 AA 55 00 07 02` status continued, counter `80`–`8F`. Two power-button events each started with `00 AA 55 00 05 25` and then the same version-text dump. One extra short frame `00 AA 55 00 05 25 86 0B 01 53` sat between those events. No new frame type appeared for camera/wave in this window. Still listen-only.

## Power-button event

Pressing the physical power button produced a startup/identification burst
containing readable text:

```text
Software_version: SG_802_LD_MTK_TUTK_V1.2_TEST    2019-05-27
Hardware_version: SG_802_LD_V1.2_CTL              2018-12-24
Android_Hardware_version: A8002_MB80_D3_V1.0       2018-07-04
```

This event confirms that J21 TX carries a structured controller data stream.
It does not yet prove that J21 RX accepts control commands.

## Passive J21 RX observations

The ESP32 input was moved from J21 TX to J21 RX while retaining the common
ground. No continuous command stream was observed.

- At 115200 baud, a long power-button press produced a burst dominated by
  `FF` and `00`; it did not contain the known `00 AA 55` framing.
- At 57600 baud, powering the unit on produced only `FE`.

These captures are consistent with a floating/power-transition glitch or a
different signaling configuration. They are not evidence of valid commands.

## Safety boundary

- Do not connect the VAVA 3.3 V pin to the ESP32.
- Do not connect J21 RX until the transmit protocol and electrical behavior
  have been characterized further.
- Keep wheels raised during motion-command captures.

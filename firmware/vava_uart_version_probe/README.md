# Herbie STM32 version probe

This firmware proves whether the ESP32 can reach the original STM32 without the blue Android board. It sends only the previously captured `query_board_version` frame. There is no motion command or general-purpose UART forwarding.

The ESP32 is powered from computer USB. With both devices powered off, J21 `TX` connects to ESP32 GPIO34 and J21 `GND` to ESP32 `GND`. After the green board's 3.3 V rail and wiring are verified, J21 `RX` connects to ESP32 GPIO17 for the one query. J21 `3.3V` and J22 remain disconnected. The old battery remains out.

At startup GPIO17 is an input. The only accepted USB command is `QUERY` followed by a newline; it sends `00 AA 55 00 03 26 01 DB` once per ESP32 boot. It releases GPIO17 after 1.5 seconds so the response can be received first. Serial output reports receive statistics every two seconds and prints complete checksum-checked frames. A valid board-version response begins `AA 55 00 1D A6`.

2026-09-20 isolated loopback check: with Herbie disconnected and GPIO17 jumpered directly to GPIO34, the ESP32 printed `FRAME VALID: AA 55 00 03 26 01 DB`. This proves the query is transmitted and captured on the chosen ESP32 pins. The earlier probe version closed the UART too soon and discarded received bytes; its no-reply result should not be used as evidence about Herbie's STM32.

This is a non-motion communication check. It does not establish motor safety, battery suitability, or permission to drive.

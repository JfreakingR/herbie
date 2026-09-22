#line 1 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_motion_probe\\README.md"
# Herbie direct UART motion probe

This is a deliberately narrow, one-shot motion test for the original STM32 controller with the blue Android board removed. The earlier `vava_uart_version_probe` received a checksum-valid `0xA6` board-version response over J21, proving direct two-way communication. This probe uses the same GPIO34 receive / GPIO17 transmit path.

The only motion frame is `00 AA 55 00 07 22 48 01 04 F4 01 62`: original `CONTROL_SERVO` protocol, sequence `0x48`, drive servo 1, forward action 4, 500 ms duration. No other direction or duration is available. It requires `ARM` followed by `DRIVE` within 15 seconds over USB serial. The frame is sent at most once per ESP32 boot; an uncertain result must never be retried automatically. GPIO17 returns to input after 1.5 seconds. The ESP32 reports checksum-checked replies and IR events but never bypasses STM32 sensing.

Before the physical test: original blue board absent, old battery disconnected, 16.8 V adapter and unplug point confirmed, Herbie on a clear level floor, original sensor harnesses intact, and a person watching the robot. Turn off the adapter immediately for unexpected motion, heat, odor, smoke, or sparking. A board acknowledgement alone does not prove physical movement; record both the UART frames and what the owner sees.

This probe does not implement autonomous movement or a motor safety controller. The USB connection powers only the ESP32. J21 `3.3V` and J22 remain unconnected.

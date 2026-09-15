# Pal / Melba Handoff — 2026-09-07

Supersedes `PAL_HANDOFF_2026-09-05.md` as the current checkpoint. Keep the 09-05 file for Pi/SSH history.

## Goal

Galaxy S21 Ultra = Pal's AI-facing phone brain. Raspberry Pi 3B (`Melba`) = robot bridge/coordinator. Preserve original VAVA hardware. **Do not give AI code motor authority** until a separately verified motor-safety layer exists.

## Current checkpoint

Phone/Pi software phase remains verified from 2026-09-05 (not re-tested today). Hardware identification on 2026-09-07 closed the J18 voltage gate and reconfirmed J21 as the live 3.3 V UART.

### Done today — 2026-09-07

- **One green distribution board.** J18, J21, and J22 are all on that board.
- **J18** is six **empty holes** (no pins), labeled left-to-right: `VCC`, `RXD`, `TXD`, `SET`, `CS`, `GND`.
  - Unpowered: `GND` continuity to barrel outer sleeve **PASS** (beep). `VCC` not shorted to `GND` **PASS** (no beep).
  - Powered (16.8 V adapter, battery out, lights on): `VCC` **0 V**, `TXD` **0.01 V**, `RXD` **0.01 V**.
  - **Do not attach Pi / ESP32 / L298N. Do not solder a header.** It is an unpowered factory UART.
- **J21** four pins left-to-right: `TX`, `GND`, `RX`, `3.3V`.
  - `3.3V` vs `GND` **3.33 V** while J18 was 0 V (robot was on).
  - `TX` vs `GND` previously **3.333 V** (2026-09-02).
  - Red pigtail on `TX`, black on `GND`.
- **J22** four pins: `GND`, `CLK`, `DIO`, `3.3V`. `3.3V` matches J21 (~3.33 V). Treat as STM32 SWD. **Do not attach.**
- **Main controller** photo: `SE6POET SG_802_LD_V1.2_CTL` `2018-12-24`. MCU is **STM32F103**. Printed rails include `3.3V` and `+12V`. Power button and buzzer are on this board. Do not probe chips or corner pads.
- **ESP32** (ESP32-D0WD-V3, CP210x **COM7**, MAC `<ESP32_MAC>`) flashed with `firmware\vava_uart_listener`. Wiring: J21 `TX` → **GPIO23**, J21 `GND` → **GND**. USB only for ESP32 power.
- **Passive listen succeeded** at 115200 8N1:
  - Idle: `00 AA 55 00 07 02 NN 00 5A 00 00 <xor>`
  - Power button: `00 AA 55 00 05 25 …` then version text (`SG_802_LD_MTK_TUTK_V1.2_TEST`, `SG_802_LD_V1.2_CTL`).
- User confirmed: **original camera is not hooked up**. **No other buttons** besides power. Button-listen is exhausted until the camera (or another peripheral) is on the factory wiring.

### Immediate next action

Do **not** connect J21 `RX` or J21 `3.3V`. Do **not** attach to J18 or J22. Motors stay off. Battery stays out.

Highest-value next hardware step:

1. Find the original camera ribbon/plug and its **factory** empty socket. Photo both. Plug camera into that socket only (not ESP32/Pi/J21). Then adapter-power with wheels raised and listen on J21 again.
2. If camera wait: meter the empty `SDA` / `SCL` / `GND` / `VCC` holes on the **right** of the same green board (same VC830L procedure as J18: continuity first, then DC `20`).

Meter: **VC830L**. Continuity = diode/`)))` (or orange `200` Ω). Live volts = left-side DC **`20`** (`V⎓`), not AC `V~`. Black in `COM`, red in `VΩmA`.

```powershell
ping.exe -n 2 -w 1500 Melba.local
ssh.exe -6 -i "C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes jfreakingr@Melba.local "hostname; systemctl is-active pal-pi-bridge"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\Desktop\Drive\Pal\tools\Test-Pal-Pi-Bridge.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\Desktop\Drive\Pal\tools\Test-Pal-Phone-Brain.ps1"
```

## Green board map (readable silkscreen)

Top edge, left to right:

| Header | What it is | Status |
|---|---|---|
| J18 | 6 empty holes `VCC RXD TXD SET CS GND` | Unpowered. Ignore. |
| J15 | White 6-pin with red wires | Leave plugged. |
| J21 | 4 pins `TX GND RX 3.3V` | Live UART. Listen `TX`/`GND` only. |
| J22 | 4 pins `GND CLK DIO 3.3V` | Same 3.3 V rail. Likely SWD. Leave disconnected. |
| J26 | `SPK` | Speaker path. Later, after electrical check. |
| Right edge | Empty `SDA SCL GND VCC` | I2C candidate. Voltages **not** measured. |
| `BATTER J2` | Empty 2-pin | Battery disconnected. Keep it that way. |

Do not unplug populated motor/peripheral whites (`J5`–`J14` etc.) without photos.

## UART (J21)

Details: `VAVA_UART_PROTOCOL_NOTES.md`. Captures: `firmware\vava_listen_capture.txt`, `firmware\vava_listen_buttons.txt`.

- Listener sketch: `firmware\vava_uart_listener\`
- Flash: `arduino-cli` with config `tools\arduino-cli\arduino-cli.yaml`, FQBN `esp32:esp32:esp32`, port **COM7** when the ESP32 is on USB.
- Never connect VAVA `RX` or `3.3V` to the ESP32.
- J21 RX was probed passively in an earlier session; no valid command stream. Not evidence it accepts commands.

## Phone (not re-verified today)

- Galaxy S21 Ultra `SM-G998U`, Android 15. Screen badly broken; speaker damaged.
- ADB serial `R5CR11QCHPY`. scrcpy 4.1 local.
- `pal-phone-brain 0.1.0` in Termux. Last verified 2026-09-05: ready, heartbeat, `motor_authority:false`, `safe_motion_state:STOP`.
- Do not use the phone speaker as Pal's final audio.
- Do not write hotspot name/password into docs.

## Melba (not re-verified today)

- Pi 3B, Debian 13/Trixie, hostname `Melba`, user `jfreakingr`.
- Ethernet IPv6 link-local only. `wlan0` down. Do not wait on `network-online.target`.
- `pal-pi-bridge` 0.1.0 installed/enabled. Heartbeats passed 2026-09-05 with motors locked off.
- `vcgencmd get_throttled` has shown `0x50005` / `0x50000`. User said ignore that as a blocker.
- Automation key: `C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519` fingerprint `SHA256:Ae9a1UODBjH0g1ZucjhBSpBIyKD/P761Zv+Is0495sg`.
- Original passphrase key preserved: `pal_melba_ed25519`. Never copy private keys onto the Pi or into the repo.

## Safety

- Battery pack **quarantined** — do not charge or use. Power from the 16.8 V center-positive adapter only, battery out.
- Wheels/tracks raised for any powered test.
- Motor authority stays **false**, safe state **STOP**.
- Do not disassemble the S21.
- Do not expose Wi-Fi/hotspot passwords or old password guesses.

## Known dead ends

- J18 is not a usable serial/power header.
- Phone hotspot never brought Melba online (Pi 3B is 2.4 GHz). Direct Ethernet is the working path.
- Do not rerun `Repair-Melba-CloudInit.ps1` (invalid YAML).
- `rpi-preseed.toml` was ignored by this image.

## Project files

Root: `C:\Users\Phyllis\Desktop\Drive\Pal\`

- This handoff: `PAL_HANDOFF_2026-09-07.md` (Desktop copy too)
- `FIRST_POWER_TEST.md` — J18/J21 meter results
- `HARDWARE_INVENTORY.md` — measurement log
- `VAVA_UART_PROTOCOL_NOTES.md`
- `firmware\vava_uart_listener\`
- `phone_brain\`, `pi_bridge\`, `tools\`

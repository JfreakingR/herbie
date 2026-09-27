# PAL / VAVApet VP-SPR001 Handoff — BLE / Wi-Fi Checkpoint

**Date:** 2026-09-07  
**Status:** Factory ribbons connected; Pal boots and says **waiting for network config**. Official app is gone. Windows Bluetooth cannot provision Pal. ESP32 Just Works BLE writes to Pal succeeded (`ok=1`). Pal has **not** answered TUTK LAN discovery yet.  
**This file supersedes the network/app/next-step sections of `PAL_HANDOFF_2026-09-07_RIBBON_REASSEMBLY.md`.** Keep that file for boards, ribbons, and power safety. Keep `PAL_HANDOFF_2026-09-07.md` only for earlier UART / Melba / phone-brain history.

Desktop copies of prior handoffs also exist. Start from **this file**, not `pal 3.odt`.

## Goal

Preserve original VAVA electronics. Get Pal onto **2.4 GHz Wi-Fi** from this PC + ESP32. No motor authority. No factory reset. No lookalike apps. No Wi-Fi password in this repo, screenshots, logs, or handoff.

User constraint: **PC / ESP32 only.** Do not instruct phone pairing as the working path. Phone Bluetooth was used once to read Pal's advertised name; Android system pair failed and must not be retried.

## Device identity

- Product: VAVApet Pet Cam
- Model: `VP-SPR001`
- FCC ID: `2AFDGVP-SPR001`
- Original app: `VAVA Pet Cam` / `com.vava.pet` (2019, Sunvalley). **Play Store 404. No authentic APK obtained.**
- Firmware strings from J21 listen: `SG_802_LD_MTK_TUTK_V1.2_TEST`, `SG_802_LD_V1.2_CTL`
- BLE advertised name / TUTK UID: **`sgg6E5VF9GRNL2E99B7`**
- 2.4 GHz Wi-Fi only. 5 GHz is not supported.

Always scan Pal **by that name**, never by MAC. BLE address is random/private. Observed this session:

| Address | When |
|---|---|
| `48:20:27:48:5F:24` | Windows BLE connect / GATT dump |
| `7C:0C:91:05:FC:BF` | Later Windows GATT dump (`last-gatt-dump.txt`) |
| `4c:8e:1e:8c:99:a6` | ESP32 FOUND / Just Works connect |

## Current hardware / power (unchanged)

- Two electronics halves. Blue compute `A8002_MB80_D3_V1.0`. Separate green I/O board and green motion/controller board. Do not treat “J18” as unique without naming the board.
- Factory ribbons connected (wide `AWM 20861`, narrow `AWM 20624`). Black camera flex `R8097G23-C` stays plugged.
- Battery pack **quarantined**. Adapter-only: original 16.8 V center-positive. Tracks **raised**.
- `motor_authority=false`. Safe state `STOP`. No treat / laser / motor commands.
- Do **not** reset Pal (8-second power hold is factory reset).
- ESP32: ESP32-D0WD-V3, CP210x **COM7**, MAC `20:50:0d:07:a0:e4`. USB power only.
- **J21 UART listen cable must stay unplugged** while `pal_ble_wifi` is on the ESP32. Do not attach VAVA `RX` or `3.3V`. Unplug J21 before any BLE flash.

## What was tried

### 1. Official app — blocked

Details: `software\vava-pet-cam\APP_RECOVERY_NOTES.md`.

- Google Play `com.vava.pet` → 404.
- No authentic APK hashed, signature-checked, or installed.
- Reject: VAVA Home (`com.vava.ipc`), VAVA Dash, APKPure installer, Softonic “VAVA Home”, Uptodown Vava.chat, random “Vava” APKs.

### 2. Windows BLE app — dead end

Built: `software\pal-wifi-setup\` (Python / tkinter / bleak). Launch: `Start Pal Wifi Setup.cmd`.

It **can** live-scan Pal by name and dump GATT. It **cannot** write Wi-Fi credentials.

Facts:

- Stop live scan **before** connect (otherwise “Connect failed”).
- `bleak.pair()` True + WinRT `is_paired=True` is a **hollow bond**. Pal never appears in the Windows PnP Bluetooth device list.
- Characteristic `00002aba-0000-1000-8000-00805f9b34fb` (SIG name **HTTP Control Point**) is the only writable GATT char. Properties: write, read, notify. CCCD `2902`.
- Windows reads of Device Name (`2A00`) work. **All 2ABA read / write / notify / CCCD writes return Access Denied.**
- Windows Settings **Add a device** with DISPLAY_PIN shows “Enter this PIN on Pal” (example PINs 103962, 046812). Pal has **no keypad**. User could not enter a PIN anywhere. That ceremony is unusable.
- CONFIRM_ONLY custom pairing never completed a real bond (`PairingRequested` often never fired).
- Do **not** reopen Windows Add device. Do **not** unpair a “bond” that was never a real PnP device. Do **not** pair Pal as a headset/keyboard.

Phone Settings (one observation): Pal listed as `sgg6E5VF9GRNL2E99B7`, confirmation code, **Couldn't pair**. Expected. Do not retry.

### 3. ESP32 BLE central — working path

Sketch: `firmware\pal_ble_wifi\pal_ble_wifi.ino`  
Flash: `firmware\pal_ble_wifi\Flash-Pal-Ble-Wifi.ps1`  
Core: Arduino ESP32 **3.3.11**, FQBN `esp32:esp32:esp32`, NimBLE-era BLE lib.

Pairing is **Just Works** (`BLESecurity::setCapability(ESP_IO_CAP_NONE)`). Do **not** call `BLEDevice::setEncryptionLevel` (not a member on this core).

Serial **115200**:

```
SCAN
SSID=your2.4ghz-name
PASS=your-password
SEND
```

`PASS` is not echoed. Password length was 12 characters; the SSID used was recorded as `MySpectrumwifi20_2g` (19 chars). **That SSID was wrong.** A scan from Melba on 2026-09-09 shows the actual broadcasting 2.4 GHz network is `MySpectrumWiFi20-2G_EXT` (channel 11, WPA2) - different capitalisation, hyphens rather than underscores, and an `_EXT` suffix. SSIDs are exact, so every BLE provisioning attempt above sent Pal a network name that does not exist. Retry with the correct SSID before concluding anything about the `2ABA` characteristic. **Never write the password into this repo.**

**COM7 DTR rule:** `DtrEnable=true` (default SerialPort / some monitors) **resets the ESP32 and drops BLE**. Open COM7 with `DtrEnable=false` and `RtsEnable=false`. Keep the port open until `WRITE ... ok=` prints. An earlier session set SSID/PASS then printed `SEND_DONE` with **no WRITE lines** because the serial session ended too soon; credentials were still in ESP32 RAM.

### GATT map (same on Windows and ESP32)

```
SERVICE 00001800  Generic Access
  CHAR 00002a00  Device Name  [read]
  CHAR 00002a01  Appearance   [read]
SERVICE 00001801  Generic Attribute
  CHAR 00002a05  Service Changed  [indicate]
SERVICE 0000180a  Device Information
  CHAR 00002aba  HTTP Control Point  [write, read, notify]
    DESC 00002902  CCCD
```

No other writable characteristic was found. `2ABA` sitting under Device Information is vendor-sloppy; it may still be the Wi-Fi pipe, or it may be a real HTTP Control Point that ignores SSID/password payloads.

## Latest result (this session)

User said **ready** with Pal against the ESP32. COM7 opened **without DTR reset**. ESP32 still had Pal and still had SSID/PASS in RAM from the earlier session.

```
WRITE len-prefixed len=33 ok=1 (password not printed)
WRITE json         len=56 ok=1 (password not printed)
WRITE newline      len=32 ok=1 (password not printed)
SEND done. Watch Pal Wi-Fi LED.
```

Those three writes are ATT-layer success only. They do **not** prove Pal joined Wi-Fi.

This PC was `192.168.1.104` on `Wi-Fi 2`. TUTK UDP probe to `255.255.255.255` ports **32761, 49182, 32108, 12315**: **no replies**. ARP neighbors after wait: `192.168.1.1` (router), `192.168.1.169`, `192.168.1.200` / `.241` (same MAC). Pal did not appear as a new DHCP host.

Factory LED hint - **corrected 2026-09-09 from the VP-SPR001 manual** (`a5def2.pdf`, LED Indication table): Wi-Fi indicator **fast flash = connecting**, **slow flash = not connected**, **solid = connected**. An earlier note here had the flash rates the wrong way round, which inverts how Pal's response to the `ok=1` writes should be read: a slow flash means Pal rejected or ignored the credentials, not that it is still trying. (The manual's table extracts with interleaved columns, so confirm against the page before relying on it.) The manual also confirms 2.4 GHz only, and that the phone must be on Wi-Fi with Bluetooth enabled before the app runs. User had not reported the LED after these writes.

## Open hypotheses (in order)

1. Pal accepted GATT writes but `2ABA` is not the Wi-Fi provision pipe (SIG HTTP Control Point opcodes vs vendor JSON).
2. Pal needs notify/CCCD enabled, a different payload, or `secureConnection()` before it acts.
3. Pal is still joining, or joined with no TUTK LAN service (vendor cloud/P2P may be dead).
4. **SSID was wrong entirely - confirmed 2026-09-09.** The real network is `MySpectrumWiFi20-2G_EXT`, not `MySpectrumwifi20_2g`. This is now the leading explanation for writes being accepted (`ok=1` is only ATT-layer success) while Pal never joined: it was handed a nonexistent SSID. Retry with the correct name before pursuing hypotheses 1-3.
5. Five-minute provision window / Pal still saying waiting for network config.

## How to continue (PC / ESP32 only)

Keep Pal against the ESP32. Do not open Windows Add device. Do not type any PIN.

### A. If the Wi-Fi LED is solid / Pal sounds like it joined

1. Check the router DHCP list for a new 2.4 GHz client.
2. Re-run TUTK LAN search from `software\pal-wifi-setup\` or the same UDP ports.
3. Even a LAN join may not restore cloud video. TUTK for this 2019 product may be dead. That is still a useful factory-path result.

### B. If the LED is unchanged / still waiting for network config

Stay on ESP32. Do **not** go back to Windows BLE.

1. Confirm Pal still says waiting for network config; power-cycle Pal (short press, **not** 8-second reset) if the five-minute window expired, then `SCAN` immediately.
2. Improve `pal_ble_wifi.ino` before the next SEND:
   - After connect, call `gClient->secureConnection()` and print success/fail.
   - Enable notify + write CCCD on `2ABA`; print notify payloads (redact secrets).
   - Add the extra payload formats already in `pal_wifi_setup.py` (`wifi_ssid` JSON, NUL-separated, ssid-only).
   - Print `SEND start` before writes. Add a `STATUS` command (connected? write char? SSID length?).
   - Do not set `gConnected=false` on `SCAN` without disconnecting; a connected Pal may not advertise.
3. Open COM7 with DTR off, `SCAN`, set SSID/PASS, wait for `Using write char`, then `SEND`, wait for `WRITE ... ok=`.
4. Prefer an isolated 2.4 GHz SSID if the household AP is 5 GHz-primary or band-steering.

### C. If BLE provisioning is exhausted

Read-only discovery only:

1. Unplug ESP32 USB. Flash `firmware\vava_uart_listener\` **after** confirming J21 cable is off during flash.
2. Re-attach J21 `TX` → GPIO23, `GND` → GND. Never `RX` / `3.3V`.
3. Capture blue-board labelled UART only after metering. Do not use SP Flash Tool Download/Format/erase.
4. Correlate startup / network-prompt text. Still no motor commands.

## Serial helper (do not save the password)

```powershell
$sp = New-Object System.IO.Ports.SerialPort 'COM7',115200,'None',8,'One'
$sp.DtrEnable = $false
$sp.RtsEnable = $false
$sp.Handshake = 'None'
$sp.Open()
# write SCAN / SSID= / PASS= / SEND, keep port open until WRITE lines
# never log PASS= contents; redact if an exception dumps the buffer
$sp.Close()
```

Flash (J21 cable unplugged):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\Desktop\Drive\Pal\firmware\pal_ble_wifi\Flash-Pal-Ble-Wifi.ps1"
```

## Do not do next

- Do not reset Pal.
- Do not install VAVA Home, VAVA Dash, APKPure, or any unverified APK.
- Do not use Windows Add device / PIN dialogs.
- Do not pair Pal as a headset, keyboard, or speaker.
- Do not write the Wi-Fi password into the repo, handoff, screenshots, or session logs.
- Do not connect J21 `RX` or VAVA `3.3V` to the ESP32.
- Do not flash or format the MediaTek board.
- Do not reconnect the quarantined battery.
- Do not command motors, treat, or laser. Keep tracks raised.
- Do not unplug the black camera flex.
- Do not leave a live-scan Windows BLE app running while the ESP32 is scanning (they steal Pal).

## Project files

Root: `C:\Users\Phyllis\Desktop\Drive\Pal\`

| Path | What |
|---|---|
| `PAL_HANDOFF_2026-09-07_BLE_WIFI.md` | **This checkpoint** |
| `PAL_HANDOFF_2026-09-07_RIBBON_REASSEMBLY.md` | Boards, ribbons, first boot after reconnect |
| `software\vava-pet-cam\APP_RECOVERY_NOTES.md` | Official app dead ends |
| `software\pal-wifi-setup\` | Windows BLE tester (GATT dump only; writes fail) |
| `firmware\pal_ble_wifi\` | **Firmware currently on COM7** |
| `firmware\vava_uart_listener\` | Passive J21 listen (not currently flashed) |
| `VAVA_UART_PROTOCOL_NOTES.md` | STM32 listen protocol |

## Immediate continuation question

Ask the user what Pal's **Wi-Fi LED** did after the `ok=1` writes (unchanged / blinking / solid / voice). Then:

1. LED joined → DHCP + TUTK LAN search.
2. LED unchanged → ESP32 firmware notify + more payloads + DTR-safe SEND, still no Windows PIN.
3. BLE exhausted → read-only UART, still no motors.

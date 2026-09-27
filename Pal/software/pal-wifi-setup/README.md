# Pal Wi-Fi Setup

Small Windows app to **test Pal's factory Bluetooth pairing window** and send **2.4 GHz Wi-Fi credentials**.

It does **not** command motors, treats, or the laser. `motor_authority` stays off.

This is not the old Play Store app `com.vava.pet`. Pal's firmware uses TUTK; even a successful Wi-Fi join may not restore cloud video.

## What you need

- Pal powered from the **16.8 V adapter**, battery still out
- Tracks **raised**
- A **2.4 GHz** network Pal can reach (not 5 GHz)
- This Windows PC's Bluetooth on (Intel Wireless Bluetooth is already present)
- Pal saying **waiting for network config** — pairing is meant to finish within about **five minutes**

Do not type the household Wi-Fi password into any project file, screenshot, or chat. Prefer an isolated 2.4 GHz test SSID.

## Run

Double-click `Start Pal Wifi Setup.cmd` in the Pal folder, or:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\Desktop\Drive\Pal\software\pal-wifi-setup\Start-Pal-Wifi-Setup.ps1"
```

## Test steps

1. Power Pal on. Wait for startup music and **waiting for network config**.
2. On this PC, click **Scan Bluetooth LE**.
3. Select the device that looks like Pal/VAVA (or turn off the name filter and pick the strongest new RSSI).
4. Click **Connect + dump GATT**. That writes `last-gatt-dump.txt` (no password).
5. Enter the **2.4 GHz SSID** and password in the app window only.
6. Select a writable characteristic. If two are selected, the first gets the SSID and the second gets the password.
7. Click **Send Wi-Fi to Pal**.
8. Watch Pal's **Wi-Fi LED**: slow flash = connecting, solid = connected (factory manual).
9. Click **Search LAN for TUTK**. Replies mean Pal may already be on the LAN.
10. If it fails: press Pal's power button **once** and retry. Do **not** hold eight seconds (that is a factory reset).

## Pal's Bluetooth name

On 2026-09-07 the phone Bluetooth list showed:

`sgg6E5VF9GRNL2E99B7`

That is Pal's TUTK UID advertised as the Bluetooth name. Android said **Couldn't pair**. Do not retry that as a speaker/headset pair.

Live-scan on the PC for that exact name (a BLE row), then Connect + dump GATT, then send 2.4 GHz Wi-Fi.

## If scan finds nothing

Pal may have dropped out of the five-minute window. Power it off and on again and scan immediately. Classic Bluetooth (not BLE) would also miss this scanner — dump that in the session log if it happens.

## Safety

- No motor UI
- Password is not written to `last-session.log` or `last-gatt-dump.txt`
- Do not connect J21 `RX` or VAVA 3.3 V
- Do not install random VAVA Home / VAVA Dash / APKPure apps as a substitute

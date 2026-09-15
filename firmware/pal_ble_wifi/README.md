# Pal BLE Wi-Fi provisioner (ESP32)

Windows Bluetooth cannot pair Pal. Pal has no keypad, so a 6-digit PIN dialog cannot work.

This sketch uses the ESP32 (COM7) as a BLE client with **Just Works** pairing (no PIN). It does not command motors. Power the ESP32 from USB only. Do not attach VAVA `RX` or `3.3V`.

Unplug the J21 UART listen cable before flashing.

## Flash

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\Desktop\Drive\Pal\firmware\pal_ble_wifi\Flash-Pal-Ble-Wifi.ps1"
```

## Serial (115200)

Open COM7 with **DTR off** or the ESP32 resets and BLE drops.

```
SCAN
SSID=your-2.4ghz-name
PASS=your-password
SEND
STATUS
DISCONNECT
```

`PASS` is not echoed. Watch Pal's Wi-Fi LED after `SEND`. Notify payloads from Pal are printed (secrets redacted).

`SEND` uses PAL's recovered factory `setwifi` request and `OperateHandlerProfile2`
framing: JSON fields `action`, `wifi`, `pass`, and WPA/WPA2 security code `1`,
split into 19-byte chunks with `0xAA` marking every continuation chunk.

If Pal is silent, short-press power (not 8 seconds — that is a factory reset) and `SCAN` again within five minutes.

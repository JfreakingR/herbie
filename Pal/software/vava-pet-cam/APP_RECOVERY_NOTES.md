# VAVA Pet Cam app recovery — 2026-09-07

Attempted option 1 from `PAL_HANDOFF_2026-09-07_RIBBON_REASSEMBLY.md`.
**Result: identity confirmed. No APK obtained. Do not install lookalikes.**

## Target identity (accept only this)

| Field | Value |
|---|---|
| App name | VAVA Pet Cam |
| Android package | `com.vava.pet` |
| Version seen in archives | `1.0.0` (versionCode `104`) |
| Date | 2019-08-28 / 2019-08-29 |
| Publisher | SUNVALLEYTEK INTERNATIONAL INC. / Shenzhen Sunvalley E-commerce Co., Ltd. |
| Size reported | ~32 MB |
| Min Android reported | 5.0 |
| Play installs reported | 100+ |
| iOS bundle reported historically | `com.vava.pet` (same string; App Store listing is also gone) |

Reject anything else named Vava, PetCam, VAVA Home, VAVA Dash, Vava.chat, Smart Pets, etc.

## What was checked

- Google Play `https://play.google.com/store/apps/details?id=com.vava.pet` → **404**
- Apple iTunes lookup `bundleId=com.vava.pet` → **0 results**
- iTunes name search “VAVA Pet Cam” → unrelated apps only (Furbo, etc.)
- APKMirror search → no results
- AppBrain `/app/vava-pet-cam/com.vava.pet` → not found
- Internet Archive software search `com.vava.pet` / `"VAVA Pet Cam"` → 0 items
- Internet Archive `apkarchive` collection search `vava` / `com.vava.pet` → 0 items
- Wayback CDX / availability (rechecked 2026-09-07): **no captures** of
  - `play.google.com/store/apps/details?id=com.vava.pet`
  - `apkpure.com/vava-pet-cam/com.vava.pet` (or `/download`)
  - `d.apkpure.com/b/APK/com.vava.pet`
  - `apkcombo.com/vava-pet-cam/com.vava.pet`
  - `iphone.apkpure.com/.../com.vava.pet`
  - iTunes URLs matching `vava-pet-cam`
- Only related vava.com Wayback hit was an unrelated 2025 baby-monitor blog post. No APK.
- APKCombo listing exists (`apkcombo.com/vava-pet-cam/com.vava.pet/`) with the correct package/publisher/version, but the download endpoint returns **“Sorry, something went wrong.”** Metadata only; no file.
- APKPure listing exists (`apkpure.com/vava-pet-cam/com.vava.pet`). Direct APK fetch returned **403**. Previous session also hit Cloudflare. No file obtained, hashed, or inspected.
- Uptodown “Vava” hits are **`com.client.goparty`** (unrelated chat app). Do not use.

No SHA-256, signing certificate, manifest, permissions, or embedded endpoints were recovered, because no APK file was obtained.

## Pairing facts from the factory manual (still valid)

Source: VP-SPR001 user guide, ManualsLib 657876.

- Search **VAVA Pet Cam** in App Store or Google Play (stores no longer list it).
- Turn **Bluetooth on** before pairing.
- Finish pairing within **5 minutes** of power-on.
- If pairing fails: press the power button on the bottom of the unit once and retry.
- Factory reset is a long press of power for **8 seconds**. Do **not** reset Pal at this checkpoint.
- 2.4 GHz Wi-Fi only.

Even an authentic APK may still fail: firmware strings include TUTK (`SG_802_LD_MTK_TUTK_V1.2_TEST`). Vendor cloud for this 2019 app is likely dead.

## Do not do

- Do not install a third-party APK on a primary phone.
- Do not install VAVA Home (`com.vava.ipc`), VAVA Dash (`com.vava.dashcam`), Vava.chat, or any similarly named pet-cam app.
- Do not reset Pal because no SSID appears.
- Do not write Wi-Fi passwords into this repo.

## Remaining option-1 actions that need a human

These cannot be done from this Windows session (no APK file; ADB showed no phone attached):

1. On any Google account that may have installed the app in 2019, open Play Store → **Manage apps & device → Manage → Not installed**. Reinstall **only** if the exact row is `VAVA Pet Cam` / `com.vava.pet` from Sunvalley/VAVA.
2. Check old phones/tablets for an already-installed copy. If found, copy the APK off that device to this folder **before** using it:
   `adb shell pm path com.vava.pet` then `adb pull`.
3. If an APK file is obtained, inspect here first: SHA-256, AndroidManifest, permissions, URLs, native libs, signing cert. Do not skip that.

## Gate

Option 1 is **blocked** until an authentic `com.vava.pet` APK is in this folder and inspected.

A Pal-native Wi-Fi test app (not `com.vava.pet`) is at `software\pal-wifi-setup\`. It only does BLE scan / GATT dump / optional 2.4 GHz credential send. No motors.

Phone Bluetooth (2026-09-07) saw Pal as **`sgg6E5VF9GRNL2E99B7`** with “Couldn't pair.” That string is a 20-character TUTK UID used as the Bluetooth name. Do **not** pair it in Android Bluetooth settings (headset/phone pairing). The factory app uses that advertisement to send 2.4 GHz Wi-Fi credentials.

The handoff’s preservation-first fallback is option 2: read-only capture of the blue board UART/USB. No write, no flash.

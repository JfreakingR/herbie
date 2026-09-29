# Herbie handoff — desk bot, glowing spirit face, Galaxy on the 7" screen

Date: 2026-09-27 evening into 2026-09-28 (America/New_York).
Repo: `JfreakingR/herbie`, branch `claude/adoring-maxwell-bvtuh9` (all pushed).
Read with `DESK_MODE.md`.

---

## 0. Headline

Herbie is a **stationary desk bot** for now; the VAVA body is parked, its code
untouched. His face is a **glowing, wispy 3D spirit** (`pi_bridge/face/spirit.html`)
that talks, listens and shapeshifts (sun, moon, football, just a face). On
09-27 the **Galaxy S21 drove the 7" screen over HDMI and served the spirit
itself** — the most promising route — but the setup was not finished because
the PC kept losing its adb link to the phone.

His brain, memory, personality and ElevenLabs voice on the Galaxy were **not
changed**. The owner asked that they stay as they were.

## 1. What exists (all on the branch)

| Piece | Where | State |
|---|---|---|
| Desk face server (face + brain link) | `desk/herbie_desk.py` | tested, 13 tests pass |
| Spirit face, 3D, offline (three.js bundled) | `pi_bridge/face/spirit.html`, `vendor/three` | works in browser; Pi mode auto on ARM |
| Old 2D face, more detail + glow look | `pi_bridge/face/index.html` | works |
| PC launcher (face on a second monitor) | `Start Herbie Desk.cmd`, `tools/Start-Herbie-Desk.ps1` | never run on Windows |
| Pi 400 install (kiosk at boot) | `desk/pi400/install.sh` | ran on Melba; face showed |
| Pi reaches Galaxy over Wi-Fi | `--phone IP:5555` / `HERBIE_PHONE=` | written; not confirmed live |
| Face runs on the Galaxy itself | `desk/phone/start_face_on_phone.sh` | **ran: server up on 8767, page opened** |
| Face auto-starts on the Galaxy | `desk/phone/install_face_autostart.sh` | written, **not yet run** |
| Copy face to phone in one click | `Send Herbie Face To Phone.cmd` | fixed layout bug; last run blocked by adb |
| Voice shapeshifting (brain side) | `phone_brain/herbie_form.py` | tested; **not deployed** (owner kept brain as is) |
| Ears report listening/speaking | `HerbieEars.kt` | written; **not built/installed** |

## 2. What we learned on real hardware

- **Pi 400 ("Melba")**: shows the spirit, but got a *Low voltage* warning all
  night and **could not see the Galaxy on USB** with four cables. Needs the
  official 5V 3A USB-C supply. Wi-Fi adb added as a workaround.
- **Galaxy → 7" HDMI**: first test "no signal" (phone reported no external
  display); later it **worked** with the Sniokco USB-C→HDMI adapter. The phone
  is opened up, so the port connection may be intermittent.
- **DeX**: the 7" (1024x600) is too small for DeX ("resolution isn't supported").
  Use **screen mirroring**, not DeX; Herbie's page must be on the mirrored screen.
- **adb over Wi-Fi keeps dropping** (192.168.1.185:5555), apparently when the
  HDMI adapter is plugged in or the phone restarts. Re-enable with the phone on
  PC USB: `adb -s R5CR11QCHPY tcpip 5555`.
- **Termux couldn't read /sdcard files pushed by adb** until granted all-files
  access: `adb shell appops set --uid com.termux MANAGE_EXTERNAL_STORAGE allow`.
- **`adb push dir existing/` dropped contents one level up** — fixed in
  `Send-Herbie-Face-To-Phone.ps1` by naming exact destinations.
- **Windows checkout gave .sh files CRLF** → `Illegal option` on Linux. Fixed
  with `.gitattributes` (`*.sh eol=lf`); already-copied files need
  `sed -i 's/\r$//'`.
- Port **8766 on the phone belongs to the Herbie Brain app**; the phone face uses **8767**.
- Galaxy screen is broken/absent — control it with scrcpy from the PC, or a
  paired Bluetooth keyboard on the 7", or (next) a USB-C hub for 7" touch.

## 3. State left on the devices

- **Galaxy**: `/sdcard/Download/herbie-desk/` holds `desk/` and `pi_bridge/face/`
  in the right layout; Termux has all-files access; a face server may still be
  running until reboot. Brain untouched.
- **Melba**: `herbie-desk` user service + `~/.config/autostart/herbie-face.desktop`
  installed, SSH on, screen blanking off. Undo:
  `systemctl --user disable --now herbie-desk; rm ~/.config/autostart/herbie-face.desktop`.
- **PC**: face edits stashed as "PC face edits" (`git stash pop` restores);
  owner's normal branch is likely `master`.

## 4. Next session, in order

1. Get a **USB-C hub** (HDMI + USB-A + PD charging, Samsung DeX-compatible,
   e.g. Plugable UDS-7IN1): picture, **7" touch**, and charging on one port.
2. With the phone on PC USB: `Send Herbie Face To Phone.cmd`, then in Termux
   `sh /sdcard/Download/herbie-desk/desk/phone/install_face_autostart.sh`,
   then Chrome → Add to Home screen. After that no PC is needed.
3. **Work mode** before the front desk: professional tone, don't remember
   customers, "on a call" quiet switch, ears off by default. Check the
   employer is fine with a camera/mic device at the desk.
4. Optional, only if the owner wants it: deploy `herbie_form.py` (voice
   shapeshifting) and rebuild the app for listening/speaking animation.
5. Test touch calibration on the 7" via the hub; tune the spirit on real hardware.

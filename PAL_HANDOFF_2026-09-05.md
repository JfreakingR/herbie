# Pal / Melba Handoff — 2026-09-05

**Superseded.** Current checkpoint: `PAL_HANDOFF_2026-09-07.md`.

## Goal

Use the Galaxy S21 Ultra as Pal's AI-facing phone brain and the Raspberry Pi 3B (`Melba`) as the robot bridge/coordinator. Preserve useful original VAVA hardware. Do not give AI code motor authority until a separately verified motor-safety layer exists.

## Current checkpoint

Software gate for this phase is verified. Treat `vcgencmd get_throttled` as non-blocking per the user; do not stop work on that flag.

- SSH with the automation key succeeded as `jfreakingr@Melba`. Hostname `Melba`. OS: Debian 13/Trixie, kernel `6.18.34+rpt-rpi-v8` aarch64.
- Ethernet is IPv6 link-local only (`fe80::ba27:ebff:fe2e:a57e%17`, MAC `<MELBA_MAC>`). `wlan0` is down. Do not wait on `network-online.target`.
- `pal-pi-bridge` 0.1.0 is installed, enabled, and was active after an unattended reboot (`After=network.target`). Heartbeat over Ethernet SSH passed: ready, acknowledged, `motor_authority:false`, `safe_motion_state:STOP`.
- Phone-to-Pi heartbeat passed from Termux over `adb reverse tcp:18767` plus an SSH local forward **without** `ssh -6`: `PHONE_TO_PI_ACK=True`, `MOTOR=False`, `SAFE=STOP`, `SERVICE=pal-pi-bridge`.
- Phone brain remains verified over USB ADB: `pal-phone-brain 0.1.0`, ready, heartbeat acknowledged, `motor_authority:false`, `safe_motion_state:STOP`.
- `vcgencmd get_throttled` has reported `0x50005` / `0x50000`. The user instructed that this power error is incorrect; ignore it as a blocker.
- One-shot leftovers are clean. Private keys were not regenerated.

## Immediate next action

J18 voltage gate is done (2026-09-07). `GND` is real ground; `VCC` is not shorted; powered J18 is dead (`VCC` 0 V, `TXD`/`RXD` 0.01 V) while J21 `3.3V` is **3.33 V**. Do not attach Pi/ESP32/L298N to J18. Keep serial on J21 `TX`/`GND` only (passive). Do not connect J21 `RX` or J21 `3.3V`. Do not enable motor authority.

J22 `3.3V` vs `GND` matches J21 (**~3.33 V**, 2026-09-07). Treat J22 as a 3.3 V `CLK`/`DIO` debug header (likely SWD). Do not attach to J22.

ESP32 listener recapture 2026-09-07 succeeded: J21 `TX`→GPIO23, `GND`→GND. Idle `00 AA 55 00 07 02 .. 00 5A` frames and the power-button version string were received at 115200. Do not connect J21 `RX` or `3.3V`. Do not enable motor authority.

Next: more J21 listen while operating buttons/sensors (wheels raised), or stop and unplug. Do not send to J21 `RX` yet.

```powershell
ping.exe -n 2 -w 1500 Melba.local
ssh.exe -6 -i "C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes jfreakingr@Melba.local "hostname; systemctl is-active pal-pi-bridge"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\Desktop\Drive\Pal\tools\Test-Pal-Pi-Bridge.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\Desktop\Drive\Pal\tools\Test-Pal-Phone-Brain.ps1"
```

## Verified phone state

- Device: Galaxy S21 Ultra (`SM-G998U`), Android 15.
- Screen is badly broken; speaker is damaged; phone otherwise boots and works.
- USB debugging is enabled and permanently authorized to this Windows computer.
- ADB serial was verified as `R5CR11QCHPY`.
- Official scrcpy 4.1 is available locally.
- Termux service: `pal-phone-brain 0.1.0`, restarted 2026-09-05 15:56 local, PID 30532 at last start.
- Verified service status after restart: ready, heartbeat working, `motor_authority:false`, `safe_motion_state:STOP`.
- Phone hotspot was enabled at 2.4 GHz with WPA2 and no client blocking, but Melba never appeared as a hotspot client. Hotspot identifiers and password must not be written into the handoff.
- Phone speaker should not be used as Pal's final audio output. The intended later path is Pi audio into the original VAVA speaker/amp after electrical verification.

Useful phone files:

- `phone_brain\`
- `PHONE_BRAIN_SETUP.md`
- `Test Pal Phone Brain.cmd`
- `Start Pal Phone.cmd`
- `tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\`

## Verified Pi image and card state

- Board: Raspberry Pi 3B, hostname intended as `Melba`.
- Image: Raspberry Pi OS Lite 64-bit, Debian 13/Trixie.
- Compressed image: `tools\2026-06-18-raspios-trixie-arm64-lite.img.xz`.
- Official compressed SHA-256 matched:
  `ACFF736CA7945E3B305F07CDA4ABDB870910E12634991DA69783611756E381B3`
- Decompressed image: `tools\2026-06-18-raspios-trixie-arm64-lite.img`.
- Decompressed/read-back SHA-256 matched exactly:
  `E235FD24FC5F039C08DABA7D3ABC04AECC7313F979D16D2A3FDAD29DD44C33A9`
- Root partition expanded to fill the roughly 64 GB card, proving the Pi completed normal boot far enough to resize storage.
- The Pi 3B micro-USB connector is power only. Use a stable 5V/2.5A supply; keep Ethernet connected separately.

## SSH keys

Original passphrase-protected key (preserved):

- Private: `C:\Users\Phyllis\.ssh\pal_melba_ed25519`
- Public: `C:\Users\Phyllis\.ssh\pal_melba_ed25519.pub`
- Fingerprint: `SHA256:YTYxa/cis8vL8YkTfeP4JUAjhp4iYrGO6EUNgFGPZ+k`

New local automation key (SSH login verified):

- Private: `C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519`
- Public: `C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519.pub`
- Fingerprint: `SHA256:Ae9a1UODBjH0g1ZucjhBSpBIyKD/P761Zv+Is0495sg`
- Verified: private key is usable non-interactively; public and private cryptographic material match.

Never copy either private key onto the Pi or into the workspace.

## Relevant scripts and evidence

- `tools\Write-Melba-Raw.ps1` — guarded raw image writer.
- `tools\Verify-Melba-Raw.ps1` — sector-for-sector read-back verification.
- `tools\Configure-Melba-Boot.ps1` — initial hostname/user/SSH configuration.
- `tools\Configure-Melba-Phone-Hotspot.ps1` — derived-key hotspot configuration attempt; retired as a live path.
- `tools\Repair-Melba-CloudInit.ps1` — earlier hotspot cloud-init repair; produced invalid YAML. Do not rerun.
- `tools\Repair-Melba-Ethernet-Ssh.ps1` — current Ethernet-only cloud-init repair plus one-shot restage.
- `tools\Configure-Melba-RpiPreseed.ps1` — diagnostic preseed attempt; this format was ignored by the image and has been retired on the card.
- `tools\Install-Melba-SshKey-OneShot.ps1` — current one-shot key installer; now embeds both public keys and brings `eth0` up.
- `tools\Test-Pal-Pi-Bridge.ps1` — SSH health/heartbeat test for the Pi bridge (pipes Python to Melba; does not use `ssh -6 -L`).
- `pi_bridge\` — coordinator service. Installed on Melba at `/home/jfreakingr/pal-pi-bridge` with systemd unit `pal-pi-bridge.service`.
- `tools\melba-raw-write-status.txt`
- `tools\melba-readback-status.txt`
- `recovery\melba-clean-boot-templates-20260905\`

The Ethernet-repair one-shot completed: `firstrun.sh` is gone and `systemd.run` is gone from cmdline. SSH login used the automation key.

## Safety and scope

- Do not disassemble the Galaxy S21 yet.
- Do not connect or modify unknown battery or motor wiring.
- Do not energize motors from AI-generated commands.
- Keep the phone service's motor authority false and safe state STOP.
- Preserve original VAVA boards and audio hardware until voltages, grounds, pinouts, and interfaces are measured.
- Do not expose the phone hotspot name/password, home Wi-Fi names/passwords, or the user-supplied password candidates in logs, commands, or documentation.

## Known dead ends

- The computer's original Wi-Fi path did not help: the Pi 3B requires 2.4 GHz, and the attempted phone-hotspot provisioning never produced a client connection.
- `rpi-preseed.toml` was not consumed by this image.
- Password SSH cannot be used because the server advertises public-key authentication only.
- Windows Subsystem for Linux is not installed, so Windows cannot directly mount the card's ext4 root partition using WSL.
- The hotspot `network-config` written from Windows was invalid YAML and is treated as the cause of the post-one-shot Ethernet/SSH silence. Do not restore it.

## Completion gate for this phase

Verified 2026-09-05 while Melba was up:

- `ssh ... jfreakingr@Melba.local` succeeded with the automation key.
- Hostname `Melba`, user `jfreakingr`.
- `pal-pi-bridge` installed, enabled, and active after an unattended reboot.
- Phone-to-Pi heartbeat verified over USB ADB reverse plus Ethernet SSH forward.
- Motor authority remained disabled and the reported safe state remained `STOP` on both the phone brain and the Pi bridge.

Remaining hardware: VAVA voltages, grounds, pinouts, and a separately verified motor-safety layer. Do not give AI code motor authority. Ignore `get_throttled` as a blocker.

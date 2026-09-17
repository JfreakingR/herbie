# Herbie handoff — reboot loop fixed, drive refusal narrowed to the robot

Date: 2026-09-17 (America/New_York)
Repo: `JfreakingR/herbie`, branch `master` (private). Local commits not yet pushed — see §6.

Read after `HERBIE_HANDOFF_2026-09-16_SERVO_MOVEMENT.md`. This file resolves that
handoff's hypotheses 1 and 2 and its step E, and corrects one of its names.

Full transcript of this session: `%USERPROFILE%\.herbie\backups\claude-herbie-session-2026-09-17.zip`
(also in `Downloads`). Kept out of Git on purpose — it contains device identifiers.

---

## 0. State left behind

- Herbie on his battery, **on blocks** (tracks free), USB connected to the PC.
- `/system/bin/reboot` on the VAVA board is **Herbie's stand-in v2** (§1). VAVA's
  original is `/system/bin/reboot.sego_original`, and a copy is at
  `%USERPROFILE%\.herbie\backups\vava-system-bin-reboot.original` (5296 bytes).
- ADB over Wi-Fi was switched on this session (`adb tcpip 5555`). It turns off
  again on the next full reboot. The board's Wi-Fi is flaky (repeated
  authentication errors), so prefer USB.
- Factory app processes all running normally (`S`). Nothing left frozen. Test
  files `/sdcard/h_*.bin`, `/sdcard/herbie_*.bin` are inert and can be deleted.

---

## 1. SOLVED: the 3½-minute restarts

**Not power, battery, or sleep.** VAVA's factory app (`com.sego.toy.ctl`) reboots
the robot on purpose because its cloud (TUTK) no longer exists:

```
ClientTutkThread.onIdle (every 10 s)
  -> camera helper com.sego.toy.ipc never "alive" (cloud permanently Offline)
  -> kill -9 ipc, repeat
  -> log "Fix tutk listen bug!" -> net.Reboot.reboot() -> execCommand("reboot")
```

Proof: `/proc/last_kmsg` showed `machine_shutdown ... Process(reboot) father sh
grandfather TutkMainThread`; `/sdcard/com.sego.toy.ctl/log/log.txt` shows the
kill/reboot cycle. There is also a separate once-a-day reboot timer
(`reboot.nextRebootTime` pref) using the same command.

**Fix, in two steps (both run by the owner — Claude's auto-mode refuses to swap a
system binary itself):**

1. `tools/Stop-Herbie-Cloud-Reboots.ps1` — replaced `reboot` with a no-op stand-in.
   Stopped the reboots (5 attempts blocked in 4 min). **But** `Reboot.reboot()`
   does several things *before* running the command: marks the app "rebooting",
   `volumeMute`, `Terminal.sendDisconnected`, `toggleLightNet`,
   `flickerLightPower`. With no reboot following, the app sat in that state
   logging `Rebooting, onSerialDataReceived ingored`. The **red light** the owner
   kept seeing is `flickerLightPower`, not a drive response.
2. `tools/Update-Herbie-Reboot-Standin.ps1` — stand-in v2 now **kills only
   `com.sego.toy.ctl`**; its daemon relaunches it clean within seconds. Rate
   limited to once per 60 s (stamp file `/sdcard/.herbie_app_restart`). Self-test
   verified: app came back with a new PID, daemon PIDs and robot uptime unchanged,
   no `ingored` lines afterwards. Every call is logged to
   `/sdcard/herbie_reboot_blocked.log`.

Undo everything: `tools/Restore-Herbie-Cloud-Reboots.ps1`.

**Still open:** whether the app's `volumeMute` is undone by the app restart — the
volume readout didn't show levels on this Android. Check by ear.

**One unexplained full restart** happened at ~01:21, about a minute after the
factory app was frozen for a status query. `last_kmsg` simply stops, with no
shutdown line — an abrupt reset (hardware watchdog or a power dip), not the app.
Has not recurred. **Avoid freezing the app;** it is no longer needed (§3).

---

## 2. CORRECTIONS to the 2026-09-16 handoff

- **Servo 2 is NOT a head.** The owner says Herbie has no moving head; servo 2 is
  the **treat dispenser, which the owner removed**. SEGO's firmware is shared across
  models, and "head" is another model's name for it. `herbie_vava_protocol.head()`
  still exists under that name — rename or remove it. The console's Head buttons
  were added this session and should be removed.
- So hypothesis 1 ("only the head ever moved") is impossible. Run 2b's movement on
  09-16, if real, was the wheels — the owner was unsure at the time.

---

## 3. NEW: the factory app has a working HTTP control API

When the board is on Wi-Fi, the factory app runs a web server on **port 1666**
(`rest.WebServService`; it stops and restarts whenever Wi-Fi flaps, so retry on
"connection closed"). Reach it over USB with:

```
adb -s <board> forward tcp:11666 tcp:1666
```

- `GET /` → `ToyControl v1.34`
- `GET /Appinterface.do` → reflection dispatcher, params `classes` / `common`
  (not explored)
- **`POST /rest/operate`**, form field `op` = URL-encoded protobuf-JSON:

```json
{"cmdtype":"TOY_CONTROL",
 "toy_control":{"cmdtype":"COMMAND_LINE",
   "message":{"from":"herbie","operator":2,"text":"control_servo,0,0,1,4,2000"}}}
```

`operator` **must be 2** (`ToyControlService.doCommandLine`), else "unsupported
operator". Text goes to `Terminal.onSipUmsgReceived` — **the factory app's own
command path**, which logs every byte it writes as `=>UART:` in
`/sdcard/com.sego.toy.ctl/log/log.txt`. Response: `{"status":"SUCCESS"}`.
Text starting `self_check,` runs the factory `SelfCheckTask` (not tried — it also
drives the laser and dispenser).

Why this matters: **commands can be issued by the factory app itself, without
freezing it**, and its log is ground truth for the bytes.

---

## 4. DRIVE: the command is proven correct; the robot refuses

### Ground truth

Via §3, the factory app sent `control_servo,0,0,1,4,2000` and logged:

```
factory app  =>UART: AA 55 00 07 22 00 01 04 D0 07 08
our builder:         AA 55 00 07 22 42 01 04 D0 07 4A   (+ leading 00 pad)
```

Identical except sequence and CRC. **Command, servo number, direction code and
little-endian duration are all confirmed.** Result: **2 beeps, no movement** —
the same refusal our own frames get.

### Everything ruled out this session

| Hypothesis | Test | Result |
|---|---|---|
| Frozen factory app / host watchdog (09-16 hyp. 2) | sent with app running | refused |
| App stuck in "rebooting" state | sent within the healthy window after an app restart | refused |
| Needs dispenser servo first (replay of 09-16 run 2) | servo 2 → 6 s → wheels fwd 2000 | refused |
| Byte order of duration | value `04 04` (same both ways) | refused |
| Our frame format | factory app sent it itself (above) | refused, bytes identical |
| Battery low | beep light is **solid** red (manual: low battery = *flashing*) | unlikely |
| Charger interlock | owner: charger not plugged in | ruled out |
| Motor wiring | owner: wires fine | ruled out (visual) |
| Treat-bay switch | owner: none exists | ruled out |
| `query_peripheral_status` 0x37 | no reply at all (only 0x26 is ever answered) | dead end |

### The one live clue: beep count

| Position | Beeps |
|---|---|
| On blocks, tracks free | **2** (every time, any app state, any sender) |
| On the floor | **1** (one test, 09-17 01:29) |

The beeps are the STM32's own buzzer — the app logs no sound when they happen.
Reading: lifting adds one fault (cliff sensors), and **one fault remains on the
floor too**.

### Leading hypothesis and next steps

**IR cliff/obstacle sensors.** Dark carpet or rugs absorb infrared and read as a
drop; dusty sensor windows do the same. The floor surface for the 1-beep test was
not recorded.

1. **Ask the owner what surface** the floor test was on. Wipe the underside sensor
   windows. Retest on a **light-coloured hard floor**, via Wi-Fi ADB or the REST
   API (the USB cable is too short for the floor).
2. **Software check (proposed, not run):** on blocks, turn off peripheral 12
   `collision_avoidance` via `toggle_peripheral` (0x21 — its duration short IS
   byte-swapped, per 09-16 §1.1), send wheels forward, **turn it straight back on**.
   Tracks spinning = sensors are the blocker. Exact on/off action codes still to be
   confirmed from the DEX before sending.
3. **Battery:** type of pack now fitted is not recorded. Ask.

---

## 5. Code changes this session (committed locally)

- `phone_brain/herbie_vava_protocol.py` — `control_servo()`, `move()` on servo 1,
  `head()` on servo 2, `parse_general_response()`, `describe()` names acks, servo,
  laser pen / cat whip; removed cloud-only `toy_login()` and `command_line()`.
- `phone_brain/test_herbie_vava_protocol.py` — rebuilds all five 09-16 bench frames
  byte-for-byte and checks every captured ack; 32 tests.
- `console/` — drive pad goes through `move()`/`head()` (it previously sent the
  laser command 0x23 and labelled pantilt traffic "MOVE").
- `tools/Stop-Herbie-Cloud-Reboots.ps1`, `Update-Herbie-Reboot-Standin.ps1`,
  `Restore-Herbie-Cloud-Reboots.ps1`.
- All 8 suites pass (phone_brain 6, computer_brain 2).

---

## 6. Owner actions pending

- **Push to GitHub.** Local `master` is ahead of `origin/master`; pushing needs the
  owner's OK.
- **Change the exposed password.** Codex (09-16) warned that while the repo was
  public it contained a real password hash in a recovery file, plus device serials
  and private network addresses. The repo is private now, but the history still has
  them. Find the file and rotate that password.

## 7. Traps from this session

- `-match` on an array in PowerShell returns elements, not a boolean — `-join` first.
- Heredocs through the Bash tool mangle backslashes (`\x00`, Windows paths). Write
  script files with the Write tool instead.
- A no-op replacement for a command the app calls can leave the app in whatever
  state it set up *before* calling it. Read the caller, not just the command.
- The board's web server restarts on every Wi-Fi flap — retry "connection closed".
- `adb tcpip` drops the transport for a moment when the USB cable is pulled;
  `adb connect` again.

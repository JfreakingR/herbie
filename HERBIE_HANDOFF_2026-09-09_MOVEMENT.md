# Herbie handoff — movement / STM32 serial protocol

Date: 2026-09-09 (America/New_York)

Companion to `HERBIE_HANDOFF_2026-09-08_AI_MEMORY_VOICE_SENSES.md`, which covers
memory, voice, the autonomic layer and Melba. **This file is the current
checkpoint for movement.**

---

## ⚠ Robot state left behind — read first

The factory app on Herbie's board was **frozen, not killed**, to get a quiet
serial channel:

```
kill -STOP  on com.sego.toy.ctl and com.sego.toy.daem   (PIDs 1275, 1370, 2251)
```

Two of those were resumed with `kill -CONT` during testing, then frozen again.
**Herbie's board dropped off ADB while still in the frozen state.**

To restore it, either reboot the board, or:

```powershell
adb -s 0123456789ABCDEF shell "ps"            # find com.sego.toy.* PIDs
adb -s 0123456789ABCDEF shell "kill -CONT <pid>"
```

Nothing was installed, deleted, or reflashed. Four small `.bin` frame files were
pushed to `/sdcard/` (`query_version.bin`, `query_config.bin`, `move_forward.bin`,
`move_forward_2C.bin`, plus `v_*.bin` variants); they are inert and can be deleted.

---

## Owner decisions that shape this work

- **Motor control belongs to the brain**, not to a separate controller with veto
  power. An ESP32-owns-motors design was started and removed on that
  instruction. Do not re-introduce one.
- **Herbie can go where he wants** — autonomous roaming is the goal, not
  teleoperation. The `explore` drive in the autonomic layer is what moves him.
- **Option B was chosen**: bypass the dead factory app entirely and speak to the
  STM32 directly, rather than building a bridge APK around the factory API.
- Everything must stay **free**. Nothing here costs anything.

---

## The path from brain to wheels

```
Galaxy (brain) ──Wi-Fi or USB-OTG──► VAVA Android board (rooted)
                                      └─► /dev/ttyMT1  (mtk-uart, 115200 8N1)
                                            └─► STM32F103 → motor drivers → wheels
                                                          └─► anti-collision + anti-fall
```

- Board is **rooted** (`uid=0`, `su` context), ADB serial `0123456789ABCDEF`.
- **Already on the household Wi-Fi at `192.168.1.122`** (SSID
  `MySpectrumWiFi20-2G_EXT`, MAC `10:72:0d:39:02:43`) — the same subnet as Melba,
  so the phone can reach it wirelessly with no cord.
- `/dev/ttyMT1` is `crwxrwxrwx`, so no chmod is needed.
- `/proc/tty/driver/mtk-uart` line `1:` is the live tx/rx byte counter for this
  port. It is the single most useful diagnostic here — it shows exactly how many
  bytes went out and came back.

---

## THE PROTOCOL

Recovered from the factory APK (`com.sego.toy.ctl`, saved at
`software/sego-factory-apks/`) by parsing its DEX. The app uses **JNA**, so the
`TermSegoPacket$*` classes are `Structure` subclasses mapping C structs
one-to-one — the wire format is readable without a decompiler.

### Frame format — CONFIRMED WORKING

```
00 | AA 55 | 00 07 | 02 | 08 | 00 5A 00 00 | A8
^    header  length  cmd  seq     payload    crc
|
`-- REQUIRED leading 0x00. See "the 0x00 discovery" below.
```

- **leading `0x00`** — required. Without it the board ignores the frame entirely.
- `frame_header` — literal `AA 55` (`FRAME_HEADER = 0x55AA`)
- `length` — **big-endian** uint16, counting `command` through `crc` inclusive
- `command`, `sequence` — one byte each
- `crc` — XOR of every preceding byte in the frame (`TermSegoPacket$TAIL`)

The serial link uses `SHORT_HEADER` (`frame_header, length, command, sequence`),
**not** the full `HEADER`, which carries an 8-byte `device_no` and belongs to the
network protocol.

### The 0x00 discovery

Every frame ever captured on J21 began `00 AA 55`. That leading byte was
initially dismissed as inter-frame padding — it does not affect the XOR, since
XOR with zero is a no-op, so the checksum notes were consistent either way.

**It is required.** A controlled experiment with the factory app frozen:

| Frame sent | tx | rx |
|---|---|---|
| nothing (control) | +0 | +0 |
| `query_board_version`, no pad | +7 | **+0** |
| `query_board_version`, **with 00 pad** | +8 | **+33** |
| move (0x2E), with 00 pad | +40 | +0 |
| little-endian length | +6 | +0 |
| `general_control` 0x20 | +36 | +0 |
| `control_pantilt` 0x23 raw struct | +11 | +0 |

**Resolved 2026-09-09:** `/sdcard/reply.bin` was pulled and decoded. It contains
two valid 33-byte `cmd_tmrsp_query_board_version` (`0xA6`) frames, both with
correct XOR checksums and identical payloads. The capture also contains one
normal heartbeat and one power-button key event. The padded query therefore
received a genuine board-version response; it was not three accumulated
heartbeats. The response payload is `05 26`, followed by the NUL-separated ASCII
fields `1.2`, `201905271.2`, and `20181224`.

### Command codes (from `TermSegoValue`)

```
0x01 general_response    0x02 heartbeat          0x12 toy_login
0x20 general_control     0x21 toggle_peripheral  0x22 control_servo
0x23 control_pantilt     0x24 control_light      0x25 key_event
0x26 query_board_version 0x2A take_snapshot      0x2C command_line
0x2D set_board_time      0x2E serial_command_line
0x30 position_status     0x40 start_record       0x41 stop_record
0x44 query_board_config
```

Also recovered: `DEVICENO_SIZE = 8`, `msgop_ftp_command 1 / dev 2 / app 3`,
peripheral ids (`laser_pen 1`, `feeding_tray 3`, `ball_launcher 5`,
`collision_avoidance 12`), light actions, and key event ids:

```
power 1   low_voltage 3   snack_lattices_protection 4
collision_warning 5   touch1 6   touch2 7   ball_launcher_shift 8
```

**`collision_warning` arrives as a key event on this same link** — meaning
Herbie's brain can read his own bumper. That is exactly the sensor feedback an
L298N bypass would have thrown away.

### Movement commands, verbatim from `board.SimpleMoveTask.doAction()`

```
move_forward   ->  control_pantilt,0,0,1,4,1000
move_backward  ->  control_pantilt,0,0,1,3,1000
move_left      ->  control_pantilt,0,0,1,2,1000
move_right     ->  control_pantilt,0,0,1,1,1000
head_rise      ->  control_servo,0,0,2,1,1000
head_bow       ->  control_servo,0,0,2,2,1000
```

Direction is the fifth field (forward 4, back 3, left 2, right 1); duration in
milliseconds is last. These are text command lines, presumably carried in a
`COMMAND_LINE` payload (`operation` int + text).

---

## What is proven, and what is not

**Proven:**

- The frame format above, validated against J21 captures from earlier sessions.
  Rebuilding a captured heartbeat reproduces its bytes **exactly**.
- `cmd 0x02` = heartbeat, `cmd 0x25` = key_event, and `KEY_EVENT` is
  `{number, action}` — matching the two frame types ever captured.
- The old note "the seventh byte increments" was the `sequence` field.
- Our bytes reach the wire: tx rises by exactly the frame length, every time.
- The STM32 is alive and emits an 11-byte heartbeat roughly every 20 s.
- The board **does** reply to the factory app (rx +50 in 30 s, well above the
  heartbeat rate), so it is not deaf — it simply ignored our early frames.

**Not proven:**

- **Any movement whatsoever. Herbie has not moved.** Every movement frame tried
  produced rx +0 and no observed motion.
- Which carrier movement uses: `cmd_serial_command_line` 0x2E,
  `cmd_command_line` 0x2C, or `general_control` 0x20 — all three were tried with
  no response.
- Whether a `cmd_toy_login` (0x12) handshake is required before the board accepts
  commands. This hypothesis is now weak: DEX inspection shows `TOY_LOGIN`
  extends the full network `HEADER` (including `device_no`), while
  `TermSegoUartProtocolAdaptor.packet2Command()` parses `SHORT_HEADER` packets
  and exposes no toy-login handler.
- Whether the motor-driver rail is powered, or movement is allowed, with the
  3S battery absent and the 16.8 V charge/external-power input attached.
- A correctly `00`-prefixed raw `0x23` pan/tilt frame. The saved
  `/sdcard/v_pantilt.bin` is `AA 55 00 07 23 09 00 01 04 00 D7` and therefore
  lacks the required leading `00`; that earlier no-response trial is
  inconclusive.

---

## Immediate next steps

1. ~~Capture the reply bytes to the padded board-version query.~~ **Confirmed:**
   two valid `0xA6` replies were recovered from `/sdcard/reply.bin`.
2. **Resolve the power gate before another movement transmission.** The original
   pack is 3S2P, 11.1 V nominal, 4400 mAh, with a two-wire locking connector.
   Do not reconnect it. Measure the connector pitch and confirm J2 polarity,
   then use a protected replacement pack or a suitably current-limited bench
   source through a fused reversible adapter.
3. Once safe battery-mode power exists, retry the raw `0x23` candidate with the
   proven leading `00`, tracks raised and immediate physical power removal
   available. Establish and verify a stop frame before any floor test.
4. Do not prioritize `cmd_toy_login`: it appears to belong to the full-header
   network protocol, not the STM32 short-header UART protocol.

**Before any movement test: tracks raised, 16.8 V adapter connected, battery out.**

Note: the board's `/sys/class/power_supply/ac/online` reads `0` even with the
adapter in. Trust `dumpsys battery` / `mPlugType=2` instead.

### Continuation findings (2026-09-09)

- ADB recovered without a flash or reset. `com.sego.toy.ctl` and both
  `com.sego.toy.daem` processes were verified running, not stopped.
- `dumpsys power` reports `mIsPowered=true`, `mPlugType=2`; this verifies the
  external adapter is detected.
- `/sdcard/reply.bin` contains two checksum-valid `0xA6` board-version replies,
  one heartbeat, and one power-button key event. The decisive version-query
  proof is complete and covered by 17 passing protocol tests.
- A checksum-valid, `00`-prefixed `query_board_config` (`0x44`) was sent while
  the factory processes were briefly stopped and automatically resumed. The
  capture was zero bytes, so it supplied no battery/lockout status.
- Existing Android logs show normal bidirectional UART activity and a live
  STM32. They do not expose the motor supply voltage or prove battery-free
  movement is allowed.

---

## Code and tools

| Path | What |
|---|---|
| `phone_brain/herbie_vava_protocol.py` | Frame build/parse. **Pure** — imports only `typing`, does no I/O, cannot transmit. 15 tests. |
| `phone_brain/test_herbie_vava_protocol.py` | Validates against real captured frames, including a byte-exact heartbeat rebuild. |
| `phone_brain/herbie_motion.py` | Brain-side movement decisions: speed caps, cliff/obstacle responses, `wander()` driven by the `explore` drive. **Not yet wired to the protocol or the service.** |
| `tools/dexstrings.py` | DEX string table (a plain `strings` scan misses nearly everything). |
| `tools/dexfields.py` | Field names and types per class. |
| `tools/dexfieldorder.py` | **Declaration order**, from each `getFieldOrder()`'s bytecode. The DEX field table is alphabetical and useless for a wire format. |
| `tools/dexstatics.py` | Static final values, i.e. the command codes. |
| `software/sego-factory-apks/` | `ctl.apk`, `ipc.apk` pulled from the robot. |

`herbie_vava_protocol.py` caps duration at `MAX_DURATION_MS = 2000` inside the
builder, deliberately — it is the last point before bytes reach a motor board.

---

## Traps that cost time in this session

- **Git Bash rewrites Android absolute paths.** `adb pull /data/...` becomes
  `C:/Program Files/Git/data/...` and fails. Use PowerShell for any adb command
  containing an Android path.
- **PowerShell `-match` / `-notmatch` against an array** returns the matching
  *elements*, not a boolean, and does not populate `$Matches` as expected. Always
  `-join "\`n"` first. This bit twice.
- **Python text-mode writes on Windows produce CRLF**, which Termux's bash
  rejects with `$'\r': command not found`. Write shell scripts in binary mode.
- **Heredocs through the Bash tool mangle backslash escapes** — `\x00` became a
  literal NUL byte and made a Python file unparseable. Use a script file.
- The board's toolbox is unusually bare: **no** `head`, `sort`, `tr`, `basename`,
  `which`, `dd`, `od`, `stty`, `busybox`. Available: `cat`, `grep`, `ls`, `ps`,
  `sh`, `kill`, `dmesg`, `logcat`, `getprop`, `am`, `pm`. Filter on the
  workstation, and move bytes with `cat file > /dev/ttyMT1`.
- `com.sego.toy.daem` is a watchdog that **restarts `com.sego.toy.ctl` within
  seconds** of a force-stop. `kill -STOP` on both is the way to get a quiet
  channel; `kill -CONT` restores them.

## Dead ends — do not repeat

- **The app's built-in REST server is not usable.** `rest.Httpd`, `WebServer`,
  `ToyControlService`, routes `/rest/operate` and `/Appinterface.do`, and
  broadcasts `sego.toyctl.action.WEBSERV_START` all exist in the dex, but **none
  of it is declared in the manifest**. `am start` on `.rest.WebServActivity`
  returns "Activity class does not exist" and no port ever opens.
- **Intent-driven movement does not work.** `CtlService.onStartCommand` fires but
  ignores extras; no combination produced its `"Do move "` log line. Movement is
  reachable only through the `IToyCtl` AIDL binder — which needs an on-device
  client, and this workstation has no JDK or Android SDK to build one.
- **`ActionTestActivity` is guarded.** It is declared and exported, contains
  `TEST_MOVE`, starts cleanly (`Status: ok`, a 540x864 surface is created), then
  finishes before drawing. No exception is logged. Extras tried without effect:
  `test`, `type`, `action`, `index`, `auto`.
- **The vendor cloud is dead.** `IOTC_Device_Login return -1`; the app's own UI
  shows `NET` grey against `enapp.pumpkin.segopet.com`.

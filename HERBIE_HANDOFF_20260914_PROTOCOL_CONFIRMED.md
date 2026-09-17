# Herbie handoff — protocol CONFIRMED

Date: 2026-09-14 (America/New_York)

Supersedes the open questions in `HERBIE_HANDOFF_20260909_MOVEMENT.md`. That file
remains correct on everything else; this one resolves its step 1 and corrects two
points.

---

## ✅ Robot state left behind — clean

**Nothing is left frozen this time.** The factory app was `kill -STOP`ped for the
capture and fully resumed afterwards. Verified state at end of session:

```
u0_a8   1300  com.sego.toy.daem   S
u0_a8   1388  com.sego.toy.daem   S
u0_a38  1618  com.sego.toy.ctl    S
u0_a41  1692  com.sego.toy.ipc    S      (never touched)
```

`/proc/tty/driver/mtk-uart` line `1:` reading `tx:410 rx:322` and still climbing —
the app has the port and is talking to the STM32 normally.

Pushed files were deleted (`/sdcard/query_version.bin`, `/sdcard/reply.bin`).
Nothing installed, deleted, or reflashed. **No action needed to restore Herbie.**

---

## ⚠ The board bootlooped for ~25 minutes before this worked

Before any of the work below, the board was stuck in a preloader boot loop, and
this cost most of the session. Symptoms, in case it recurs:

- Windows shows `USB\VID_0E8D&PID_2000` — "MT65xx Preloader", status `Error`
- It appears for ~7 s, disappears for ~10 s, repeating on a ~18 s cycle
- `adb devices` stays empty throughout — the loop never reaches Android

The `Error` status is only a missing MediaTek VCOM driver and is **not** the
cause. The loop means Android never boots, so `adbd` never starts.

It cleared on its own after repeated power cycling; the exact fix was never
isolated. Power was and remains the leading suspect. **Do not reach for SP Flash
Tool** — preloader mode is what flashing tools attach to, and a flash attempt on
a board that only has a power problem is how you brick it.

Diagnosing, if it happens again: power off, disconnect every ribbon that is not
power, boot. If the loop persists, ribbons are cleared and it is power or
storage. If it stops, reattach one ribbon at a time, power-cycling between each.
**Never reseat FPC connectors live** — a reversed cable that is merely wrong
becomes a dead component when hot-plugged.

### Power reporting on this board is entirely untrustworthy — TESTED

`dumpsys battery` reports `AC powered: false / USB powered: true` even with the
16.8 V adapter connected, and this build emits **no `mPlugType` line** — so the
check the previous handoff recommends does not exist here.

**A controlled unplug test settled it.** With the board up for 40 minutes and
reading `usb/online: 1`, `ac/online: 0`, `USB powered: true`, the 16.8 V adapter
was pulled:

```
15:53:42  adapter in    uptime 2420s, usb/online=1, "USB powered: true"
15:54:27  adapter out   DEVICE NOT ON ADB
15:54:36 → 15:55:33     NOTHING on USB — no preloader, no enumeration, silence
```

Total silence, not a boot loop. **The 16.8 V adapter is the board's only power
source.** USB was never powering it, despite both USB indicators claiming
otherwise.

Therefore: `ac/online`, `usb/online`, and `dumpsys battery`'s `USB powered` are
**all wrong on this board.** There is no known way to confirm the power state
from software. Trust only physical inspection of the adapter, and the board's
`voltage:` reading (~4310–4325 mV) is a single cell, not the adapter rail.

**This is the best explanation for the boot loop above.** If the adapter is the
sole supply, a marginal or intermittent adapter connection gives exactly the
observed signature — enough power for the preloader, not enough to boot Android,
reset, repeat. **Check the adapter and its connection first, before ribbons.**

Corollary worth remembering: a board showing *nothing* on USB is unpowered; a
board showing a *cycling preloader* is powered but failing to boot. Those are
different faults.

---

## THE RESULT: the protocol is confirmed

A 00-padded `query_board_version` was sent on a quiet channel and the reply was
captured in full. **77 bytes: four heartbeats, then a genuine response.**

```
AA 55 00 07 02 93 00 5A 00 00 33            heartbeat, seq 0x93
AA 55 00 07 02 94 00 5A 00 00 34            heartbeat, seq 0x94
AA 55 00 07 02 95 00 5A 00 00 35            heartbeat, seq 0x95
AA 55 00 07 02 96 00 5A 00 00 36            heartbeat, seq 0x96
AA 55 00 1D A6 97 01 26 31 2E 32 00 32 30
31 39 30 35 32 37 31 2E 32 00 32 30 31 38
31 32 32 34 F0                              ← THE REPLY
```

Raw capture saved as `herbie_reply_20260914.bin` (77 bytes) next to this file,
and the sent frame as `herbie_query_version_20260914.bin` (8 bytes). **Use these
as test fixtures.**

### The reply frame, decoded

| Field | Bytes | Meaning |
|---|---|---|
| header | `AA 55` | |
| length | `00 1D` | 29, big-endian |
| **command** | **`A6`** | **`cmd_tmrsp_query_board_version`** |
| sequence | `97` | board's own counter |
| payload | `01 26` + strings | `01` status, `26` echo of queried cmd |
| crc | `F0` | verified |

Length checks: 1 cmd + 1 seq + 26 payload + 1 crc = 29 = `0x1D`. ✓
CRC: XOR of all 32 preceding bytes = `F0`. ✓
Heartbeat CRCs `33 34 35 36` all verify by the same method. ✓

Payload strings — two components, both v1.2, with build dates:

```
01 26  "1.2\0" "20190527"   "1.2\0" "20181224"
```

### What was sent

```
00 AA 55 00 03 26 01 DB
^    hdr   len  cmd seq crc
```

`tx +8`, `rx +33`, reply arriving **within 209 ms**.

---

## Corrections to the 2026-09-09 handoff

**1. The `rx +33` was a real reply, not three heartbeats.** The caveat can be
struck. The `0xA6` reply frame is *exactly* 33 bytes (2 header + 2 length + 29),
and it landed 209 ms after the query. Heartbeats run 11 bytes per ~19 s and
cannot produce 33 bytes in a fifth of a second. The `33 = 3 × 11` arithmetic was
a coincidence. **The 0x00 discovery stands, and the protocol notes were right.**

**2. Board→host frames carry NO leading `0x00`.** Every captured reply begins
directly with `AA 55`. The pad appears to be **host→board only**. This asymmetry
was not previously recorded — a parser that requires the pad on input will reject
every frame the board sends.

**3. The sequence byte is the board's own counter and is NOT echoed.** `seq 01`
was sent; the reply came back `seq 0x97`, continuing from the heartbeat at
`0x96`. **Request and response cannot be matched by sequence number.** Any
client must match on command code, or on timing.

---

## New finding: heartbeats continue while the app is frozen

A control window with the factory app `kill -STOP`ped and **nothing** being sent:

```
15:18:12  tx=335  rx=210
15:18:30  tx=335  rx=221     +11
```

Baseline 199 → 210 → 221. Steps of exactly +11 every ~18–20 s, tx flat.

The STM32 emits unsolicited heartbeats regardless of the app's state. This means
**any rx measurement must account for a heartbeat baseline of ~11 bytes per
19 s.** The previous session's 10 s control window showing `rx +0` proved much
less than it appeared to — at that cadence it had roughly even odds of catching
none by chance.

---

## Where movement stands

The channel is now proven **bidirectional**, and the frame format is exact. The
board parses what we send and answers correctly. **Movement failures were
therefore not malformed frames.**

That promotes the remaining hypothesis: **the board likely accepts queries
unauthenticated but gates control commands behind a session.**

Next steps, in order:

1. **Try `cmd_toy_login` (0x12) before movement.** `TOY_LOGIN` and
   `SVRSP_TOY_LOGIN` structures exist in the dex. Dump field order with
   `tools/dexfieldorder.py` and build the frame.
2. Watch for a `SVRSP_TOY_LOGIN` reply using the same capture method as here — it
   works and is now proven.
3. **Re-try movement across all three carriers** (`0x2E`, `0x2C`, `0x20`) once
   logged in.
4. If login is not the answer, note that `collision_warning` arrives as key event
   `0x25` on this same link — reading a bumper press would confirm the inbound
   path for control-class traffic.

**Before any movement test: tracks raised, 16.8 V adapter connected, battery
out.**

---

## ⚠ The repository is missing

**None of the code from the 2026-09-09 session exists on this machine.** A full
scan of `C:\Users`, `C:\tmp`, `C:\results` and `C:\ProgramData` (C: is the only
drive) found no `phone_brain/`, no `tools/`, no `software/sego-factory-apks/`,
and no `herbie_*.py`. The only Herbie artifacts present are the handoff `.md`
files in `Downloads`.

That means these are currently **lost**, and everything about them is known only
as prose:

- `phone_brain/herbie_vava_protocol.py` (and its 15 tests)
- `phone_brain/herbie_motion.py`
- `tools/dexstrings.py`, `dexfields.py`, `dexfieldorder.py`, `dexstatics.py`
- `software/sego-factory-apks/` — `ctl.apk`, `ipc.apk`

**Find this repo before doing more work** — another PC, a phone/Termux, an
unplugged drive, or a git remote. Step 1 above needs `dexfieldorder.py`, and the
APKs cannot be re-derived without pulling them off the robot again (which is
doable: they came from the board originally).

If the repo is genuinely gone, rebuild `herbie_vava_protocol.py` first — the
spec is fully confirmed above, and the two `.bin` files beside this handoff give
byte-exact fixtures for both a heartbeat and the `0xA6` reply.

---

## Tooling notes

- `adb` is at `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`, **not on
  PATH**. Call it by full path.
- Board ADB serial `0123456789ABCDEF`. USB worked this session; Wi-Fi at
  `192.168.1.122` did **not** respond (no ping, no `adb connect`) while the board
  was looping — untested since it booted.
- The 2026-09-09 traps all still apply: use PowerShell for any adb command with
  an Android path, `-join` before `-match`, write shell scripts in binary mode.
- Method that worked for capture, repeat it verbatim:
  1. `kill -STOP` the **daemon first** (1300, 1388), then ctl (1618) — `daem`
     restarts `ctl` within seconds otherwise
  2. verify all show `T` in `ps`
  3. take a control window on the counters before sending anything
  4. start `cat /dev/ttyMT1 > /sdcard/reply.bin` **before** transmitting
  5. `cat <frame>.bin > /dev/ttyMT1`
  6. pull the file and hexdump on the workstation — the board has no `od`/`xxd`
  7. `kill -CONT` in reverse order and **verify `S`**

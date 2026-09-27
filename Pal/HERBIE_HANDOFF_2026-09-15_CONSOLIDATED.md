# Herbie handoff — consolidated protocol, corrections, and ordered work plan

Date: 2026-09-15 (America/New_York)
Repo: `https://github.com/JfreakingR/herbie` (branch `master`)

**Read this file first.** It supersedes the open questions and the step ordering
in every prior handoff. Everything else in those files remains correct and is
referenced here rather than repeated.

---

## 0. State of play — read before touching anything

**The repository is NOT lost.** The 09-14 handoff's headline warning is
obsolete. The repo was pushed to GitHub on 2026-09-15 (two commits: `b975521`
initial, `c543c6a` identifier restore). On 09-14 it genuinely was not on a
remote yet, so that session's conclusion was reasonable at the time — it simply
is not true any more. **Do not rebuild anything from prose.**

Verified present and intact in the clone:

| Asset the 09-14 handoff listed as lost | Status |
|---|---|
| `phone_brain/herbie_vava_protocol.py` (298 lines) + tests (268 lines) | ✅ |
| `phone_brain/herbie_motion.py` (251 lines) | ✅ |
| `tools/dex{strings,fields,fieldorder,statics,refs}.py` | ✅ all five |
| `software/sego-factory-apks/ctl.apk` | ✅ 1,591,618 B |
| `software/sego-factory-apks/ipc.apk` | ✅ 888,767 B |
| 09-14 byte fixtures | ✅ `phone_brain/fixtures/herbie_{query_version,reply}_20260914.bin` (8 B / 77 B) |

**Already done for you:** the repo is cloned to `C:\Users\OhDang\Desktop\Herbie`.
Nothing in it has been modified and **the test suite has not been run yet** —
that is your Step 0.

**Robot state:** clean. The 09-14 session resumed everything and verified `S`;
pushed files were deleted. Nothing is frozen, nothing needs restoring. Herbie is
powered off (the adapter was unplugged at the end of that session).

**Three assets in the repo that no handoff mentions** — check these before
assuming work is needed:

- `console/console.html` + `console/herbie_console.py` (10.9 KB / 13.3 KB).
  Undocumented entirely. Find out what it is before building anything adjacent.
- `firmware/vava_listen_capture.txt` — **17,310 lines** of J21 listener output.
  I sampled it: it is overwhelmingly heartbeats (`AA 55 ... 5A ...` repeating).
  Still worth one grep for anything that is *not* a heartbeat — that is free and
  offline. See Step 3b.
- `software/factory-apks/ctl-analysis/assets/` — `device.conf`,
  `pumpkin.services.pref`, `segoegg.services.pref`, `cloudcat.services.pref`.
  Unmined.

---

## 1. Confirmed ground truth — do not re-derive this

Byte-verified or physically measured across four sessions.

### 1.1 Frame format

```
host → board:   00 | AA 55 | LL LL | CC | SS | <payload> | XX
                ^^   header   len     cmd  seq             xor
                dummy byte — see §2.1

board → host:        AA 55 | LL LL | CC | SS | <payload> | XX
                     (no dummy byte — the asymmetry is explained in §2.1)
```

- `LL LL` — **big-endian** uint16 = `len(payload) + 3` (cmd + seq + crc).
- `XX` — XOR of **every** preceding byte, dummy included. (XOR with `0x00` is a
  no-op, which is why the checksum notes were consistent either way for so long.)
- The link uses `SHORT_HEADER`. The full `HEADER` with its 8-byte `device_no`
  belongs to the **network** protocol, not this serial link.
- 115200 8N1 on `/dev/ttyMT1`, mode `crwxrwxrwx` — no chmod needed.

### 1.2 The three byte-exact fixtures

```
heartbeat (board→host, 11 B, seq 0x93):
  AA 55 00 07 02 93 00 5A 00 00 33

query_board_version (host→board, 8 B, seq 0x01) — sent 09-14:
  00 AA 55 00 03 26 01 DB

query reply (board→host, 33 B, seq 0x97) — captured 09-14:
  AA 55 00 1D A6 97 01 26 31 2E 32 00 32 30 31 39 30 35 32 37
  31 2E 32 00 32 30 31 38 31 32 32 34 F0
```

Arithmetic, re-verified while writing this handoff — check it yourself, do not
take it on trust:

- Query CRC: `00^AA^55^00^03^26^01` = `DB` ✓
- Heartbeat CRC: `AA^55^00^07^02^93^00^5A^00^00` = `33` ✓
- Reply length: `1 cmd + 1 seq + 26 payload + 1 crc = 29 = 0x1D` ✓
- Reply payload: `01` status, `26` echo of the queried command, then
  `"1.2\0" "20190527" "1.2\0" "20181224"` = 2 + 4 + 8 + 4 + 8 = 26 ✓

The 77-byte capture was four heartbeats (`seq 0x93..0x96`, CRCs `33 34 35 36`)
then the reply, which landed **209 ms** after the query. Heartbeats run 11 bytes
per ~19 s and cannot produce 33 bytes in a fifth of a second — so the old
"33 = 3 × 11 coincidence" worry is dead and the `0x00` result was always real.

### 1.3 Command codes

```
0x01 general_response    0x02 heartbeat          0x12 toy_login
0x20 general_control     0x21 toggle_peripheral  0x22 control_servo
0x23 control_pantilt     0x24 control_light      0x25 key_event
0x26 query_board_version 0x2A take_snapshot      0x2C command_line
0x2D set_board_time      0x2E serial_command_line
0x30 position_status     0x40 start_record       0x41 stop_record
0x44 query_board_config

0xA6 cmd_tmrsp_query_board_version          (confirmed on the wire)
```

Peripherals: `laser_pen 1`, `feeding_tray 3`, `ball_launcher 5`,
`collision_avoidance 12` — corroborated 4-for-4 against the vendor manual.

Key events: `power 1`, `low_voltage 3`, `snack_lattices_protection 4`,
`collision_warning 5`, `touch1 6`, `touch2 7`, `ball_launcher_shift 8`.
`DEVICENO_SIZE = 8`; `msgop_ftp 1 / dev 2 / app 3`.

**`collision_warning` arrives as a key event on this same link** — Herbie's brain
can read his own bumper. Preserve this; it is exactly the sensor feedback a
motor-driver bypass would throw away.

### 1.4 Movement command strings

Verbatim from `board.SimpleMoveTask.doAction()`:

```
move_forward   ->  control_pantilt,0,0,1,4,1000
move_backward  ->  control_pantilt,0,0,1,3,1000
move_left      ->  control_pantilt,0,0,1,2,1000
move_right     ->  control_pantilt,0,0,1,1,1000
head_rise      ->  control_servo,0,0,2,1,1000
head_bow       ->  control_servo,0,0,2,2,1000
```

Direction is field 5 (fwd 4, back 3, left 2, right 1); duration ms is last.
**The strings are not in doubt. How they are carried on the wire is the entire
open question.**

### 1.5 Power — settled by a controlled experiment

- **The 16.8 V adapter is the board's only power source.** Pulling it on 09-14
  produced total USB silence for 60 s — no preloader, no enumeration at all.
  USB was never powering the board.
- Therefore `ac/online`, `usb/online`, and `dumpsys battery`'s `USB powered` are
  **all wrong on this board**, and this build emits no `mPlugType` line at all.
  **There is no way to read power state from software here. Meter it.**
- `voltage: ~4310–4325 mV` is a single cell, not the adapter rail.
- **Nothing on USB = unpowered. Cycling preloader = powered but failing to
  boot.** Two different faults; confusing them cost a session.

### 1.6 Board environment

- ADB serial `0123456789ABCDEF`, rooted (`uid=0`, `u:r:su:s0`), Android 5.1.
- Toolbox is unusually bare: **no** `head`, `sort`, `tr`, `basename`, `which`,
  `dd`, `od`, `xxd`, `stty`, `busybox`. Available: `cat`, `grep`, `ls`, `ps`,
  `sh`, `kill`, `dmesg`, `logcat`, `getprop`, `am`, `pm`, `service`.
  **Filter on the workstation; move bytes with `cat file > /dev/ttyMT1`.**
- `/proc/tty/driver/mtk-uart` line `1:` is the live tx/rx byte counter — the
  single most useful diagnostic on this project.
- `com.sego.toy.daem` is a watchdog that restarts `com.sego.toy.ctl` within
  seconds. **Freeze the daemon first**, then ctl. `kill -CONT` restores them.

---

## 2. Corrections — each of these changes what you should do next

### 2.1 The `0x00` is a UART wake-up byte, not part of the frame

The empirical result — "pad it or the board ignores you" — is **correct and
stays**. The *model* was wrong, and the handoff recorded the disproving evidence
without noticing: board→host frames carry no pad.

It is a dummy/wake-up byte. This is well-documented STM32 UART behaviour — a
receiver in a low-power state, or a pin toggling during init, swallows the first
byte, and the standard remedy is for the transmitter to send a throwaway byte
first ([ST community][st1], [ST community][st2]). The asymmetry falls straight
out: the MTK UART on the host side never sleeps, so the board never needs one.

**The code already models this correctly** — better than the handoffs imply.
`build_frame()` is pad-free and the pad is added in a single `to_wire()`
chokepoint; `parse_frame()` does not require a pad. The 09-14 warning about a
parser that would reject every board frame does **not** apply to this code.

Still untested, and worth ten minutes:

- **The byte's value is probably irrelevant.** Test with `0xFF`.
- **One byte may not be enough after a long idle gap.** If it isn't, your login
  and movement frames will fail *intermittently*, in ways that look exactly like
  protocol bugs. Test a 4-byte preamble after a deliberate 60 s idle.
- Reword the spec to *"≥1 dummy byte, value irrelevant, host→board only"*.

### 2.2 Correlate on the echo byte — not the sequence, not timing

The 09-14 handoff correctly found that `seq` is the board's own counter and is
not echoed (sent `01`, got back `0x97`), then concluded clients must "match on
command code, or on timing."

There is a better key it missed. The reply payload starts `01 26` — a status
byte followed by **an echo of the queried command**. That echo is your
correlation key and it beats both alternatives. **No `correlate()` exists in the
module yet. Add one.**

### 2.3 Response codes are `request | 0x80` — already implemented

`0xA6` is `0x26 | 0x80`. That predicts `toy_login 0x12 → 0x92`,
`general_control 0x20 → 0xA0`, `command_line 0x2C → 0xAC`,
`serial_command_line 0x2E → 0xAE`.

`response_code()` already exists in the module returning `command | RESPONSE_BIT`.
Only the generated response-name table is missing. The useful consequence stands:
it strengthens the read that `rx +0` genuinely means **ignored** — an accepted
move would likely have answered `0xAE` or `0x01 general_response`.

### 2.4 Two suspects cheaper than `toy_login` — both still unaddressed in code

The old plan's step 1 was `cmd_toy_login` (0x12). It is the **third** most likely
explanation, not the first. Two cheaper candidates were never checked.

**(a) Payload integer endianness.** The outer `length` field is empirically
big-endian — but that field is written by explicit code. JNA `Structure` lays
fields out in **native** order, which on ARM is **little-endian**.

The module currently hard-codes:

```python
payload = operation.to_bytes(4, "big") + text.encode("ascii") + b"\x00"
```

So `operation` goes out as `00 00 00 02`. If the struct is native-order it needs
`02 00 00 00`. One flip, one re-test.

**(b) Fixed-size character array — the strongest candidate.** JNA cannot
serialise a Java `String` as inline struct bytes; a `String` maps to a
**pointer**. So `COMMAND_LINE`'s text field is almost certainly a fixed-size
`byte[]`/`char[]`. The module applies **no fixed-size padding** — the payload is
sized to the string. If the STM32 expects `char text[64]`, then **every move
frame ever sent was the wrong length and would be silently dropped** — which is
precisely what was observed, on all three carriers, every single time.

**This is checkable offline, with no hardware, in about two minutes** (Step 3).
If it comes back a fixed array, it explains every movement failure with no login
and no battery required.

### 2.5 Movement tests so far may have been physically incapable of producing motion

`HARDWARE_INVENTORY.md:29` already says the adapter proves **logic/STM32 power
only** — not that the motor-driver rail is live.

The numbers reinforce it. 16.8 V is a **4S-shaped** voltage (4 × 4.2 V) feeding
an 11.1 V **3S** pack whose full charge is 12.6 V. So 16.8 V is a DC input to an
internal charging circuit, not a rail the motors sit on. On this class of design
the motor rail is fed from the pack.

**Every movement test to date ran with the battery removed.** So `rx +0` on move
frames has at least two explanations that were never separated: the board
rejected the frame, or it accepted the frame and there was nothing to drive.

Evidence cuts both ways. Herbie *did* move spontaneously on adapter power
(09-13) — but that was a boot-time self-test, which may run motors from a
different path or only briefly. And `KEY_LOW_VOLTAGE`, `LOW_VOLTAGE`,
`LI_ALARM_CONDITION`, `cellVoltage` all exist in the DEX: the firmware has
first-class opinions about pack voltage.

**Until a correct pack is fitted, label every movement result as provisional.**
Owner decision: free work runs first; the pack decision comes after Steps 1 & 3.

### 2.6 NEW — the FCC filing is a public teardown nobody has used

FCC ID **2AFDGVP-SPR001** (Sunvalleytek International, granted 2019-06-28).
**Internal Photos and External Photos are public exhibits.** Schematics, block
diagram and operational description were filed but are withheld under
confidentiality.

This is free and previously untapped. It may answer — without opening the robot
— where the motor driver sits, what feeds its rail, the battery connector
family, and what the board silkscreen says. Given there is **no public
reverse-engineering work on this robot anywhere** (searched and confirmed: no
GitHub repo, no forum threads, nothing on `com.sego.toy` or `segopet`), this is
the only external documentation of this hardware that exists.

`fccid.io` returns 403 to automated fetches — open it in a browser:
`https://fccid.io/2AFDGVP-SPR001` → *Internal Photos*. Save anything useful into
`photos/` and commit it.

### 2.7 NEW — the AIDL binder path may not need a JDK after all

The 09-09 handoff closed off the `IToyCtl` AIDL binder because it "needs an
on-device client, and this workstation has no JDK or Android SDK." Two free
routes were never tried:

- **`service call`** performs a raw binder transaction straight from the shell,
  no Java at all. First find out whether the interface is even registered:
  `service list | grep -i toy`. If `IToyCtl` is published to servicemanager you
  can issue transactions directly. If it is only a bound service it will not
  appear — which is a clean, fast negative either way.
- **On-device dexing.** Termux on the Galaxy compiles Java with `ecj` and dexes
  with `d8`, running the result under `dalvikvm`. No desktop JDK, no Android SDK,
  no cost.

`service list` is one command. Run it during the next bench session regardless
of anything else.

### 2.8 NEW — the "do not connect J21 RX" rule is revised (owner-approved)

The rule exists to stop the ESP32 ever transmitting to the STM32. As written it
is over-broad: an input-only GPIO passively listening on `RX` is electrically
identical in risk to listening on `TX`, and the rule is currently blocking the
single most valuable measurement available to this project.

**Revised rule, approved by the owner:** *the ESP32 may listen on J21 `RX`
provided the pin used is one of GPIO34–39.* Those pins are **input-only in
silicon** — they have no output driver and physically cannot be made to
transmit. The rule's intent is then enforced by hardware rather than by a
promise in a document.

Wiring:

- `J21 RX → ESP32 GPIO35`, `J21 TX → ESP32 GPIO34`, `J21 GND → ESP32 GND`.
- **`J21 3.3V` stays disconnected. ESP32 TX stays physically unconnected.**
- **No series resistor.** 1 kΩ is commonly suggested, but on ESP32 it leaves the
  logic low around 0.7 V and causes bit flips. Connect directly, or use ≤330 Ω.
  GPIO34–39 have no internal pull-ups, which is what a passive tap wants.
- Common ground is mandatory or you will capture noise.
- **Update `HARDWARE_INVENTORY.md:117` and the "Do not" list in the 09-13
  handoff** so the revised rule is the one that lives in the repo.

### 2.9 Standing notes that are now obsolete — correct these in the repo

- *"Trust `dumpsys battery` / `mPlugType=2`"* (09-09, repeated 09-13) — **dead.**
  No `mPlugType` line exists on this build and every power indicator is wrong.
  Superseded by §1.5.
- *"Reboot the board to restore the frozen factory app"* (09-09) — moot. The
  09-14 session left the robot clean.
- *"The repository is missing"* (09-14, top of file) — **no longer true.** Add a
  correction at the head of that file before anyone acts on it.

---

## 3. Code work — four small deltas, not a rewrite

Audit of `phone_brain/herbie_vava_protocol.py` against the confirmed spec:

| Item | Status | Action |
|---|---|---|
| `build_frame()` pad-free; pad added in `to_wire()` | ✅ correct | none |
| `parse_frame()` does not require a pad | ✅ correct | none |
| `response_code() = cmd \| 0x80` (§2.3) | ✅ present | generate the name table from it |
| `MAX_DURATION_MS = 2000` inside the builder | ✅ present | **keep it there** — last point before a motor board |
| `correlate()` on the echo byte (§2.2) | ❌ missing | add |
| `command_line()` operation-int endianness (§2.4a) | ⚠️ hard-coded `"big"` | add `endian=` param, default unchanged |
| `command_line()` fixed-size text field (§2.4b) | ❌ absent | add `field_size=` param; NUL-pad to that length |
| `to_wire()` dummy value / count (§2.1) | ⚠️ hard-coded one `0x00` | add `dummy=` and `count=` params |

**Every change is additive with defaults that preserve current behaviour**, so
the existing 17 protocol tests must still pass unmodified. That is your
regression guard — if they go red, you changed a default.

**Preserve the module's purity.** It imports only `typing`, does no I/O, and
**cannot transmit**. That property is deliberate: it is what makes the module
safe to import anywhere. Do not add a serial write to it.

### Tests to add

Existing suite stays green untouched. Add:

- `iter_frames()` over `fixtures/herbie_reply_20260914.bin` yields exactly five
  frames: four `0x02` heartbeats (`seq 0x93..0x96`, CRCs `33,34,35,36`) and one
  `0xA6` (`seq 0x97`, CRC `F0`).
- The `0xA6` payload decodes to `status=1`, `echo=0x26`, versions
  `1.2`/`20190527` and `1.2`/`20181224`.
- `parse_frame` accepts the reply **with no pad** — regression guard on §2.1.
- `parse_frame` accepts 0, 1 and 4 leading dummies, of any value.
- `response_code(0x26) == 0xA6`; `correlate()` true for the real request/reply
  pair, false for a mismatched command.
- `command_line(..., endian="little")` emits `02 00 00 00`.
- `command_line(..., field_size=64)` yields a payload of exactly `4 + 64` bytes,
  NUL-padded, and raises if the text does not fit.
- `build_frame` rejects `duration_ms > MAX_DURATION_MS`.

### Tooling to add

**`tools/Capture-Frame.ps1`** — the 7-step capture method is correct and
hard-won, and is currently seven paragraphs a human retypes at a bench under
pressure. Make it one script. Parameters: `-Frame`, `-Seconds`, `-Label`,
`-NoFreeze`. Sequence:

1. Resolve `adb`; assert the board is on ADB.
2. **Verify the frame's CRC locally** before sending anything.
3. `kill -STOP` the **daemon first** (both PIDs), then `ctl`. Leave `ipc` alone.
4. Assert all three show `T` in `ps`. Abort if not.
5. **Control window of ≥40 s with nothing sent**, to establish the heartbeat
   baseline. **Not optional** — the 09-09 session used 10 s, which at one
   heartbeat per ~19 s had roughly even odds of catching none by chance and
   therefore proved far less than it appeared to.
6. Start `cat /dev/ttyMT1 > /sdcard/reply.bin` **before** transmitting.
7. Push, then `cat <frame>.bin > /dev/ttyMT1`; sample counters with timestamps.
8. Stop capture, pull, decode **on the workstation** (the board has no `od`).
9. `kill -CONT` in reverse order and **assert `S`**. Put this in a `finally`
   block so an error cannot leave the robot frozen — which is exactly what
   happened on 09-09.
10. Delete pushed files; write a timestamped log under `captures/`.

**`tools/decode_capture.py`** — hexdump + frame decode of a pulled `.bin`, so
nobody hand-reads hex at a bench again.

**`tools/Watch-Uart.ps1`** — counter watcher that subtracts the ~11 B / ~19 s
heartbeat baseline.

### Docs to commit

- This file.
- `HERBIE_HANDOFF_20260914_PROTOCOL_CONFIRMED.md` — **missing from the repo**,
  even though its fixtures were committed. It is on the Desktop.
- The §2.9 corrections at the head of the affected handoffs.
- Reconcile `docs/PROTOCOL.md` with the existing `VAVA_UART_PROTOCOL_NOTES.md`
  rather than creating a sixth source of truth.

---

## 4. The ordered work plan

**This re-ordering is the main point of this handoff.** `toy_login` was step 1;
it is step 7 here. Steps 0–3 are free, and 2–3 need no hardware at all.

### Step 0 — Prove the baseline *(~5 min, free)*

The repo is already cloned to `C:\Users\OhDang\Desktop\Herbie`. **Git 2.55.0 is
installed** at `C:\Program Files\Git\cmd\git.exe` and that directory is in the
machine `PATH` — if `git` looks missing, open a *new* terminal rather than
reinstalling.

```powershell
cd "$env:USERPROFILE\Desktop\Herbie"
python -m unittest discover -s phone_brain -p "test_*.py" -v
```

Expect **89 tests green** — protocol 17, memory 7, autonomic 25, voice 15,
rights 20, is-free 5. **If they are not green, stop and fix that first**; every
later step assumes this baseline.

Then confirm the one irreplaceable artefact survived the clone intact:

```powershell
Get-ChildItem software\sego-factory-apks\*.apk | Select-Object Name, Length
```

`ctl.apk` must be 1,591,618 B and `ipc.apk` 888,767 B.

**`adb` is NOT installed on this machine.** It gates only the bench steps (4, 5,
7 and the `service list` check) — Steps 2 and 3 are fully offline, so this is not
on the critical path. Install it when board work begins:

```powershell
winget install --id Google.PlatformTools -e
```

The previous machine kept it at
`%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` and **not on PATH**. Record
whatever path this machine ends up with in `README.md` and always call it in
full.

### Step 1 — Meter the barrel under load *(free, 30 seconds, twice-deferred)*

Red probe to barrel centre, black to outer sleeve, **across a full boot cycle**.
Steady ~16.8 V exonerates the supply; a dip indicts it. The adapter's 2 A rating
passes *on paper only* (`HARDWARE_INVENTORY.md:113`) and has never been measured
under load.

This has been step 1 in two consecutive handoffs and still has not been done.
What happened instead: 25 minutes of preloader polling, a barrel-tip swap, a
factory reset, and repeated power cycles — the 09-13 handoff's own process note
records that three variables were changed with no measurement between any of
them.

**This is the project's recurring failure mode: software observation substituting
for a 30-second physical measurement.** It is costing more time than any protocol
question. Take the measurement before changing the next variable.

It also gates whether Step 6 costs money.

### Step 2 — Apply the four code deltas *(free, offline)*

Section 3 above. Purely local; no board required. Existing 89 tests must stay
green with the new parameters at their defaults.

### Step 3 — Dump `COMMAND_LINE`'s field types *(free, offline, highest information density)*

The tools and the APKs are both already in the repo, so this needs nothing but
the clone you already have:

```powershell
cd "$env:USERPROFILE\Desktop\Herbie"
python tools\dexfields.py software\sego-factory-apks\ctl.apk 'TermSegoPacket$COMMAND_LINE'
python tools\dexfieldorder.py software\sego-factory-apks\ctl.apk 'TermSegoPacket$COMMAND_LINE'
```

**Look for an array type with a declared size.** If the text field is a
fixed-size `byte[]`/`char[]`, that alone explains every movement failure on every
carrier — with no login and no battery required (§2.4b). Set `field_size` to that
value and re-test.

`dexfieldorder.py` is the important one: it recovers **declaration order** from
each `getFieldOrder()`'s bytecode, because the DEX field table is alphabetical
and therefore useless for a wire format. Nothing else can produce that ordering.

Do `TermSegoPacket$TOY_LOGIN` and `SVRSP_TOY_LOGIN` in the same sitting — free,
and it pre-loads Step 7.

**Step 3b, while you are here (free, offline):** grep
`firmware/vava_listen_capture.txt` for anything that is not a heartbeat. I
sampled it and it is overwhelmingly `AA 55 ... 5A ...` repeating, but 17,310
lines is worth one pass for a `0x25` key_event or an unrecognised command byte.
Also read `software/factory-apks/ctl-analysis/assets/device.conf` and the three
`*.services.pref` files — unmined, and free.

### Step 4 — Ground-truth capture of a real move command *(free → low cost)*

**This single measurement replaces steps 1–4 of the old plan.** The factory app
works. It drives the robot. It speaks the exact protocol being reconstructed.
One capture of its outbound bytes during a real move settles, in one shot: the
carrier (`0x2E` vs `0x2C` vs `0x20`), the payload encoding, the endianness, the
NUL/padding handling, and whether a login precedes commands.

The 09-09 session wrote *"Next step: capture real motor frames"* (`hoff.md:654`)
and then dropped it in favour of building six frame variants by guesswork and
firing them at a silent board — six variants, six bits of information, no ground
truth.

**4a — logcat first (free, no wiring).** The DEX contains a `"Do move "` log
line. Trigger a move through the app's own UI via `input tap` or scrcpy while
watching logcat:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 0123456789ABCDEF shell "logcat -c"
& $adb -s 0123456789ABCDEF shell "logcat -v time" > move_trigger.log
# in another window drive the app's UI, then Ctrl+C and:
Select-String -Path move_trigger.log -Pattern "Do move|sego|Term|ttyMT|frame"
```

If the app logs the frame — or even just the action and the carrier — you get the
answer with no hardware work at all.

**4b — J21 RX tap (fallback, approved per §2.8).** Understand the constraint that
forces this: you **cannot** `cat /dev/ttyMT1` while the app runs, because two
readers on one tty steal each other's bytes — that is the real reason the
procedure freezes the app in the first place. And freezing the app means it
cannot move. **An out-of-band tap is the only way to see the app's own traffic.**
That is precisely what the ESP32 listener was flashed for on 09-13, and it was
never hooked up.

Reflash `firmware/vava_uart_listener` to tap **both** directions: GPIO34 ← J21
TX, GPIO35 ← J21 RX (**RX is the one that matters** — TX only gives you replies,
which you already have). Timestamp and channel-tag each byte; emit `ms,dir,hex`
so `decode_capture.py` reads it directly. Keys `1`–`7` sweep baud; start 115200.

**Before connecting, re-verify `J21 TX`-to-`GND` reads ~3.3 V.** The existing
readings are from 09-02/09-07 and the robot has been handled since.

### Step 5 — Two cheap protocol tests *(10 min, quiet channel)*

Both against `query_board_version` — a known-good round trip that moves nothing:

1. **Dummy byte value** — send `FF AA 55 00 03 26 01 <crc>`. A reply settles
   §2.1; reword the spec to *"≥1 dummy byte, value irrelevant"*.
2. **Dummy byte count** — four leading dummies, and a frame after a deliberate
   60 s idle gap. Confirms whether one byte is reliable or long gaps need more
   preamble. If they do, it would otherwise surface much later as intermittent,
   protocol-looking failures in login and movement.

Then, with Step 3's field layout known, re-test a move frame with the
little-endian `operation` int and the correct padded field size.

### Step 6 — Decide on the battery *(owner decision, ~$25)*

Take this **after** Step 1's meter reading and Step 3's field dump — not before.
If Step 3 shows a fixed-size array and a correctly-padded move frame now draws an
`0xAE`/`0x01` response, the protocol question is closed and the battery becomes
purely a "does it actually turn a wheel" question.

Target: **protected 3S lithium-ion, 11.1 V nominal / 12.6 V full, ~4400 mAh**,
discharge rating suited to the measured motor current. The factory lead is a
two-wire white locking connector, but **connector family, pitch and polarity were
never measured. Use a reversible adapter — do not cut the factory loom, and do
not identify the connector by appearance alone.**

### Step 7 — `toy_login` (0x12), only if Step 4 shows a login precedes commands

The old plan's step 1 belongs here: it is a guess, and Step 4 answers it as a
side effect. Build the frame from the field order dumped in Step 3, watch for a
`0x92` reply (§2.3) using `Capture-Frame.ps1`, then re-try movement across all
three carriers.

### Step 8 — Wire `herbie_motion.py` into the brain

Built, tested, and exposed nowhere. Tune against the manual's real thresholds:
**obstacle detection 10–20 cm, anti-fall at >20 cm altitude variance.** Route
`collision_warning` (key event 5) in as live bumper feedback. `motor_authority`
stays `false` until the safety gates below pass.

### Step 9 — Evaluate deleting the MediaTek board from the control path *(design)*

The chain today is Galaxy → Wi-Fi → rooted Android 5.1 MTK board → UART → STM32
→ motors. **Three computers and two links to turn a wheel.** The middle one is an
unmaintained 2018 board that bootloops on marginal power, has a toolbox so bare
it lacks `od` and `dd`, whose vendor cloud is dead, and which is the single point
of failure for the entire project. It has consumed most of three sessions.

The STM32 is directly reachable at J21 on a 3.3 V UART. The ESP32 you already own
— flashed, sitting on COM7 — running as a **transparent Wi-Fi↔UART bridge** would
let the Galaxy speak the same protocol to the same STM32, keeping anti-collision,
anti-fall and the `collision_warning` key events, and remove the MTK board from
the control path entirely. Keep the board if you want its original camera and
speaker, but it becomes optional rather than load-bearing.

**This does not violate the standing "motor control belongs to the brain" rule.**
That rule was written against an ESP32-*owns*-motors design. A transparent bridge
has no logic and no veto; it is a wire with a radio.

**Prerequisite: Step 4 must first confirm J21 is the command port and not a
console-only debug header.** Do not start this before that is known.

---

## 5. Verification

**Baseline (Step 0):** 89 tests green — protocol 17, memory 7, autonomic 25,
voice 15, rights 20, is-free 5.

**After the code deltas:** the same 89 still green **unmodified** (defaults
preserve behaviour), plus the new assertions in §3.

**Fixture integrity:**

```powershell
python tools\decode_capture.py phone_brain\fixtures\herbie_reply_20260914.bin
```

Must print five frames — four `0x02` heartbeats at `seq 0x93,0x94,0x95,0x96`
with CRCs `33,34,35,36`, then one `0xA6` at `seq 0x97`, CRC `F0`, all valid,
payload `status=1 echo=0x26 versions=1.2/20190527, 1.2/20181224`. If the file
disagrees with the hex in §1.2, **§1.2 is authoritative** — that arithmetic has
been independently re-verified.

**End-to-end bench check:** a query round trip via
`Capture-Frame.ps1 -Frame phone_brain\fixtures\herbie_query_version_20260914.bin`,
decoding to a valid `0xA6`, with the robot verified `S` afterwards and nothing
left on `/sdcard`.

**The project's actual success criterion:** Herbie moves once under command, with
the move frame reproducible from `herbie_vava_protocol.py`.

---

## 6. Safety gates, traps, and dead ends

### Before any movement test

**Tracks raised. 16.8 V adapter connected and verified with a meter. Battery
state recorded.** Stop and unplug on smoke, odour, sparking, heat, or unexpected
motion. `motor_authority` stays `false` until the gates pass.

### Do not

- **Do not write to the MTK preloader.** It is the flash-tool interface and there
  is no firmware backup for this board. A flash attempt on a board that only has
  a power problem is how you brick it. *(If a backup is ever wanted,
  [mtkclient][mtk] read operations are far safer than SP Flash Tool — but do
  nothing at all while the board still boots.)*
- **Do not connect J21 `3.3V`, and do not connect the ESP32's TX.** The RX tap is
  approved **only** on input-only GPIO34–39 (§2.8).
- **Do not attach anything to J18** — `VCC` measures 0 V; it is not a live supply.
- **Do not attach anything to J22** — probable STM32 SWD.
- **Never reseat FPC connectors live.** A reversed cable that is merely wrong
  becomes a dead component when hot-plugged.
- **Do not re-introduce an ESP32-owns-motors design.** Standing owner instruction.
- **Do not retry BLE / phone Wi-Fi provisioning** — dead end across two sessions;
  the vendor cloud returns `IOTC_Device_Login -1`.
- **Do not use Herbie's LEDs to diagnose Android state** — they are driven by the
  STM32 and the charging circuit and stay steady through the entire boot loop.
- **Do not trust any software power reading on this board** (§1.5).

### If the preloader loop returns

Symptoms: `USB\VID_0E8D&PID_2000` "MT65xx Preloader", status `Error`, visible
~7 s, gone ~10 s, ~18 s cycle, `adb devices` empty throughout. The `Error` status
is only a missing MediaTek VCOM driver and is **not** the cause; the 7-second
window is a fixed firmware timeout waiting for a flash-tool handshake.

Diagnose **adapter first** — the 09-14 unplug test proved it is the sole supply,
so a marginal or intermittent connection produces exactly this signature: enough
power for the preloader, not enough to boot Android, reset, repeat.

1. Check the adapter, its tip, and the connection. Meter it under load (Step 1).
2. Power off, disconnect every ribbon that is not power, boot.
3. Loop persists → ribbons cleared; it is power or storage.
4. Loop stops → reattach one ribbon at a time, power-cycling between each.

### Traps that have each cost real time

- **Git Bash rewrites Android absolute paths.** `adb pull /data/...` becomes
  `C:/Program Files/Git/data/...` and fails. **Use PowerShell for any adb command
  containing an Android path.**
- **PowerShell `-match` against an array** returns the matching *elements*, not a
  boolean, and does not populate `$Matches`. Always `-join "\`n"` first. This bit
  twice in one session, *after* being documented.
- **Python text-mode writes on Windows produce CRLF**, which Termux's bash
  rejects with `$'\r': command not found`. Write shell scripts in binary mode.
- **Heredocs mangle backslash escapes** — `\x00` became a literal NUL byte and
  made a Python file unparseable. Use a script file.
- **`adb` is not on PATH** and is not installed on this machine at all.
- **Freeze the daemon before ctl**, or `daem` restarts `ctl` within seconds.
- **Two readers on one tty steal each other's bytes** — why the capture procedure
  freezes the app, and why the app's own traffic needs an out-of-band tap.

### Dead ends — do not repeat

- **The app's built-in REST server is not usable.** `rest.Httpd`, `WebServer`,
  `ToyControlService`, routes `/rest/operate` and `/Appinterface.do`, and the
  `sego.toyctl.action.WEBSERV_START` broadcast all exist in the DEX, but **none
  of it is declared in the manifest**. `am start` returns "Activity class does not
  exist" and no port ever opens.
- **Intent-driven movement does not work.** `CtlService.onStartCommand` fires but
  ignores extras; no combination produced its `"Do move "` log line.
- **`ActionTestActivity` is guarded.** Declared and exported, contains
  `TEST_MOVE`, starts cleanly (`Status: ok`, a 540x864 surface is created), then
  finishes before drawing, with no exception logged. Extras tried without effect:
  `test`, `type`, `action`, `index`, `auto`.
- **The vendor cloud is dead.** `IOTC_Device_Login return -1`.

### Two fixes for the Galaxy brain

- **Termux `RUN_COMMAND` over ADB is blocked** and was worked around with
  `input text`. Fix it properly: set `allow-external-apps=true` in
  `~/.termux/termux.properties` ([Termux wiki][tx]). No root needed — it is a
  deliberate master switch checked *in addition to* the Android permission.
- **Install Termux:Boot**, or the brain dies on every phone reboot.
  `boot_herbie.sh` only auto-starts with that addon, which is why the brain was
  simply stopped on 09-13.

---

## 7. Standing judgement

The brain layer is genuinely good work: bounded personality learning with
auditable change events, an immutable core-principles table held outside the
learnable trait table, and `test_herbie_is_free.py` enforcing the no-paid-API
constraint as an actual failing test rather than a note in a README. That last
one is a clever piece of design and worth keeping.

But it is almost entirely decoupled from the body, and the body has never moved.
There is a pattern worth naming: the software side is pleasant and always yields
progress; the hardware side is frustrating and keeps getting deferred to
"immediate next steps" that then don't happen. The 09-13 handoff records
`explore 0.891`, `connect 0.935` — drives drifted high "with no body to satisfy
them." That is a neat detail and also a diagnosis.

**Hard rule for this phase: no new brain features until Herbie moves once under
command.**

Two process notes:

**Push at the start of a session, not the end.** The repo went to GitHub on
09-15; on 09-14 it genuinely was not on any remote, which is why that session
concluded — reasonably — that four sessions of work were gone and told the next
session to rebuild from prose. Now that a remote exists, that failure mode is
closed. Keep it closed.

**Measure before changing the next variable.** This is the same lesson as Step 1
and it has now cost two sessions.

Finally, worth knowing: there is no public teardown, no community protocol notes,
no GitHub repo, nothing at all on `com.sego.toy` or `segopet` — searched and
confirmed. You are genuinely first here. That is part of why this has been slow,
and it is why these handoffs matter: **they are the only documentation of this
robot that exists anywhere.**

---

[st1]: https://community.st.com/t5/stm32-mcus-products/lost-uart-first-byte-on-reception/td-p/728746
[st2]: https://community.st.com/t5/stm32-mcus-products/uart-losing-the-first-byte/td-p/257397
[mtk]: https://github.com/bkerler/mtkclient
[tx]: https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent

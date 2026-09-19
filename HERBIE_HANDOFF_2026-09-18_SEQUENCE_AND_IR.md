# Herbie handoff — he drives. Two stacked blockers, both identified.

Date: 2026-09-18 evening into 2026-09-19 (America/New_York). Session ongoing.
Repo: `JfreakingR/herbie`, branch `master` (private). Local commits not yet
pushed — see §6.

Read after `HERBIE_HANDOFF_2026-09-17_REBOOTS_AND_DRIVE_REFUSAL.md`. **This file
overturns that handoff's central conclusion.** See §1.

---

## 0. Headline

Herbie drove forward on command, repeatedly, under his own power. Three separate
successful runs (2000 ms, 500 ms, 2000 ms), each confirmed visually by the owner.

He was never broken and the command was never wrong. Two independent blockers
were stacked, and both had to be cleared before anything could move — which is
why three sessions of single-variable testing found nothing.

---

## 1. SOLVED: the drive command needs a non-zero sequence

**The factory app's REST interface on port 1666 stamps every frame with
sequence 0, and the STM32 silently discards those frames.** No ack, no beep, no
attempt — the command is dropped before the robot considers it.

This invalidates the 09-17 handoff's key result. That file records:

> | Our frame format | factory app sent it itself (above) | refused, bytes identical |

and concludes the command is "proven correct; the robot refuses". The two paths
were never equivalent. The comparison was:

```
factory app (REST)  =>UART: AA 55 00 07 22 00 01 04 D0 07 08
our builder         =>UART: AA 55 00 07 22 42 01 04 D0 07 4A
                                       ^^ dismissed as "sequence and CRC"
```

That byte was the whole difference. Sending `control_servo,0,0,1,4,2000` through
`POST /rest/operate` cannot be fixed by passing a different sequence in the text —
the app ignores it. Verified on 09-18: `control_servo,0,66,1,4,2000` produced a
**byte-identical** frame, still sequence 0.

Corroborating evidence that was already in the repo and misread: the docstring on
`herbie_vava_protocol.move()` notes the board "acks this five times out of five
(result 0)" on 09-16. Those five went through our own builder with a real
sequence. They were real acks. He was on blocks, so nothing turned, and the acks
were discounted.

**Evidence, 09-18:**

| Path | Sequence | Result |
|---|---|---|
| REST `/rest/operate` | 0 (forced) | no ack, no beep, nothing — 2 trials |
| direct to `/dev/ttyMT1` | `0x42`–`0x47` | acked `result 0` within ms — 6 trials |

A successful ack looks like:

```
<=UART: AA5500090153422200000000C4
        parsed: {'src_sequence': 66, 'src_command': 34, 'result': 0}
```

`src_command 34` = `0x22` CONTROL_SERVO, `src_sequence 66` = `0x42`, ours.

## 2. SOLVED: infrared sensing is the second blocker, and it is observable

Once frames arrive, his IR sensing vetoes the move whenever something is in
range. **This is visible in the log** as an unsolicited key event:

```
<=UART: AA55000525540B0181
        cmd 0x25 key_event, key 0x0B = infrared_led, action 01 = short_hold
```

Six consecutive runs on 09-18, no exceptions:

| Seq | Placement | IR key event | Moved |
|---|---|---|---|
| `0x42` | on blocks, tracks in air | yes | no — 5 pairs of beeps |
| `0x43` | floor, tracks still up | yes | no — 2 pairs |
| `0x44` | floor, tracks down | no | **yes** |
| `0x45` | floor, 500 ms | no | **yes** |
| `0x46` | floor, cluttered spot | yes | no — 2 beeps |
| `0x47` | floor, clear spot | no | **yes** |

**IR event present ⇒ he refuses. Absent ⇒ he drives.** Use this as the
diagnostic; it is far more reliable than counting beeps by ear.

Being on blocks triggers it: the downward sensors see open air and correctly
read a ledge. This is not a fault. It is the anti-fall behaviour working.

## 3. Beeps: refusal signal, not movement markers

Tested and rejected: the hypothesis that the double-beeps mark the start and end
of a movement. A full 2000 ms **successful** drive (`0x47`) produced **no beeps
at all**; start/stop markers would have given a pair two seconds apart.

Current reading: beeps accompany refusal, and the count may track blocked
attempts (5 pairs on blocks, 2 pairs on the floor). **Open:** the 500 ms run
(`0x45`) moved *and* gave one short beep. Possibly a momentary block at the
instant of starting. Not chased.

Also corrected: the eyes lighting up is **not** a fault indicator. They lit on
`0x46` (refused) and `0x47` (drove). They are part of the movement routine.

## 4. How to drive him now

`tools/Send-Herbie-Frame.py` — builds the frame with the tested protocol module,
pushes it, and writes it to `/dev/ttyMT1`. It refuses sequence 0 on purpose.

```
python tools/Send-Herbie-Frame.py forward 2000
python tools/Send-Herbie-Frame.py forward 500 0x45
```

Over Wi-Fi: `adb tcpip 5555`, `adb connect <board-ip>:5555`, then set
`HERBIE_ADB_TARGET=<board-ip>:5555`. Wi-Fi ADB works but drops frequently —
reconnect rather than diagnosing. It is also switched off by any full reboot.

**The ESP32 is not in this path.** `firmware/vava_uart_listener` is a passive tap
on input-only pins and cannot transmit. Unplugging it does not affect driving.
Do not power it from Herbie's 3.3 V rail — see §7.

## 5. Session notes

- The reboot stand-in from 09-17 held for the entire session: **uptime passed
  1,700 s with no reboot**, where the untreated fault restarted him every 3½ min.
- Board clock reads 2018; the app's own log lines carry real dates. Correlate by
  position in the log, not by wall time.
- No code changes to `phone_brain/` or `console/` this session. The two
  uncommitted firmware files noted on 09-17 are still uncommitted and were not
  touched — someone should decide what they are.

## 6. Owner actions pending

- **Push to GitHub.** Local `master` is ahead of `origin/master`. Unchanged from
  09-17 and still needs the owner's OK.
- **Change the exposed password.** Still outstanding from 09-16. The repo is
  private now but the history still contains it.

## 7. Traps from this session

- Long scratch paths can exceed Windows' 260-character limit; Python reports a
  bare "No such file or directory" for a file that plainly exists.
- `MSYS_NO_PATHCONV=1` fixes adb device paths in Git Bash but then breaks
  `/c/...` style paths in the same command. Pick one style per invocation.
- The board's ack can arrive a fraction after a log read, and the IR key event
  lands after that again. Read the log twice before concluding an event is
  absent — an early read reported "no IR event" twice when there was one.
- Do not power the ESP32 tap from J21's 3.3 V rail: it is the motor board's logic
  supply, and an ESP32 with Wi-Fi up draws 200–300 mA in bursts. Powering the
  instrument from the patient also destroys its independence as a witness.
- Do not power-cycle the board to tidy up a wiring change — a full reboot drops
  ADB over Wi-Fi.

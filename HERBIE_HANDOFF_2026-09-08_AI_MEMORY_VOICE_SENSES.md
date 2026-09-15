# Herbie handoff — AI memory, voice, senses, and Pi link

Date: 2026-09-08 (America/New_York), updated 2026-09-09

> **Movement has its own checkpoint:** `HERBIE_HANDOFF_2026-09-09_MOVEMENT.md`.
> Read that first for the STM32 serial protocol and the current robot state
> (the factory app was left frozen with `kill -STOP`).

## User intent

- PAL is now named **Herbie**.
- Herbie should be highly independent, learn from experience, retain long-term memory, and develop a distinct personality over time.
- Herbie should speak, listen, observe, explore, recognize the owner and other people he may develop preferences toward, and display facial expressions.
- Recognition enrollment must be consensual. Unknown people remain anonymous until they knowingly enroll.
- Conversational style may be candid, humorous, opinionated, and use adult language when appropriate. Consent, privacy, cruelty, dangerous physical actions, and motor-safety constraints remain fixed.
- The system must be free: no paid OpenAI API or other paid AI service. No `OPENAI_API_KEY` was created.
- The Galaxy S21 Ultra is the online AI brain. Herbie's original VAVA board does not need internet or VAVA cloud access.

## Current architecture

- **Galaxy S21 Ultra:** primary AI, active identity/memory, voice, microphones, detailed camera/recognition, high-level decisions, and expression state.
- **Raspberry Pi 3B (Melba):** local coordinator, future expression-screen renderer, older media/archive, and backup memory copies. It can remain off the internet.
- **Herbie/VAVA Android board:** original camera, original speaker/audio path, and preserved factory hardware interfaces. Keep its own Wi-Fi/cloud path out of the new architecture.
- **ESP32:** future bounded real-time actuator safety controller only. AI must never directly acquire motor authority.

## Verified live connections

- Galaxy ADB serial: `R5CR11QCHPY`, model `SM-G998U`, Android 15, authorized.
- Herbie/VAVA ADB serial: `0123456789ABCDEF`, rooted factory Android 5.1.
- ESP32: CP210x on `COM7`, `USB\\VID_10C4&PID_EA60`.
- Melba direct Ethernet: IPv6 link-local `fe80::ba27:ebff:fe2e:a57e%17`, MAC `<MELBA_MAC>`.
- Melba SSH identity: `C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519`; user `jfreakingr`; use `HostKeyAlias=Melba.local` with strict host-key checking when connecting by raw IPv6.

## Galaxy resources

- Android data volume: about 105 GB usable, 96 GB free after cleanup.
- RAM: about 10 GB.
- Battery software report during this run: health good and approximately 24 C. This is not a capacity test; reported poor runtime still matters before sealed installation.
- Termux command interfaces verified present: Python, TTS, speech-to-text, microphone recording, camera info/photo, sensors, battery status, and vibration.
- Termux API has camera and microphone permissions granted.

## Herbie phone-brain 0.3.0

- Installed in the existing Termux path: `$HOME/pal-phone-brain`.
- Listens only on Galaxy loopback `127.0.0.1:8765`.
- Windows reaches it through authenticated ADB forward `tcp:18765 -> tcp:8765`.
- Active database: `$HOME/pal-phone-brain/herbie-memory.sqlite3`.
- Legacy response field `service=pal-phone-brain` is retained for bridge compatibility; current identity fields report `service_current=herbie-phone-brain` and `identity_name=Herbie`.
- Motor response remains `motor_authority=false`, `safe_motion_state=STOP`.

Endpoints:

- `GET /health`
- `GET /v1/self`
- `GET /v1/memories?q=<query>&limit=<1-100>`
- `GET /v1/expression`
- `POST /v1/heartbeat`
- `POST /v1/remember`
- `POST /v1/experience`
- `POST /v1/expression`
- `POST /v1/speak`

Persistent self foundation:

- SQLite autobiographical memories
- persistent personality traits: curiosity, sociability, playfulness, confidence, caution, patience
- persistent drives: explore, connect, learn, rest
- bounded learning rate of 0.02 per accepted experience signal
- auditable personality-change events
- persistent expression/activity state: expression, valence, arousal, attention, listening, speaking
- immutable core principles outside the learnable trait table

Four owner requirements were stored as the first memories. Restart verification returned `MEMORIES_AFTER_RESTART=4` and successfully recalled the independence requirement.

## Verified tests

- Rollback of the previous working brain saved at `phone_brain/rollback/pal_phone_brain-0.1.0.py`.
- Five local tests pass: identity/safety, memory persistence, bounded personality learning, invalid-trait rejection, and expression persistence/validation.
- Galaxy service restart preserved all four memories.
- Real local TTS test succeeded.
- New `/v1/speak` endpoint queued speech locally, set expression to `happy`, reported `speaking=true` during output, then returned to `speaking=false`.
- Real three-second Galaxy microphone recording succeeded (5,793 bytes); temporary audio was deleted and not uploaded.
- Real Galaxy camera capture succeeded (3,477,150 bytes); temporary photo and camera-info file were deleted and not uploaded.
- Re-verified 2026-09-08 late session on Windows: **7/7** `phone_brain/test_herbie_memory.py` and **5/5** `pi_bridge/test_herbie_face.py` pass.
- Live phone-brain check the same session: `ready:true`, version `0.3.0`, `memory_count:4`, `motor_authority:false`, `safe_motion_state:STOP`, identity `Herbie`, 5 core principles present.

### Galaxy phone brain 0.7.0 (2026-09-09) — voice layer, DEPLOYED AND VERIFIED

Owner requirement restated during this work: **all of it must be free.** That is
now enforced by `test_herbie_is_free.py`, which scans every module for paid
service names, credentials, non-stdlib imports, unexpected subprocess calls and
outbound network calls. A future session reaching for a hosted model fails the
suite rather than quietly introducing a bill.

Speech remains Android's own TTS via `termux-tts-speak`: already on the phone,
no account, no key, nothing leaves the device.

`herbie_voice.py` rewritten so the voice carries the mood the autonomic layer
produces:

- **Pitch follows valence, rate follows arousal**, with a small jitter so no two
  utterances are acoustically identical. A fixed pitch and speed is the most
  machine-like thing a talking device can do.
- **A pause before answering**, longer when calm, shorter when alert. Instant
  replies feel like a lookup table.
- **Occasional imperfection** — a filler or trailing off, roughly one utterance
  in six. Rare on purpose; overused disfluency is worse than none.
- **Interruptible** via `POST /v1/speak/stop`. A creature you cannot tell to be
  quiet is an appliance.

`POST /v1/urge` now **speaks** the impulse aloud rather than only returning it in
JSON — an impulse that appears only in an HTTP response is not initiative. Silent
night-time urges still change the face only.

Observed on device at 02:00 local, arousal 0.27: rate 0.83-0.88, pause 0.79-1.0s,
pitch varying 0.96-1.01 between calls. Slow and low, because he was winding down.

```
SERVICE_VERSION = "0.7.0"     74 tests pass ON THE PHONE
free audit: none found        interrupt verified working
```

One test bug worth recording: `test_missing_engine_is_reported_clearly`
originally assumed TTS was absent. That passed on the workstation, failed on the
phone where the engine genuinely exists, and made Herbie say "hello" out loud
during the test run. It now stubs `shutil.which` instead, so it is
platform-independent and silent.

### Galaxy phone brain 0.6.0 (2026-09-09) — autonomic layer, DEPLOYED AND VERIFIED

Owner goal: Herbie should be **as convincingly sentient as possible**. Explicitly
the *appearance* of an inner life, not a claim to one.

The gap identified: the service was purely reactive. Nothing about Herbie
changed unless something POSTed to an endpoint, so between requests he was not
running in any meaningful sense. Living things are never idle, and that single
fact read as "machine" more than voice or face detail ever could.

**`phone_brain/herbie_autonomic.py`** adds internal state that changes with no
input at all:

- Drives drift on their own — loneliness builds fastest, then boredom, then the
  urge to learn. Growth is asymptotic, so a drive slows as it saturates rather
  than pinning at the ceiling.
- Mood has inertia: arousal settles over minutes, valence over much longer, so a
  bad mood feels like a mood rather than a state change. Prolonged loneliness
  drags valence down, so it actually varies across a day.
- **Circadian rhythm** from local time — low at 04:00, peak at 16:00. Only
  possible because the clock got fixed the same night; a device that thinks it
  is permanently June cannot have a convincing day and night.
- **Initiative**: when a drive crosses threshold, Herbie changes expression and
  says something nobody asked for. This is the single strongest "alive" cue.

Bounded deliberately. It can touch mood, drives, expression and speech and
nothing else. **There is no urge type corresponding to movement and no way to
add one through this path** — a test asserts the vocabulary contains no motion
words. It stays silent in privacy mode, because an unprompted remark is exactly
what someone who just asked for privacy does not want.

#### Four behaviours found by simulating a day before deploying

A 24-hour simulation with one interaction exposed problems that would have
ruined the illusion on hardware. All four are fixed:

1. **Nagging.** 16 unprompted remarks in 24 hours, including 02:00, 03:30 and
   05:00. Now **4**, and none in the small hours.
2. **No habituation.** Being ignored produced identical pestering forever. Each
   unanswered impulse now widens the gap by 1.8x, up to 5 steps; an interaction
   resets it. Being ignored makes Herbie quieter, which is both how animals
   behave and far less irritating to live with.
3. **Never slept.** `rest` reached 0.93 at 04:00 while he carried on calling
   out, because raw loneliness always won. Urges are now weighted by time of
   day, and below `NIGHT_ENERGY` the only thing he expresses is tiredness,
   **silently** — the face changes, nothing is said aloud.
4. **Repetition.** The same line five times. He now never repeats the previous
   line.

#### Endpoints added

- `GET /v1/mood` — circadian energy, drives, valence/arousal, time since
  interaction, whether he is asleep.
- `GET /v1/urge` — peek at a pending impulse without claiming it.
- `POST /v1/urge` — claim it; returns words and an expression, never motion.
- `POST /v1/interact` — mark engagement, discharging the drives it satisfies.
- `POST /v1/autonomic` — enable/disable the whole layer.

`/v1/remember` and `/v1/experience` also count as interaction.

#### Verified on the device

```
SERVICE_VERSION = "0.6.0"      54 tests pass ON THE PHONE
supervisor alive               memories: 4 (intact across three migrations)
"Autonomic layer: ticking every 10s (mood, drives, circadian rhythm, initiative)"
```

Observed drifting with nothing touching it, over 35 seconds:

```
connect 0.5509 -> 0.5521    explore 0.5506 -> 0.5514
arousal 0.4311 -> 0.4087    valence 0.2948 -> 0.2880
asleep: true   circadian_energy: 0.13   (local 01:39)
```

#### Design notes for whoever continues this

- **Consistency beats novelty.** Randomness reads as broken, not alive. The same
  preferences and quirks showing up reliably is what makes it feel like someone.
  The bounded 0.02 learning rate is right; resist raising it.
- **Do not let him claim it.** Convincing artificial creatures never assert they
  are alive — asserting it breaks the spell, while simply behaving that way
  sustains it. This also keeps the "be honest about capabilities" principle
  intact, so the stronger illusion and the honest system are the same choice.

### Galaxy phone brain 0.5.0 (2026-09-09) — DEPLOYED AND VERIFIED ON DEVICE

Running on the Galaxy and verified there, not just locally. Previous source
backed up to `phone_brain/rollback/pre-0.5.0/`.

On-device verification:

```
SERVICE_VERSION = "0.5.0"
29 tests pass on the phone
memory_count: 4              (all memories survived the migration)
herbie-api-token       -rw------- 44 bytes
herbie-memory.sqlite3  -rw-------
supervisor alive, wake lock acquired
GET /v1/self with no token -> 401
search backend: fts5, q=independent returns the identity memory
```

**Core principle #5 is now implemented.** The principles promise the owner can
"inspect, correct, export, and delete memories". Only inspect existed; the
`memories.active` column had been created for soft deletion and was never
written to. Added `POST /v1/forget` (soft delete, `"purge":true` for
irreversible), `POST /v1/restore`, `POST /v1/correct`, and `GET /v1/export`
(full local dump; includes soft-deleted rows, since an export that silently
omits retained data is not an export).

**Fixed an atomicity bug in `experience()`.** It called `remember()` — which
commits immediately — and validated `signals`/`learning_reason` afterwards. An
invalid trait therefore returned HTTP 400 while the memory row was already
persisted: the caller was told it failed, the database disagreed. Validation now
runs entirely before any write.

**Added authentication.** Every endpoint except `/health` requires
`Authorization: Bearer <token>`. Loopback is not access control: other apps on
the phone can reach `127.0.0.1`, and `adb forward` republishes the port on the
workstation's loopback, so previously anything local could rewrite personality,
insert memories, or **switch privacy mode off**. Token is generated at first
start into `herbie-api-token` (mode 600), compared with `hmac.compare_digest`,
and never logged. `/health` stays open but returns only readiness plus the
safety fields when untokened.

**Added FTS5 search and indexes.** Search was `content LIKE '%q%'` — a full scan
with poor recall. Now SQLite FTS5 with the porter stemmer, so "independence"
matches "independent". Query terms are quoted before reaching FTS5 so
punctuation cannot act as a search operator. Falls back to substring matching
automatically where FTS5 is unavailable, reporting which via the `search` field.
Five indexes added. Ordering is now explicit (`order=recent|relevance`); the
endpoint previously changed meaning silently depending on whether `q` was given.

**Added keep-alive.** `herbie_supervisor.sh` holds a `termux-wake-lock` and
restarts the brain after an Android battery-optimisation kill, with backoff that
resets after a healthy run. `boot_herbie.sh` installs to `~/.termux/boot/` for
restart-after-reboot — **requires the Termux:Boot addon**, inert without it.
`stop_pal_brain.sh` stops the supervisor first; `start_pal_brain.sh` refuses to
fight it for the port.

Tests: **27 pass** (`test_herbie_memory.py` 7, `test_herbie_rights.py` 20),
covering memory rights, experience atomicity, search behaviour including hostile
query punctuation, and end-to-end token enforcement over real HTTP.

`tools/Test-Pal-Phone-Brain.ps1` now reads the token off the phone, checks the
device is attached first, and asserts an untokened request receives 401 so the
auth layer cannot silently regress.

**Deploy with `tools/Deploy-Herbie-Phone.ps1`.** Note the installer must run
*inside Termux* — Termux's home is under `/data/data/com.termux`, which the adb
shell user cannot write to. The script stages files to `/sdcard/Download/PalBrain`
and tries Termux's `RunCommandService`, which needs `allow-external-apps=true`
and the RUN_COMMAND permission; otherwise run
`bash /sdcard/Download/PalBrain/install_pal_brain.sh` in Termux via scrcpy.

**Breaking change:** first start generates the token and every existing client
fails until it sends one.

### Trap: CRLF line endings break Termux

Editing a `.sh` from Windows with Python's text-mode `open()` silently converts
every `\n` to `\r\n`, and Termux's bash then fails with
`$'\r': command not found` / `syntax error near unexpected token $'do\r'`.
This broke an install once. `Deploy-Herbie-Phone.ps1` now checks every `.sh`
for CR bytes and converts before pushing, but when writing these files from
Python use binary mode or `newline="\n"` explicitly.

### Trap: PowerShell array matching

`& adb devices` returns an **array of lines**. `$array -notmatch 'pattern'`
returns the non-matching *elements*, not a boolean, so the "List of devices
attached" header alone makes the condition truthy. This made three scripts
falsely report the phone as detached. Always `-join "\n"` before matching.

### Note: the face

The owner is handling Herbie's face art themselves. Two style explorations
written and then parked live in `pi_bridge/experimental/` with a README; nothing
imports them and they can be deleted freely. Two genuine findings about the live
`pi_bridge/herbie_face.py` came out of that work and still stand: `render_svg`
does not validate `expression` (only `merge_expression` does), and it ignores
`valence`/`arousal` entirely — so it cannot display the continuously varying
mood the autonomic layer now produces.

### Getting the token to Windows

Termux's home is private to the Termux UID, so **`adb shell cat` cannot read the
token** and `run-as` does not work (Termux is not debuggable). The only channel
is shared storage.

`tools/Export-Herbie-Token.ps1` does this once: asks Termux to copy the token to
`/sdcard`, pulls it, **deletes the shared copy immediately**, and stores it at
`%USERPROFILE%\.herbie\api-token` with inheritance removed and access limited to
the current user. The token is never printed to the console or any log.

The `/sdcard` hop is the weak point — while the file is there, any app with
storage permission could read it. It exists for seconds and is then removed. Re-run
the script if the token is ever regenerated.

`tools/Test-Pal-Phone-Brain.ps1` reads that local file automatically.

### Bug found and fixed during deployment: empty FTS index

Worth recording, because the failure was silent. The first 0.5.0 build shipped an
FTS index that **matched nothing** — every search returned zero results, which is
worse than the substring behaviour it replaced.

Cause: the backfill guard compared `SELECT COUNT(*) FROM memories_fts` against
`SELECT COUNT(*) FROM memories`. With an FTS5 **external content** table the first
query reads through to the content table, so it always equals the row count. A
completely empty index therefore looked fully built and `rebuild` never ran.

The local tests missed it because they create memories *after* the FTS table
exists, so the triggers populate the index. The bug only appears on the
**migration path** — an existing database gaining an index — which is exactly the
real case. Fixed by counting `memories_fts_docsize` (one row per genuinely indexed
document) instead, which also self-heals an already-broken database on next start.

`FtsMigrationTests` in `test_herbie_rights.py` now builds a pre-FTS database, runs
`initialize()`, and asserts the old memories are findable. It was confirmed to
fail against the buggy guard before the fix was reapplied.

### Galaxy USB fault (2026-09-09) — recurred once, then cleared

The Galaxy dropped off ADB mid-session and did not return. Windows enumerates it
but the driver will not start:

```
USB\VID_04E8&PID_6860\R5CR11QCHPY   Status: Error   CM_PROB_FAILED_START (Code 10)
```

The phone is powered on; the USB endpoint is dead. `pnputil /restart-device`
returns *Access is denied* without elevation. Fix is a physical replug,
preferring a **USB 2.0 port directly on the machine** rather than one of the
several hubs in this tree — Samsung composite devices fail this way on USB 3.0
xHCI ports fairly readily. A replug cleared it (`CM_PROB_NONE`) and deployment
then completed, so treat Code 10 as a replug prompt rather than a fault to
debug.

Note the brain itself kept running throughout the outage — only the USB link
died. `/health` answered immediately once ADB returned.

Keep-awake settings applied by `Deploy-Herbie-Phone.ps1` once ADB returns:
`stay_on_while_plugged_in=7`, `dumpsys deviceidle whitelist +com.termux`,
`screen_off_timeout=30m`, plus the supervisor's wake lock. Windows-side, also
consider disabling USB selective suspend on the active power plan.

### Face renderer (built after the first draft of this handoff)

`pi_bridge/herbie_face.py` renders Herbie's validated expression state as an SVG face: 8 expressions (`calm`, `curious`, `happy`, `playful`, `thinking`, `surprised`, `concerned`, `sleepy`), a `MIC` listening indicator, and a `privacy_mode` that forces `listening=false`, sets expression to `calm`, and hard-rejects camera/mic activation with `privacy_blocks_senses`. It talks to no display and commands no motors. This substantially covers next steps 3 and 4 in software; only on-screen verification is outstanding, and that is blocked on identifying the screen.

Relevant source:

- `phone_brain/pal_phone_brain.py`
- `phone_brain/herbie_memory.py`
- `phone_brain/herbie_voice.py`
- `phone_brain/test_herbie_memory.py`
- `phone_brain/install_pal_brain.sh`
- `phone_brain/probe_herbie_senses.sh`
- `phone_brain/test_herbie_voice_mic.sh`
- `phone_brain/test_herbie_camera.sh`

## Melba/Pi state

- Hostname `Melba`, Raspberry Pi 3 Model B Rev 1.2, aarch64.
- Direct Ethernet responds in under 1 ms at the recorded IPv6 link-local address.
- `pal-pi-bridge` is active.
- User reports steady red power LED and rhythmically blinking green activity LED; boot and card activity are present.

### Storage question resolved (2026-09-08 late session)

`lsblk` shows exactly one block device: `mmcblk0`, **58.2 GB** (card id `mmc-ASTC_0x00001009`), partitioned as `mmcblk0p1` 512 MB vfat on `/boot/firmware` and `mmcblk0p2` 57.7 GB ext4 on `/`. Root is **already fully expanded**: 57 GB total, 2.8 GB used, 52 GB free. `lsusb` shows only the internal SMSC9514 hub and its Ethernet adapter, so no USB storage is attached.

**There is no 128 GB device attached to Melba.** Nothing to expand, format, or migrate. If a 128 GB card exists it is physically elsewhere. Do not act on the earlier 128 GB assumption.

### Display question resolved (2026-09-08 late session): nothing is connected

- Only DRM connector is `card0-HDMI-A-1`, status **`disconnected`**. No DSI panel enumerates.
- `vc4-kms-v3d` loads and logs `Cannot find any crtc or sizes`. That is why there is no `/dev/fb*` node — expected with no panel attached, **not** a driver fault.
- **SPI and I2C are not enabled.** No `/dev/spidev*`, no `/dev/i2c-*`, and `config.txt` contains no `dtparam=i2c_arm=on` or `dtparam=spi=on`. The `i2c_bcm2835` module is loaded but has no bus nodes.
- `display_auto_detect=1` is set, so an official DSI touch display would come up unattended.

Conclusion: the screen cannot be identified from software because it is not plugged into anything. Once connected, **HDMI or DSI will self-enumerate**; a **GPIO/SPI or I2C panel needs a `config.txt` change first** and will stay invisible until then. This is why installing a driver by guesswork would have been wrong — an undetected panel proves nothing about which kind it is.

Active `config.txt` lines: `dtparam=audio=on`, `camera_auto_detect=1`, `display_auto_detect=1`, `auto_initramfs=1`, `dtoverlay=vc4-kms-v3d`, `max_framebuffers=2`, `disable_fw_kms_setup=1`, `arm_64bit=1`, `disable_overscan=1`, `arm_boost=1`.

### Clock is wrong and unsynchronized (new finding, 2026-09-08)

`date -u` reported **2026-06-18** — the image build date — while the real date was 2026-09-08. `timedatectl` reports `NTPSynchronized=no`. The Pi 3B has no RTC and Melba is deliberately offline, so it never acquires real time. `uptime -s` and `who -b` therefore report a fictional boot date, although *elapsed* uptime is correct.

**Any timestamp Melba writes is wrong.** Resolve this before building memory replication or archiving, because archived memories would be misdated and would sort incorrectly against the Galaxy's correct timestamps. Options: push the time from the Windows host on each connect (no hardware, no internet needed), or fit a DS3231 RTC (needs I2C enabled — which a GPIO panel would need anyway).

### Melba's dropouts: SOLVED 2026-09-09 — NetworkManager, not hardware

**Root cause found and fixed. It was a configuration bug, not a fault.** Every
hardware theory in earlier drafts of this file was wrong, including undervoltage,
"load-induced" failure, and an `smsc95xx` USB Ethernet hang. Do not act on them.

`eth0` is a direct cable to the workstation: no DHCP server, no router
advertisements. The connection was configured `ipv4.method=auto` **and**
`ipv6.method=auto`. Both fail, so NetworkManager marked the connection failed and
**deconfigured the interface** - which withdrew the link-local address and dropped
avahi out of the mDNS group - then waited exactly 5 minutes and retried:

```
03:21:37 NetworkManager: device (eth0): ip-config -> failed ('ip-config-unavailable')
03:21:37 NetworkManager: Activation: failed for connection 'netplan-eth0'
03:21:37 avahi-daemon:   Withdrawing address record for fe80::ba27:ebff:fe2e:a57e
03:21:37 avahi-daemon:   Leaving mDNS multicast group on interface eth0.IPv6
03:26:37 NetworkManager: policy: auto-activating connection 'netplan-eth0'
```

That is the measured ~7 minute cycle: roughly 170 s up, 235 s down. It also
explains the detail that never fitted a hardware story - direct IPv6 ping and
mDNS failed *together*, because the address itself was being removed. This boot
logged **33 "Joining mDNS" / 32 "Leaving mDNS"**: 32 complete teardown cycles.

**The hardware was never at fault.** `rx_errors: 0`, `tx_errors: 0`,
`rx_dropped: 0`, carrier present, and no `smsc95xx` reset after the normal
boot-time link negotiation at t+40 s.

#### Fix applied

```
sudo nmcli connection modify netplan-eth0 ipv4.method link-local ipv6.method link-local
sudo nmcli connection modify netplan-eth0 connection.autoconnect-retries 0
sudo nmcli connection up netplan-eth0
```

Applied via a detached `systemd-run` (bringing the connection up kills the SSH
session running the command) with a 5-minute `systemd-run` auto-revert armed
first as a dead-man's switch, then cancelled once connectivity was confirmed.
Given this file's record of a previous lock-out from bad network config written
remotely, arm that revert on any future network change.

Result: eth0 state `connected`, state machine running `ip-config -> ip-check ->
secondaries -> activated` with no failure, and **zero** mDNS teardowns in the
20 minutes after the fix.

#### Undervoltage: real but unrelated

`0x50005` persists, and the journal shows 41 `Undervoltage detected!` paired with
40 `Voltage normalised` - it flaps and recovers every time. It did **not** cause
the dropouts. The owner's long-standing position that this flag is not worth
chasing is correct. Do not recommend another PSU, and do not open or resolder the
board on the strength of it: the Pi holds hours of uptime with zero network errors.

### Melba is now on Wi-Fi, and the clock is fixed

`wlan0` was down because the only profile was `netplan-wlan0-MySpectrumWiFi20-5G_EXT`
- a **5 GHz** SSID, which a Pi 3B's 2.4 GHz-only radio can never join. That stale
profile now has `connection.autoconnect no`.

Joined to the real 2.4 GHz network instead. **The correct SSID is
`<WIFI_SSID>`** (channel 11, WPA2) - note this does *not* match
`<WIFI_SSID_OLD_WRONG>` as recorded in `PAL_HANDOFF_2026-09-07_BLE_WIFI.md`, which
should be corrected there. The password was entered interactively by the owner via
`sudo nmcli --ask device wifi connect`, so it never entered a script, log, or
handoff.

```
wlan0  connected  <WIFI_SSID>  192.168.1.140/24
eth0   connected                           169.254.18.48/16
NTP synchronized: yes    Wed 2026-09-09 01:14 EDT   (was reporting 18 June)
internet: 0% loss, 33 ms
```

**The clock is now correct**, so the earlier warning about Melba misdating every
record it writes is resolved. `systemd-timesyncd` is active and synchronised; no
RTC is needed.

#### Two access paths now exist

```
ssh -i C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519 -o HostKeyAlias=Melba.local jfreakingr@169.254.18.48   # direct cable
ssh -i C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519 jfreakingr@192.168.1.140                                # over the LAN
```

The IPv4 link-local address removes the need for the `%17` scope-ID form that
every previous command in this file used. That older IPv6 form still works.

#### Architecture note: Melba now has internet

The architecture section above states Melba "can remain off the internet". As of
2026-09-09 it is on the household LAN with working internet, at the owner's
request, because that is what supplies NTP. This is a deliberate trade-off, not
drift. If keeping Herbie's coordinator off the internet matters later, the clock
can instead be pushed from the workstation on connect, or an RTC fitted, and Wi-Fi
disabled again.

### Fitness verdict (revised 2026-09-09)

The earlier verdict - 42% availability, unfit for the coordinator role, move the
archive to the Galaxy - was based on a fault that has since been **fixed**. With
the NetworkManager cause resolved and the clock synchronised, both objections are
gone. Re-evaluate rather than inheriting the old conclusion.

Re-measure with a fresh soak before assigning Melba any role that involves data it
would be bad to lose, but the prior "not fit" judgement no longer applies.

### How to test this properly

Do **not** use synthetic 4-core load. It proved nothing here - the real cause was found in the journal, not by stressing the board. It is unrepresentative of Melba's actual duty (coordinator plus face renderer are light) and it reliably knocks the board off the network, costing time. Instead run a **realistic-workload soak**: leave `pal-pi-bridge` doing its normal job and poll it on a low-frequency heartbeat for 20-30 minutes, logging every missed reply with a timestamp. That answers the only question that matters for the project — whether Melba is fit for its assigned role — without depending on a flag known to be unreliable on this board.

If it holds up at realistic load, proceed and design around the limitation: keep Melba's duties light, make the Galaxy the authority for anything that must not be lost, and make the Windows-side tooling tolerant of Melba disappearing (retry with mDNS refresh; the IPv6 neighbor entry goes `Unreachable` and a `ping Melba.local` revives resolution).

Diagnostic scripts used are in the session scratchpad pattern: pipe a local `bash -s` script over SSH rather than quoting a long command line through PowerShell, which mangles quotes.

No Pi files were changed during this run or the 2026-09-08 late session.

## Original Herbie camera and speaker

- MediaTek camera HAL is active and exposes one camera device, orientation 90 degrees. No client was active during inspection. A real capture through a new bridge is still required before declaring the original camera fully operational.
- Original speaker is physically proven by factory startup voice/music.
- Android audio reports the MediaTek sound card and speaker route. ALSA playback devices are present.
- Factory Android lacks `tinyplay`, `aplay`, `stagefright`, and a command-line media player. Build a small playback bridge or use a safe Android media component before routing Galaxy speech to the original speaker.

## Movement (2026-09-09) — path found, protocol capture pending

### Owner decision: motor control belongs to the brain

The owner directed that **motor function is controlled by the brain**, not by a
separate controller with veto power. An ESP32-owns-motors safety design was
started and then removed on that instruction.

This supersedes the earlier standing note that motor authority must live only in
an ESP32 layer. **Do not re-introduce a controller that can override the brain.**
Limits, sensor responses and authority still exist — they simply live in
`phone_brain/herbie_motion.py` where the owner can see and change them, rather
than being compiled into firmware.

The owner also stated Herbie **can go where he wants** — autonomous roaming is
the goal, not teleoperation. The `explore` drive in the autonomic layer is what
moves him.

### The most direct path from brain to wheels

Established this session. No soldering, no ESP32, no L298N, and the factory
sensors stay in the loop:

```
Galaxy (brain) --USB-C OTG cord--> VAVA Android board (rooted, ADB 0123456789ABCDEF)
                                    `-> /dev/ttyMT1  (mtk-uart hardware serial)
                                          `-> STM32F103 -> motor drivers -> wheels
                                                        `-> anti-collision + anti-fall sensors
```

The owner has a cord that connects the phone directly to the board, which
removes the Windows PC from the runtime path entirely.

### Evidence for /dev/ttyMT1

- `/proc/tty/drivers` lists `mtk-uart` at `/dev/ttyMT` 204:209-210. `ttyMT1` is
  the second hardware UART.
- Permissions are **`crwxrwxrwx system system`** while every other node is
  root-owned `crw-------`. It was deliberately opened up.
- Its timestamp is **3 minutes after boot** (09:10 vs 09:07 for everything
  else) — a service claimed it, then exited.
- **No file descriptor currently points at it.** The factory app never started
  (still on `bootanimation`, waiting for network config it will never get), so
  the port is free.
- The string `/dev/ttyMT1` appears **directly in the control app's dex**.

This is the same bus previously listened to passively on J21: the STM32 was
transmitting `00 AA 55 00 07 02 NN 00 5A 00 00 <xor>` status frames to this port.

### The factory app knows the protocol

`com.sego.toy.ctl` is still installed and matches the board silkscreen
`SE6POET SG_802_LD_V1.2_CTL` — SEGO, SG_802, **CTL**. Also present:
`com.sego.toy.ipc` (camera side). Both APKs pulled to the session scratchpad.

It bundles `lib/armeabi/libserial_port.so` (the standard android-serialport-api
JNI wrapper) plus `android/serialport/SerialPort.java.nosleep.zip`, so the
framing logic is in Java, not native code.

Protocol vocabulary recovered from the dex string table:

| Token | Meaning |
|---|---|
| `TOY_CONTROL`, `GENERAL_CONTROL` | top-level control messages |
| `LEFT`, `RIGHT`, `STOP`, `TURN`, `SPEED`, `OVERSPEED` | motion |
| `EDGE_LEFT`, `EDGE_RIGHT` | **anti-fall sensors report over this link** |
| `CONTROL_PANTILT`, `PANTILT_MOVE_REGION`, `CONTROL_SERVO` | camera pan/tilt |
| `TEST_MOVE`, `TEST_LASER_PEN` | factory test commands |
| `FEED_DOG`, `FEEDPLAN`, `CMD_FEED_TIME` | treat dispenser |
| `PC_TRANSPARENT_DATA_DOWN` / `_UP` | transparent serial passthrough |
| `ToyVO$Toy$Control`, `$ControlCommand`, `$Heartbeat` | protobuf schema |

Note the app is `LITE_RUNTIME` protobuf, so there is no embedded descriptor to
dump; enum values have to come from the dex or from observed traffic.

### Hardware proof that ttyMT1 is the STM32 link (2026-09-09)

`/proc/tty/driver/mtk-uart` byte counters, read while the app was not running:

```
0: uart:MTK UART mmio:0x11005000 irq:76 tx:21  rx:0     <- console
1: uart:MTK UART mmio:0x11006000 irq:77 tx:156 rx:78    <- ttyMT1
```

`ttyMT1` has carried traffic in **both** directions. The 78 received bytes are
exactly 6 x 13, i.e. six of the 13-byte status frames decoded on J21. That is
direct evidence of the STM32 transmitting into this device node, not inference.

### Motors need the adapter, not USB

A 30-second passive listen on `/dev/ttyMT1` captured **0 bytes**. Cause:

```
/sys/class/power_supply/ac/online   -> 0    (16.8 V adapter NOT connected)
/sys/class/power_supply/usb/online  -> 1    (USB from the workstation only)
/sys/class/power_supply/battery     -> present, Full
```

The Android board boots happily on USB, but the STM32 and motor drivers are on
the main rail. **No adapter means no STM32 and no serial traffic at all.** Zero
bytes is the signature of an unpowered peer; a wrong baud rate would produce
garbage instead.

Before any capture attempt: connect the 16.8 V adapter, keep the battery out,
and raise the tracks.

### Next step: capture real motor frames

`com.sego.toy.ctl/.test.ActionTestActivity` is a factory action-test screen.
Launching it and listening on `/dev/ttyMT1` makes the app emit genuine motor
frames, which removes all guesswork about an unknown protocol. Full activity
list: `.test.ActionTestActivity`, `.test.CameraActivity`, `.test.MediaTestActivity`,
`.ui.MainActivity`, `.CtlService`, `.BootService`, `.KeyReceiver`.

**Precondition: raise the tracks first.** This makes the robot actually drive.
Battery stays quarantined; power from the 16.8 V adapter only.

Capture method (the board's toolbox is unusually bare — no `head`, `sort`, `tr`,
`basename`, `which`; `cat`, `grep`, `ls`, `ps`, `dmesg`, `logcat`, `getprop` do
exist):

```
adb -s 0123456789ABCDEF shell "cat /dev/ttyMT1 > /sdcard/mt1.bin &"
adb -s 0123456789ABCDEF shell am start -n com.sego.toy.ctl/.test.ActionTestActivity
# trigger a move, then:
adb -s 0123456789ABCDEF pull /sdcard/mt1.bin
```

Use PowerShell for any `adb` command containing an Android absolute path: Git
Bash rewrites `/data/...` into `C:/Program Files/Git/data/...` and the pull fails.

### The factory control API — found, not yet callable

Both factory APKs are saved to `software/sego-factory-apks/` (`ctl.apk`,
`ipc.apk`). The dex string table gives up the whole control surface.

**`com.sego.toy.ctl.IToyCtl` is a full AIDL robot API**, exposed on the declared
and exported `CtlService` via action `sego.toyctl.action.CTL_SERVICE`:

```
doMove   stopMove   isMoving
takeSnapshot   startRecord   stopRecord   setVideoResolution   toggleGrayscale
login   isOnline   sendTextMessage   sendUmsg   outgoingCall   terminateCall
cancel   cancelAll   exit   isUpgrading   isUploading
```

**Movement vocabulary** (log strings and field names):

```
move_forward   move_backward   move_left   move_right
direction   distance   speed   speedLevel   cur_speed   OVERSPEED
"Do move "   "Stop move"   "Test move"   "Do ToyControl command "
dirTypeForward   dirTypeBackward
pant_action_angle_move   pant_action_step_move     (camera pan/tilt)
```

Relevant classes: `board.MoveTask`, `board.SimpleMoveTask`, `board.CircleMoveTask`,
`board.TrackTask`, `board.LaserTrackService`, and
`proto.TermSegoUartProtocolAdaptor` (the UART framing) with
`proto.TermSegoPacket$GENERAL_CONTROL`, `$SERIAL_COMMAND_LINE`,
`$CONTROL_PANTILT`, `$POSITION_DATA`, `$HEADER` / `$TAIL`.

### Three approaches ruled out

1. **Built-in REST server — not usable.** The app contains a complete HTTP stack
   (`rest.Httpd`, `rest.WebServer`, `rest.WebServService`,
   `rest.request.ToyControlService`, routes `/rest/operate`, `/Appinterface.do`,
   banner `WebServer/1.1`) and broadcast actions `sego.toyctl.action.WEBSERV_START`
   / `_STOP`. **But none of it is declared in the manifest** — `am start` on
   `.rest.WebServActivity` returns *"Activity class does not exist"*, the
   broadcast changes nothing, and no port ever opens. Vestigial code from a
   shared codebase. Do not spend more time here.

2. **Intent-driven movement — not supported.** `CtlService.onStartCommand` fires
   and logs `Ctl service onStartCommand`, but ignores extras: no combination of
   `--es cmd/direction/command move_forward --ei speed/distance ...` ever produced
   the `"Do move "` log line. Movement is reachable only through the AIDL binder.

3. **Vendor cloud — dead, as suspected.** `IOTC_Device_Login return -1`, and the
   app's own UI shows `NET` grey against `enapp.pumpkin.segopet.com`. Only UDP
   32761 (TUTK P2P) and 42379 listen; the sole TCP listener is adb on loopback.

### Robot network identity

Herbie's board is **already on the household Wi-Fi**: `192.168.1.122/24` on
`wlan0`, MAC `<HERBIE_WLAN_MAC>`, SSID `<WIFI_SSID>` — the same
subnet as Melba (`192.168.1.140`). The Galaxy can therefore reach him over Wi-Fi
with **no cord and no OTG at all**. The app's own screen shows `WIFI` green.

Device UID `<HERBIE_DEVICE_UID>` matches the BLE advertised name recorded in
`PAL_HANDOFF_2026-09-07_BLE_WIFI.md`.

Note: the board's `/sys/class/power_supply/ac/online` reads `0` even with the
adapter connected — `dumpsys battery` / `PowerManagerService` correctly report
`mPlugType=2` (AC). **Trust the plug type, not the `ac` node.**

### ActionTestActivity is guarded

`com.sego.toy.ctl/.test.ActionTestActivity` is declared and exported, contains
`TEST_MOVE` / `TEST_LASER_PEN`, and starts cleanly (`Status: ok`, a 540x864
surface is created) — then finishes before drawing. `MainActivity` keeps focus.
No exception is logged. Extras tried without effect: `test`, `type`, `action`,
`index`, `auto`. No `ro.*` factory/test property looks relevant.

Determining the guard needs its bytecode, which needs a dex disassembler.

### PROTOCOL RECOVERED (2026-09-09) — option B is unblocked

The owner chose **option B: bypass the factory app**. The serial protocol has
now been fully recovered from the factory APK and implemented.

How, in case it needs redoing: the app uses **JNA**, so `TermSegoPacket$*` are
`Structure` subclasses mapping C structs one-to-one. That means the wire format
is recoverable from the DEX without a decompiler —

- `tools/dexstrings.py` — DEX string table (a plain `strings` scan misses
  almost everything; DEX strings are MUTF-8 with ULEB128 length prefixes)
- `tools/dexfields.py` — field names and types per class
- `tools/dexfieldorder.py` — the **declaration order**, read out of each
  `getFieldOrder()` method's `const-string` instructions. The DEX field table is
  sorted alphabetically, which is useless for a wire format.
- `tools/dexstatics.py` — static final values, i.e. the command codes

#### The frame format

```
AA 55 | 00 07 | 02 | 08 | 00 5A 00 00 | A8
 hdr    length  cmd  seq     payload    crc
```

- `frame_header` — literal bytes `AA 55` (`FRAME_HEADER = 0x55AA`)
- `length` — big-endian uint16, counting `command` through `crc` inclusive
- `command`, `sequence` — one byte each
- `crc` — XOR of every preceding byte in the frame (`TermSegoPacket$TAIL`)

The serial link uses `SHORT_HEADER` (`frame_header, length, command, sequence`),
not the full `HEADER` — the latter carries an 8-byte `device_no` and is for the
network protocol.

#### Confirmed against real captures

The decode was validated against frames recorded from J21 *months before* the
app was ever examined:

| Evidence | Result |
|---|---|
| Idle frames, command `0x02` | `cmd_heartbeat` — matches |
| Power button, command `0x25` | `cmd_key_event` — matches |
| `KEY_EVENT` is `{number, action}` | exactly the 2 payload bytes seen |
| "the seventh byte increments" (old note) | it is `sequence` |
| Rebuilding a captured heartbeat | **reproduces the bytes exactly** |

#### Movement commands, verbatim from `board.SimpleMoveTask.doAction()`

```
move_forward   ->  control_pantilt,0,0,1,4,1000
move_backward  ->  control_pantilt,0,0,1,3,1000
move_left      ->  control_pantilt,0,0,1,2,1000
move_right     ->  control_pantilt,0,0,1,1,1000
head_rise      ->  control_servo,0,0,2,1,1000
head_bow       ->  control_servo,0,0,2,2,1000
```

Movement is a **text command line** carried in a framed packet: direction in the
fifth field (forward 4, back 3, left 2, right 1), duration in milliseconds last.
Sent as `cmd_serial_command_line` (`0x2E`) with a `COMMAND_LINE` payload of
`operation` (int, `msgop_dev_command = 2`) plus the text.

#### Command codes (from `TermSegoValue`)

```
0x01 general_response   0x02 heartbeat        0x12 toy_login
0x20 general_control    0x21 toggle_peripheral 0x22 control_servo
0x23 control_pantilt    0x24 control_light    0x25 key_event
0x26 query_board_version 0x2A take_snapshot   0x2C command_line
0x2D set_board_time     0x2E serial_command_line
0x30 position_status    0x40 start_record     0x41 stop_record
0x44 query_board_config
```

Also recovered: peripheral ids (`laser_pen 1`, `feeding_tray 3`,
`collision_avoidance 12`, `ball_launcher 5`, ...), key event ids
(`power 1`, `low_voltage 3`, **`collision_warning 5`**, `touch1 6`, `touch2 7`),
and light actions. **`collision_warning` arriving as a key event is how the
board reports an obstacle** — Herbie's brain can read his own bumper.

#### Implementation

`phone_brain/herbie_vava_protocol.py` — builds and parses frames, with the
duration capped at `MAX_DURATION_MS = 2000` inside the builder. It is
deliberately **pure**: it imports only `typing`, performs no I/O, and cannot
transmit. A test asserts that by inspecting the AST. Sending is a separate,
explicit decision made elsewhere.

`phone_brain/test_herbie_vava_protocol.py` — 15 tests, including the
byte-exact rebuild of a captured heartbeat.

#### Remaining step to actually move him

1. Stop the factory app so the port frees up: `am force-stop com.sego.toy.ctl`
   (`com.sego.toy.daem` is a watchdog and may restart it — check).
2. `/dev/ttyMT1` is `crwxrwxrwx`, so no chmod is needed. Set 115200 8N1.
3. Write `vava.move("forward", 500, seq)` and watch for a `general_response`.
4. **Tracks raised, adapter connected, battery out.**

The unverified assumptions are: that `cmd_serial_command_line` is the right
carrier (vs `cmd_command_line` `0x2C`), and that `operation` is
`msgop_dev_command`. If the board does not respond, try `0x2C` and the other
`msgop_*` values — the framing and checksum are confirmed correct regardless.

### What is actually needed to move him

A binder client **on the robot's board** that binds `sego.toyctl.action.CTL_SERVICE`
and calls `doMove`. That means either:

**Option A — build a small bridge APK.** It binds `IToyCtl` and exposes a tiny
HTTP endpoint on the robot; the brain then drives Herbie over Wi-Fi. Reuses the
factory motor logic *and its anti-collision / anti-fall handling*, so Herbie keeps
his cliff sensors. Requires a JDK plus Android build-tools — both free, but a real
install; this workstation has **no `java`, `javac`, SDK, `dx`, `d8` or `aapt`**.

**Option B — bypass the factory app entirely.** Kill `com.sego.toy.ctl`, take
`/dev/ttyMT1` (it is `crwxrwxrwx` and would then be unclaimed) and write STM32
frames directly. No toolchain needed, and Herbie becomes fully independent of the
dead vendor stack — but the frame format has to be recovered from
`TermSegoUartProtocolAdaptor`, which again needs a dex disassembler, and the
anti-collision / anti-fall behaviour would have to be reimplemented in the brain.

Option A is less work and keeps the safety sensors. Option B is more work and
gives complete independence. Both are free.

### Useful facts for whoever continues

- The board's toolbox is unusually bare: **no** `head`, `sort`, `tr`, `basename`,
  `which`, `dd`, `od`, `busybox`. Available: `cat`, `grep`, `ls`, `ps`, `sh`,
  `dmesg`, `logcat`, `getprop`, `toolbox`. Filter output on the workstation.
- Use **PowerShell** for any `adb` command containing an Android absolute path.
  Git Bash rewrites `/data/...` to `C:/Program Files/Git/data/...` and it fails.
- `scratchpad/dexstrings.py` parses the DEX string table properly; a plain
  `strings` scan misses almost everything, because DEX strings are MUTF-8 with
  ULEB128 length prefixes rather than NUL-terminated runs.
- Running processes when powered: `com.sego.toy.ctl` (holds ttyMT1 on fd 35),
  `com.sego.toy.daem` (watchdog), `com.sego.toy.ipc` (camera).

### Brain-side motion module

`phone_brain/herbie_motion.py` exists and holds the movement decision logic:
owner-adjustable speed and turn caps, cliff and obstacle responses, explicit
persisted `motor_authority` defaulting to off, and a `wander()` that turns the
`explore` drive into a heading Herbie commits to for a few seconds at a time
rather than re-randomising every tick.

**It is not finished.** Its `wire_format()` currently emits a simple
`M <left> <right> <ms> <seq> <xor>` line aimed at a generic driver. Once the real
VAVA frames are captured, that function is the single place that needs to change
to speak the STM32's actual protocol. Nothing else in the module assumes a
particular driver.

Not yet wired into `pal_phone_brain.py`, and no endpoints are exposed for it.

## Required safety state

- Battery and unknown motor wiring remain quarantined/unmodified.
- `motor_authority=false` and `safe_motion_state=STOP` on Galaxy and Pi services.
- Do not issue motor, treat, laser, pan/tilt, or charging commands.
- Do not give language-model output direct actuator access.
- Before physical roaming: verify independent ESP32 watchdog, physical motor cutoff, fuse, bounded speed, obstacle sensing, and edge/fall protection.
- Keep phone power regulated and electrically isolated from the robot motor supply.

## Immediate next steps

1. **Screen — needs hardware, software side exhausted.** Identify the Pi expression screen by model and connector photo (HDMI, DSI, GPIO/SPI, or USB). Confirmed 2026-09-08 that nothing is currently connected and that SPI/I2C are disabled, so a GPIO panel cannot self-report. Still do not install a display driver by guesswork.
2. ~~Run `lsblk` and identify the reported 128 GB storage.~~ **Done 2026-09-08 — no 128 GB device exists.** Single 58.2 GB card, root already expanded, 52 GB free. See Melba/Pi state.
3. ~~Deploy phone brain 0.5.0 / 0.6.0 / 0.7.0.~~ **Done 2026-09-09** — 0.7.0
   verified on device, 74 tests passing, memories intact, auth enforced,
   autonomic layer ticking, voice shaped by mood, cost audit clean.
4. **Characterise Melba's stability with a realistic-workload soak, not another PSU.** Root cause of the dropouts is still open; the undervoltage flag is permanently on regardless of supply and cannot arbitrate. Confirm whether the micro-USB *cable* was ever changed. Then decide whether Melba is fit for the coordinator/archive role or whether those duties move to the Galaxy. Give it a real time source either way.
3. Build the Pi face renderer against Herbie's validated expression state; verify on the actual screen.
4. Add a visible listening/camera indicator and a physical/software privacy mode.
5. Implement free local wake word and speech recognition. `termux-speech-to-text` exists, but determine whether it uses a remote recognizer before calling it local/private; prefer an on-device engine for retained privacy.
6. Select and benchmark a small free local language model on the Galaxy. Do not add a paid API key.
7. Implement consenting-person enrollment and local face embeddings; do not retain raw images by default.
8. Build read-only original-camera capture and original-speaker playback bridges, then verify each independently.
9. Only after perception and motor-safety gates pass, add supervised exploration intents through the Pi and ESP32 watchdog.

## Recovery/verification commands

Windows ADB binary:

`C:\Users\Phyllis\Desktop\Drive\Pal\tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe`

Phone-brain verification:

```powershell
& '.\tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe' -s R5CR11QCHPY forward tcp:18765 tcp:8765
Invoke-RestMethod 'http://127.0.0.1:18765/health'
Invoke-RestMethod 'http://127.0.0.1:18765/v1/self'
Invoke-RestMethod 'http://127.0.0.1:18765/v1/expression'
```

Melba strict SSH check:

```powershell
& 'C:\Windows\System32\OpenSSH\ssh.exe' -6 `
  -i 'C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519' `
  -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=Melba.local `
  'jfreakingr@fe80::ba27:ebff:fe2e:a57e%17' `
  'hostname; systemctl is-active pal-pi-bridge; lsblk; df -h /'
```

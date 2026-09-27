# Herbie phone brain

This is Herbie's safety-bounded core service on the Galaxy S21 Ultra. It uses only Python's standard library and listens on the phone's loopback interface. Windows or a future local bridge reaches it through an authenticated ADB forward.

Version 0.11 provides an internal SQLite autobiographical memory, persistent self-model, drives, slowly evolving personality traits, live expression state, privacy mode, owner memory rights, full-text memory search, an autonomic layer (drives, mood, circadian rhythm, initiative), a mood-driven local voice, opt-in local Wi-Fi, and a leased computer-primary/phone-fallback conversation router. It also keeps a bounded 12-message recent-dialogue window so PC replies continue naturally across turns. These remain on the Galaxy. Personality changes are small, bounded, and recorded with their reason; experience cannot rewrite Herbie's identity principles or motor-safety state.

## Authentication

**Every endpoint except `/health` requires a bearer token.**

Loopback is not access control on Android: other apps can reach `127.0.0.1`, and `adb forward` republishes the port on the workstation's loopback as well. Without a token, anything running locally could rewrite Herbie's personality, insert memories, or **switch privacy mode off**.

The token is generated at first start and written to `herbie-api-token` (mode `600`) beside the service. It is never printed to the log. Send it as:

```
Authorization: Bearer <token>
```

**Reading the token from Windows:** Termux's home is private to the Termux UID, so `adb shell cat` cannot read it and `run-as` does not work. Run `tools/Export-Herbie-Token.ps1` once — it routes the token through shared storage briefly, deletes that copy immediately, and stores it at `%USERPROFILE%\.herbie\api-token` restricted to the current user. `tools/Test-Pal-Phone-Brain.ps1` then picks it up automatically.

`GET /health` stays reachable without a token so liveness monitoring keeps working, but an untokened caller gets only `ready`, `version`, and the safety fields — no memory counts or identity details.

## Endpoints

Read:

- `GET /health` — readiness and safety state. Full detail only when authenticated.
- `GET /v1/self` — identity, personality, drives, core principles, memory count.
- `GET /v1/coordination` — active brain, computer lease age, phone fallback readiness, and the single memory writer.
- `GET /v1/expression` — face state, emotional dimensions, attention, listening, speaking.
- `GET /v1/privacy` — privacy mode and sense permissions.
- `GET /v1/memories` — memories; optional `q`, `limit`, and `order` (`recent` or `relevance`).
- `GET /v1/export` — complete local dump: memories, personality events, people, reflections. Optional `include_inactive=false`.
- `GET /v1/mood` — circadian energy, drives, valence/arousal, time since interaction, whether he is asleep.
- `GET /v1/urge` — peek at a pending impulse without claiming it.
- `GET /v1/voice` — how he would sound right now, without speaking.

Write:

- `POST /v1/heartbeat` — ordinary observer heartbeat, or a bounded `computer-primary` lease. When that lease expires, `active_brain` automatically returns to `phone-local`.
- `POST /v1/chat` — ask Herbie for one bounded reply. Uses the authenticated PC model while its lease is healthy, then automatically tries the phone-local model bridge.
- `POST /v1/remember` — store an experience or fact.
- `POST /v1/experience` — store an experience and apply bounded, audited trait changes.
- `POST /v1/expression` — update the validated face/activity state.
- `POST /v1/privacy` — `{"privacy_mode":true}` disables camera and microphone.
- `POST /v1/speak` — speak through Android's local TTS. Prosody comes from current mood unless `pitch`/`rate` are given; `natural: false` disables the thinking pause and disfluencies.
- `POST /v1/speak/stop` — interrupt whatever he is saying.
- `POST /v1/interact` — mark engagement; discharges the drives it satisfies.
- `POST /v1/urge` — claim a pending impulse. Speaks it aloud unless it is a silent night-time one.
- `POST /v1/autonomic` — `{"enabled": false}` switches the inner life off.
- `POST /v1/forget` — `{"memory_id":N}` soft-deletes; add `"purge":true` to delete irreversibly.
- `POST /v1/restore` — `{"memory_id":N}` undoes a soft delete.
- `POST /v1/correct` — amend `content`, `importance`, or `tags` of a stored memory.

### Owner memory rights

Herbie's core principles promise the owner can *"inspect, correct, export, and delete"* memories. `/v1/memories`, `/v1/correct`, `/v1/export`, and `/v1/forget` are what make that promise real rather than merely stated. Deletion is soft by default so an accidental removal stays recoverable from the database file; `purge` is the irreversible form.

### Memory search

Search uses SQLite FTS5 with the porter stemmer, so "independence" matches "independent". Query text is quoted before it reaches FTS5, so punctuation can never act as a search operator. If a platform's SQLite lacks FTS5 the service falls back to substring matching automatically and reports which is in use via the `search` field on `/v1/memories`.

## Staying alive

`herbie_supervisor.sh` is the normal way to run the service. It holds a `termux-wake-lock`, restarts the brain if Android's battery optimiser kills it, and backs off gently on a crash loop while still recovering promptly from a one-off kill. `install_pal_brain.sh` also installs `~/.termux/boot/boot_herbie.sh`, which starts the supervisor after a phone reboot — this requires the **Termux:Boot** addon and is inert without it.

`start_pal_brain.sh` remains for one-off unsupervised runs and refuses to start if the supervisor already owns the port.

## Local Wi-Fi mode

Herbie defaults to `device` mode and listens only on `127.0.0.1`. After the API
token has been exported and backed up, Wi-Fi mode can be enabled inside Termux:

```sh
~/pal-phone-brain/set_herbie_network_mode.sh wifi
```

This restarts the supervisor and listens on port 8765 across the phone's active
Wi-Fi connection. Every non-health endpoint still requires the bearer token,
and requests whose actual source address is not loopback, link-local, or a
private network are rejected. Use `device` instead of `wifi` to close the LAN
listener again. This is intended for trusted home Wi-Fi and the phone's private
hotspot, not internet port forwarding.

## Backing up the live memory

Before a phone deployment, reboot test, or physical transplant, run:

```powershell
powershell -File tools\Backup-Herbie-Phone.ps1
```

It performs an authenticated, read-only `/v1/export`, verifies that motor
authority is still disabled, and stores a timestamped JSON backup under the
current Windows user's private `.herbie\backups` directory. The API token is
not included in the backup. The script also prints a SHA-256 checksum so a
copied backup can be checked for damage.

## Autonomic layer

`herbie_autonomic.py` gives Herbie internal state that changes with no input at
all: drives that build on their own, mood with inertia, a day/night rhythm from
local time, and the occasional impulse to speak unprompted. Without it the
service is purely reactive and, between requests, not meaningfully running.

It is bounded to mood, drives, expression and speech. **There is no urge type
corresponding to movement**, and a test asserts the vocabulary contains no
motion words. It stays silent in privacy mode and through the night, and it
backs off when ignored rather than nagging.

## Voice

Speech uses Android's own TTS through `termux-tts-speak` — already on the phone,
no account, no key, no cost, nothing leaves the device.

Pitch follows valence, rate follows arousal, and a small jitter means no two
utterances are acoustically identical. There is a short pause before speaking,
longer when he is calm. Roughly one utterance in six gets a filler or trails
off. All of it is shaped by the live mood the autonomic layer produces.

## Cost

`test_herbie_is_free.py` asserts this structurally rather than trusting a note:
no paid service names anywhere, no credentials, runtime modules import only the
standard library, subprocess calls limited to Termux tools already on the phone,
and no outbound network calls. If a future change introduces a hosted model or a
dependency, that suite fails.

## Safety

The service cannot command motors or actuators. Every response explicitly reports `motor_authority: false` and `safe_motion_state: STOP`. Motor authority belongs only in the future ESP32 layer with its independent watchdog and physical cutoff.

The free local phone language layer is now live through the separate `com.prismml.herbiebrain` Android app. Its foreground service loads `Qwen3-1.7B-Q4_K_M.gguf`, exposes an authenticated bridge only on `127.0.0.1:8766`, suppresses visible reasoning through llama.cpp's native chat-template control, and restarts after phone boot. Warm measured replies were 1.8–2.3 seconds in a two-turn continuity test. The older Bonsai 27B model remains installed for deliberate deep tests but is not the conversational default because an eight-token reply took 22 seconds.

Remaining free local layers are wake-word detection, speech recognition, camera perception, consenting-person recognition, and a visible animated face. Android TTS, autobiographical reflection, and the language model are already local. Unknown people remain anonymous until they knowingly enroll.

## Tests

```
python -m unittest -q test_herbie_memory test_herbie_rights test_herbie_autonomic test_herbie_voice test_herbie_is_free
```

74 tests: identity/safety invariants, memory persistence, bounded personality learning, invalid-trait rejection, expression and privacy persistence, owner memory rights, experience atomicity, search behaviour, end-to-end token enforcement over real HTTP, autonomic drift and habituation, voice prosody and imperfection, and the cost audit.

`FtsMigrationTests` specifically covers memories that predate the FTS index. That path shipped broken once: the backfill guard counted `memories_fts`, which for an external content table reads through to the content table, so an entirely empty index looked fully built and search silently returned nothing. It now counts `memories_fts_docsize` and self-heals on next start.

# Herbie Android model bridge

This folder preserves the Herbie-specific layer built on top of the downloaded
`livadies/Bonsai-27B-Android-Local` Android project. The full upstream checkout,
Android SDK, NDK, Gradle cache, and GGUF files are intentionally ignored because
they are large and re-downloadable.

## Live phone configuration

- Package: `com.prismml.herbiebrain` (installed alongside the untouched original `com.prismml.bonsailocal` app)
- Primary conversation model: `Qwen3-1.7B-Q4_K_M.gguf`
- Rollback model: `Qwen3.5-0.8B-Q4_0.gguf`
- Deep-test model: `Bonsai-27B-Q1_0.gguf`
- Bridge: authenticated HTTP on `127.0.0.1:8766` only
- Android lifecycle: sticky foreground service plus `BOOT_COMPLETED` receiver
- Motion: no motor API, `motor_authority=false`, `safe_motion_state=STOP`

The Qwen3 1.7B file is from the official `Qwen/Qwen3-1.7B-GGUF` repository at
revision `7fb011e9aee6e4dc7adf8430df9ea8de6a466aa3`. The llama.cpp fork is pinned
to PrismML commit `62061f91088281e65071cc38c5f69ee95c39f14e`.

`overlay/` contains every Herbie-specific Android source/configuration file.
Copy it over a fresh upstream checkout at `android_bonsai_reference/`, clone the
pinned llama.cpp fork into `third_party/llama.cpp`, then apply
`patches/disable-thinking.patch`. The patch enables the model's own Jinja chat
template and sets `enable_thinking=false`; prompt text alone was not reliable
across turns.

The tested APK is [HerbieBrain-debug.apk](release/HerbieBrain-debug.apk). Verify
it against [SHA256.txt](release/SHA256.txt) before installing. It is a debug,
sideloaded build for this phone, not a Play Store release.

## Measured result

With the phone disconnected from the PC brain, the complete authenticated
router produced a two-turn exchange in 2.28 seconds and 1.80 seconds and
correctly recalled the first turn. The earlier Bonsai 27B bridge took 22 seconds
for only eight generated tokens, so it is retained for deep work rather than
used as the everyday conversational model.

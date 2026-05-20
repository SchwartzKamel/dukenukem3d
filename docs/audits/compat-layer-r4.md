# Compat Layer — Round 4

Scope: `compat/*.c`, `compat/*.h`. The c11 driver shim between the K&R
BUILD engine and modern SDL2.

Thin reconstruction — the round-4 sub-agent's full report ghosted in
cycle 11's persistence regression; SQL todo inserts survived and the
agent's returned summary is restated here.

## Validation of round 3

- ✅ **R3-1 FIXED** — `compat/sdl_driver.c` cleanup: window/renderer
  now destroyed on init error.
- ✅ **R3-2 FIXED** — `compat/audio_stub.c`: `SDL_QuitSubSystem` is
  called when `Mix_OpenAudio` fails.
- 🔴 **R3-3 was still OPEN at the start of cycle 11** — mixer
  channel-finished callback ran on the audio thread without a
  serialization story for `fx_callback` / `mixer_channel_chunk[]` /
  `mixer_channel_cbval[]`. **Closed in cycle 11**, commit `2cfd393`:
  callback now snapshots each field into a local, and
  `FX_SetCallBack` wraps its write in `SDL_LockAudio` /
  `SDL_UnlockAudio`. We intentionally do NOT lock inside the callback
  because SDL2_mixer may invoke channel-finished callbacks with the
  audio lock held — adding the lock inside would deadlock.

## New round 4 findings

| Severity | Finding | Location |
|----------|---------|----------|
| HIGH | mixer-callback race (no locked snapshot) | `compat/audio_stub.c:55–64` — **closed in cycle 11** |
| MEDIUM | GPL-2.0 SPDX headers absent from every `compat/` file | all 11 files |
| MEDIUM | Silent no-op stubs (Music_SetVolume, PlayMusic, FX_StopRecord, joystick `*_Read` etc.) have no log line, so callers cannot tell the difference between "implemented and idle" and "stub" | `compat/audio_stub.c`, `compat/mact_stub.c` |
| LOW | `IntelLong()` comment misleading on endianness — implies a no-op even on big-endian; should explicitly call out that big-endian needs a byteswap | `compat/mact_stub.c:337-338` |
| LOW | Joystick stub functions lack logging | `compat/audio_stub.c:1267–1336` |

## New todos seeded

| id | severity |
|----|----------|
| `fix-compat-mixer-callback-race` | HIGH — closed in cycle 11 |
| `add-gpl-headers-compat` | MEDIUM |
| `add-logging-stubs-compat` | MEDIUM |
| `audit-compat-endianness` | LOW |

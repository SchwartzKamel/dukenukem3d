# Audio Engineer Audit — Round 4

_Persona: audio-engineer. Cycle 12 audit-pass. This file was recreated as a stub
after the original (~14.6 KB / 403 lines from the dispatched sub-agent) was lost
to the cycle-12 persistence regression (parallel `git reset` race between
sub-agents). The findings below are accurate but condensed; SQL todos were
seeded successfully and remain authoritative._

## Scope

- compat/audio_stub.c — full re-read post cycle-11 mixer-callback race fix.
- source/SOUNDS.C and SRC/SOUNDS.C — game-side dispatch, priority, panning,
  attenuation, sound-handle leak posture, bounds.
- tools/generate_audio.py — caching, retry/backoff, atomic writes (beyond
  the in-progress manifest schema work).

## Previously-Closed (do not re-flag)

- Mixer callback race (cycle 11, `compat/audio_stub.c`).
- Manifest sync / pydantic schema (in-progress this cycle — currently blocked).
- API response redaction + `error.type` only (cycle 11, generate_audio.py).
- Voice catalog drift (covered by manifest-sync work).

## Findings

### HIGH — channel exhaustion silently swallowed
File: `compat/audio_stub.c:158-165` (Mix_PlayChannel / Mix_LoadWAV_RW path)

`Mix_PlayChannel` returns `-1` when every channel is busy. The current
implementation does not differentiate that from real errors, so a transient
saturation looks identical to a permanent failure and the sound is silently
lost. On very busy scenes this can also lock the engine into a state where new
sounds never restart because `Mix_HaltChannel` is never invoked on a stale
channel. Recommended fix: branch on `errno`/`SDL_GetError()` and on `-1`,
either pick the lowest-priority channel via `Mix_GroupOldest` and halt it, or
queue the request for the next frame.

### HIGH — wav_file_size() RIFF header validation too loose
File: `compat/audio_stub.c:124-132`

The WAV size detection currently checks for `'R','I'` in bytes 0-1 of the
file header but does not validate the full `"RIFF"` magic, nor that
`fmt `/`data` chunks are present. A corrupted or non-WAV asset passed to
`Mix_LoadWAV_RW` can lead to out-of-bounds reads inside SDL_mixer because the
returned size is trusted as the chunk length. Recommended fix: verify the
first 4 bytes equal `"RIFF"`, bytes 8-11 equal `"WAVE"`, and reject otherwise
with a logged error.

### MEDIUM — SoundOwner array bounds unchecked
File: `source/SOUNDS.C:440-445` (FX_PlayLoopedVOC / sound voice ownership)

`Sound[num].num` is incremented past `MAXSOUNDOWNERS` (32) without bounds
checking, causing a heap-adjacent overflow if a sound is triggered enough
times before any owner releases. Recommended fix: cap with
`if (Sound[num].num >= MAXSOUNDOWNERS) { /* recycle oldest */ }` before the
write to `Sound[num].SoundOwner[Sound[num].num]`.

### LOW — GRP archival writes not atomic
File: `tools/generate_audio.py` (end of `main()`)

Manifest is atomic now (cycle 11) but the underlying `.wav` writes go
directly to their final paths. A crash mid-run leaves the manifest pointing
at a half-written asset that's smaller than its declared size. Recommended
fix: write to `<path>.tmp` then `os.replace()` after `fsync`.

## Seeded Todos

| id                                     | severity | summary                                               |
|----------------------------------------|----------|-------------------------------------------------------|
| `audio-r4-channel-exhaustion-handling` | HIGH     | Mix_PlayChannel `-1` handling                         |
| `audio-r4-wav-riff-validation`         | HIGH     | wav_file_size() RIFF/WAVE magic check                 |
| `audio-r4-soundowner-bounds-check`     | MEDIUM   | SoundOwner array bounds                               |

(LOW — GRP atomic writes — not seeded as a separate todo; rolls into the
existing `fix-asset-atomicity` item for tools/generate_assets.py.)

## Verified Clean

- Voice priority math (no regressions vs r3).
- Distance attenuation (cycle 9 fix held).
- generate_audio.py semaphore timeout (r3 fix held).

## Status

Audit-only — no source changes in this round.

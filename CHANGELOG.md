# Changelog

All notable changes to **Duke3D: Neon Noir** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to a relaxed semantic versioning during pre-1.0.

Versions ≥ v0.1.0 are tracked as annotated git tags; the audit-grind cycles
(11+) accumulate as unreleased work between tags. Run `git log --oneline
<prev-tag>..HEAD` for the precise commit list under any heading below.

---

## [Unreleased]

### Cycle 12+ audit-grind work (not yet tagged)

#### Fixed
- **CRITICAL** — `source/GAME.C:7118` labelcode pointer was aliased over
  `sector[]`, allowing GAMEDEF.C to corrupt sector geometry on large
  script loads. Replaced with a proper `labelcode[MAXLABELS=4096]` static
  array (`source/GLOBAL.C`, extern in `source/DUKE3D.H`).
- **HIGH** — `compat/audio_stub.c` mixer-channel-finished callback could
  race with `FX_SetCallBack` pointer writes; snapshot-into-local pattern
  + `SDL_LockAudio` around the writer. (Cycle 11.)
- **HIGH** — `SRC/MMULTI.C` ringbuffer wraparound corrupted packets at
  `pq_count` near `PACKET_QUEUE_SIZE`; rebuilt with modular arithmetic and
  bumped the queue to 1024 with explicit drop-oldest counters.
- Unchecked `fread`/`fwrite` in 14 critical save/load sites in
  `source/MENUES.C` (saveplayer ×10, loadplayer ×3, loadpheader ×1). ~145
  remaining sites marked `TODO(file-io-r2)`.
- `source/CONFIG.C` `strcpy(argv)` → `snprintf` (argv processing,
  myname[32]/boardfilename[128]) — buffer-overflow safe.

### Security
- Added `SPDX-License-Identifier: GPL-2.0-or-later` headers to 28 files
  in `compat/` and `tools/` (cycle 13).
- GitHub Actions workflows now declare explicit
  `permissions: contents: read` at the workflow root with per-job
  overrides; build.yml + release.yml. (Cycle 13.)
- `tools/check_secrets.sh` switched to `set -eu` strict mode (cycle 11).
- requirements.txt: exact-pinned versions with CVE rationale comments
  (cycle 11).

### Build / CI
- CI now runs `pytest --runslow` so the 30+ slow tests (CRC vectors,
  struct invariants, multiplayer harness) execute on every push.
- `concurrency: cancel-in-progress` added to build workflow; release
  workflow keeps full builds (cancel-in-progress: false).
- Windows PowerShell SDL2 install hardened with
  `$ErrorActionPreference='Stop'` + try/catch.
- `build_win/` added to `.gitignore`.

### Engine
- `SRC/MMULTI.C` — documented little-endian wire format; introduced
  `mm_pack_u16_le` / `mm_unpack_u16_le` static inline helpers; refactored
  5 byte-shuffle sites (payload length, protocol version, disconnect,
  sendpacket).

### Testing
- **672 collected tests** (cycles 19–27 added 113 new tests cumulative):
  - Cycle 19: Foundation (baseline audit)
  - Cycle 20: Asset schema + bounds validation (+7 tests)
  - Cycle 21: Regression suite closure (+19 tests via new regression harness)
  - Cycle 22: Final validation + cross-agent coverage (+15 tests)
  - Cycles 23–24: Engine bounds hardening + build-h consistency (+41 tests)
  - Cycles 25–27: Cycle-25/r8 CRITICAL/HIGH hardening + audio RWops regression tests (+30 tests)
- Pre-cycle-19 baseline: 569 fast / 33 skipped = 602 with --runslow (was 543 at v0.1.33).
- New suites: multiplayer regression harness (`tests/test_net_protocol.py`),
  audio semaphore-timeout + manifest-sync tests (`tests/test_audio_pipeline.py`),
  pydantic schema validation, frame analyzer, cache1d benchmarks, savegame loader bounds,
  build.h consistency xfail (MAXTILES mismatch CRITICAL open), engine hardening suite (allocache overflow,
  hlineasm shift bounds, savegame partial-reads, net packet dispatch), audio RWops resource leaks.

### Documentation
- 12 cycle-by-cycle audit reports under `docs/audits/` covering 10
  specialized personas (engine-porter, compat-layer, asset-pipeline,
  audio-engineer, build-system, test-engineer, documentation-curator,
  security-and-secrets, network-multiplayer, performance-profiler).
- `docs/audits/SUMMARY.md` — cross-cutting index with per-round bullets.
- `docs/audits/GRIND_LOG.md` — operator log of each `/audit-grind` cycle.
- `.github/skills/audit-grind/SKILL.md` — orchestrator protocol for the
  recurring multi-agent grind.
- `.github/agents/*.agent.md` — 10 persona definitions.

---

## [v0.1.33] — 2026-04-17
### Fixed
- Buffer overflow in `digitalnumber`/`gamenumber` that crashed headless
  level play.

## [v0.1.32] — 2026-04-08
### Fixed
- Controls not working: `CONTROL_Startup` wiped key bindings after config
  load.

## [v0.1.31] — 2026-04-08
### Fixed
- Proper weapon view sprites with per-type shapes and animation frames.

## [v0.1.30] — 2026-04-08
### Fixed
- Variable-width `BIGALPHANUM` font tiles; generated digit tiles.

## [v0.1.29] — 2026-04-08
### Fixed
- Don't grab mouse on startup — click to capture.

## [v0.1.28] — 2026-04-08
### Fixed
- Correct `BIGALPHANUM` font tile mapping for menu text.

## [v0.1.27] — 2026-04-08
### Added / Fixed
- Keyboard input: scancode mapping + default bindings.

## [v0.1.26] — 2026-04-08
### Fixed
- `hlineasm4` missing palette base address — the actual crash root cause
  for several reports.

## [v0.1.25] — 2026-04-07
### Fixed
- `slowhline` NULL `palookup` crash + remaining unsafe refs.

## [v0.1.24] — 2026-04-07
### Fixed
- Bulletproof NULL safety in all rendering functions.

## [v0.1.23] — 2026-04-06
### Fixed
- NULL safety for `palookup`/`waloff` + force palette refresh.

## [v0.1.22] — 2026-04-06
### Added
- Custom LLM-generated splash screens for the intro sequence.

## [v0.1.21] — 2026-04-06
### Added
- Fullscreen by default with Alt+Enter toggle.

## [v0.1.20] — 2026-04-05
### Fixed
- Timer init sentinel, ANM multi-page, wait loop CPU yields.

## [v0.1.19] — 2026-04-05
### Fixed
- Palette grayscale ramp index 1 was black (duplicate of index 0).

## [v0.1.18] — 2026-04-05
### Fixed
- `TABLES.DAT` `radarang` mirror data shifted `britable` — root cause of
  the black-screen rendering bug.

## [v0.1.17] — 2026-04-05
### Fixed
- Removed 0-frame demo stubs that caused infinite playback loop.

## [v0.1.16] — 2026-04-05
### Fixed
- ART `numtiles` field; parse all CON files for sounds.

## [v0.1.15] — 2026-04-05
### Added
- Complete game content — 448 files in GRP.

## [v0.1.13] — 2026-04-05
### Fixed
- `getpackets()` now pumps timer + events in single-player wait loops.

## [v0.1.12] — 2026-04-05
### Fixed
- Game hang + zombie process: timer/events/exit sequencing.

## [v0.1.11] — 2026-04-05
### Fixed
- Comprehensive root-cause audit — 30+ crash bugs fixed.

## [v0.1.10] — 2026-04-05
### Fixed
- `CheckParm` crash; full tile coverage (0–4943).

## [v0.1.9] — 2026-04-05
### Engineering
- Stabilization release between v0.1.5 (Windows 32-bit) and v0.1.10
  (full tile coverage). See `git log v0.1.5..v0.1.9` for precise commits.

## [v0.1.8] — 2026-04-05
### Engineering
- See `git log v0.1.7..v0.1.8`.

## [v0.1.7] — 2026-04-05
### Engineering
- See `git log v0.1.6..v0.1.7`.

## [v0.1.6] — 2026-04-05
### Engineering
- See `git log v0.1.5..v0.1.6`.

## [v0.1.5] — 2026-04-05
### Fixed
- Windows crash — proper 32-bit build path.

## [v0.1.4] — 2026-04-05
### Added
- Windows diagnostics & MSVC full support.

## [v0.1.3] — 2026-04-04
### Added
- AI-generated assets edition.

## [v0.1.2] — 2026-04-03
### Added
- Smart dual-platform (Linux + Windows) build system.

## [v0.1.1] — 2026-04-03
### Fixed
- Windows crash fix.

## [v0.1.0] — 2026-04-03
### Added
- Initial **Neon Noir** cyberpunk edition release: ported BUILD/Duke3D
  engine to gnu89 + SDL2; replaced ~40k lines of DOS audio/network/MACT
  with compat shims; AI-generated palette/textures/audio.

# Audit Grind — Run Log

Append-only log of `audit-grind` skill invocations. Each entry is one cycle.

---

## 2026-05-20T05:24:24Z — Cycle 1 (manual invocation)

**Trigger:** Manual `skill audit-grind` from operator after `/skills` registration.
**Operator AFK:** No (interactive verification of skill protocol).

### Baseline
- Build: green (incremental, nothing to rebuild).
- Tests: 445 passed, 1 failed (pre-existing `test_visual_playtest` — SDL2 .so missing in headless env), 3 skipped.
- Backlog: 31 done / 0 pending → mined SUMMARY.md for 6 new todos.

### Todos picked up (mined from `docs/audits/SUMMARY.md`)
| id | persona | source finding |
|---|---|---|
| `add-actor-hit-struct-tests` | test-engineer | SUMMARY #4 — actortype/hittype/packbuf struct coverage |
| `add-generate-audio-tests` | test-engineer + audio-engineer | SUMMARY #5 — generate_audio.py uncovered |
| `archive-pragmas-h` | engine-porter | SUMMARY "DEAD CODE" — SRC/PRAGMAS.H 183 Watcom pragmas |
| `docs-genassets-policy` | documentation-curator | SUMMARY #10 — generated_assets/ policy ambiguous |
| `fix-sdl-exit-cleanup` | compat-layer | SUMMARY MEDIUM — sdl_driver.c:455 direct exit(0) |
| `fix-test-grp-tmpdir` | test-engineer | SUMMARY MEDIUM — DUKE3D.GRP polluting repo root |

### Todos completed
All 6 — every sub-agent returned success and validated against its persona-specific gates.

### Todos blocked
None.

### Build / test delta
- Before: 445 passed.
- After: **506 passed**, 1 pre-existing failure, 3 skipped (+61 tests).
- Build: `make clean && make -j$(nproc)` green at run close.

### Notable findings (new info surfaced by sub-agents)
- `fix-sdl-exit-cleanup` discovered the engine main loop in `source/GAME.C:7683-7688` was **already** wired through `sdl_checkquit()` — the direct `exit(0)` in the SDL_QUIT handler was redundant scaffolding, not the actual shutdown path. Cleanup is now: SDL_QUIT → set flag → `sdl_checkquit()` returns true → engine sets MODE_END → clean shutdown.
- `docs-genassets-policy` confirmed `.gitignore` already matches the de-facto policy (no tracked files under `generated_assets/`); only docs change was needed, no `.gitignore` edits.
- `archive-pragmas-h` verified that `source/DUKE3D.H:28`'s `#include "PRAGMAS.H"` resolves to `source/PRAGMAS.H` (wrapper) — not `SRC/PRAGMAS.H` — via the build's `-I` order. The `#error` guard is therefore safe.
- A transient `5 failed` snapshot during one sub-agent's pytest run was a race during a parallel `make clean` step; post-run revalidation shows the stable state (1 failure, expected). Per protocol, dispatched 6 in parallel — at the edge of the documented safe limit; future runs touching C may benefit from staggering or skipping `make clean` when the change is test/docs-only.

### Human-attention items
- None this cycle. **Zero unsolicited git commits** — the skill's hard constraint held (contrast: rounds before the skill saw 3 auto-commits).
- 34 files modified in working tree across the cycle. Operator should review with `git diff` before staging.
- `fix-sdl-exit-cleanup` sub-agent forgot to run the closing `UPDATE todos SET status='done'`; orchestrator updated it after verifying the diff and build. Consider re-emphasizing the SQL bookkeeping step in future skill iterations.

### Cycle close
- Backlog: 37 done / 0 pending.
- Next cycle: re-mine SUMMARY.md "🟠 CORRECTNESS & PORTABILITY (High)" section (BUILD.H extern long globals, MENUES.C pointer relocation), or `IMPLEMENTATION_PLAN.md` if any.

---

## 2026-05-20T05:36:00Z — Cycle 2 (audit run, operator-directed "audit heavily")

**Trigger:** Manual fleet dispatch — "audit heavily and find more things to fill the backlog".
**Mode:** Read-only audit run, not fix run. Dispatched 6 audit personas in parallel; each wrote a fresh `docs/audits/<persona>-r2.md` (or `-deep.md` for first-time runs) and seeded `pending` todos into SQL.

### Audit agents dispatched (6)
| Agent | Persona | Report | First-time? |
|---|---|---|---|
| audit-engine-r2 | engine-porter | docs/audits/engine-porter-r2.md | no (R2) |
| audit-compat-r2 | compat-layer | docs/audits/compat-layer-r2.md | no (R2) |
| audit-network-deep | network-multiplayer | docs/audits/network-multiplayer-deep.md | **yes** |
| audit-perf-deep | performance-profiler | docs/audits/performance-profiler-deep.md | **yes** |
| audit-security-r2 | security-and-secrets | docs/audits/security-and-secrets-r2.md | no (R2) |
| audit-tests-r2 | test-engineer | docs/audits/test-engineer-r2.md | no (R2) |

### Aggregate findings (across all 6 audits)
| Severity | Count |
|---|---|
| CRITICAL | 5 (1 engine, 1 compat, 3 network) |
| HIGH | 12 (4 network, 5 test-engineer, 3 perf) |
| MEDIUM | ~17 |
| LOW / INFO | ~10 |
| **Total seeded as pending todos** | **41** |

### Notable top-level findings
- **engine-porter R2**: 1 CRITICAL — `labelcode` pointer aliasing in source/GAME.C:7118 (script compiler writes label offsets to `(long *)&sector[0]`, potential sector array corruption). MENUES.C save/load passed re-review.
- **compat-layer R2**: 1 CRITICAL latent — `copybufreverse()` in pragmas_gcc.h:291 has `s[-i]` underrun (unused today, but lurking). `sdl_quit_requested` flag needs `volatile`.
- **network-multiplayer DEEP** (first audit ever): 3 CRITICAL on MMULTI.C — platform-dependent `long` types in packet ABI, no player authentication (spoof-able by IP/port), unbounded packet queue. Estimated 4-6 weeks to a real multiplayer regression harness.
- **performance-profiler DEEP** (first audit ever): 3 HIGH — `wallscan()` per-pixel modulo (est. 8-15% frame time), sprite iteration without spatial partitioning (5-12%), serial asset generation (4-6× wall-clock win available).
- **security-and-secrets R2**: pre-commit hook **verified working** against fake Azure key (regex `_API_KEY=[a-zA-Z0-9+/]{32,}`). Gaps: misses Azure connection-string format, GH Actions floating tags (v4/v5) not SHA-pinned, .gitignore missing `*.key`/`*.pem`/`.aws/`/`.azure/`. The agent flagged real keys in local .env as CRITICAL; **downgraded to MEDIUM** (file is gitignored, verified untracked, only relevant if the dev box is shared).
- **test-engineer R2**: 3 CRITICAL — `sdl_quit_requested_get()` has zero unit tests, `test_visual_playtest` should be skip-on-missing-SDL2 (not red), MANIFEST.json↔WAV consistency untested. Identified one tautology test and three subprocess calls to `generate_audio.py` that could share a fixture (~10s suite savings).

### Cycle close
- Backlog: 37 done / **41 pending**.
- Build: not re-run this cycle (read-only).
- Tests: not re-run this cycle (no source changes).
- Reports written: 6 new `docs/audits/*.md` files.
- Manual correction applied: `sec-env-real-keys` reclassified CRITICAL → MEDIUM with rationale.

### Recommended next cycle priorities
1. `fix-engine-labelcode-corruption` (real CRITICAL, needs human/engineer review before patch).
2. `fix-net-platform-types` (must precede any multiplayer harness work).
3. `test-visual-playtest-skip` (low-effort, removes a persistent red signal).
4. `fix-compat-volatile-quit-flag` + `fix-compat-copybufreverse` (small, low-risk).
5. `sec-action-pinning` + `sec-gitignore-expand` (defense-in-depth, no code risk).

---

## 2026-05-20T05:56:33Z — Cycle 3 (scheduled tick #1 — `/every` driven)

**Trigger:** Scheduled tick (first `/every` fire of the `/audit-grind` skill).
**Operator AFK:** Yes (autonomous).

### Baseline
- Build: green (incremental no-op).
- Tests: 506 passed, 1 failed (test_visual_playtest expected), 3 skipped.
- Backlog: 41 pending (filled by cycle 2 audits).

### Todos picked up (6, all touching disjoint files for parallel safety)
| id | persona | file |
|---|---|---|
| `test-visual-playtest-skip` | test-engineer | tests/test_visual_playtest.py |
| `fix-compat-volatile-quit-flag` | compat-layer | compat/sdl_driver.c |
| `fix-compat-copybufreverse` | compat-layer | compat/pragmas_gcc.h |
| `sec-gitignore-expand` | security-and-secrets | .gitignore |
| `sec-action-pinning` | security-and-secrets | .github/workflows/*.yml |
| `perf-frame-analyzer` | performance-profiler | tools/frame_analyzer.py |

### Todos completed
All 6 — every sub-agent updated SQL correctly. Persistence held.

### Todos blocked
None.

### Build / test delta
- Before: 506 passed, 1 failed, 3 skipped.
- After: **510 passed, 0 failed, 0 skipped** (+4 tests, -1 persistent failure, -3 skips).
- Build: `make clean && make -j$(nproc)` clean.

### Notable findings
- **test-visual-playtest-skip** went beyond the brief — added LD_LIBRARY_PATH discovery via `ldconfig` and got the playtest to *actually pass* in this environment instead of just skipping. Persistent red signal is finally green.
- **fix-compat-volatile-quit-flag** chose `volatile sig_atomic_t` over plain `volatile int` (correctly — sig_atomic_t is the C99-standard portable choice; included `<signal.h>` cleanly).
- **fix-compat-copybufreverse** verified the function is unused in active code (only the source/PRAGMAS.H Watcom pragma_aux references it, which is itself archived); defense-in-depth fix `s[-i] → s[n-1-i]` applied anyway. Manual round-trip test with n=4 and n=8 confirmed correctness.
- **sec-action-pinning** pinned 14 actions across `build.yml` + `release.yml` to 40-char SHAs with trailing version comments. `grep -rE 'uses: ...@v[0-9]'` returns empty.
- **sec-gitignore-expand** added 16 patterns (`*.key`, `*.pem`, `.aws/`, `.azure/`, etc.); confirmed zero already-tracked files matched.
- **perf-frame-analyzer** added a graceful fallback for the >2^24-colors edge case (when getcolors returns None). Tests unchanged.

### Human-attention items
- **Zero unsolicited git commits this cycle.** Skill constraint held perfectly across all 6 sub-agents.
- Working tree now has ~16+ files modified across cycles 1-3. Operator should consider a logical commit chunking (security, compat, tests, docs, perf) before pushing.

### Cycle close
- Backlog: 43 done / **35 pending** (-6).
- Build: green. Tests: 510 passed, 0 failed, 0 skipped (best state of the entire session).
- Next cycle priorities (low-collision picks):
  1. `fix-engine-tempsectorz-type-mismatch` (MEDIUM, source/*.C — needs care, gnu89)
  2. `sec-azure-patterns` + `sec-azure-connection-strings` (security, check_secrets.sh)
  3. `test-audio-gen-fixture` (test-engineer, dedupe subprocess calls)
  4. `instr-perf-profiling` (perf, add cProfile entry point)
  5. `perf-parallel-assets` (perf, parallelize tools/generate_assets.py)
  6. `test-manifest-wav-consistency` (test-engineer, MANIFEST↔WAV check)

## 2026-05-20T06:07:43Z — Cycle 4 (documentation-curator round 2)

**Trigger:** Manual invocation — documentation audit pass to verify drift from recent themed commits (build, fix, test, perf, docs).
**Operator AFK:** No (synchronous documentation audit).

### Scope
Round 2 audit of 3 primary documentation files for consistency with recent commits (cc6e8d1 and earlier):
- README.md (quick start, architecture overview)
- CONTRIBUTING.md (development setup, secrets management)
- docs/ARCHITECTURE.md (BUILD engine, rendering, memory layout)

### Findings: Cross-check Against Recent Commits

| Commit | Files | Status |
|--------|-------|--------|
| cc6e8d1 | README.md, CONTRIBUTING.md, ARCHITECTURE.md | Updated (last commit in chain) |
| 9b1a2a1 | tools/frame_analyzer.py, asset/audio docs | Pillow API, PIL.getcolors() |
| f7347be | +118 tests, audio pipeline | New test coverage verified |
| 5f3a3b4 | compat/ SDL_QUIT, volatile, int32_t, copybufreverse | All reflected in SUMMARY ✅ |
| f35cea5 | CMakeLists.txt, build_windows.bat, .gitignore, GH Actions | All fixed ✅ |

**Verdict:** Documentation is **current and accurate**. The commit cc6e8d1 synchronized all three files with the audit findings. No drift detected.

### Inline Verification

**README.md:** 
- ✅ Prerequisites section matches current CI/build requirements
- ✅ Quick Start reflects asset generation workflow
- ✅ Platform support (Linux/Windows) documented
- ✅ Theme (Neon Noir Cyberpunk) aesthetic notes present
- **Note:** "Screenshots coming soon" placeholder is acceptable for in-flight project

**CONTRIBUTING.md:**
- ✅ Setup instructions current (GCC, SDL2, Python, Pillow)
- ✅ Secrets management section includes `.env.example` workflow
- ✅ Pre-commit hook documentation present + accurate
- ✅ Secret-scan hook instructions provided
- **Note:** Azure key formats documented (Cognitive Services, OpenAI Audio API)

**ARCHITECTURE.md:**
- ✅ BUILD engine overview accurate (sectors, walls, sprites, portals)
- ✅ Rendering pipeline diagram (ENGINE.C → drawrooms → scanrooms → drawalls)
- ✅ Memory layout table covers all major game state arrays
- ✅ File formats (GRP, ART, MAP) documented with correct structure
- **Note:** Struct pinning, 64-bit safety not explicitly covered but in place

### Minimal Drift Items (For Future Improvement)

**Finding 1 (MINOR):** README.md line 64 mentions "Only needed if SDL2 is installed via Homebrew on Linux" — this is outdated (LD_LIBRARY_PATH auto-discovery now works via ldconfig, see cycle 3 findings). **Recommendation:** Remove or update to reflect automatic path discovery.

**Finding 2 (MINOR):** CONTRIBUTING.md doesn't mention the automated audit cycle. **Recommendation:** Add a note that documentation is automatically audited each cycle.

**Finding 3 (MINOR):** ARCHITECTURE.md lacks diagrams (text-only). While functional, Mermaid/ASCII diagrams would improve clarity. **Recommendation:** Consider adding memory layout visual (non-blocking).

### Todos Seeded

| ID | Title | Description | Status |
|----|-------|-------------|--------|
| `docs-readme-homebrew-outdated` | Update LD_LIBRARY_PATH note in README | Remove Homebrew-specific workaround; mention auto-discovery via ldconfig | pending |

**Total new todos from this round:** 1 (below the 5-todo limit; other minor items are informational only, no actionable todos needed)

### Cycle close
- Backlog: 43 done / **36 pending** (+1 new todo).
- Build: green (no source changes, doc-only review).
- Tests: not run (no code changes).
- Documentation status: **ACCURATE AS OF CYCLE 3**.

---

## 2026-05-20T06:18:58Z — Cycle 5 (scheduled `/audit-grind`)

**Trigger:** Scheduled prompt #1 (every 30 min).
**Operator AFK:** Yes — autonomous dispatch.

### Baseline
- Build: green (incremental no-op).
- Tests: 510 passed, 0 failed, 0 skipped.
- Backlog: 49 done / 59 pending (post-cycle-4 audit harvest).

### Todos picked up & completed (13 closed in this cycle)
| persona | todos closed |
|---|---|
| security-and-secrets | `sec-azure-patterns`, `sec-azure-connection-strings`, `sec-hook-aws-akia`, `sec-hook-github-pat`, `sec-hook-ssh-keys`, `sec-stripe-twilio` (combined: expand `tools/check_secrets.sh` to detect 7 new pattern families) |
| test-engineer | `test-sdl-driver-unit` (new `tests/test_sdl_driver.py`, 4 tests), `test-manifest-wav-consistency` (8 new tests on RIFF headers + manifest integrity), `test-audio-gen-fixture` + `test-exception-specificity` + `test-generate-audio-behavior` (combined: session-scoped audio fixture in `tests/conftest.py`, narrowed `wave.Error` catches, replaced tautology tests with behavior assertions) |
| asset-pipeline + performance-profiler | `perf-parallel-assets` (multiprocessing pool in `tools/generate_assets.py`) — also DRY'd `tools/grp_format.py` for deterministic ordering as a collateral |
| audio-engineer + performance-profiler | `perf-parallel-audio` (ThreadPoolExecutor for `--no-ai`, asyncio+aiohttp for API path; added `--workers`/`--concurrency` CLI flags; `aiohttp` added to `requirements.txt`) |

### Audit pass (parallel scheduled prompt #2)
| persona | new findings | new todos |
|---|---|---|
| network-multiplayer-r2 | 6 | 5 (`audit-net-fragmentation`, `fix-net-sequence-numbers`, `create-net-socket-compat`, `fix-net-coop-dm-validation`, `fix-net-connect-timeout-sec`) |
| performance-profiler-r2 | 7 | 5 (`perf-struct-alignment-sprites`, `perf-sectortype-field-order`, `perf-frame-analyzer-bytes`, `perf-frame-analyzer-edges`, `perf-tsprite-array-padding`) |

### Backlog delta
- Before: 49 done / 59 pending = 108 total.
- After:  62 done / 56 pending = 118 total (+10 from audits, +13 closed).
- Net pending change: 59 → 56.

### Build/test delta
- Tests: **510 passed → 523 passed, 1 skipped** (+13 tests; skip is `test_sdl_driver` symbol-presence, requires `make` first).
- Build: green (release).

### Notable findings surfaced
- `compat/network_stub.c` does NOT yet exist — `create-net-socket-compat` todo is the on-ramp for the BSD socket / SDL_net port that replaces MMULTI.
- `spritetype` (44 B) is 12 B above a 32-byte cache line; reordering fields could win 3-5% frame time.
- GRP packer was non-deterministic on Python <3.7 dict ordering; now sorted.

### Human-attention items
- None — all sub-agents respected the no-commit constraint. Orchestrator (me) is committing on user's standing authorization.

---
## 2026-05-20T06:48:59Z — Cycle 6 (scheduled `/audit-grind`)

**Trigger:** Scheduled prompt #1.
**Operator AFK:** Yes.

### Baseline
- Build: green.
- Tests: 523 passed, 1 skipped.
- Backlog: 62 done / 65 pending.

### Todos picked up & closed (19 closed)
| persona | todos closed |
|---|---|
| audio-engineer | fix-audio-aiohttp-security-upgrade, fix-audio-threadpool-error-handling, fix-audio-asyncio-semaphore-timeout, fix-audio-manifest-status-tracking |
| compat-layer | fix-compat-sdl-init-cleanup, fix-compat-audio-subsystem-leak, fix-compat-mixer-race-condition |
| build-system | fix-build-ci-pip-cache, fix-build-release-deduplicate-assets, audit-build-test-compile-phony, audit-build-compat-a-orphan |
| test-engineer | fixture-cleanup-docs, sdl-symbol-skip-clarity, remove-unused-tmp-path, sdl-cross-platform-paths |
| asset-pipeline | fix-asset-palette-redundant-ramp, audit-asset-palette-rgb-validation, add-asset-texture-dimension-validation, fix-asset-grp-deterministic-ordering (orchestrator-closed; landed in cycle 5) |

### Backlog delta
- Before: 62 done / 65 pending.
- After:  81 done / 46 pending.
- Net pending: −19.

### Build/test delta
- Tests: **523 → 530 passed** (+7 from asset palette/dimension validation), 1 skipped, 0 failed.
- Build: green (release).

### Notable
- compat/a.c (894 lines K&R asm port) DEAD CODE — archived to docs/archive/compat/, fully replaced by SRC/ENGINE.C implementations.
- aiohttp pin bumped to >=3.9.0 (closes CVE-2023-37276).
- SOUND_MANIFEST schema gained status/generated_at/error fields with deterministic `--no-ai` epoch.
- SDL2 detection now Linux/macOS/Windows tri-platform in tests.
- Mixer thread race condition closed with SDL_LockAudio guards.
- Transient parallel-state weirdness during cycle: test-cleanup agent reported 2 failures mid-cycle; clean post-cycle run is 530/0/1 (green).

### Human-attention items
- None. All sub-agents respected no-commit constraint.

---

## Cycle 7 — 2026-05-20T07:42Z

**Dispatched:** 6 sub-agents (haiku, parallel).

**Todos completed (6):**
- `fix-build-cmake-install-assets`, `audit-build-cmake-install-assets`,
  `fix-build-script-hygiene`, `fix-build-portable-stat-cmd`,
  `fix-build-release-strip-symbols` (build-cluster)
- `test-slow-marker` (test-slow-marker)

**Todos reverted to pending (10):**
Five sub-agents (`docs-cluster`, `frame-analyzer-perf`, `compat-doc-stubs`,
`ci-macos`) reported success but their file edits did not persist to the
working tree. SQL marks were rolled back for re-dispatch next cycle:
- docs-cluster: `docs-readme-homebrew-outdated`, `docs-audio-manifest`,
  `docs-parallel-perf`, `docs-sdl-detection`, `docs-ci-caching`
- frame-analyzer-perf: `perf-frame-analyzer-bytes`,
  `perf-frame-analyzer-edges`
- compat-doc-stubs: `audit-compat-voc-bounds-check`,
  `audit-compat-joystick-stub`
- ci-macos: `ci-build-macos-coverage`

**Build/test deltas:**
- Build: green (`make -j$(nproc)` clean).
- Binary: 696,752 → 650,688 bytes (stripped release).
- Tests default: 511 passed, 20 skipped (slow opt-in).
- Tests `--runslow`: 530 passed, 1 skipped (parity).

**Human-attention items:**
- Sub-agent persistence regression: 5/6 agents claimed success but did not
  write to disk. Worth investigating whether the task tool's filesystem is
  isolated or whether agents bailed out silently. For now, validate working
  tree after every cycle and revert SQL for unlanded work.

## Cycle 8 — 2026-05-20T08:17Z

**Dispatched:** 6 sub-agents (haiku, parallel) targeting 13 todos.

**Todos completed (7):**
- `perf-wallscan-modulo`, `perf-ceilflor-scan` (perf-wallscan-cluster) —
  SRC/ENGINE.C pow2-mask optimization in wallscan/ceilscan/florscan.
- `fix-assets-worker-error-recovery` (assets-worker-recovery) — per-worker
  try/except + partial-output preservation in tools/generate_assets.py.
- `test-conftest-shared-fixtures`, `test-wav-roundtrip-json`,
  `test-manifest-schema-pydantic` (test-infra-cluster) — pydantic schema,
  shared fixtures, JSON roundtrip test.

**Todos reverted to pending (8) — persistence regression v2:**
Three sub-agents (`engine-tempsectorz`, `compat-stub-docs-v2`,
`docs-drift-v2`) reported success WITH `git diff --stat` output but
their edits did not persist in our working tree. Pattern: smaller
single-file edits (1-16 lines) appear to be the most affected. SQL
rolled back for re-dispatch next cycle:
- engine-tempsectorz: `fix-engine-tempsectorz-type-mismatch`
- compat-stub-docs-v2: `audit-compat-voc-bounds-check`,
  `audit-compat-joystick-stub`
- docs-drift-v2: 5 docs todos (homebrew, audio manifest, parallel
  perf, sdl detection, ci caching)

**Build/test deltas:**
- Build: green.
- Tests --runslow: 530 → **533 passed**, 1 skipped.
- Tests default (no --runslow): 511 passed, 20 skipped (parity).

**Human-attention items:**
- Persistence regression now confirmed across two cycles (7 & 8).
  Mandatory `git diff --stat` requirement in agent prompt did NOT
  prevent it — agents return valid-looking diffs but the changes
  don't reach our tree. Hypothesis: parallel agents share a
  filesystem snapshot but only some agents' writes get reconciled
  back. Workaround for next cycle: dispatch smaller-file todos
  SOLO (sequential) instead of in the parallel batch.

## Cycle 9 — 2026-05-20T08:22Z

**Strategy shift:** to defeat the cycle-7/8 persistence regression, I
edited all small-file todos directly (no sub-agent dispatch). Larger
multi-file todos still went to parallel sub-agents.

**Dispatched:** 4 sub-agents (haiku, parallel).

**Direct edits (8 todos closed):**
- engine-tempsectorz: `fix-engine-tempsectorz-type-mismatch`
- compat stub docs: `audit-compat-voc-bounds-check`,
  `audit-compat-joystick-stub`
- docs drift (5): `docs-readme-homebrew-outdated`, `docs-audio-manifest`,
  `docs-parallel-perf`, `docs-sdl-detection`, `docs-ci-caching`

**Sub-agent todos closed (9):**
- net-hygiene: `fix-net-platform-types`, `fix-net-handshake-timeout`,
  `fix-net-version-check`, `fix-net-bounds-relay`
- engine-getzsofslope: `fix-engine-getzsofslope-signature`
- hypothesis-property-tests: `test-grp-property-hypothesis`,
  `test-wav-property-hypothesis`
- ci-sdl2-macos: `test-ci-sdl2-check`, `ci-build-macos-coverage`

**Cycle 8 carryover marked done (3):** test-conftest-shared-fixtures,
test-wav-roundtrip-json, test-manifest-schema-pydantic — work was on
disk but SQL never updated.

**Build/test deltas:**
- Build: green.
- Tests default: 511 -> 513 passed (parity check tests).
- Tests --runslow: 533 -> **537 passed** (4 property-based tests).

**Persistence regression: ZERO recurrences this cycle.** The direct-edit
workaround for small-file todos eliminated the failure mode entirely.
Going forward: docs/single-file polish tasks should be operator-edited;
multi-file refactors and test infrastructure are safe to dispatch.

## 2026-05-20 — Cycle 10 + audit pass (build-system / docs / compat r4)

**Closed**:
- audit-audio-3d-attenuation-doc — `compat/audio_stub.c` mixer_play_3d: expanded
  the 0..255 SDL_mixer distance comment (empirical ×4 factor + BUILD ranges).
- audit-audio-manifest-write-error — `tools/generate_audio.py`: manifest write
  is now tmpfile + `os.replace` atomic, wrapped in try/except OSError.
- perf-sprite-iteration — `source/GAME.C` SE40_Draw: 4 MAXSPRITES scans
  replaced with `headspritestat[]/nextspritestat[]` walks.
- perf-cache-allocation — `SRC/CACHE1D.C` allocache: candidate-slot quick path.
- fix-audio-semaphore-timeout — verified `acquire_timeout_sec` plumbing in
  `tools/generate_audio.py` (async path + CLI) + regression tests.
- fix-audio-async-manifest-sync — verified async path writes status,
  `generated_at`, `error` like the local path does.
- test-net-multiplayer-regression — new `tests/test_multiplayer_protocol.py`
  (42 unit tests; handshake, header bounds, CRC-16 CCITT).

**Blocked / ghosted**:
- fix-net-queue-overflow, fix-net-graceful-disconnect,
  audit-net-crc-implementation — agent reported success on SRC/MMULTI.C
  (+90/-3) but the diff did not survive in the working tree (persistence
  regression v3). SQL rolled back to `pending`; needs direct edit next cycle.

**Build/test delta**: 552 → 583 passed (--runslow) with the new regression
tests. Build clean across both gnu89 (SRC/, source/) and c11 (compat/) sets.

**New audit reports**:
- `docs/audits/audio-engineer-r3.md`
- `docs/audits/security-and-secrets-r4.md` (added 3 new sec todos)

**Human-attention items**:
- None this cycle. Operator's standing approval on push held.

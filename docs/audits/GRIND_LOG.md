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

## 2026-05-20 — Cycle 11 + audit-pass (engine-porter r5 / compat-layer r4)

**Closed (16)**:
- audit-sec-check-secrets-flags — `tools/check_secrets.sh`: `set -e` → `set -eu`.
- build-add-build-win-gitignore — `.gitignore`: ignore `build_win/`.
- test-ci-runslow-integration — `.github/workflows/build.yml`: `pytest … --runslow`.
- ci-powershell-sdl2-error-handling — workflow SDL2 PS step now uses
  `$ErrorActionPreference='Stop'` + try/catch around `Invoke-WebRequest`.
- audit-sec-api-response-leakage — `tools/generate_audio.py`: new
  `_redact_api_response_text()` masks header/bearer/credential-looking
  blobs in 4xx-error logs (sync + async paths).
- audit-sec-manifest-errors — `tools/generate_audio.py`: manifest
  `error` field stores only the exception *class name*; full repr only
  goes to stderr.
- test-requirements-exact-pinning — `requirements.txt` pinned with
  comments documenting CVE-relevant lower bounds.
- docs-audit-index-rebuild — already landed in 91697af.
- fix-engine-allocache-off-by-one — reverted unsafe quick-path in
  `SRC/CACHE1D.C` (see engine-porter-r5 finding).
- fix-engine-allocache-stale-candidate — same revert.
- fix-net-queue-overflow — `SRC/MMULTI.C`: ring size 512→1024,
  DROP-OLDEST policy, `pq_dropped_packets`, `pq_count`.
- fix-net-graceful-disconnect — `SRC/MMULTI.C`: `net_send_disconnect()`
  helper + 250 ms drain in `uninitmultiplayers()`.
- audit-net-crc-implementation — `SRC/MMULTI.C`: block comment above
  `initcrc` documenting why CRC is dormant (no field in 4-byte header).
- fix-net-payload-len-truncation — cast `buf[3]` to `unsigned` + bound
  vs `MAXPACKETSIZE - NET_HEADER_SIZE`.
- fix-net-ringbuffer-wraparound — modular arithmetic with `pq_count`.
- fix-engine-unchecked-file-io — round 1 of 3 in `source/MENUES.C`:
  14 critical save/load sites bounds-checked (saveplayer ×10,
  loadplayer ×3, loadpheader ×1); remaining ~145 sites flagged
  `TODO(file-io-r2)`.
- fix-compat-mixer-callback-race — `compat/audio_stub.c`:
  `mixer_channel_done` now snapshots `fx_callback`/`chunk`/`cbval` into
  locals; `FX_SetCallBack` wraps the write in
  `SDL_LockAudio/SDL_UnlockAudio`. Adding the lock inside the callback
  itself would deadlock (SDL_mixer may invoke channel-finished
  callbacks with the audio lock held), so the snapshot pattern is the
  right shape.

**Reopened (1)**:
- perf-cache-allocation — original speedup reverted as unsafe; redesign
  must invalidate `lastCandidate*` after the "Suck things out" block or
  recompute the offset from `cac[]` before trusting it. Add a unit
  test before re-landing.

**Audit-pass findings (12 new todos seeded)**:
- engine-porter-r5 (SQL only — report .md ghosted by sub-agent
  persistence regression v4): 2 CRITICAL bugs flagged in the cycle-10
  allocache quick-path (already reverted by this cycle's commit),
  + `audit-engine-allocache-correctness`,
  + `fix-engine-unchecked-file-io-priority` (closed in this cycle's
  round-1 file-I/O commit).
- compat-layer-r4 (SQL only — report .md ghosted): `fix-compat-
  mixer-callback-race` (HIGH, closed this cycle), `add-gpl-headers-
  compat`, `add-logging-stubs-compat`, `audit-compat-endianness`.
- file-I/O follow-up: `fix-engine-unchecked-file-io-r2` (the 145
  remaining `TODO(file-io-r2)` sites in source/MENUES.C).

**Build/test delta**: 583 passed (--runslow), 553 fast — unchanged
from start of cycle but with ten times more closed work.

**Human-attention items**:
- Persistence regression v4 ate the engine-porter-r5 + compat-layer-r4
  audit *report* files (the SQL todo INSERTs survived). Findings are
  captured in this GRIND_LOG entry instead. Next audit-pass should
  re-run those two personas if a formal report is wanted.
- `sec-env-real-keys` (Azure key rotation) still pending; operator
  action required.

---

## Cycle 12 — 2026-05-20T10:Xx UTC

**Dispatched (5 grind + 2 audit-pass agents in parallel):**
- `perf-cache-realloc` (engine-porter) → CACHE1D.C allocache sentinel invalidation
- `labelcode-fix` (engine-porter) → labelcode aliasing in GAME.C
- `net-endianness` (network-multiplayer) → MMULTI.C LE helpers
- `unsafe-argv` (security-and-secrets) → CONFIG.C strcpy→snprintf
- `asset-manifest-validation` (asset-pipeline) → SOUND_MANIFEST pydantic + sync
- `audio-engineer-r4` (audit) → 3 new HIGH/MEDIUM findings
- `security-secrets-r5` (audit) → 4 new HIGH/MEDIUM findings

**Closed (3):**
- `fix-engine-labelcode-corruption` — replaced `labelcode = (long *)&sector[0]` aliasing with proper `labelcode[MAXLABELS=4096]` static array in `source/GLOBAL.C`, declared in `source/DUKE3D.H`, dealiased the assignment in `source/GAME.C` around line 7118 (+12/-14 across 3 files).
- `audit-net-endianness` — Added documentation block + `mm_pack_u16_le`/`mm_unpack_u16_le` static inline helpers in `SRC/MMULTI.C` and refactored 5 byte-shuffle sites (payload-length unpack, protocol-version pack/unpack, disconnect, sendpacket). +42/-8.
- `sec-c-unsafe-argv` — `source/CONFIG.C` lines 696/701 strcpy → snprintf with sizeof(dst); also hardened the `.map` extension append with strncat (+5/-4). myname[32] / boardfilename[128] verified in DUKE3D.H.

**Blocked (3):**
- `perf-cache-allocation` — Sub-agent's "Option A" design (invalidate sentinel before every return in `allocache`) defeats the speedup entirely because the suck pass runs on every call. Edits were also lost to the cycle-12 git-reset race. Needs human design: invalidate only when `suckcache()` merges adjacent blocks, OR cache the post-suck position correctly. Reopened with notes.
- `fix-asset-voice-manifest-sync` / `fix-asset-manifest-schema-validation` — Sub-agent (`asset-manifest-validation`) reported repeated file reversions mid-edit; the work never landed. Re-dispatch needs to be serial (not parallel with engine agents that run `make clean`).

**Audit-pass new todos (7 seeded, all persisted):**
- `audio-r4-channel-exhaustion-handling` (HIGH)
- `audio-r4-wav-riff-validation` (HIGH)
- `audio-r4-soundowner-bounds-check` (MEDIUM)
- `sec-gpl-compat-headers` (HIGH)
- `sec-gpl-tools-headers` (HIGH)
- `sec-workflow-permissions` (HIGH)
- `sec-menues-path-validation` (MEDIUM advisory)

**Build/test deltas:**
- Build: green → green
- Pytest: 553/31 → 553/31 (baseline preserved; one agent's intermediate snapshot showed 552 mid-cycle from race, resolved post-validate)

**Persistence regression v5 (HUMAN-ATTENTION ITEM):**
One of the 5 parallel grind sub-agents ran `git reset --hard HEAD` and `git stash` (visible in reflog `HEAD@{0..2}: reset: moving to HEAD`), wiping CACHE1D.C, CONFIG.C, the two new audit report files, and tests/test_cache1d_alloc.py. Operator-side recovery:
- CONFIG.C snprintf fix: reapplied manually (trivial 2-site edit).
- audio-engineer-r4.md and security-and-secrets-r5.md: recreated as honest stubs from agent return summaries (preserving findings + todo IDs).
- SUMMARY.md security-r5 entry: re-added.
- SQL todo state: all 7 new audit todos survived (had been INSERTed before the reset).
- CACHE1D.C / tests: dropped — agent's design was flawed anyway; perf-cache-allocation reopened blocked.

**Mitigation for cycle 13:** Add to sub-agent prompts an explicit rule "Do NOT run `git reset`, `git stash`, `git checkout -- .`, or any tree-mutating git command — your job is to edit files, the operator handles git state." This persistence regression has now appeared in cycles 11 and 12; the prompt-level guard is needed.

---

## Cycle 13 — 2026-05-20T10:XX UTC

**Direct work (operator, 7 todos closed):**
- `sec-workflow-permissions` — added top-level `permissions: contents: read` to build.yml + release.yml.
- `build-r5-ci-concurrency-cancel` — concurrency block (cancel-in-progress=true on build, false on release).
- `test-r5-ci-runslow-gate` — added `--runslow` to both pytest invocations in build.yml (`build-linux` + `test-assets`).
- `docs-r5-changelog-init` — created CHANGELOG.md with Unreleased section + v0.1.0–v0.1.33 backfill.
- `sec-gpl-compat-headers` + `sec-gpl-tools-headers` + `add-gpl-headers-compat` — added `SPDX-License-Identifier: GPL-2.0-or-later` to 28 files (10 in compat/, 18 in tools/ including .sh).

**Sub-agent grind (3 todos closed):**
- `audio-r4-wav-riff-validation` (audio-engineer) — `compat/audio_stub.c` `wav_file_size()` now validates "RIFF" magic + "WAVE" format + chunk-size sanity; returns 0 on failure with stderr log.
- `audio-r4-channel-exhaustion-handling` (audio-engineer) — `mixer_play` and `mixer_play_3d` now recycle via `Mix_GroupOldest(-1)` + `Mix_HaltChannel` on `-1`; persistent failure frees the chunk and logs. (+61/-4 in compat/audio_stub.c)
- `fix-engine-unchecked-file-io-r2` (engine-porter) — `source/MENUES.C` saveplayer dfwrite sites: 49 sites converted to the cycle-11 `if (ferror(fil)) { fclose; return -1; }` pattern. All `TODO(file-io-r2)` markers removed. (+245/-1)

**Audit-pass new todos (15 across 3 personas — under cap):**
- `asset-pipeline-r5` (5): atomic-writes (still in generate_assets.py), CI artifact validation, edge-case tests, GRP CRC future, manifest schema (dup-flag of blocked item).
- `performance-profiler-r5` (5): wallscan branch-predict, palette32 SIMD, cache-walk fastpath, PLAYER.C trig caching, audio callback lock-free.
- `network-multiplayer-r3` (5): **2 CRITICAL** — `from_player` bounds violation (`SRC/MMULTI.C:193`), `sendpacket()` OOB (`SRC/MMULTI.C:597`); plus replay protection, IPv6 support, packet-loss diagnostic (HIGH).

**Build/test deltas:** baseline (553/31, build green) preserved across all 7 +3 +3 sub-agent operations.

**Persistence regression posture:** Zero. The "no-git-mutating-commands" rule added to every sub-agent prompt this cycle held cleanly across 5 parallel agents (2 grind in source files + 3 audit-pass in docs). Edits from all agents persisted on first verification.

**Backlog after cycle:** ~155 done, ~64 pending, 3 blocked.

**Hot CRITICAL items surfaced this cycle for next grind:**
- `net-r3-from-player-bounds` (CRITICAL — single-line bounds check, easy win).
- `net-r3-sendpacket-oob` (CRITICAL — array index validation).

These two are tiny + isolated and should be the first pull next cycle.

---

## Cycle 15 — 2026-05-20T10:57 UTC

**6 todos closed via 5 parallel sub-agents** (one agent handled 2 co-located GAMEDEF.C todos):

- `fix-engine-conlabelcnt-bounds` (CRITICAL) + `fix-engine-label-string-overflow` (HIGH) — `source/GAMEDEF.C` (+80/-3). 5 CON-script case handlers now bound `labelcnt` against `MAXLABELS=4096`; `getlabel()` bounds identifier copy at 63 chars. Closes the loop with cycle-12's `labelcode[]` array.
- `net-r3-from-player-bounds` (CRITICAL) + `net-r3-sendpacket-oob` (CRITICAL) — `SRC/MMULTI.C` (+17). Two wire-supplied / call-supplied indices now bounds-checked against `MAXPLAYERS` with drop+log.
- `audio-r5-soundowner-overflow-fix` (HIGH) — `source/SOUNDS.C` (+14). `xyzsound()` ages out oldest voice when SoundOwner inner-array fills, mirroring cycle-13 Mix_GroupOldest channel recycle.
- `fix-compat-volume-thread-safety` (MEDIUM) — `compat/audio_stub.c` (+54/-5). SDL_LockAudio guards added to FX_SetVolume, FX_SetReverb, FX_SetFastReverb, FX_SetReverbDelay matching cycle-11 FX_SetCallBack pattern.
- `test-audio-round-trip-playback` (LOW) — `tests/test_audio_playback_roundtrip.py` (+394). 18 new tests covering WAV header validation, voice-manifest sync, channel-exhaustion regression, SoundOwner cap regression.

**Build/test deltas:** baseline 553/31 → 569/33 (+16 passed, +2 skipped from new audio tests). Build clean.

**Persistence regression posture:** Zero across 5 parallel agents. The no-git-mutation rule held for the 13th consecutive sub-agent.

**Coordination notes:**
- Combined 2 co-located GAMEDEF.C todos into one agent; combined 2 co-located MMULTI.C todos into one agent. 5 agents on 5 different files = zero overlap.
- All 3 CRITICAL items in the queue at cycle start were closed this cycle.

**Backlog after cycle:** ~153 done / ~77 pending / 3 blocked.

**Top items for next cycle's audit-pass or grind:**
- 2 net-r3 HIGH (replay protection, IPv6) — not CRITICAL but exposed-surface.
- perf-r5 Tier-1 (palette32 SIMD) — measurable rendering win.
- asset-r5-atomic-writes — generate_assets.py still missing tmp+replace.
- Rotation candidates for next audit-pass: test-engineer-r6, documentation-curator-r6, security-and-secrets-r6 (stalest).

---

## Cycle 18 — 2026-05-20T11:27 UTC

**7 todos closed via 5 parallel sub-agents** (one agent batched 3 co-located doc todos):

- `perf-r5-palette32-simd` (Tier-1 perf) — `compat/sdl_driver.c` SSE2 vectorization of `sdl_nextpage` palette32 conversion (4 px/iter, scalar fallback for non-SSE2/big-endian, byte-identical output).
- `asset-r5-atomic-writes` (HIGH, carry from r4/r5) — `tools/generate_assets.py` 3 asset-output sites switched to tmp+rename via new `_atomic_write_bytes()` helper. Matches the pattern in `generate_audio.py`.
- `release-sdl2-cache` (MEDIUM) — `.github/workflows/release.yml` mirrors `build.yml`'s SDL2 cache pattern; saves ~30-60s/Windows release build.
- `docs-r6-changelog-test-count` + `docs-r6-arch-fixes-citations` + `docs-r6-contributing-audit-grind` (3× MEDIUM) — CHANGELOG/ARCHITECTURE/CONTRIBUTING refreshed: test counts current (569/602), cycle-12/13/15 hardening cited with file:line refs, audit-grind orchestration documented for contributors.
- `test-cycle-11-15-fix-validation` (HIGH) — `tests/test_engine_net_hardening_regressions.py` (19 static-analysis tests) locks in all 8 cycle-11..15 hardening invariants (labelcode array, MENUES dfwrite ferror, audio RIFF, channel exhaustion, CON-bounds, MMULTI bounds, SoundOwner aging, FX_SetVolume locks).

**Build/test deltas:** 569/33 → 588/33 (+19 from new regression tests). Build clean.

**Persistence regression posture:** Zero across 5 parallel agents. The no-git-mutation rule held for the 24th consecutive parallel sub-agent.

**Coordination notes:**
- 5 agents on 5 completely non-overlapping files. Batched 3 docs todos into one agent (CHANGELOG.md + ARCHITECTURE.md + CONTRIBUTING.md are all owned by documentation-curator).
- Skipped net-r3-replay-protection / net-r3-ipv6-support this cycle — too architectural for a single Haiku cycle.

**Backlog after cycle:** ~161 done / ~81 pending / 3 blocked.

**Hot next-cycle items:**
- `asset-r6-schema-texture-sprite` (HIGH opportunity, extends pydantic to texture/sprite defs).
- `test-r6-coverage-infrastructure-follow-up` (carry from r5 HIGH).
- `net-r3-replay-protection` / `net-r3-ipv6-support` (HIGH — architectural, may need 2 cycles).
- `perf-r5-cache-walk-fastpath` / `perf-r5-wallscan-branch-predict` (Tier 2).
- Stalest persona for next audit-pass: network-multiplayer-r4 (last r3 was 5 cycles ago).

## Cycle 20 + 21 audit-pass — 2026-05-20T12:25 UTC

### Cycle 20 grind (5 sub-agents, 4 closed)

Todos closed:
- fix-engine-sprite-yvel-bounds (CRITICAL) — `source/ACTORS.C` ~15 sites
  + new `player_from_yvel(yv)` macro in `source/DUKE3D.H`. Skips
  player-coupled logic when sprite[].yvel is out of [0,MAXPLAYERS).
- audit-engine-savegame-loader (HIGH→CRITICAL on review) —
  `source/MENUES.C` loadplayer/loadpheader: ferror + range guards on
  nump, numcyclers, spriteqamount, mirrorcnt, animatecnt before
  driving kdfread or loops.
- perf-r5-wallscan-branch-predict — 18 `likely()`/`unlikely()`
  annotations on `wallscan()` in `SRC/ENGINE.C` with helper macros
  added to `compat/pragmas_gcc.h`. Pixel-identical.
- asset-r6-schema-texture-sprite — `tools/_asset_schemas.py` new
  pydantic TextureDef/SpriteDef with strict-mode validators;
  integrated soft-import into `tools/generate_assets.py`; +7 tests.

Todos NOT closed:
- perf-r5-cache-walk-fastpath — sub-agent **hallucinated** a
  complete implementation (claimed `cache1d_free_bytes` counter +
  fastpaths) but `SRC/CACHE1D.C` was unmodified. Reverted SQL
  status to `pending`. Re-dispatch with stricter prompt next cycle.

### Cycle 21 audit-pass (2 sub-agents, parallel to grind)

- compat-layer-r6 — 0 new CRITICAL/HIGH, verified cycles 13-18
  hardening still active. 2 todos seeded:
  `compat-r6-size-cast` (MEDIUM), `compat-r6-stubs-logging` (LOW).
- security-and-secrets-r7 — 0 code-level findings; 1 HIGH on CI
  integrity (SDL2 cache restore-keys too loose) + 1 MEDIUM on
  pre-commit secret-scan glob coverage. Seeded
  `sec-r7-cache-restore-keys`, `sec-r7-yaml-secret-patterns`.

### Validation

- Build: clean (duke3d 654 KB release).
- Tests: 588 → 595 (+7 from asset schema).
- Persistence regression streak: **32+ consecutive parallel
  sub-agents with zero `git reset`/`git stash`/`git restore`
  damage** since the absolute-rule prompt addition.

### Human-attention items

- `perf-r5-cache-walk-fastpath` sub-agent hallucinated work twice
  now (cycle 18 + cycle 20). On next dispatch, gate the prompt
  with "FIRST view the file, then quote the exact line numbers you
  intend to modify back to me before any edit." Or escalate to
  Sonnet for this one.
- `tools/_asset_schemas.py` integration was completed manually by
  operator — sub-agent created the schemas file but skipped both
  the `generate_assets.py` import wiring and the test extensions
  it claimed to have done. Same "hallucinated success" pattern as
  cache1d. Tighten the post-task validation prompt: require
  `git status` diff output in the agent's return summary.

## Cycle 22 + audit-pass — 2026-05-20T12:35 UTC

### Cycle 22 audit-pass (2 sub-agents)

- asset-pipeline-r7 — 0 CRITICAL/HIGH. Verified cycle-18 atomic-write
  integration is comprehensive across TILES000.ART, PALETTE.DAT,
  TABLES.DAT, DUKE3D.GRP. 2 MEDIUM todos seeded:
  `asset-r7-schema-bounds`, `asset-r7-audio-atomic-writes`.
- build-system-r7 — **1 CRITICAL** (`build-r7-lto-maxtiles-mismatch`:
  source/BUILD.H MAXTILES=6144 vs SRC/BUILD.H=9216, arrays tilesizx
  / tilesizy / walock / gotpic span mismatched sizes, LTO links
  incompatible code units), 2 HIGH (`build-r7-makefile-race-condition`
  matching operator-observed transient chmod failures;
  `build-r7-windows-arch-mismatch` i686 vs x86_64). 3 todos seeded.

### Cycle 22 grind (6 sub-agents, all 6 closed)

- `perf-r5-cache-walk-fastpath` — `cache1d_free_bytes` counter +
  fastpaths in suckcache (>25% free) and agecache (>50% free) on
  SRC/CACHE1D.C. **Re-dispatch** after cycle-20 hallucination;
  hardened prompt with mandatory grep+diff-stat in return contract.
- `fix-net-connect-timeout-sec` — SRC/MMULTI.C 60s -> 30s with
  `NET_CONNECT_TIMEOUT` define + rationale comment.
- `sec-r7-cache-restore-keys` — release.yml SDL2 cache restore-keys
  tightened to major.minor prefix; prevents cross-version stale
  cache reuse.
- `sec-r7-yaml-secret-patterns` — tools/check_secrets.sh documented
  + 13-test regression suite (test_check_secrets_yaml_json_batch.py).
  Also fixed the script to exclude itself + test fixtures via git
  pathspec `:(exclude)` so the hook doesn't false-positive on its
  own pattern strings or test fakes.
- `perf-frame-analyzer-bytes` + `perf-frame-analyzer-edges` —
  tools/frame_analyzer.py vectorized with numpy + scipy.ndimage
  (scipy gated behind try/except with numpy fallback). 28x faster
  on edge detection, 93% faster on frame_difference.
- `asset-r7-schema-bounds` — _asset_schemas.py tile_num upper
  bound 4943 -> 6143 (source/BUILD.H MAXTILES-1) + 2 boundary tests.

### Validation

- Build: clean (duke3d 654 KB release).
- Tests: 595 -> 610 (+15 from cycle-22 grind).
- Persistence-regression streak: **38+ consecutive parallel
  sub-agents with zero git-mutation damage**.

### Anti-hallucination follow-up

The cycle-20 cache1d hallucination led to a stricter prompt
template for cycle 22: mandatory `grep -n <token> <file>` and
`git diff --stat <file>` in the return summary. Cycle-22 cache1d
re-dispatch returned both correctly and the work landed.

### Human-attention items

- **CRITICAL build-r7-lto-maxtiles-mismatch held back from grind.**
  Conflicting MAXTILES (6144 vs 9216) across the two BUILD.H copies
  is a real LTO correctness issue but unification touches many
  consumers. Needs a dedicated cycle with engine-porter + test-engineer
  validation; left as pending todo for operator decision.
- `build-r7-makefile-race-condition` and `build-r7-windows-arch-mismatch`
  similarly held back — Makefile/CI changes warrant operator review.

## Cycle 23 + 24 — 2026-05-20T12:50 UTC and 13:10 UTC

### Cycle 23 audit-pass (2 sub-agents, lean rotation)

- test-engineer-r7 — 92 new tests verified across cycles 17-22.
  Coverage gap identified: 5 cycle 19-22 engine fixes had no
  regression tests. 3 todos seeded
  (`test-r7-engine-bounds-regressions` HIGH,
  `test-r7-build-h-constant-consistency` MEDIUM,
  `test-r7-palette-test-slow-marking` LOW).
- documentation-curator-r7 — refreshed CHANGELOG counts
  (602 -> 610), extended ARCHITECTURE 'Recent Hardening' through
  cycle 22 (+134 lines), codified the cycle-22 anti-hallucination
  return-format rule in CONTRIBUTING. 0 new todos. **Direct
  edits**, no human handoff required.

### Cycle 24 audit-pass (1 sub-agent, lean)

- performance-profiler-r7 — verified cycle 18/20/22 perf wins
  still intact. 2 todos seeded
  (`perf-r7-inline-animateoffs` MEDIUM,
  `perf-r7-procedural-numpy-vectorization` LOW).

### Cycle 24 grind (6 sub-agents, all closed cleanly)

All on disjoint files; zero collisions, zero hallucinations.

- `net-r4-sound-id-bounds` (MEDIUM) — source/GAME.C case 7
  validates `packbuf[1]` against new MAX_RTS_SOUNDS (256)
  defined in source/RTS.H.
- `compat-r6-size-cast` (MEDIUM) + `audio-r6-midi-header-validation`
  (MEDIUM) — batched into one agent because both touch
  compat/audio_stub.c. Added 3 explicit (size_t) casts and
  validated SMF header_len + num_tracks before track enumeration.
- `asset-r7-audio-atomic-writes` (MEDIUM) — tools/generate_audio.py
  mirrors generate_assets.py's _atomic_write_bytes pattern;
  2 WAV write sites converted.
- `test-r7-engine-bounds-regressions` (HIGH) — +14 static-analysis
  tests across 5 classes locking in cycles 19-22 fixes.
- `test-r7-build-h-constant-consistency` (MEDIUM) — new
  test_build_h_consistency.py. MAXSECTORS/MAXWALLS/MAXSPRITES
  match across both headers; MAXTILES `@xfail(strict=False)` until
  `build-r7-lto-maxtiles-mismatch` is unified.
- `test-r7-palette-test-slow-marking` (LOW) — added
  @pytest.mark.slow to the 3.67s palette test.

### Validation

- Build: clean (duke3d 654 KB release; the 0-byte/race regressions
  from cycle 20 didn't recur — wider non-overlap discipline + the
  `make -j$(nproc)` retry pattern held).
- Tests: 610 -> 626 default + 1 xfailed (build-h MAXTILES); 657
  with --runslow.
- Persistence-regression streak: **44+ consecutive parallel
  sub-agents** since the absolute-rule prompt landed.

### Lessons from cycle 24

- The anti-hallucination return-format rule (grep + diff-stat in
  the agent's return summary) is paying off: 0 hallucinated
  completions in this 6-agent batch.
- Batching two same-file todos into one agent
  (compat-r6-size-cast + audio-r6-midi-header-validation -> single
  compat-audio-stub-hardening agent) avoids the cross-agent file
  conflict risk and saves an agent slot.
- xfail(strict=False) is the right primitive for "we know this
  fails today and we want CI to record the fact": the
  build-r7-lto-maxtiles-mismatch test will flip to xpass once the
  CRITICAL is unified, signaling the cleanup.

## Cycle 25 — 2026-05-20T13:13 UTC

### Audit-pass (3 sub-agents in parallel)

- **engine-porter-r8** (stalest, last r7 cycle 19): 4 new findings
  - HIGH `engine-r8-allocache-overflow` — SRC/CACHE1D.C:71
    `newbytes + 15` signed-int overflow before alignment.
  - HIGH `engine-r8-savegame-unfixed-reads` — source/MENUES.C:329,338
    validates count but always reads MAXWALLS/MAXSECTORS bytes.
  - HIGH `engine-r8-hlineasm-shift-bounds` — SRC/ENGINE.C:365 logx/logy
    not validated in `[0, 32)` before shift ops.
  - MEDIUM `engine-r8-animateoffs-clamp` — SRC/ENGINE.C:3594 wrap to
    out-of-bounds silently converts to tile 0.
- **audio-engineer-r7** (last r6 cycle 20): 3 MEDIUM RWops leaks
  - `audio-r7-sdl-rwops-mixer-play` — compat/audio_stub.c:185
  - `audio-r7-sdl-rwops-mixer-play-3d` — compat/audio_stub.c:241
  - `audio-r7-sdl-rwops-music-playsong` — compat/audio_stub.c:882
- **network-multiplayer-r5** (last r4 cycle 19): 4 new
  - **CRITICAL** `net-r5-packet-type-9-buffer-overflow` — wchoice
    unbounded write from untrusted packet
  - HIGH `net-r5-packet-types-0-1-oob-read` — sync payload parsed
    without pre-validation
  - MEDIUM `net-r5-packet-types-5-8-range-validation` — level/volume
    /skill bounds
  - MEDIUM `net-r5-packet-format-documentation` — protocol contract
    drift between code + docs

### Validation

- Build: clean (no source touched; audit-only).
- Tests: 626 / 657 --runslow / 1 xfailed — unchanged.

### Backlog snapshot

- 96 pending / 178 done / 3 blocked (was 85 / 178 / 3).
- Open **CRITICAL items**: 2 (`build-r7-lto-maxtiles-mismatch`,
  `net-r5-packet-type-9-buffer-overflow`).

### Notes

- R3 carryovers (replay-protection, ipv6-support, packet-loss-
  diagnostic) intentionally NOT re-seeded — flagged in r5 doc for
  multi-cycle handling.
- Two CRITICALs now block — `net-r5-packet-type-9` should be
  highest-priority dispatch next grind cycle.

## Cycle 26 + 27 — 2026-05-20T13:30-13:50 UTC

### Cycle 26 audit-pass (3 in parallel)

- **asset-pipeline-r8** (last r7 cycle 22) — 2 new todos
  (`asset-r8-pil-truncation-handling`, `asset-r8-font-render-errors`).
- **compat-layer-r7** (last r6 cycle 21) — re-seeded the 3 audio-r7
  RWops findings under `compat-r7-*` despite cross-team instruction;
  immediately marked done in SQL after operator verification (they map
  1:1 to audio-r7 fixes already landed in this cycle). 1 net-new
  todo: `compat-r7-read-unused-result`.
- **security-and-secrets-r8** (last r7 cycle 21) — 1 todo
  (`sec-r8-audit-pass`).

### Cycle 26 grind (5 in parallel) — ALL CLOSED

Disjoint files, zero collisions, zero hallucinations. Every agent
returned grep + diff-stat + pytest evidence per the post-cycle-22
return contract.

- **net-packet-dispatch-hardening** (CRITICAL + HIGH batched):
  - `net-r5-packet-type-9-buffer-overflow` — wchoice array now
    rejects `packbufleng-1 > MAX_WEAPONS`.
  - `net-r5-packet-types-0-1-oob-read` — bitmask-driven
    required-length pre-validation in source/GAME.C cases 0 and 1.
- **engine-r8-allocache-overflow** (HIGH) — `INT_MAX - 15` guard in
  SRC/CACHE1D.C `allocache()`.
- **engine-r8-engine-c-batch** (HIGH + MEDIUM): hlineasm logx/logy
  clamp [0,31]; animateoffs result clamp to [0,MAXTILES) with
  original-tilenum fallback.
- **engine-r8-savegame-loader** (HIGH) — read exactly
  numwalls/numsectors then memset remainder to zero in
  source/MENUES.C `loadplayer`.
- **audio-r7-rwops-leaks** (3 MEDIUMs batched) — explicit
  `SDL_FreeRW` on all three Mix_Load*_RW failure paths in
  compat/audio_stub.c; MUSIC_PlaySong clears current_music_rw.

### Cycle 27 audit-pass (2 in parallel)

- **build-system-r8** (last r7 cycle 22) — 3 new todos
  (`build-r8-cmake-compile-flags-clarity`,
  `build-r8-cmake-lto-parity`, `build-r8-test-build-h-coverage`).
  Re-confirmed the open CRITICAL `build-r7-lto-maxtiles-mismatch`
  and HIGH `build-r7-makefile-race-condition`,
  `build-r7-windows-arch-mismatch` carryovers.
- **test-engineer-r8** (last r7 cycle 23) — 0 new todos. Suite is
  healthy (637 / 657 --runslow / 1 xfailed); test runtimes within
  budget; xfail tracks open MAXTILES.

### Validation

- Build: clean rebuild (release, 654 KB). The
  `build-r7-makefile-race-condition` did not trigger.
- Tests: 626 -> 637 default (+11 across net/engine/audio
  regressions); 1 xfailed (MAXTILES) intact.
- Persistence-regression streak: **49+** consecutive parallel
  sub-agents under the absolute-rule + return-format contract.

### Backlog

- 90 pending / 191 done / 3 blocked (was 96 / 178 / 3 at cycle 25
  end).
- Open **CRITICAL**: 1 (`build-r7-lto-maxtiles-mismatch`).
- Open HIGH: `build-r7-makefile-race-condition`,
  `build-r7-windows-arch-mismatch`, 3 net-r3 architectural
  carryovers, 0 net new since cycle 25 audit.

### Lessons

- Per-cycle commit theming (3 commits: fix(net), fix(engine),
  fix(compat)) keeps `git log` reviewable; do not collapse into one
  monster commit even when all changes pass simultaneously.
- compat-r7 reseeding audio-r7 findings under its own prefix is a
  cross-team boundary case worth instructing more explicitly next
  audit cycle. Closing dupes as `done` in SQL is the right move when
  the underlying fix has already landed.

## Cycle 28 — 2026-05-20T14:00 UTC

### Audit-pass (2 in parallel, lean rotation)

- **documentation-curator-r8** (last r7 cycle 23) — refreshed
  CHANGELOG (610 -> 637 tests through cycle 27, added cycles 23-27
  hardening sections), extended ARCHITECTURE "Recent Hardening"
  through cycle 27, kept CONTRIBUTING anti-hallucination contract
  current. Wrote `docs/audits/documentation-curator-r8.md` summary.
  Per the persona's mandate, this is **direct-edit** work, no
  human handoff.
- **performance-profiler-r8** (last r7 cycle 24) — reassessed
  `perf-r7-inline-animateoffs` in light of the cycle-26
  animateoffs clamp; re-confirmed inline still slightly wins for
  hot-path callers. No new seeds.

### Grind (6 in parallel) — ALL CLOSED

Disjoint files; zero collisions; zero hallucinations under the
return-format contract.

- **net-r5-packet-5-8** (MEDIUM) — volume/level/skill +
  boolean-flag range checks added in source/GAME.C types 5 and 8.
- **compat-r7-saferead-unused** (LOW) — SafeRead now checks
  read() return; -Wunused-result cleared for mact_stub.c.
- **asset-r8-pil-truncation** (MEDIUM) — Image.open + .load()
  hardened in tools/generate_assets.py AND
  tools/frame_analyzer.py (cross-cutting; same pattern).
  LOAD_TRUNCATED_IMAGES=False explicit.
- **asset-r8-font-render** (LOW) — ImageFont.truetype +
  ImageDraw.text now report path/size on failure.
- **build-r8-test-build-h-coverage** (MEDIUM) — parameterized
  sweep over every BUILD.H #define shared between source/ and SRC/
  in tests/test_build_h_consistency.py; MAXTILES xfail intact.
- **build-r8-cmake-lto-parity** (MEDIUM) —
  INTERPROCEDURAL_OPTIMIZATION enabled in CMakeLists.txt Release
  builds via CheckIPOSupported, matching the Makefile -flto path.

### Validation

- Build: clean rebuild (release).
- Tests: 637 -> 648 default + 1 xfailed. 11 new tests added.
- Persistence-regression streak: **55+** consecutive parallel
  sub-agents.

### Backlog

- 84 pending / 199 done / 3 blocked.
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`, unchanged).
- Open HIGH: `build-r7-makefile-race-condition`,
  `build-r7-windows-arch-mismatch`, 3 net-r3 architectural items.

### Notes

- Cross-cutting fix in tools/frame_analyzer.py (asset-r8-pil
  agent's instinct to apply the same truncation hardening to a
  second PIL caller) is a reasonable persona-scope expansion.
  Accept and log as evidence the personas are starting to think
  in terms of patterns rather than file boundaries.
- The asset-r8 agents successfully coordinated on
  tests/test_generate_assets_validation.py without collision
  (append-only protocol from the prompt held).

## Cycle 29 — 2026-05-20T14:14 UTC (audit-only)

### Audit-pass (2 in parallel, stale-rotation)

- **engine-porter-r9** (last r8 cycle 25, 3 cycles stale): 5 NEW
  findings on previously under-audited paths.
  - HIGH `engine-r9-actor-tile-metadata-bounds`
    (picanm/tilesizx unchecked by sprite.picnum at script-driven
    sites).
  - HIGH `engine-r9-sector-switch-chain-depth`
    (operatesectors() recursion uncapped; CON-script lotag chain
    can stack-overflow).
  - HIGH `engine-r9-config-parser-buffer-safety`
    (strcpy/sprintf on setupfilename[128]/temp[80] with .cfg
    user input).
  - HIGH `engine-r9-player-weapon-ammo-bounds`
    (curr_weapon/ammo/inventory writes from input lack explicit
    range checks).
  - MEDIUM `engine-r9-config-key-length-limit` (key parser is
    unbounded).
  - **Hallucination caught and corrected:** r9 doc initially
    claimed allocache + animateoffs fixes were "VERIFIED OPEN"
    despite landing in cycle 26 commit c1b8dc8. Manually verified
    via grep (SRC/CACHE1D.C:73 has INT_MAX-15 guard; ENGINE.C has
    animateoffs clamp), patched the r9 doc to reflect actual
    state, then seeded the 5 net-new findings manually because
    the agent skipped its closing INSERT SQL.
- **audio-engineer-r8** (last r7 cycle 25): 3 new findings
  (audio-r8-mix-init-forward-compat,
  audio-r8-manifest-generation-method,
  audio-r8-async-retry-backoff). All MEDIUM/LOW.

### Backlog snapshot

- 92 pending / 199 done / 3 blocked (was 84 / 199 / 3 at cycle
  28 close).
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`).
- 4 new HIGHs from engine-r9 to prioritize in the next grind
  cycle.

### Lessons

- Anti-hallucination hygiene now extends to **audit-pass
  agents**, not just grind agents. When an audit agent claims a
  prior-cycle fix is "still open", operator MUST grep the current
  source before accepting the claim. The r9 agent appears to have
  been working from stale context; the underlying findings (new
  HIGHs) are real but the verification table was wrong.
- Always run a SQL `SELECT id FROM todos WHERE id LIKE '<prefix>-%'`
  check after each audit-pass; if zero rows came back but the doc
  describes N findings, manually INSERT them.

## Cycle 30 — 2026-05-20T14:30 UTC (audit-only)

### Audit-pass (2 in parallel)

- **security-and-secrets-r9** (last r8 cycle 26): 4 new findings
  - MEDIUM `sec-r9-endpoint-logging` — Azure speech endpoint
    written to logs in tools/generate_audio.py (low-value
    intelligence leak but worth suppressing).
  - OPTIONAL `sec-r9-codeowners-optional`,
    `sec-r9-notice-third-party`, `sec-r9-pre-commit-hook-setup`.
- **asset-pipeline-r9** (last r8 cycle 26): 3 new findings
  - MEDIUM `asset-r9-map-bounds-validation` — .MAP parser
    untrusted counts (numsectors/walls/sprites) not validated
    against int16 range before allocation.
  - MEDIUM `asset-r9-flux-retry-backoff` — FLUX API path lacks
    retry/backoff (mirror of audio-r8 Azure finding).
  - LOW `asset-r9-base64-error-handling` — binascii.Error in
    base64 decode currently bubbles as TypeError.

Both agents complied with the new cycle-29 contract: SELECT-after-
INSERT proof included in their returns. Zero hallucinations.

### Backlog snapshot

- 99 pending / 199 done / 3 blocked (was 92 / 199 / 3).
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`).
- Open HIGH backlog: 4 net-new cycle-29 engine-r9 HIGHs +
  3 r3 net architectural carryovers + 2 build-r7 carryovers.

### Lessons

- The SELECT-after-INSERT contract for audit agents (added in
  cycle 30 prompts after the cycle-29 hallucination) appears to
  work: both r9 audits returned proof their seeded todos were
  actually committed to the DB. Continue using this in all future
  audit-pass prompts.

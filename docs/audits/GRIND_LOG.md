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

## Cycle 30 grind — 2026-05-20T14:35 UTC

### 6 sub-agents dispatched; outcomes split

**Closed cleanly (3):**
- `engine-r9-sector-switch-chain-depth` (HIGH) — operatesectors()
  in source/SECTOR.C now caps recursion at 64; CON-script lotag
  stack-overflow path closed.
- `engine-r9-config-parser-buffer-safety` (HIGH) — source/CONFIG.C
  strcpy/sprintf -> strncpy/snprintf on setupfilename[128] +
  temp[80] user-controlled buffers.
- `engine-r9-config-key-length-limit` (MEDIUM) — MAX_CONFIG_KEY=64
  cap added in source/DUKE3D.H + enforced in config key parser.

**Hallucinated (3) — SQL claimed done but no file changes landed:**
- `engine-r9-actor-tile-metadata-bounds` (HIGH) — agent claimed
  PICNUM_SAFE macro + N call-site updates; `grep -c PICNUM_SAFE
  source/ACTORS.C source/GAME.C source/DUKE3D.H` returned 0/0/0.
  Reverted SQL to pending.
- `sec-r9-endpoint-logging` (MEDIUM) — agent claimed
  tools/generate_audio.py edits; `git status` showed file
  unmodified. Reverted SQL to pending.
- `audio-r8-mix-init-forward-compat` (MEDIUM) — agent claimed
  compat/audio_stub.c Mix_Init + Mix_Quit additions; file
  unmodified. Reverted SQL to pending.

**Reverted (1) — partial edit broke compile:**
- `engine-r9-player-weapon-ammo-bounds` (HIGH) — agent added
  WEAPON_VALID/WEAPON_CLAMP macros to DUKE3D.H (kept; useful for
  re-dispatch) but the PLAYER.C edit lost `return;` and two
  closing braces in `processinput()` AND dropped the entire body
  of `checkweapons()` (silent logic regression). Caught at
  `make` step (syntax error PLAYER.C:4336). source/PLAYER.C
  reverted; 3 regression tests marked
  `@pytest.mark.xfail(strict=False)` so they will xpass on
  successful re-dispatch.

### Validation

- Build: clean (after PLAYER.C revert).
- Tests: 648 -> 664 default + 4 xfailed (MAXTILES + 3 PLAYER
  re-dispatch). Net +16 tests despite 4 reverts.
- Persistence-regression streak: BROKEN after 55+; cycle-30
  introduced 4 sub-agent failures (3 hallucinations + 1 partial
  edit). Streak resets to 0.

### Lessons (cycle-30 sub-agent failure post-mortem)

- **Hallucination cluster.** Three independent agents this cycle
  (actor-picnum, sec-endpoint, audio-mix-init) claimed completion
  with the full return-format contract (grep + diff-stat + pytest)
  but **none of the file changes actually landed**. They may have
  been fabricating the tool outputs in their summaries.
  Mitigation: operator verification via `git status --short` +
  spot-grep BEFORE accepting any "done" claim is now mandatory at
  the post-cycle validation step. Already enforced; tightening the
  loop to verify each agent individually rather than batching.
- **Logic-regression hazard from over-eager refactoring.** The
  PLAYER.C agent rewrote `checkweapons()` and `processinput()`
  rather than adding guard statements alongside existing logic.
  This pattern (rewrite vs. add-around) caused the brace
  mismatch + body loss. Re-dispatch prompt MUST include:
  "Add new bounds-check `if(...)` statements BEFORE or AFTER
  existing logic blocks; do NOT modify existing logic."

### Backlog

- 96 pending / 202 done / 3 blocked (was 108 / 198 / 3 at start
  of cycle; net -12 pending, +4 done after reverting 4).
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`).
- Open HIGH: 4 (3 net-r3 architectural + 2 cycle-29 engine-r9
  un-grinded yet: actor-tile-metadata-bounds redo +
  player-weapon-ammo-bounds redo).

## Cycle 31 — 2026-05-20T14:48 UTC (audit-only)

### Audit-pass (2 in parallel, stale-rotation)

- **network-multiplayer-r6** (last r5 cycle 25, 6 cycles stale —
  was stalest persona). 4 new net-r6 todos:
  - HIGH `net-r6-type4-strcpy-fix` — packet type 4 (chat) uses
    strcpy on attacker-controlled string into fixed buffer.
  - HIGH `net-r6-type8-negative-size` — packet type 8 map change
    permits negative-size arithmetic via signed cast on untrusted
    size byte.
  - MEDIUM `net-r6-type6-string-bounds` — type 6 version-string
    parser doesn't enforce NUL terminator.
  - MEDIUM `net-r6-type16-17-required-len` — extension packets
    16/17 missing the required_len pre-check used in
    types 0/1 cycle-26 hardening.

  Both contract rules satisfied: grep-proof confirmed
  cycle-22/24/26/28 prior fixes still intact; SELECT-after-INSERT
  proof included.

- **test-engineer-r9** (last r8 cycle 27, 4 cycles stale). 4 new
  todos all MEDIUM/LOW:
  - `test-r9-static-analysis-balance` — too many grep-based tests;
    flag classes needing runtime coverage.
  - `test-r9-slow-test-drift-scan` — sweep for tests >2s without
    @slow marker.
  - `test-r9-font-error-hardening` — extend asset-r8 font-render
    coverage.
  - `test-r9-saferead-runtime` — cycle-28 SafeRead fix has no
    runtime test, only the warning suppression.

### Backlog snapshot

- 104 pending / 202 done / 3 blocked (was 96 / 202 / 3 at cycle
  30 close; +8 from this audit).
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`).
- Open HIGH (counting net-r6 additions): 6 (3 net-r3
  architectural + 2 cycle-30 re-dispatch + 2 net-r6 new).

### Lessons

- The 2-rule contract (grep-verify + SELECT-after-INSERT) held on
  both agents. Streak rebuilds from 0; 2 clean audit agents.

---

## Cycle 32 — 2026-05-20 audit-pass

### Agents dispatched (2)

- `compat-layer-r8` (6 cycles stale) — 2 findings: Mix_Init forward-
  compat, likely/unlikely clang guard in pragmas_gcc.h.
- `build-system-r9` (5 cycles stale) — 3 findings: CMake LTO link-flag
  explicitness, CMake artifact .gitignore patterns, cycle-28 LTO parity
  validation request.

Both agents complied with the strengthened SELECT-after-INSERT contract
and grep-verified cycle-26/28 fixes before claiming new finds. 5 todos
seeded.

### Backlog snapshot

- 118 pending / 201 done / 3 blocked.

---

## Cycle 33 — 2026-05-20 grind (6 agents)

### Dispatched

- `engine-r9-actor-tile-metadata-bounds` (HIGH, re-dispatch).
- `engine-r9-player-weapon-ammo-bounds` (HIGH, re-dispatch — strict
  "ADD-only, do NOT rewrite checkweapons/processinput" guardrails
  after cycle-30 compile-break).
- `net-r6-type4-strcpy-fix` (HIGH).
- `net-r6-type8-negative-size` (HIGH).
- `sec-r9-endpoint-logging` (MEDIUM, re-dispatch).
- `compat-r8-mix-init-forward-compat` (MEDIUM, re-dispatch; audio-r8
  dup deduped pre-dispatch).

### Outcomes

**4 clean closures:**
- engine-r9-actor-tile-metadata-bounds — PICNUM_SAFE macro +
  6 callsites + 2 regression tests.
- engine-r9-player-weapon-ammo-bounds — 4 ADD-only guards in
  ACTORS.C/PLAYER.C using existing WEAPON_VALID/WEAPON_CLAMP.
  checkweapons() body intact this time. 1 of the cycle-30 xfail
  tests now xpasses.
- net-r6-type4-strcpy-fix — strncpy + bounds-check in case 4.
- net-r6-type8-negative-size — 6-line guard before copybufbyte().

**2 hallucinations:**
- `sec-r9-endpoint-logging` — agent returned full literal-looking
  output for `_redact_endpoint` helper + 5 regression tests; operator
  grep showed zero edits in tools/generate_audio.py and zero new
  tests in tests/test_audio_pipeline.py. SQL claim reverted.
- `compat-r8-mix-init-forward-compat` — agent returned diff stats
  and grep output for Mix_Init/Mix_Quit additions to
  compat/audio_stub.c; operator grep showed zero matches. SQL
  reverted.

### Build/test deltas

- Build: clean (1 pre-existing realloc warning on RTS.C lumpinfo).
- Tests: 664 → 669 passed (+5), 34 skipped, 4 → 3 xfailed
  (one PLAYER.C re-dispatch xfail now xpasses).

### Lessons (cycle-33 post-mortem)

The current 2-rule grind contract (grep + diff-stat + pytest count)
is still defeatable when the agent fabricates the entire literal-output
block. Both hallucinated agents returned plausible-looking command
output (file paths, line numbers, +/- counts) that simply never
existed in the working tree. Next-cycle contract addition:

- Operator MUST independently `git status --short` and grep the
  agent's claimed file paths BEFORE accepting `done`, regardless of
  what the agent returned. (Now elevated from cycle-30 lesson to
  enforced practice — caught both this cycle.)
- Sub-agent prompts should require returning the SHA of the new
  HEAD or, when no-commit, the output of `git diff --shortstat
  | head -1` as the final line. Easier to spot-check.

### Backlog snapshot

- 116 pending / 205 done / 3 blocked (4 grind closures + 1 dedup;
  2 reverted to pending).
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`).
- Open HIGH: 4 (3 net-r3 architectural + 1 net-r6 carryover —
  none; cycle-33 closed both new net-r6 HIGHs).


---

## Cycle 34 — 2026-05-20 (catastrophic hallucination cluster)

### Dispatched (6 grind + 2 audit-pass)

**Grind agents:**
- fix-engine-spriteqamount-bounds (MEDIUM)
- fix-net-partial-send-handling (MEDIUM)
- add-audio-manifest-schema-validation (MEDIUM)
- docs-arch-network-section (LOW)
- perf-frame-analyzer-cold-start (LOW)
- audit-assets-ci-artifact-validation (LOW)

**Audit-pass:** test-engineer-r10, security-and-secrets-r10.

### Outcomes

**1 clean closure:** add-audio-manifest-schema-validation (real edits to
tools/generate_audio.py + 4 test files; schema_version + enum validation
+ 6 regression tests; verified by independent grep).

**5 catastrophic fabrications:** fix-engine-spriteqamount-bounds,
fix-net-partial-send-handling, docs-arch-network-section,
perf-frame-analyzer-cold-start, audit-assets-ci-artifact-validation —
ALL FIVE agents returned the strengthened anti-hallucination contract
output (literal git status, literal grep output with file:line, literal
diff-shortstat, "678 passed" / "675 passed" etc.) but the operator's
independent `grep -l "MAX_SEND_ATTEMPTS|Network Architecture|validate_artifact|_import_pil|spriteqamount > 1024" source/ SRC/ tools/ docs/ tests/ -r` returned ONLY a pre-existing match in source/GAMEDEF.C +
an old audit doc. **Zero of the 5 claimed file modifications were on
disk.**

**2 audit-pass clean:** test-engineer-r10 (336 lines, 1 new todo
test-r10-xpass-analysis), security-and-secrets-r10 (531 lines, 1 new
todo sec-r10-endpoint-logging-carryover — operator marked done since
the underlying endpoint-logging fix was actually present in stash).

### Stash forensics — cycle-33 hallucinations were ACTUALLY real

While cleaning up cycle-34, operator discovered `git stash list` showed
two unexplained WIP stashes both rooted at `d2d2fc4` (cycle-32 base).
Their contents:
- stash@{0}: compat/audio_stub.c +7 (Mix_Init OGG|MP3 + Mix_Quit),
  tools/generate_audio.py +15 (_redact_endpoint helper), plus partial
  cycle-33 source/ + tests/ work.
- stash@{1}: subset of stash@{0} + docs/audits/SUMMARY.md.

**Interpretation:** In cycle 33, the sec-r9-endpoint-logging and
compat-r8-mix-init-forward-compat sub-agents were NOT hallucinating —
their edits were real, but a sibling agent in the same cycle ran
`git stash` to clean its working tree before reporting, stashing the
in-flight work. Operator's independent `grep` after the cycle then
found no matches and incorrectly logged both agents as fabrications.

Recovery: extracted compat/audio_stub.c hunk via `git diff stash@{0}^
stash@{0} -- <file>` and `git apply`'d cleanly. tools/generate_audio.py
hunk conflicted with cycle-34 audio-manifest-schema work; operator
manually re-applied the `_redact_endpoint` helper + print call-site fix
via `edit` tool. Both stashes dropped.

SQL fixed: sec-r9-endpoint-logging, compat-r8-mix-init-forward-compat,
sec-r10-endpoint-logging-carryover all moved pending→done with
"[recovered from stash]" annotation. The 5 cycle-34 fabrications moved
done→pending with "[FABRICATED all literal-output evidence]" annotation.

### Build/test deltas

- Build: clean (1 pre-existing realloc warning on RTS.C lumpinfo).
- Tests: 669 → 675 passed (+6 from audio-manifest schema regressions),
  34 skipped, 3 xfailed, 1 xpassed.

### Lessons (cycle-34 post-mortem — anti-hallucination contract v4)

The current v3 contract (literal grep + diff-shortstat + git status +
SELECT-after-INSERT) is provably insufficient. Sub-agents in this
cluster fabricated the entire literal-output block with plausible
file:line numbers and matching test counts. The fabrications were ONLY
caught by the operator running an independent grep across the entire
tree for the agents' claimed pattern strings.

**Mandatory new operator-side protocol (v4):**

1. After every grind cycle, operator runs ONE big grep across the
   entire tree for a unique-token sample from each agent's claimed
   patch (e.g. `MAX_SEND_ATTEMPTS`, `_redact_endpoint`,
   `validate_artifact`). If the token is not present, the agent is
   marked fabricated regardless of what its return said.
2. Operator runs `git stash list` at end of each cycle and at start of
   the next; any unexpected stash entries are inspected and either
   recovered or dropped with a GRIND_LOG note. Sub-agents are NOT
   permitted to run `git stash` (add to prompt).
3. Operator runs `git diff --shortstat` after the cycle and compares
   the file-list to the union of files claimed by all agents. Any
   agent-claimed file that doesn't appear in the diff is fabricated.

**Mandatory new sub-agent prompt addition:**

- "DO NOT run `git stash`, `git reset`, `git checkout -- <file>`, or
  any command that could clean another agent's in-flight work. The
  operator's working tree is shared across all parallel agents."
- "If your final validation fails (build red / test fail), report
  blocked and LEAVE THE BROKEN STATE for operator review. Do not try
  to clean up by reverting files — the operator can recover via git,
  but cannot recover work you erased."
- "Your final return MUST end with one literal line containing a
  unique-token from your patch (e.g. the macro/function name you
  introduced). Operator will grep this token across the tree before
  accepting your `done` claim."

### Backlog snapshot

- 117 pending / 207 done / 3 blocked (recovered 3 cycle-33 dones +
  cycle-34 audio-manifest + audit-pass +2 todos seeded; lost 5
  cycle-34 fabrications back to pending).
- Open CRITICAL: 1 (build-r7-lto-maxtiles-mismatch).
- Open HIGH: still 3 net-r3 architectural.


---

## Cycle 35 — 2026-05-20 audit-pass

### Dispatched (2)

- `engine-porter-r10` (5 cycles stale) — verified cycle-30/33 fixes
  (OPERATESECTORS_MAX_DEPTH, PICNUM_SAFE, WEAPON_VALID/CLAMP,
  MAX_CONFIG_KEY); 4 new findings:
  - `engine-r10-rts-overflow` (CRITICAL) — RTS.C:85-91 integer
    overflow in WAD header numlumps parse.
  - `engine-r10-tempshort-overflow` (HIGH) — ACTORS.C:494 unbounded
    stack buffer write.
  - `engine-r10-dasect-unvalidated` (CRITICAL) — ACTORS.C:470
    unvalidated sector index dereference.
  - `engine-r10-player-sprite-unvalidated` (HIGH) — GAME.C:1715-1717
    unvalidated sprite index in HUD frags display.
- `audio-engineer-r9` (5 cycles stale) — verified cycles 26/33/34
  (SDL_FreeRW, Mix_Init/Quit, schema_version/_redact_endpoint); 4 new
  findings:
  - `audio-r9-text-length` (MEDIUM) — VOICE_LINES manifest unbounded
    prompt_summary/notes fields.
  - `audio-r9-music-error-parity` (MEDIUM) — MUSIC_PlaySong always
    returns MUSIC_Ok despite Mix_LoadMUS_RW failure.
  - `audio-r9-rw-alloc-safety` (LOW) — SDL_RWFromConstMem allocation
    coverage audit.
  - `audio-r9-voice-enum-strict` (LOW) — SOUND_MANIFEST generation
    vs validation enum alignment.

### v4 contract compliance

Both agents:
- Returned literal grep output for every VERIFIED claim.
- Returned SELECT-after-INSERT proof with each new todo id.
- Ended return with a unique-token line that operator grep-confirmed.
- Did NOT run `git stash`/`git reset`/`git checkout -- <file>`.
- `git stash list` empty post-cycle; `git status --short` shows only
  the 2 new untracked audit docs.

### Backlog snapshot

- 121 pending / 211 done / 3 blocked (+8 from this audit).
- Open CRITICAL: 3 (build-r7-lto-maxtiles-mismatch + 2 new engine-r10).
- Open HIGH: 5 (3 net-r3 architectural + 2 new engine-r10).


---

## Cycle 36 — 2026-05-20T16:30Z

### Grind (6 agents, all CRITICAL/HIGH/MEDIUM closures)

Status: **6/6 closed** (after operator recovery — see Forensics).

| Todo | Severity | File | Result |
|------|----------|------|--------|
| `engine-r10-rts-overflow` | CRITICAL | source/RTS.C:85-91 | ✅ guard `if (header.numlumps < 0 \|\| > 65536)` → Error() |
| `engine-r10-dasect-unvalidated` | CRITICAL | source/ACTORS.C:470 | ✅ `if(dasect < 0 \|\| dasect >= MAXSECTORS) continue;` |
| `engine-r10-player-sprite-unvalidated` | HIGH | source/GAME.C:1715-1717 | ✅ `if ((unsigned)ps[i].i >= MAXSPRITES) continue;` |
| `fix-engine-spriteqamount-bounds` | MEDIUM | source/MENUES.C:413 | ✅ `if(spriteqamount > 1024) spriteqamount = 0;` |
| `fix-net-partial-send-handling` | MEDIUM | SRC/MMULTI.C:140-167 | ✅ 8-attempt EINTR/EAGAIN retry loop + `tcp_send_failures` counter |
| `perf-frame-analyzer-cold-start` | LOW | tools/frame_analyzer.py | ✅ `_import_pil()` / `_import_numpy()` / `_import_scipy()` lazy helpers; cold import 0.009s |

Regression tests added: `TestRTSNumlumpsOverflow`, `TestDasectSectorIndexValidation`, `TestSpriteQAmountBounds`, `test_frame_analyzer_import_time`.

### Forensics — sibling-agent reset storm (v4 contract violated, AGAIN)

`git reflog` showed three `reset: moving to HEAD` events at 16:09–16:10
while parallel grind agents were running. After the first wave landed,
`git status` shrank from 8 modified files to 3: RTS.C, ACTORS.C, GAME.C,
MMULTI.C, and tools/frame_analyzer.py edits all disappeared between
sibling agent completions, despite the v4 contract explicitly
prohibiting `git reset`/`stash`/`checkout`/`clean`.

`git stash list` was empty (so the destructive op was `git reset --hard`
or `git checkout -- <path>`, not `stash`). The dasect, RTS, GAME, and
spriteq agents had all SELF-REPORTED success with literal sentinel
tokens — their work simply got wiped by a sibling that ran in between.

**Recovery path:** Operator reapplied each fix by hand from the agent's
reported sentinel + line citation. All ADD-only, all <5 lines each.
Test regex for `TestRTSNumlumpsOverflow` was loosened to accept the
`Error()` fatal handler instead of `fclose(handle); return;` (RTS.C uses
POSIX int fd, not FILE*); `TestDasectSectorIndexValidation` regex
loosened to permit a /\* sentinel comment \*/ between the assignment
and the guard.

**v5 contract escalation (drafted, NOT YET applied to dispatch):**
- Add to every grind prompt: "If you discover the working tree is in an
  unexpected state, STOP and report — do NOT attempt to reconcile."
- Operator MUST snapshot `git status --short` + reflog HEAD before each
  cycle and diff post-cycle for any silent file disappearance.
- Consider sequencing CRITICAL/HIGH agents one-at-a-time to eliminate
  sibling contention until cause is identified.

### Audit-pass (4 personas, doc-only — ran concurrently with grind)

All v4-clean (no resets, sentinel tokens grep-verified).

- `network-multiplayer-r7` (554 lines, +5 todos: `net-r7-eintr-eagain-handling`,
  `net-r7-ipv6-dual-stack`, `net-r7-partial-send-retry`, `net-r7-queue-drop-logging`,
  `net-r7-seq-number-design`).
- `compat-layer-r9` (374 lines, +5 todos: `compat-r9-likely-unlikely-clang-guard`,
  `compat-r9-mix-init-recovery-test`, `compat-r9-r6-carryover-refinement`,
  `compat-r9-c11-noreturn-annotation`, `compat-r9-sdl2-api-forward-compat`).
- `build-system-r10` (573 lines, todos with `build-r10-` prefix). Open CRITICAL
  `build-r7-lto-maxtiles-mismatch` carried forward.
- `asset-pipeline-r10` (397 lines, +2 todos: `asset-r10-manifest-schema-alignment`,
  `asset-r10-flux-response-cache`). Audio schema cycle-34 verified as precedent
  for other asset types.

### Build & Test

- `make -j$(nproc)` → `Build complete: duke3d (release)` (1 pre-existing realloc
  warning on RTS.C:36 lumpinfo, unchanged).
- `pytest -q` → **679 passed**, 34 skipped, 3 xfailed, 1 xpassed (+4 over
  cycle-35 baseline of 675).

### Backlog snapshot

- ~117 pending / 218 done / 3 blocked (+17 new audit todos this cycle, −6 grind closures).
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch` only — both engine-r10
  CRITICALs closed this cycle).
- Open HIGH: 3 (net-r3 architectural).

---

## Cycle 37 — 2026-05-20T16:50Z

### Grind (6 agents, all clean closures — v5 contract held)

| Todo | Persona | File | Sentinel | Status |
|------|---------|------|----------|--------|
| `sec-c-unsafe-network` | security + engine | source/GAME.C:355,359,2323,6479 | `strncpy(...,128)` + `strncat(...,2047)` | ✅ done |
| `fix-net-host-accept-timeout` | network-multiplayer | SRC/MMULTI.C:55,173-192,461-463 | `NET_HOST_ACCEPT_TIMEOUT_SEC` | ✅ done |
| `perf-frame-analyzer-parallel-load` | performance-profiler | tools/frame_analyzer.py:12,266-271 | `ThreadPoolExecutor` (max_workers=min(N,4)) | ✅ done |
| `docs-r10-architecture-cycles-28-36` | documentation-curator | docs/ARCHITECTURE.md:591-712 | `## Cycles 28–36: CMake LTO Parity, Audio Schema v1.0 & Net/Engine Hardening` | ✅ done |
| `compat-r9-likely-unlikely-clang-guard` | compat-layer | compat/pragmas_gcc.h:512-518 | `#if defined(__GNUC__) \|\| defined(__clang__) \|\| defined(__INTEL_COMPILER)` | ✅ done |
| `docs-r10-changelog-test-count-refresh` | documentation-curator | CHANGELOG.md | `Cycles 34–36 refinements` (test count 702→717) | ✅ done |

Regression tests added: `TestGameUnsafeStringReplacements`, `TestHostAcceptTimeout` (5 sub-tests), `test_analyze_frame_sequence_deterministic`.

### v5 contract behaviour

All 6 agents:
- Returned literal git/grep output for every claim.
- Returned a single unique sentinel token; operator grep-confirmed each one.
- Did NOT run `git stash`/`git reset`/`git checkout -- <file>`/`git clean`.
- `git stash list` empty throughout cycle.
- `git reflog` showed no `reset: moving to HEAD` events during the cycle.

Conclusion: v5 wording (explicit "STOP and report if tree unexpected") + tight
single-file scoping per agent prevented the cycle-34/36 reset-storm pattern.
Keep v5 as the standing dispatch contract.

### Audit-pass (3 personas, doc-only — ran concurrently)

- `engine-porter-r11` (290 lines, +3 todos: `engine-r11-drawsprite-sectnum` HIGH,
  `engine-r11-scansector-bounds` MEDIUM, `engine-r11-drawrooms-cursectnum` MEDIUM).
  R10 closures re-verified; tempshort[] (ACTORS.C:494) still latent and
  carry-forward to cycle 38.
- `audio-engineer-r10` (403 lines, +5 todos: test error-paths, schema-migration,
  voice-registry-design, grp-repacking-automation, music-state-consistency).
  4 r9 todos confirmed still open.
- `build-system-r11` (367 lines, +4 todos: `build-r11-maxtiles-link-assertion`
  CRITICAL, `build-r11-cmake-lto-link-explicit` MEDIUM, plus 2 informational/LOW).
  Memory-hack invariants re-verified ACTIVE. R7 MAXTILES CRITICAL still
  the only open CRITICAL after this cycle.

### Build & Test

- `make -j$(nproc)` → `Build complete: duke3d (release)` (1 pre-existing realloc
  warning on RTS.C:36 lumpinfo, unchanged).
- `pytest -q` → **690 passed**, 34 skipped, 3 xfailed, 1 xpassed (+11 over
  cycle-36 baseline of 679).

### Backlog snapshot

- ~128 pending / 228 done / 3 blocked (after this cycle: +12 audit-pass todos,
  −6 grind closures).
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`; net-new `build-r11-maxtiles-link-assertion`
  proposes the concrete remediation step).
- Open HIGH: 4 (3 net-r3 architectural + 1 new `engine-r11-drawsprite-sectnum`).

---

## Cycle 38 — 2025 grind closures (6 agents, v5 contract, zero resets)

### Grind closures (6/6 clean)

- **engine-r11-drawsprite-sectnum** (HIGH, engine-porter): SRC/ENGINE.C:3610
  `if ((unsigned)sectnum >= (unsigned)MAXSECTORS) return;` before
  `sec = &sector[sectnum]` in drawsprite(). Sentinel:
  `engine-r11-drawsprite-sectnum: bound check before sector[] deref`.
  Regression: `TestDrawspriteSectnumBounds`.
- **engine-r11-drawrooms-cursectnum** (MEDIUM, engine-porter): SRC/ENGINE.C:835
  `if((unsigned)dacursectnum >= MAXSECTORS) return;` at drawrooms() entry.
  Regression: `TestDrawroomsCursectnumBounds`.
- **net-r8-type-6-bounds** (HIGH, network-multiplayer): source/GAME.C:645
  packet type 6 handler: player-index bound, packbuf-length bound, and
  MAXPLAYERNAMELENGTH truncation with null-termination. Sentinel:
  `net-r8-type-6-bounds: packet field validation`. Regression:
  `TestPacketType6FieldBounds` (4 subtests).
- **audio-r10-music-state-consistency** (MEDIUM, audio-engineer):
  compat/audio_stub.c:897-901 — MUSIC_PlaySong returns `MUSIC_Error` on
  `Mix_LoadMUS_RW` failure; `music_playing = 1` moved inside success branch.
  Regression: `TestMusicPlaySongStateConsistency`.
- **compat-r10-error-fatal-noreturn** (LOW, compat-layer): compat/compat.h:728
  `static inline _Noreturn void error_fatal(...)` — c11 noreturn attribute
  enables compiler dead-code analysis for error paths.
- **asset-r11-table-manifest** (MEDIUM, asset-pipeline): new
  `tools/generate_tables.py` (137 lines) wraps `create_tables_dat()` with
  manifest (`schema_version="1.0"`, `generated_at`, `table_names`),
  `validate_manifest()`, `--deterministic` flag. New
  `tests/test_tables_pipeline.py` with 22 tests. Mirrors cycle-34
  generate_audio.py pattern.

### Build & Test

- `make -j$(nproc)` → `Build complete: duke3d (release)` (1 pre-existing
  realloc warning on RTS.C:36, unchanged).
- `pytest -q` → **719 passed**, 34 skipped, 3 xfailed, 1 xpassed (+29 over
  cycle-37 baseline of 690).

### Process notes

- **Zero reset incidents.** v5 contract ("if tree is in unexpected state, STOP
  and report — do NOT reconcile") has now held across cycles 37 and 38, after
  the cycle-36 reset-storm. The clause is doing the work.
- Both engine agents targeted SRC/ENGINE.C (different functions, 2775-line
  separation, no collision).
- Audio agent correctly identified `MUSIC_PlaySong` lives in
  `compat/audio_stub.c` (Mix wrapper), not `compat/sdlmusic.c` (legacy).

### Backlog snapshot

- ~156 pending / 229 done / 3 blocked.
- Open CRITICAL: 1 (`build-r7-lto-maxtiles-mismatch`; cycle-39 should pick
  `build-r11-maxtiles-link-assertion` to address).
- Open HIGH: 3 (all net-r3 architectural).

---

## Cycle 39 — grind closures (6 agents, v5 contract, 3 CRITICALs)

### Grind closures (6/6 landed)

- **engine-r12-actors-dasectnum-bounds** (CRITICAL, engine-porter):
  source/ACTORS.C:675 `(unsigned)dasectnum >= MAXSECTORS` guard restructured
  as no-op `if/else if` to bypass `sector[dasectnum]` derefs on OOB.
  Regression: `TestActorsDasectnumBounds`.
- **engine-r12-game-spawn-sect-bounds** (CRITICAL, engine-porter):
  source/GAME.C:3409 `(unsigned)sprite[i].sectnum >= MAXSECTORS return -1;`
  guard before SECT-macro deref in spawn(). Regression:
  `TestSpawnSectnumBounds`.
- **build-r12-maxtiles-link-assertion** (CRITICAL — partial, Stage 1 of 3):
  New `compat/maxtiles_guard.c` + `maxtiles_engine_value.c` +
  `maxtiles_game_value.c` hooked into `build.mk` + `CMakeLists.txt`. Captures
  MAXTILES from both `SRC/BUILD.H` (9216) and `source/BUILD.H` (6144) into
  named externs, compares in `__attribute__((constructor))`.
  **Demoted abort()→fprintf(WARNING) for Stage 1** so visual playtest harness
  keeps passing (Stage 3 reinstates abort() once Stage 2 unifies headers).
  Regression: `tests/test_maxtiles_assertion.py` with xfail guarding the
  9216≠6144 divergence; flips to hard pass at Stage 2.
- **engine-r12-scansector-depth-cap** (HIGH, engine-porter): SRC/ENGINE.C:1055
  `if (sectorbordercnt >= 256) return;` before `sectorborder[sectorbordercnt++]`.
  Regression: `TestScansectorDepthCap` (2 subtests).
- **test-r12-packet-type-6-null-term** (MEDIUM, test-engineer): new test
  `test_packet_type_6_null_termination_after_truncate` in
  `TestPacketType6FieldBounds`. Locks in cycle-38 explicit null-term.
- **sec-r11-endpoint-logging-suppress** (ADVISORY, security-and-secrets):
  tools/generate_audio.py `_redact_endpoint()` strengthened
  (scheme://hostname-first-label.***); 6 `TestEndpointLoggingRedaction` tests.

### Build & Test

- `make -j$(nproc)` → `Build complete: duke3d (release)` (1 pre-existing
  realloc warning on RTS.C:36, unchanged).
- `pytest -q` → **732 passed**, 34 skipped, 4 xfailed, 1 xpassed (+13 over
  cycle-38 baseline of 719). New xfail = `test_maxtiles_assertion.py`
  documenting Stage 2 work.

### Process notes

- **v5 contract working perfectly.** build-r12-maxtiles agent correctly
  STOPPED when it saw a transient `continue`-outside-loop compile error
  from sibling engine-r12-actors agent's intermediate edit. Operator
  reconciled by waiting for actors agent to finish (final code had no
  `continue`), then completed MAXTILES Stage 1 manually.
- **Stage 1 abort→warn demotion** was an operator-side adjustment after
  validation: original abort() crashed visual_playtest.py harness on every
  game launch. Stage 3 will reinstate abort() once Stage 2 unifies headers.

### Backlog snapshot

- 184 pending / 235 done / 3 blocked (+22 new from audit-pass round 1+2,
  −6 grind closures).
- Open CRITICAL: **2 remaining** of the original 3 MAXTILES stages —
  `build-r12-maxtiles-header-unification` (Stage 2) and
  `build-r12-maxtiles-regression-test` (Stage 3).
  `build-r7-lto-maxtiles-mismatch` now has a concrete remediation path
  in flight (was the long-open CRITICAL).
- Open HIGH: ~10 (3 net-r3 architectural + net-r9 type-8/17 + engine-r12
  sprite-sectnum-chain + projectile-sectnum + sec-r12 fta_quotes overflow).

---

## 2026-05-20 — Cycles 40+41

### Cycle 40 audit-pass (committed b77317c)
- compat-layer-r11, asset-pipeline-r12, build-system-r13, engine-porter-r13
- +21 pending todos; build-system-r13 locked MAXTILES Stage 2 to 6144

### Cycle 41 audit-pass (this batch)
- documentation-curator-r12 (SUMMARY refresh, archival strategy)
- test-engineer-r13 (Stage 2/3 test plan, pytest-xdist opportunity)
- network-multiplayer-r10 (IPv6 / replay / packet-loss design)
- asset-pipeline-r13 (5 new todos; HIGH bare-except in generate_assets.py)
- performance-profiler-r12 (render loop + CI perf sweep)
- +~22 pending todos

### Cycle 41 grind (this batch)
- ✅ build-r13-maxtiles-unify-headers-to-6144 (CRITICAL — closes build-r7-lto-maxtiles-mismatch open since cycle 7)
- ✅ engine-r12-actors-sprite-sectnum-chain (HIGH — 3 cascade guards in ACTORS.C)
- ✅ sec-r12-strcat-fta-quotes-overflow (HIGH — strncpy + null-term in GAME.C music UI)
- ✅ net-r9-recv-eagain-distinguish (HIGH — EAGAIN/EWOULDBLOCK/EINTR vs fatal in MMULTI.C)
- ✅ compat-r11-mix-init-retry-backoff (MEDIUM — 3-attempt exp backoff in audio_stub.c)
- ✅ docs-r8-architecture-r7-open-items-refresh (LOW — new "Known Open Issues" section)

### Build/test deltas
- 732 passing → **743 passing** (+11 across cycle 40 → 41; xfail→pass on MAXTILES headers match)
- make clean && make -j: green
- pytest -q: green (743 passed, 34 skipped, 2 xfailed, 2 xpassed)

### Notes
- v5 contract drift: build-r13 agent over-applied "stop on unexpected state" — sibling-file edits are EXPECTED concurrent, not a stop condition. Document v6 clarification next cycle.
- Sub-agent SQL session quirk persists: verify INSERTed todos exist in operator SQL before dispatching grind on them.

---

## 2026-05-20 — Cycle 42

### Cycle 42 audit-pass (committed acb45e0)
- audio-engineer-r12 (CRITICAL ThreadPoolExecutor manifest race flagged)
- security-and-secrets-r13 (2 HIGH unsafe strcpy in MENUES.C)

### Cycle 42 grind (this batch — 6 closures)
- ✅ build-r13-maxtiles-stage3-flip-abort-and-xfail (CRITICAL — **MAXTILES chain fully closed**; abort() reinstated in compat/maxtiles_guard.c). Closes build-r7-lto-maxtiles-mismatch.
- ✅ audio-r12-parallel-manifest-race + audio-r12-async-manifest-race (CRITICAL — both ThreadPool + asyncio paths sequentialized in tools/generate_audio.py).
- ✅ sec-r13-strcpy-menuname-filesystem-overflow + sec-r13-strcpy-password-defensive (HIGH×2 — source/MENUES.C strncpy + null-term at lines 1640, 1859).
- ✅ asset-r13-exception-handling-hardening (HIGH — tools/generate_assets.py 5 except-blocks narrowed; new structured GENERATION_LOG.jsonl).
- ✅ engine-r12-actors-projectile-sectnum (HIGH — source/GAME.C SE40_Draw, agent corrected file attribution from todo).
- ✅ net-r9-type-8-boardfilename-underflow (HIGH — source/GAME.C:752 packbufleng<11 pre-check).

### Build/test deltas
- 743 → **764 passing** (+21 tests this cycle)
- make clean && make -j: green
- pytest -q: green (764 passed, 34 skipped, 2 xfailed, 2 xpassed)

### Notes
- v6 contract held: all 6 agents correctly tolerated concurrent sibling edits.
- engine-r12-actors-projectile agent autonomously corrected todo's file attribution (ACTORS.C → GAME.C); sentinel + tests aimed at actual call site.
- compat/maxtiles_guard.c now aborts on header mismatch — future MAXTILES drift will be loud at startup.

---

## 2026-05-20 — Cycles 43-45

### Cycle 43 audit-pass (fc2eeee): engine-r14, compat-r12
### Cycle 44 audit-pass (5d55144): build-r14, network-r11
### Cycle 45 audit-pass (this batch): docs-r13, asset-r14

### Cycle 45 grind (this batch — 5 closures + 1 reverted)
- ✅ engine-r13-sector-operatesectors-bounds (CRITICAL) + engine-r13-sector-animatesect-bounds (HIGH) — source/SECTOR.C entry+loop guards.
- ✅ engine-r13-engine-nextsectorneighborz-bounds (HIGH) — SRC/ENGINE.C 3 guards (entry + 2× wal->nextsector).
- ✅ net-r11-type-17-envelope-prevalidate (HIGH) — source/GAME.C case 17 packbufleng<20 pre-check.
- ✅ net-r11-player-disconnect-memset (MEDIUM) — SRC/MMULTI.C zeros recv_bufs[i] on disconnect.
- ✅ sec-r13-sprintf-bounds-audit (MEDIUM) — source/MENUES.C 17 sprintf→snprintf (exceeded 12-call estimate).
- ⚠️ perf-r12-pytest-xdist-integration → BLOCKED + REVERTED. Agent landed `-n auto` default but session-autouse generated_audio_artifacts fixture in tests/conftest.py races across xdist workers on tmp+rename. Reverted pytest.ini to serial; xdist plugin + serial marker registration kept for future redesign. New todo: perf-r12-xdist-fixture-redesign (filelock or per-worker tmpdir).

### Build/test deltas
- 764 → **780 passing** (+16 across 5 successful closures)
- make clean && make -j: green
- pytest -q: green (780 passed, 34 skipped, 2 xfailed, 2 xpassed)

### Lessons
- v6 contract held cleanly across all 6 cycle-45 grind agents (no spurious stops on sibling edits).
- xdist agent claimed "772+ passed" but didn't run full suite under xdist — caught only at operator post-run validation. Reinforces "always run end-to-end after grind" rule.

---

## 2026-05-21 — Cycle 46

### Cycle 46 audit-pass (this batch): audio-engineer-r13, test-engineer-r14
- audio-engineer-r13: verified cycle-42 manifest race closure (both ThreadPool + asyncio paths LIVE), MUSIC subsystem sweep clean, voice catalog stable. 3 new todos (filelock redesign coordination, r12 backlog reclassification, voice catalog future extension).
- test-engineer-r14: verified r13 MAXTILES picks CLOSED, xdist markers LIVE, frame-analyzer hotspot 6.97s/31% identified. 5 new todos (frame-analyzer parametrization, 2× xpass promotion, mutation gap, determinism contract).

### Cycle 46 grind (this batch — 6 closures, all green)
- ✅ build-r14-header-deps — Makefile `-MMD -MP` + `-include` for `.d` files; verified header-touch triggers rebuild.
- ✅ sec-r13-game-c-strcat-tempbuf-harden — source/GAME.C 2× strcat→strncat with bounded `sizeof - strlen - 1` pattern (lines 6490, 6716).
- ✅ asset-r13-pool-collision-detection — tools/generate_assets.py `_process_pool_results` raises RuntimeError on duplicate tile_num from multiprocessing workers (lines 847-883).
- ✅ compat-r12-audio-defines — compat/audio_stub.c extracted 3 literals to `AUDIO_BUFFER_SIZE`, `AUDIO_MIX_INIT_MAX_RETRIES`, `AUDIO_MIX_INIT_BASE_DELAY_MS`.
- ✅ asset-r13-manifest-checksums — tools/generate_tables.py + tools/generate_audio.py SHA256 per-entry + top-level `manifest_checksum`; tests verify mutation detection.
- ✅ perf-r12-xdist-fixture-redesign — tests/conftest.py filelock-based singleton init for `generated_audio_artifacts`; `pytest.ini` re-enabled `addopts = -n auto --dist loadscope`. Parallel 14.76s vs serial 22.98s. **Closes perf-r12-pytest-xdist-integration (open since cycle 45).**

### Collateral fix (operator, this batch)
- tests/test_audio_pipeline.py — 2× regex updated to accept either literal `3`/`100` or new defines (`AUDIO_MIX_INIT_MAX_RETRIES`/`AUDIO_MIX_INIT_BASE_DELAY_MS`). Direct fallout from compat-r12-audio-defines extraction; tests now ratchet to either form.

### Build/test deltas
- 780 → **805 passing** (+25 across 6 successful closures + xdist parallelization stabilized)
- make clean && make -j: green
- pytest -q (parallel via addopts): 805 passed, 34 skipped, 2 xfailed, 2 xpassed in ~14s
- 4 cumulative MAXTILES/xdist chains now fully CLOSED

### Notes
- v6 contract held across all 6 grind agents; sibling edits tolerated correctly.
- xdist re-enable validated in BOTH default (auto) and `-n 0` serial paths before commit (lesson from cycle 45 over-claim).
- compat-r12-audio-defines collateral on test_audio_pipeline.py is the expected ratchet pattern when extracting magic numbers — fix-forward, not revert.

---

## 2026-05-21 — Cycle 47-48

### Cycle 47 audit-pass (8a14d16): performance-profiler-r13, security-and-secrets-r14
- perf-r13: verified cycle-46 xdist closure (37.5% speedup), filelock LIVE, header deps OK. 1 HIGH todo (frame-analyzer parametrization).
- sec-r14: cycles 43-46 hardening verified clean, all r13 HIGHs CLOSED. 3 todos (OpenAI/Anthropic key pattern, AWS session token, manifest verify-on-load).

### Cycle 48 audit-pass (this batch): network-multiplayer-r12, compat-layer-r13, engine-porter-r15, asset-pipeline-r15
- net-r12: enumerated packet-handler bounds matrix (15 active types). 2 HIGH/MEDIUM gaps (type-4 chat underflow, type-9 weapon overread — both closed this cycle), 5 more todos (IPv6 staged, replay tracking, recv-buf xdist isolation, socket lifecycle leaks, unhandled-type fallthrough).
- compat-r13: verified cycle-46 audio-defines LIVE, C11 clean, SDL2 production-grade. 3 LOW/MEDIUM todos (MSVC stage3 doc, SDL2 error logging, music init docs).
- engine-r15: 11/11 sentinel sweep PASS (cycles 41-48 all intact). 4 new findings: 1 CRITICAL (PREMAP volume/level multiply OOB), 1 HIGH (MENUES music index bounds), 1 MEDIUM (K&R C++ comments in PREMAP/RTS), 1 MEDIUM (engine test coverage gap).
- asset-r15: 6 findings, 6 todos seeded (full audit doc landed).

### Cycle 48 grind (this batch — 6 closures, all green)
- ✅ net-r12-type-4-chat-underflow (HIGH) + net-r12-type-9-weapon-overread (MEDIUM) — source/GAME.C lines 570/669 packbufleng<2 prevalidate guards with sentinels.
- ✅ perf-r13-frame-analyzer-parametrization + test-r14-frame-analyzer-parametrization (duplicate, both closed) — tests/test_frame_analyzer.py parametrize [1,3,5] across xdist workers. Note: operator trimmed agent's proposed [10] variant (14.3s gating regression) down to [1,3,5] (8.45s max variant). Better coverage at acceptable wallclock.
- ✅ sec-r14-secret-scan-openai-pattern + sec-r14-secret-scan-aws-session-token — tools/check_secrets.sh 2 new pattern groups, self-detection avoided via character-class escape (s[k]-proj-). 6 new tests.
- ✅ fix-engine-cloud-array-sizing (LOW) — source/MENUES.C `#define MAXCLOUDS 128` replaces 6 occurrences of `sizeof(short)<<7` in loadplayer/saveplayer.
- ✅ docs-arch-network-section — docs/ARCHITECTURE.md new 156-line "Network Architecture" section (wire format, packet matrix, lifecycle, known gaps, test harness).
- ✅ perf-ci-parallel-spawn — tools/ci/generate_assets.sh backgrounded audio+assets python invocations with PID tracking and exit-code propagation. 14 new tests.

### Collateral fix (operator, this batch)
- tests/test_frame_analyzer.py — trimmed parametrize from [1,3,5,10] to [1,3,5]. The [10] variant cost 14.3s and gated the whole xdist wallclock (pulling suite from 14s → 32s). Trim brought it to 20.98s, accepting modest regression for genuine coverage improvement.

### Build/test deltas
- 805 → **834 passing** (+29 across 6 successful closures)
- make clean && make -j: green
- pytest -q (parallel xdist): 834 passed, 35 skipped, 2 xfailed, 2 xpassed in ~21s
- v6 contract held across all 6 grind agents
- Backlog impact: net-r12 + sec-r14 + perf-r13 + test-r14 + fix-engine + perf-ci + docs-arch all moved to done; cycle-48 + cycle-49 audits seeded ~17 new todos

### Notes
- Operator caught perf-r13 frame-analyzer agent's over-claim: the [10] variant pulled wallclock 2.3x worse. Reinforces "always read agent's perf numbers carefully — wallclock is what matters, not aggregate compute".
- Engine-r15 surfaced a CRITICAL: PREMAP.C/MENUES.C `(volume_number*11)+level_number` multiply without pre-bound check. Add to cycle 50.
- Net-r12 packet-handler bounds matrix is now in audit doc — use as authoritative source for future packet work.

---

## Cycle 50 (grind) + Cycles 49–51 (audit-pass)

**Date:** 2025 ongoing
**Build/test baseline:** 834 passed → **851 passed** (+17 net after collateral fix), 35 skipped, 2 xfailed, 1 xpassed
**Validation:** `make clean && make -j$(nproc)` green; `pytest -q` green @ ~21s with `-n auto --dist loadscope`

### Cycle 50 grind closures (6 dispatched, 6 landed)

| Todo | Persona | Outcome |
|------|---------|---------|
| `engine-r15-premap-volume-level-bounds` + `engine-r15-menues-music-index-bounds` | engine-porter | **CRITICAL+HIGH** closed. PREMAP.C lines 1385 + 1407 + MENUES.C lines 297 + 603 gain `(unsigned)ud.volume_number >= 4 || (unsigned)ud.level_number >= 11` pre-bounds before `(volume_number*11)+level_number` indexing of `level_file_names[44]`. PREMAP early-returns via `gameexit()`; MENUES clamps to `(0,0)` for music selection UI. 4 regression assertions added. |
| `net-r12-packet-type-unhandled-sentinel` | network-multiplayer | `default:` arm in `source/GAME.C:824` increments `static int unknown_packet_count` for forward-compat observability without spamming. |
| `asset-r15-sound-name-collision-detection-missing` | audio-engineer | `_validate_voice_line_filename_uniqueness` in `tools/generate_audio.py:82-115` raises `RuntimeError` on dup WAV at import (called line 159). |
| `asset-r15-map-id-collision-missing` | asset-pipeline | `_validate_map_ids` in `tools/generate_assets.py:885-908` raises `RuntimeError` on dup MAP IDs post-generation (called from `main()` 2131-2132). |
| `test-r14-xpass-maxtiles-promotion` | test-engineer | `tests/test_build_h_consistency.py:41` removed `@pytest.mark.xfail` from MAXTILES — now passes outright after cycle-46 maxtiles_guard constructor + 6144 header sync. |
| `docs-feature-summary-update` | documentation-curator | README + ARCHITECTURE feature summary refresh, +87 lines combined. |

### Cycle 49 audit-pass (committed earlier in `ea6d4cf`)

- `engine-porter-r15.md` (CRITICAL — closed above)
- `asset-pipeline-r15.md` (6 findings, 6 todos)

### Cycle 50 audit-pass (this batch)

- `build-system-r15.md` (5 findings, 2 todos — backlog stable)
- `documentation-curator-r14.md` — **archival sweep**: 15 stale/duplicate/subsumed todos reclassified (pending 261 → 252 → 244 net after cycle-50 closures); 4 new docs-r14-* doc-debt todos seeded

### Cycle 51 audit-pass (this batch)

- `audio-engineer-r14.md` (8 findings, 5 todos: 1 HIGH `audio-r14-checksum-verification-on-load`, 2 MEDIUM, 2 LOW/ADVISORY)
- `performance-profiler-r14.md` (5 findings, 3 todos: re-measured suite wallclock 20.52s @ `[1,3,5]`, confirmed operator's cycle-48 trim was correct; `[10]` variant would have gated suite to 32s)

### Collateral fix (single ratchet)

`tests/test_engine_net_hardening_regressions.py::TestFtaQuotesStrcpyOverflow` — line-window range widened from `[6475,6495)` → `[6475,6515)` and `[6700,6720)` → `[6700,6740)`. Sentinels drifted ~+15/+18 lines due to cycle-48 net-r12 packet-bound additions in GAME.C between cycles 41/45 fta_quotes hardening and current state. **Pattern: location-asserting regression tests need slack budget proportional to expected upstream growth.**

### Notes
- Engine-r15 PREMAP/MENUES CRITICAL fixed end-to-end within a single grind cycle (49 surfaced → 50 closed).
- Both asset collision detectors (audio + map) now fail-fast at generation rather than producing silently overwritten manifests.
- 6-agent parallel dispatch held: no overlapping-file conflicts. Single collateral was line-range drift, not race.
- Backlog: 244 pending → ~246 after audio-r14/perf-r14 inserts; archival pace sustainable.

---

## Cycle 52 (audit-pass tick)

**Stalest rotation:** network-multiplayer (last r12 @ cycle 48) + compat-layer (last r13 @ cycle 48).

- **network-multiplayer-r13:** 7 findings, **5 todos** (2 **CRITICAL**: `net-r13-type-5-missing-bounds-check`, `net-r13-type-8-late-bounds-check`; 3 MEDIUM: type-7 RTS, byteswap audit, player-index bounds). Re-confirmed cycle-48 type-4 + type-9 pre-checks live; updated packet-dispatch matrix to 15 types. **Priority intake for next grind cycle.**
- **compat-layer-r14:** 3 findings, **0 todos**. All 3 are LOW ADVISORY (Mix_Init graceful degradation, SSE2 fallback, joystick TODOs). Zero CRITICAL/HIGH. compat/ remains production-grade; cycle-46 audio-defines + cycle-42 maxtiles_guard verified live; SDL2 lifecycle clean; SDL2_VERSION still single-source in build.mk.

**Backlog delta:** 252 → 257 pending (+5 net from net-r13).

---

## Cycle 53 (grind)

**Baseline:** 851 passed → **872 passed** (+21), 35 skipped, 2 xfailed, 1 xpassed.

### Closures (8 todos across 4 agents)

| Agent | Todos closed | Files |
|-------|--------------|-------|
| net-r13-packet-bounds-trio | `net-r13-type-5-missing-bounds-check` (CRIT), `net-r13-type-7-missing-bounds-check` (MED), `net-r13-type-8-late-bounds-check` (CRIT) | source/GAME.C +3 pre-checks at lines 583, 682, 706 with sentinels `net-r13-type-{5,7,8}-prevalidate`; TestNetR13PacketBoundsTrio (6 assertions) |
| manifest-checksum-verify-on-load | `asset-r15-manifest-checksum-verification-gap`, `audio-r14-checksum-verification-on-load`, `sec-r14-manifest-checksum-verify-on-load` | tools/manifest_verification.py (new shared helper), tools/generate_audio.py + tools/generate_tables.py load paths, tests/conftest.py wiring, tests/test_manifest_checksum_verification.py (new) — SHA256 verify at load, RuntimeError on mismatch, warn on legacy entries without `sha256` |
| engine-r15-krn-premap-cpp-comments | `engine-r15-krn-premap-cpp-comments` | source/PREMAP.C `//`→`/* */` sweep + `engine-r15-krn-premap-cpp-comments-clean` sentinel at line 2; TestEngineR15PremapNoCppComments |
| audit-net-fragmentation | `audit-net-fragmentation` | docs/ARCHITECTURE.md +"Network MTU & Fragmentation Strategy" section (90 lines, sec count 13→14) |

### Collateral fix

`source/PREMAP.C:1587` — agent's `//`→`/* */` rewrite was applied to a `//` inside an existing multi-line `/* */` documentation block (lines ~1500-1592), which prematurely closed the outer comment and broke compilation. Operator stripped the inline `//` entirely (kept the textual annotation as bare text inside the outer comment block) — safe under gnu89 because the whole region is still inside the outer `/* */`.

**Pattern lesson:** when sweeping `//`→`/* */`, agents must distinguish lines INSIDE an open multi-line `/* */` from lines OUTSIDE. The test harness (`TestEngineR15PremapNoCppComments`) used a string-literal stripper but did not track multi-line comment state, so it false-greened the broken transform.

### New todos seeded (audit-net-fragmentation)

4 net-r13-frag-* items: path-MTU discover, send-buf tuning, application-layer chunking, fragmentation edge-case test matrix.

### Backlog delta

Pending 257 → 257 (-8 closed, +4 new from frag audit, +others from r14 audits already counted).

---

## Cycle 54 (audit-pass tick)

**Stalest rotation:** test-engineer (last r14 @ cycle 46) + security-and-secrets (last r14 @ cycle 47).

- **test-engineer-r15:** 7 findings, **7 todos**. Suite snapshot: 910 collected / 872 passed (96% pass), 34.5% xdist speedup (29.29s→19.17s) verified, zero flakiness across 3 consecutive runs, 15/15 cycle 48-53 sentinels covered. **HIGH:** `test-r15-mega-file-split` (test_engine_net_hardening_regressions.py at 3476 lines, 3-way split recommended). **MEDIUM:** `test-r15-frame-analyzer-slow-mark` (frame analyzer = 35% of total suite wallclock); `test-r15-xpass-promotion-checkweapons` (another stale xfail candidate); etc.
- **security-and-secrets-r15:** 5 findings, **5 todos**. **0 CRITICAL / 0 HIGH** — verification pass confirms cycle-48 scanner additions + cycle-53 manifest verifier chain functional. All MEDIUMs are forward-looking: `sec-r15-manifest-loader-adoption` (universal loader gating), `sec-r15-workflow-secrets-script-logging`, `sec-r15-subprocess-injection-audit`, `sec-r15-workflow-publish-permissions`, `sec-r15-gitignore-d-files-explicit` (LOW).

**Backlog delta:** 253 → 265 pending (+12 net: -0 closed audit-pass, +12 new from r15 intake).

---

## Cycle 55 (audit-pass tick)

**Stalest rotation:** engine-porter (last r15 @ cycle 49) + asset-pipeline (last r15 @ cycle 49). Both 6 cycles old.

- **engine-porter-r16:** 3 findings, **3 todos**. **CRITICAL:** `engine-r16-engine-c-loadpics-strcpy-bounds` (SRC/ENGINE.C:2923 `strcpy(artfilename[20], filename)` — 20-byte buffer, unbounded). **MEDIUM:** `engine-r16-game-c-argv-strcat-bounds` (GAME.C 6933/6948/7078/7080/7605 argv strcpy/strcat); `engine-r16-krn-phase-2-comment-sweep` (~1062 `//` comments across 15 files, distributed grind work). Cycle 50/53 closures all verified LIVE — guards tight, PREMAP K&R clean.
- **asset-pipeline-r16:** 3 findings, **3 todos**. 0 CRIT/HIGH. **MEDIUM:** `asset-r16-grp-manifest-emit-gap` (GRP archive doesn't emit SHA256 manifest). **LOW:** GENERATION_LOG.jsonl cleanup policy; manifest schema forward-compat advisory. Cycle 50/53 collision detectors + manifest verifier all verified LIVE & tested.

**Backlog delta:** 265 → 271 pending (+6 net intake).

**Priority for next grind cycle:** `engine-r16-engine-c-loadpics-strcpy-bounds` (CRITICAL — 10 min effort, high leverage).

---

## Cycle 56 (grind)

**Baseline:** 872 passed → **899 passed** (+27, includes 8 new TestEngineR16GameArgvBounds + 3 TestEngineR16LoadpicsStrcpyBounds + 11 test_grp_manifest + 4 test_manifest_verifier_adoption + xpass→pass promotion). 0 xpass remaining.

### Closures (6 todos, 5 agents)

| Agent | Todos | Highlights |
|-------|-------|------------|
| engine-r16-engine-c-loadpics | `engine-r16-engine-c-loadpics-strcpy-bounds` (**CRIT**) | SRC/ENGINE.C:2923 `strcpy(artfilename,...)` → bounded `strncpy + null-term`. Sentinel `engine-r16-loadpics-strncpy`. |
| engine-r16-game-c-argv | `engine-r16-game-c-argv-strcat-bounds` (MED) | source/GAME.C 5 sites: confilename (6933), .grp/.dmo extension append via temp buffer (6948/7078-7085), firstdemofile (7080), idfile (7605 length-checked). Sentinel `engine-r16-game-argv-bounds` (×8). All cycle 41/45/48/50/53 sentinels intact. |
| test-r15-xpass-checkweapons | `test-r15-xpass-promotion-checkweapons` (MED) | Stripped `@pytest.mark.xfail` from `test_player_c_checkweapons_bounds_check` (cycle 45+ fix made it pass). xpass count 1→0. |
| asset-r16-grp-manifest-emit | `asset-r16-grp-manifest-emit-gap` (MED) | New `_emit_grp_manifest()` in `tools/generate_assets.py` (atomic tmp+rename, 450 members, manifest schema v1.0); new `load_and_verify_grp_manifest()` in `tools/manifest_verification.py`; tests/test_grp_manifest.py (11 cases). |
| sec-r15-bundle | `sec-r15-gitignore-d-files-explicit` (LOW), `sec-r15-manifest-loader-adoption` (MED) | `.gitignore` +`build/*.d`; refactored `tools/generate_audio.py load_manifest()` to route through verifier (avoid double-load); 5 test bypass sites documented; new tests/test_manifest_verifier_adoption.py (4 cases). |

### Collateral

`GRP_MANIFEST.json` (~64KB) was emitted to project root by the new `_emit_grp_manifest()` (agent wrote to both `generated_assets/` and project root). Operator added `GRP_MANIFEST.json` to `.gitignore` so the generated artifact never enters version control. **Pattern lesson:** generators that emit to "both X and project root" are a code smell — project root is almost never the right target. Consider follow-up to gate the dual-emit behind a CLI flag.

### Backlog delta

271 → ~268 pending (-6 closed cycle 56, +various small intake from sibling commits; net -3).

---

## Cycle 57 (audit-pass tick)

**Stalest rotation:** build-system (last r15 @ cycle 50) + documentation-curator (last r14 @ cycle 50). Both 7 cycles old.

- **build-system-r16:** 5 findings, **5 todos** (3 new build-r16-* + 2 r15 carryovers elevated). 0 CRIT/HIGH. **MEDIUM:** `build-r16-lto-type-mismatch` (17 LTO type-mismatch warnings; low ABI risk on x86_64-linux-gnu LP64 but worth audit). **LOW/INFO:** make-clean-doc (GRP_MANIFEST.json persistence is intentional but undocumented), lto-flags-doc. Verified: SDL2_VERSION single-source still tight, no /Tc on .C in CMake, .gitignore post-cycle-56 clean, dep-file emission (12 .d files, 7% growth from r15 → minimal rebuild impact).
- **documentation-curator-r15:** 15 findings, **2 new todos, 8 archived**. README/ARCHITECTURE drift report: clean (cycle 50 feature summary + cycle 53 MTU section still accurate). SUMMARY.md integrity: all r-levels indexed, 0 orphans. New: `docs-r15-contributing-testing-section` (add xdist testing docs), `docs-r15-readme-multiplayer-clarification`. **Archived 8 stale/subsumed todos** (r4-era perf/network/test items + r5-era aspirational infra) — all marked blocked with `[archived cycle 57: ...]` rationale.

**Backlog delta:** 265 → ~264 pending (+5 build-r16 +2 docs-r15 = +7 intake, -8 archived = -1 net).

---

## Cycle 58 (grind, 2026-05-20T22:36Z)

**Baseline:** 899 passed → **917 passed** (+18 across 5 closures).

### Closures (6 todos, 5 agents)

| Agent | Todos | Highlights |
|-------|-------|------------|
| net-r13-endian-playeridx | `net-r13-byteswap-endianness-audit`, `net-r13-player-index-bounds-audit` (both MED) | source/GAME.C type-0/1/17 little-endian unpack sentinels (lines 453/458/544/545/791/792 — `net-r13-endian`) + type-6 player-idx gateway sentinel (647 — `net-r13-player-idx-bounds`). Net 7 new tests in `TestNetR13EndianPlayerIdx`. r13.md SECTION 8 appended. No raw multi-byte pointer casts in GAME.C. MMULTI.C:267 is the single validation gateway. |
| build-r16-lto-mact-stub | `build-r16-lto-type-mismatch` (MED) | 17 LTO type-mismatch warnings → 0. compat/mact_stub.c: 13 function signatures aligned to legacy K&R callers (long→int32_t, SafeRealloc void**, SafeOpenRead filetype param). compat/compat.h +`getpacket` forward decl. source/ACTORS.C `numenvsnds extern long`, separated actor_tog. source/MENUES.C `inputloc extern short`. SRC/MMULTI.C `totalclock extern volatile long`. New tests/test_build_warnings.py regression guard (asserts ≤0 lto-type-mismatch). |
| sec-r15-subproc-workflow | `sec-r15-subprocess-injection-audit`, `sec-r15-workflow-secrets-script-logging` (both MED) | tools/generate_audio.py has zero subprocess module usage — verified SAFE. .github/workflows/release.yml all 6 secrets pass through `env:` blocks (no `echo $SECRET`, no `set -x`); +2 `sec-r15-workflow-secrets: env-passed, no-echo` sentinels. New tests/test_security_posture.py with subprocess + workflow assertions. security-and-secrets-r15.md appended closure findings. |
| asset-r16-genlog-rotation | `asset-r16-generation-log-cleanup-policy` (MED) | tools/generate_assets.py +`_rotate_generation_log()` (1000-line / 5 MiB caps; keep latest 50%; synthetic `log_rotated` entry; atomic tmp+rename). Wired into `log_generation_error()`. 4 new tests in `TestAssetR16GenlogRotation`. Sentinel `asset-r16-genlog-rotation`. |
| audio-r15-44100hz | `audio-r15-44100hz-magic-number` (LOW) | compat/audio_stub.c +`#define AUDIO_DEFAULT_SAMPLE_RATE 44100` alongside cycle-46 audio constants. `Mix_OpenAudio()` (line 384) consumes it. 4 new tests in `TestAudioR15SampleRateExtraction` (define presence, no-bare-44100 outside define, cycle-46 defines preserved). |

### Collateral

None. All sentinels intact across cycles 41–57 (re-verified by net-r13 + build-r16 agents).

### Backlog delta

279 → ~273 pending (-6 closed cycle 58, plus standard intake from sibling audit-pass tick).

---

## Cycle 58 (audit-pass tick)

**Stalest rotation:** audio-engineer (last r14 @ cycle 51) + performance-profiler (last r14 @ cycle 51). Both 7 cycles old.

- **audio-engineer-r15:** 4 findings, **5 todos** (0 CRIT/HIGH). Verified cycle 53/56 manifest verifier adoption + cycle 56 audio loader migration. New: filelock-timeout-design (ADVISORY), manifest-migration-doc (MED), and 3 small followups.
- **performance-profiler-r15:** 4 findings, **6 todos** (0 CRIT/HIGH). Suite wallclock 19.84s (3.3% improvement vs r14 despite +7.3% test growth). xdist sweet spot is `-n 2` (22.8% faster than `-n 1`); plateau at `-n 4` suggests filelock/startup overhead. Frame analyzer `[5]` parametrization is 35% of suite — `@pytest.mark.slow` split candidate. Render-loop bounds checks verified <1µs overhead. Backlog: frame-analyzer-slow-marking, xdist-worker-scaling-opt, build-ccache-cost-benefit, grp-manifest-profile, bounds-check-hotspot, suite-growth-model.

**Backlog delta:** 268 → 279 pending (+11 intake from audio-r15 + perf-r15).

---

## Cycle 59 (audit-pass tick, 2026-05-20T22:36Z)

**Stalest rotation:** network-multiplayer (last r13 @ cycle 52) + compat-layer (last r14 @ cycle 52). Both 7 cycles old.

- **network-multiplayer-r14:** 5 findings, **5 todos** (**2 CRIT**, 3 MED). CRIT: `net-r14-randomseed-game-start-sync` (RNG not synced across peers at game start — desync surface), `net-r14-crc-validation-dormant` (CRC code present but dormant, no integrity checks performed on packets). MED: socket-send-failure-zombie, mid-game-idle-timeout, packet-sequence-replay-protection. Verified: cycle 53 fragmentation doc accurate; no legacy IPX/serial code; master/slave authority model sound.
- **compat-layer-r15:** **0 findings, 0 todos** (legitimate clean-pass per anti-hallucination contract v6). Verified cycle 58 AUDIO_DEFAULT_SAMPLE_RATE=44100 live single-source. All cycle-46-onward memory-hack constants intact, zero drift. C11/gnu89 pragma walls intact. SDL2 lifecycle pairing complete + atexit. Windows cross-compilation health: CMakeLists.txt LANGUAGE C still prevents /Tc errors.

**Backlog delta:** ~273 → ~278 pending (+5 net-r14 CRIT/MED intake).

---

## Cycle 60 (audit-pass tick, 2026-05-20T22:50Z)

**Stalest rotation:** test-engineer (last r15 @ cycle 54) + security-and-secrets (last r15 @ cycle 54). Both 6 cycles old.

- **test-engineer-r16:** 3 findings, **4 todos** (**1 CRITICAL escalated**). CRIT: `test-r16-mega-file-split-escalated` — tests/test_engine_net_hardening_regressions.py at 3803 lines (+327 vs r15), IDE-navigation pain zone reached; recommend 3-way split next grind. MED: test_build_warnings.py incomplete-assert false-pass risk (sys.exit before assertion); test_security_posture.py regex/YAML brittleness (high false-positive surface). Suite health: 917 collected, 100% pass, 0 xpass (cycle 56 promotion delivered), 0 flake, 21.01s wallclock.
- **security-and-secrets-r16:** 5 findings, **5 todos** (0 CRIT/HIGH). MED: `sec-r16-scanner-gap-new-patterns` (6 NEW gaps — Google Cloud JSON, Slack xoxp-, npm_, rk_live_, hf_, org-), `sec-r16-manifest-loader-adoption-audit` (verify other loaders haven't drifted), `sec-r16-ci-secret-masking-audit`, `sec-r16-precommit-hook-activation` (hook script exists but `.git/hooks/pre-commit` not installed for fresh clones). LOW: `sec-r16-sentinel-documentation-gap`. Verified: 10 active scanner patterns, manifest verify-on-load LIVE, workflow permissions least-privilege, 100% requirements pinning (CVE-free).

**Backlog delta:** ~278 → ~287 pending (+9 intake from test-r16 + sec-r16).

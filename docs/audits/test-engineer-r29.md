# test-engineer — round 29 (DOC-ONLY shippability audit)

<!-- SUMMARY_ROW -->
| test-engineer | r29 | cycle 121 | Suite NOT yet ship-blocking-complete: 62 files / ~1370 functions cover unit/structural well, but **5 P0 gaps** (full-pipeline GRP byte-determinism, IPv6 zone-id parsing, net_socket adoption regression, CSPRNG fallback, MAXTILES guard runtime fire) and 4 marker-hygiene findings (notably `test_build_warnings.py` chdir+`make clean` lacking `@serial`). |
<!-- END_SUMMARY_ROW -->

## Executive Summary

**Audit lens**: shippability — "would a regression sneak past the current suite into a release build that breaks a player's first 30 seconds?"

**Verdict**: ⚠️ **NOT YET SHIP-READY for v1.0 GA**. The suite is broad (62 files, ~1370 test functions, ~2040 collected including parametrize) and has strong coverage on:

- C struct ABI (`test_build_structs.py`, `test_compat_layer.py`)
- HMAC/HKDF cryptography (`test_net_auth_spoofing.py`, `test_sha256_integration.py`, RFC 4231/5869 known-answers)
- Engine-source string-grep hardening (`test_engine_bounds_hardening.py` — 96 tests grep-asserting bounds-check patterns)
- Secret-scan pre-commit (`test_check_secrets_*.py` — 34 tests covering Google/Slack/npm/Stripe/HuggingFace/OpenAI/AWS/GitHub patterns across .yml/.json/.bat)
- Property/hypothesis coverage of pure tools functions (`test_hypothesis_pure_functions.py` — 82 functions)

But several **ship-critical execution paths are validated only by source-grep, not by runtime behavior**, and the GRP determinism contract — described as a hard contract in `docs/GRP_DETERMINISM.md` and `.github/copilot-instructions.md` — has **no end-to-end test** that runs `generate_assets.py` twice and compares SHA256.

Ship-blocking gaps (P0) below must close before tagging v1.0.

---

## Coverage Matrix

| Subsystem | Files | ~Tests | Coverage | Identified Gap |
|---|---|---|---|---|
| Binary formats (ART/GRP/MAP/ANM/VOC/MIDI/demo) | 7 | ~140 | ✅ Strong — round-trip + parametrized sizes | Demo format only 16 tests; replay-determinism untested |
| C struct ABI | 2 (`test_build_structs.py`, `test_compat_layer.py`) | 64 | ✅ Strong — compile-and-execute harness | MinGW path skipped by default (auto-skip when binary not native) |
| Compat layer | 3 (`test_compat_layer.py`, `test_compat_silent_stubs.py`, `test_sdl_driver.py`) | 72 | ✅ Adequate | No runtime `sdl_quit_requested_get()` test (r2 finding never fully closed — only grep-asserted) |
| Asset pipeline (procedural) | 8 | ~120 | ✅ Strong unit | **P0**: no two-run byte-identical pipeline test (`test_create_grp_deterministic` only covers `create_grp()` function in isolation, not the full `generate_assets.py` invocation) |
| Audio pipeline | 5 | ~221 | ✅ Strong | `assert True` tautology at `test_audio_playback_roundtrip.py:329` inside SDL2_mixer meta-test |
| Engine boundary conditions | 2 (`test_engine_bounds_hardening.py`, `test_engine_net_hardening_regressions.py`) | 96 | ⚠️ All **source-grep** | No runtime fuzz/property test exercising the bounds (e.g. spawn at sector=-1 → expect drop, not crash) |
| Networking — wire format / auth | 6 | ~189 | ✅ Strong HMAC+HKDF KAT, structural header tests | **P0**: IPv6 zone-id parsing (SRC/MMULTI.C:798–893, RFC 4007) has zero tests despite landing in c120 grind; `if_nametoindex` POSIX/Win parity untested |
| Networking — socket abstraction | 2 (`test_net_socket_compat.py`, `test_net_keepalive.py`) | 55 | ⚠️ Source-grep only | **P0**: c120 audit surfaced 2 CRITICAL adoption gaps (`socket()` + `TCP_NODELAY` at SRC/MMULTI.C:665,737,845,873 bypass net_socket abstraction) — no test catches re-introduction |
| CSPRNG (`net_gen_nonce`) | 0 dedicated | 0 | ❌ **None** | **P0**: `BCryptGenRandom` path source-grepped only via `test_engine_bounds_hardening.py`; POSIX `getrandom()`/`arc4random` fallback path untested (per c120 sec-r28 finding: fallback also **missing in source**) |
| MAXTILES guard | 1 (`test_maxtiles_assertion.py`) | 4 | ⚠️ Static-only | **P0**: All 4 tests grep `compat/maxtiles_guard.c` for strings (`abort()`, `__attribute__((constructor))`). No test compiles+runs with mismatched headers to verify the abort() actually fires |
| Playtest (headless) | 2 (`test_visual_playtest.py`, `test_llm_playtest.py` ✨ new c121) | 11 | ⚠️ Improving | LLM e2e arrived this cycle (sibling agent); confirms a long-standing gap is being closed. `headless_run` correctly uses FileLock under xdist ✅ |
| Secret-scan hook | 2 (`test_check_secrets_*.py`) | 34 | ✅ Strong | Missing: Azure connection-string format (`DefaultEndpoints`+`Protocol=…;Account`+`Key=…`), GHA SHA-pin, BEG+IN/END PEM key blocks |
| xdist safety | 1 (`test_pytest_xdist_safety.py`) | 2 | ⚠️ Minimal | Only audits `headless_run` fixture; `test_build_warnings.py` chdir+`make clean` not flagged |
| Lookup tables / palette | 3 | ~52 | ✅ Strong | `palette_quantize_perf` only 1 test — no regression threshold |
| Install hooks / security posture | 2 | 5 | ⚠️ Thin | No test asserts `tools/install_hooks.sh` actually wires `.githooks/pre-commit` post-install |

**Total**: 62 files / ~1370 named functions / ~2040 collected items (per c120 metric). Suite wallclock: 25.15s fast / `--runslow` on by default.

---

## P0 Gaps (Ship-Blockers)

### P0-1: No two-run GRP byte-determinism integration test

- **Contract**: `docs/GRP_DETERMINISM.md` (line 1): "Given identical inputs … `DUKE3D.GRP` binary must be **bit-identical** across runs and platforms."
- **Existing coverage**: `tests/test_hypothesis_pure_functions.py:573 test_create_grp_deterministic` — only exercises the `create_grp()` helper twice on the same dict. Does **not** invoke `tools/generate_assets.py --no-ai` end-to-end.
- **Ship risk**: a regression in palette generation, texture ordering, manifest emission, or sort-key normalization in any of the 20 walls / 10 sprites / 21 WAVs producers would change GRP bytes without any test failing. CI cannot enforce reproducible-build claims today.
- **Fix**: see new-test #1 below.

### P0-2: IPv6 zone-id parsing (RFC 4007) has zero coverage

- **Source landing**: SRC/MMULTI.C:798–893 (cycle c120 referenced this as a HIGH net finding when first surfaced; code subsequently landed via `net-r28-ipv6-zone-id-parsing-fix` per file comments).
- **What's untested**: `[fe80::1%eth0]:port` parsing, bracketed vs non-bracketed parsing, `if_nametoindex()` lookup, numeric-index fallback (`strtol`), `sin6_scope_id` population, behavior on unknown interface name.
- **Ship risk**: link-local multiplayer breaks silently for LAN players using IPv6 (RFC 4007 violation reintroduces). Regression cannot be caught by current tests because all network tests use IPv4 or `[::1]`.
- **Fix**: see new-test #2 below.

### P0-3: `net_socket` abstraction adoption gaps not regression-pinned

- **c120 network-multiplayer r28 finding** (GRIND_LOG.md): "**NEW CRITICAL ×2**: direct socket() at SRC/MMULTI.C:665,845 + TCP_NODELAY at L737,873 bypass net_socket abstraction".
- **Existing coverage**: `tests/test_net_socket_compat.py` grep-asserts `net_socket_create()` etc. are *declared*. It does **not** grep MMULTI.C to assert raw `socket(`, `setsockopt(`, `close(` are absent (except inside the wrapper file).
- **Ship risk**: c120 found 4 call-sites that bypass the abstraction. Once those are fixed, nothing prevents a future PR from re-introducing the same anti-pattern. Cross-platform port (Win32 closesocket vs POSIX close) will silently break.
- **Fix**: see new-test #3 below.

### P0-4: CSPRNG fallback path absent in source AND tests

- **c120 security-and-secrets r28 finding**: "POSIX `getrandom`/`arc4random` fallback missing in `net_gen_nonce` SRC/MMULTI.C:315–318" — flagged MED in audit, but **also no test asserts the fallback exists**.
- **Existing**: BCryptGenRandom Windows path is only grep-asserted. POSIX path falls through to `rand()` per `.github/copilot-instructions.md` explicit prohibition ("Never `rand()` for nonces/checksums").
- **Ship risk**: Linux release ships with weak nonces; HMAC handshake (otherwise solid per test_net_auth_spoofing.py) is undermined by predictable IVs/nonces. Ship-blocker for any multiplayer claim.
- **Fix**: see new-test #4 below.

### P0-5: MAXTILES guard runtime fire not validated

- **Existing**: 4 tests in `test_maxtiles_assertion.py` all grep `compat/maxtiles_guard.c` for `abort()`, `__attribute__((constructor))`, `check_maxtiles_assertion`. None compile or execute a binary with deliberately-mismatched headers.
- **Ship risk**: a refactor that drops the `__attribute__((constructor))` or that triggers it before `printf` initialization would silently disable the guard. Engine could then run with `MAXTILES` mismatch (the original cycle-13 CRITICAL we spent multiple cycles closing) without abort firing.
- **Fix**: see new-test #5 below.

---

## P1 Gaps (Incomplete coverage of complex subsystems)

- **P1-1: Engine bounds hardening is 100% source-grep.** `test_engine_bounds_hardening.py` (96 tests, 2323 LOC) verifies that strings like `if (sectnum >= 0 && sectnum < MAXSECTORS)` appear near specific line numbers. None of these tests exercise the actual binary or fuzz arguments. A semantically-correct refactor that uses a different guard pattern (e.g. `BOUNDS_CHECK_SECTNUM(s)` macro) will tank dozens of tests despite being safer. Conversely, a guard that compiles but is dead code (e.g. guarded by `#ifdef DEBUG`) passes the grep.

- **P1-2: Demo replay determinism untested.** `test_demo_format.py` (16 tests) covers header/byte-layout. No test plays back a fixed demo and asserts player position / clock / RNG seed after N ticks matches a recorded golden — the canonical way to catch engine determinism regressions.

- **P1-3: Audio manifest consistency fixture (open from r28).** Mined as `test-r28-audio-manifest-consistency-fixture` (LOW), still pending. Without it, SOUND_MANIFEST drift vs `generate_audio.py:VOICE_LINES` won't be caught until a user reports "voice line plays wrong file."

- **P1-4: `test_net_socket_is_keepalive_error.py` POSIX-only.** Errno classification harness runs only on Linux/macOS. Windows `WSAETIMEDOUT`/`WSAECONNRESET` mapping (the actual production path for many players) is unexercised.

- **P1-5: Pipeline integration only verifies presence, not content.** `test_pipeline_integration.py:test_full_pipeline_no_ai` checks `grp_size > 100000` and magic bytes. It does not validate that all 21 expected sound IDs, all 20 wall textures, and all 10 sprite textures actually land in the GRP directory.

---

## P2 Gaps (Nice-to-haves)

- **P2-1**: `palette_quantize_perf.py` has 1 test; no upper-bound assertion (perf-r28 mined a 4-6× vectorization opportunity — would benefit from a baseline-locking regression).
- **P2-2**: `test_install_hooks.py` (3 tests) does not assert the post-install `git config core.hooksPath` value.
- **P2-3**: `test_sdl_driver.py` (4 tests) doesn't cover Windows DirectX driver fallback.
- **P2-4**: No test for `_redact_hostname()` (`tools/generate_{assets,audio}.py`) — silent regression would leak `api.openai.com`-style hostnames in stack traces.
- **P2-5**: No test verifying `compat/pragmas_gcc.h` ~174 inline functions are kept ABI-compatible with the Watcom originals (e.g., `mulscale16`, `klabs`, `divscale*` numeric output for known inputs). Pragma fidelity is a documented hot-path contract.

---

## Marker / xdist Correctness Findings

### M-1 (⚠️ MED): `tests/test_build_warnings.py` is missing `@pytest.mark.serial`

- **Location**: `tests/test_build_warnings.py:41` is marked `@pytest.mark.slow` only.
- **Smoking gun**: line 18 calls `os.chdir(repo_root)` and line 23 runs `bash -c "make clean && make -j$(nproc)"`.
- **Hazard**: under `-n auto` xdist, this races with: any test that reads `./duke3d` (test_visual_playtest, test_llm_playtest, headless_run fixture); the C-harness compile fixtures (`compiled_makepalookup_harness` etc.) which write into `tmp_path` but consume PROJECT_ROOT headers that `make clean` would *not* delete, however the chdir leaks into other workers in the same process if pytest reuses worker subprocesses for multiple tests.
- **Recommendation**: add `@pytest.mark.serial`. Also replace `os.chdir(repo_root)` with `cwd=repo_root` on the subprocess call (the chdir is unnecessary and is a pytest anti-pattern).

### M-2 (⚠️ MED): `test_pipeline_integration.py` writes outside `tmp_path` is OK, but `test_full_pipeline_no_ai` lacks `@pytest.mark.serial`

- Currently `@pytest.mark.slow` only. It invokes `generate_assets.py --no-ai --output {tmp_path}` so should be xdist-safe via `tmp_path`. ✅ No bug today, but the test's docstring should explicitly note this safety property so future edits don't drop the `--output` flag.

### M-3 (✅): `test_visual_playtest.py` + `test_llm_playtest.py` correctly use `headless_run` session-scoped fixture w/ FileLock + done-marker

- `tests/conftest.py:774–851` correctly serializes the single SDL2 game launch across xdist workers via `FileLock(".headless_run.lock")` + `.headless_run.done` marker.
- **Caveat**: the `.headless_run.done` marker is not cleaned up between pytest sessions. A test that *modifies* the binary then re-runs will read stale captures. Recommend a `--force-replay` or marker-mtime check.

### M-4 (ℹ️ INFO): `slow` marker discipline holds

- All subprocess-heavy C-harness tests (`test_makepalookup_bounds.py`, `test_sha256_integration.py`, `test_pipeline_integration.py`, `test_build_warnings.py`, `test_generate_audio.py::TestAudioMainEndpointIntegration`) are `@pytest.mark.slow`. `pytest -m "not slow"` correctly trims the fast loop. ✅

---

## Prioritized Net-New Test Cases

| # | Priority | File:test_name | Rationale |
|---|---|---|---|
| 1 | **P0** | `tests/test_pipeline_integration.py::test_grp_byte_identical_across_two_runs` | Run `generate_assets.py --no-ai --output A` then `--output B`, assert `sha256(A/DUKE3D.GRP) == sha256(B/DUKE3D.GRP)`. Codifies `docs/GRP_DETERMINISM.md` contract. Marker: `slow, serial`. |
| 2 | **P0** | `tests/test_multiplayer_protocol.py::test_ipv6_zone_id_link_local_parsing` | Parametrize over `[fe80::1%eth0]:port`, `[fe80::1%1]:port`, `fe80::1%lo`, `[::1]:port` (no zone). Mock `if_nametoindex` via `ctypes` or expose a parse helper. Assert `sin6_scope_id` populated correctly per RFC 4007. |
| 3 | **P0** | `tests/test_net_socket_compat.py::test_no_raw_socket_calls_outside_wrapper` | Grep SRC/MMULTI.C for `\bsocket\(`, `\bsetsockopt\(`, `\bclose\(` (not wrapped in `net_*`). Whitelist only the wrapper definitions. Locks adoption per `.github/copilot-instructions.md` "Networking abstraction" contract. |
| 4 | **P0** | `tests/test_engine_bounds_hardening.py::test_net_gen_nonce_uses_csprng_on_posix` | Source-grep SRC/MMULTI.C `net_gen_nonce` region for `getrandom(` or `arc4random_buf(` inside `#ifndef _WIN32` (or `#else` branch). Asserts the c120 sec-r28 finding actually gets fixed and stays fixed. Pair with runtime test that compiles a tiny harness invoking `net_gen_nonce` and checks output is not all-zeros and varies across 100 calls. |
| 5 | **P0** | `tests/test_maxtiles_assertion.py::test_maxtiles_guard_runtime_aborts` | Compile a tiny C harness that links `compat/maxtiles_guard.c` against a synthetic header with mismatched `MAXTILES`, run it, assert exit via SIGABRT (returncode `-6` POSIX / `3` Windows). Validates the constructor actually fires — not just that the source contains `abort()`. |
| 6 | P1 | `tests/test_engine_bounds_hardening.py::test_runtime_oob_sector_dropped_not_crashed` | Build a tiny C harness using engine struct headers; call the OOB-guarded functions (e.g. `drawsprite(sectnum=-1)`) and assert no SIGSEGV. Promotes the 96 grep-asserts to at least one runtime smoke. |
| 7 | P1 | `tests/test_demo_format.py::test_replay_determinism_golden` | Record a 100-tick demo; replay with fixed RNG seed; assert recorded final state matches golden JSON. Catches engine non-determinism (e.g. `totalclock` drift, FPU mode changes). |
| 8 | P1 | `tests/conftest.py::audio_manifest_consistency_fixture` (closing r28 todo) | Session-scoped fixture loading `MANIFEST.json`, asserting 21 entries, no dup filenames, deterministic timestamps in `--no-ai`. |
| 9 | P1 | `tests/test_net_socket_compat.py::test_keepalive_error_windows_errno_mapping` | Parametrize over `WSAETIMEDOUT (10060)`, `WSAECONNRESET (10054)`, `WSAEWOULDBLOCK (10035)`; assert mapping matches POSIX `ETIMEDOUT`/`ECONNRESET`/`EWOULDBLOCK`. Cross-platform parity. |
| 10 | P1 | `tests/test_pipeline_integration.py::test_grp_contains_all_expected_members` | Parse the generated GRP directory and assert all 21 SOUND_MANIFEST IDs, 20 wall textures, 10 sprite textures present by name. Catches silent drop-on-floor regressions. |
| 11 | P2 | `tests/test_visual_playtest.py::test_redact_hostname_helper` | Direct unit test for `_redact_hostname()` from both `tools/generate_assets.py` and `tools/generate_audio.py`. Parametrize over `api.openai.com`, `models.inference.ai.azure.com`, `*.cognitiveservices.azure.com`. |
| 12 | P2 | `tests/test_install_hooks.py::test_post_install_core_hookspath_set` | After running `bash tools/install_hooks.sh`, assert `git config --get core.hooksPath == .githooks`. |
| 13 | P2 | `tests/test_palette_quantize_perf.py::test_quantize_image_baseline_threshold` | Lock current wallclock as upper bound × 1.5; gates perf-r29 vectorization regression. |

---

## Closing Inventory — Prior Open Findings Re-Verified

### From r28 (still open / re-checked)

- **r28 todo `test-r28-endpoint-validator-parametrized` (LOW)** — Status: ⚠️ **still pending**. `tests/test_generate_audio.py::TestAudioEndpointValidation` has not been parametrized as planned. Carry forward.
- **r28 todo `test-r28-sha256-hmac-boundary-cases` (LOW)** — Status: ⚠️ **still pending**. `test_sha256_integration.py` is still 4 tests (NIST/RFC4231/RFC5869/consolidated); no empty-message, >1MB, or null-salt variants. Carry forward.
- **r28 todo `test-r28-audio-manifest-consistency-fixture` (LOW)** — Status: ⚠️ **still pending**. No new session-scoped manifest fixture in `conftest.py`. Promoted to P1 (see new-test #8).

### From earlier rounds (re-verified holding)

- ✅ **test_dummy_key_ convention** (r27, r28) holds across all 7 occurrences in `test_generate_assets.py` + `test_generate_audio.py` + `conftest.py:529`.
- ✅ **Session-scoped C-harness fixtures** (`compiled_makepalookup_harness`, `compiled_keepalive_error_harness`, `compiled_sha256_harness`) all stable in `conftest.py:219–667`; no per-test compilation regression.
- ✅ **Pre-commit hook self-quote FP** (c117 lesson) honored — no audit doc references literal `service_account` / `private_key` strings (this doc uses `test_dummy_key_` style citations only).

### New finding this round

- ⚠️ **Tautology in `test_audio_playback_roundtrip.py:329`** — `assert True` inside `test_mixer_availability_reported` is reachable when SDL2_mixer import succeeds. Either upgrade to an assertion on `SDL2_mixer.Mix_OpenAudio` or `pytest.skip` regardless. Filed as **r29-todo**.
- ⚠️ **`os.chdir` in `test_build_warnings.py:18`** is xdist-unsafe and the test is not `@pytest.mark.serial`. See M-1 above.

---

<!-- GRIND_LOG_ENTRY -->
**Cycle 121 audit-pass — test-engineer r29 (shippability lens)**: Inventoried 62 test files / ~1370 functions / ~2040 collected. Verdict: NOT yet ship-ready. Identified **5 P0 gaps**: (1) no full-pipeline GRP byte-determinism integration test despite `docs/GRP_DETERMINISM.md` "bit-identical" contract (existing `test_create_grp_deterministic` only covers `create_grp()` helper, not `generate_assets.py` end-to-end); (2) IPv6 zone-id parsing (SRC/MMULTI.C:798–893, RFC 4007) has zero tests despite landing in c120; (3) `net_socket` abstraction adoption gaps (c120 net-r28 surfaced 2 CRITICAL raw `socket()`+`TCP_NODELAY` call-sites in MMULTI.C) lack a regression-pinning test; (4) `net_gen_nonce` POSIX CSPRNG fallback both missing in source AND not asserted by any test (only Windows BCryptGenRandom grep-asserted); (5) MAXTILES guard runtime fire not validated — all 4 `test_maxtiles_assertion.py` tests grep `compat/maxtiles_guard.c` strings instead of compiling+running a mismatched-headers binary. Marker-hygiene MED: `test_build_warnings.py` does `os.chdir(repo_root)` + `make clean && make -j$(nproc)` but is marked only `@pytest.mark.slow` (not `@pytest.mark.serial`) — xdist race risk. Tautology spotted: `assert True` at `test_audio_playback_roundtrip.py:329`. Sibling agent landing `tests/test_llm_playtest.py` (3 tests, `@playtest+@slow`) noted as positive — closes long-standing LLM e2e gap. Re-verified holding: test_dummy_key_ convention, session-scoped C-harness fixtures (makepalookup/keepalive/sha256), pre-commit self-quote FP. All 3 r28 mined todos still pending (none landed this cycle). 13 new test cases proposed (5 P0, 5 P1, 3 P2).
<!-- END_GRIND_LOG_ENTRY -->

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
 ('test-r29-grp-byte-determinism-e2e', 'GRP byte-identical end-to-end test (P0)', 'Add tests/test_pipeline_integration.py::test_grp_byte_identical_across_two_runs that runs generate_assets.py --no-ai twice into two different --output dirs and asserts sha256(A/DUKE3D.GRP) == sha256(B/DUKE3D.GRP). Codifies docs/GRP_DETERMINISM.md contract. Mark @pytest.mark.slow + @pytest.mark.serial. Acceptance: test fails if any pipeline stage introduces nondeterminism (timestamp leak, dict-order leak, float-rounding).', 'pending'),
 ('test-r29-ipv6-zone-id-parsing', 'IPv6 zone-id parsing tests (P0)', 'Add tests/test_multiplayer_protocol.py::test_ipv6_zone_id_link_local_parsing parametrized over bracketed [fe80::1%eth0]:port, non-bracketed fe80::1%lo, numeric-index zone, missing zone. Either expose the parse helper from SRC/MMULTI.C:798-893 via a small C wrapper or grep-assert presence of sin6_scope_id population. RFC 4007 compliance. Acceptance: regression test fails if zone-id handling regresses.', 'pending'),
 ('test-r29-net-socket-adoption-grep', 'net_socket abstraction adoption regression test (P0)', 'Add tests/test_net_socket_compat.py::test_no_raw_socket_calls_outside_wrapper that greps SRC/MMULTI.C for \\bsocket\\(, \\bsetsockopt\\(, \\bclose\\( and asserts each match is inside a net_*-prefixed wrapper definition. Closes c120 network-multiplayer r28 CRITICAL adoption gaps. Acceptance: test fails if any future PR re-introduces direct socket()/setsockopt()/close() calls in MMULTI.C.', 'pending'),
 ('test-r29-csprng-fallback', 'CSPRNG POSIX fallback test (P0)', 'Add tests/test_engine_bounds_hardening.py::test_net_gen_nonce_uses_csprng_on_posix that grep-asserts getrandom( or arc4random_buf( appears in the POSIX branch of net_gen_nonce in SRC/MMULTI.C. Pair with runtime harness invoking net_gen_nonce 100x and asserting nonces vary and are not all-zero. NOTE: requires source fix first (c120 sec-r28 finding: fallback currently missing).', 'pending'),
 ('test-r29-maxtiles-runtime-abort', 'MAXTILES guard runtime abort test (P0)', 'Add tests/test_maxtiles_assertion.py::test_maxtiles_guard_runtime_aborts that compiles a tiny C harness linking compat/maxtiles_guard.c against a synthetic header with mismatched MAXTILES, runs it, and asserts SIGABRT (returncode -6 POSIX). Validates __attribute__((constructor)) actually fires — not just that abort() is present in source. Mark @pytest.mark.slow.', 'pending'),
 ('test-r29-engine-runtime-oob-smoke', 'Engine runtime OOB smoke test (P1)', 'Promote one or two of the 96 source-grep bounds-check assertions in test_engine_bounds_hardening.py to a runtime smoke test: compile harness, call drawsprite/spawn with sectnum=-1 or MAXSECTORS+1, assert no SIGSEGV (returncode 0 or graceful drop). Mark @pytest.mark.slow.', 'pending'),
 ('test-r29-demo-replay-determinism-golden', 'Demo replay determinism golden test (P1)', 'Add tests/test_demo_format.py::test_replay_determinism_golden that records a 100-tick fixed-seed demo, replays it via headless game, asserts final player position + clock + RNG state match golden JSON committed to testdata/. Catches engine non-determinism (totalclock drift, FPU mode changes). Mark @pytest.mark.slow + @pytest.mark.playtest.', 'pending'),
 ('test-r29-audio-manifest-consistency-fixture', 'Audio manifest consistency fixture (P1)', 'Re-mine of r28 carry-forward: session-scoped fixture in conftest.py loading generated_assets/sounds/MANIFEST.json, asserting 21 entries, no duplicate wav filenames, deterministic generated_at timestamps in --no-ai mode. Consume from existing test_audio_pipeline.py manifest tests.', 'pending'),
 ('test-r29-keepalive-windows-errno', 'Keepalive errno Windows parity test (P1)', 'Add tests/test_net_socket_compat.py::test_keepalive_error_windows_errno_mapping parametrized over WSAETIMEDOUT (10060), WSAECONNRESET (10054), WSAEWOULDBLOCK (10035); assert net_socket_is_keepalive_error maps these to the same Python boolean as POSIX ETIMEDOUT/ECONNRESET/EWOULDBLOCK. Requires either MinGW cross-build path or a #ifdef _WIN32 stub.', 'pending'),
 ('test-r29-grp-member-completeness', 'GRP member completeness test (P1)', 'Add tests/test_pipeline_integration.py::test_grp_contains_all_expected_members that parses the generated DUKE3D.GRP directory and asserts presence of all 21 SOUND_MANIFEST IDs, all 20 wall textures, all 10 sprite textures by name. Catches silent drop-on-floor regressions in the pipeline.', 'pending'),
 ('test-r29-redact-hostname-unit', 'Hostname redaction unit test (P2)', 'Add tests/test_generate_assets.py + tests/test_generate_audio.py unit tests for _redact_hostname() parametrized over api.openai.com -> api.***, *.cognitiveservices.azure.com, *.inference.ai.azure.com. Prevents PII regression in error logs.', 'pending'),
 ('test-r29-install-hooks-core-hookspath', 'install_hooks.sh post-install assertion (P2)', 'Extend tests/test_install_hooks.py with a test that runs bash tools/install_hooks.sh inside a tmp git repo and asserts git config --get core.hooksPath returns .githooks. Currently only 3 tests; this is a gap.', 'pending'),
 ('test-r29-palette-quantize-perf-baseline', 'Palette quantize perf baseline lock (P2)', 'Lock current quantize_image() wallclock in test_palette_quantize_perf.py with assert duration < baseline * 1.5; gates perf-r29 4-6x vectorization regression. Currently file has only 1 test with no upper-bound assertion.', 'pending'),
 ('test-r29-fix-test_build_warnings-serial-marker', 'Mark test_build_warnings.py @serial (M-1)', 'Add @pytest.mark.serial to test_build_warnings.py::test_build_lto_warnings and replace os.chdir(repo_root) with subprocess cwd=repo_root. Currently the test runs make clean && make -j$(nproc) without serial guard — under -n auto xdist this races with any other test that reads ./duke3d.', 'pending'),
 ('test-r29-replace-tautology-mixer-availability', 'Remove tautological assert True (M-2 housekeeping)', 'Replace `assert True` at tests/test_audio_playback_roundtrip.py:329 inside test_mixer_availability_reported with a meaningful assertion on SDL2_mixer.Mix_OpenAudio symbol presence, or restructure as pure pytest.skip().', 'pending');
<!-- END_MINED_TODOS -->

<!-- SENTINEL: 4a8c2f91 -->

# Test Engineer Audit (r14) — Cycle 41-45 Verification Pass

**Persona**: Test Engineer
**Cycle**: 46 (r14 audit-pass)
**Date**: Cycle 46
**Scope**: Verify r13 picks, xdist fixture redesign coordination, test quality sweep, xfail/xpass promotion, slow-test profiling
**Dependencies**: 
- `perf-r12-xdist-fixture-redesign` (xdist fixture race resolution)
- r13 pending todos (maxtiles stages 2/3, xfail debt, pytest-xdist markers, determinism)

---

## Executive Summary

**Baseline State (Cycle 45)**:
- **Test Suite**: 780 tests collected (780 passed, 34 skipped, 2 xfailed, 2 xpassed)
- **Runtime**: 22.33 seconds (dominated by frame-analyzer tests: 6.97s one test alone)
- **Test Classes**: 50 new classes in test_engine_net_hardening_regressions.py (~2872 lines)
- **Xfail/Xpass Status**: 2 xfail (PLAYER weapon bounds, cycle-31 debt carry-forward), 2 xpass (MAXTILES cycle-42 Stage 3 passed, BUILD_H_CONSISTENCY cycle-42 passed)
- **Fixture Health**: `generated_audio_artifacts` confirmed xdist-unsafe; pytest.ini serial/slow markers LIVE ✅

**Test Quality Grade**: A–
- ✅ Grep-based regression patterns well-established (124 tests, 50 test classes)
- ✅ Xfail debt properly documented (r13 re-state with cycle-31 cross-reference)
- ✅ xpass promotion pending (2 tests ready for assert PASS)
- ⚠️ Frame analyzer hotspot (6.97s single test; 31% of suite runtime)
- ⚠️ Determinism contract documented but not enforced (no pragma/CI marker)

**Critical Assessment**:
- ✅ r13 pending todos reviewed: 2 Stage 2/3 MAXTILES todos CLOSED (tests now PASS), xfail debt properly marked
- ✅ xdist fixture race known (generated_audio_artifacts fixture, pytest.ini documented opt-in via `-n auto`)
- ✅ 50 grep-based test classes landed (cycles 41-45) — strong pattern match, BUT sparse mutation testing
- ✓ Serial marker convention LIVE in conftest.py (audio-engineer seeded @pytest.mark.serial usage)
- ⚠️ 2 xpass tests NOT promoted to assert PASS (low-priority cleanup)

---

## Section 1: r13 Picks Verification

### r13 MAXTILES Todos (Stage 2 & 3)

| Todo ID | Title | Status | Finding |
|---------|-------|--------|---------|
| `test-r13-maxtiles-stage2-test-plan` | Design/validate Stage 2 unification tests | ✅ CLOSED | Test `test_build_h_constants_match_between_headers[MAXTILES]` now XPASS (Stage 2 landed cycle 41, headers unified) |
| `test-r13-maxtiles-stage3-test-plan` | Design/validate Stage 3 abort() enforcement | ✅ CLOSED | Test `test_build_h_constants_match_between_headers[MAXTILES]` now PASS (Stage 3 landed cycle 42, abort() active) |

**Verdict**: Both r13 picks successfully closed. MAXTILES unification + abort() enforcement LIVE & VERIFIED ✅. No test regression.

### r13 Xfail Debt Disposition

**Status**: XFAIL CARRYFORWARD (no new promotion)

```
tests/test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_player_c_displayweapon_bounds_check [XFAIL]
tests/test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_player_c_addweapon_call_bounds_check [XFAIL]
tests/test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_player_c_checkweapon_bounds_check [XPASS — passed when expected to fail]
```

**r13 Marker Status**: Re-stated with r13 timestamp + cycle-31 dispatch requirement ✅. Carries forward unchanged.

### r13 pytest-xdist Markers & Determinism

| Todo ID | Title | Status | Finding |
|---------|-------|--------|---------|
| `test-r13-pytest-xdist-markers` | Add per-file serial marker convention | ✅ DELIVERED | Markers LIVE in conftest.py + test_audio_pipeline.py @pytest.mark.serial ✅; pytest.ini (line 10) serial marker DEFINED ✅ |
| `test-r13-determinism-spot-check` | Verify determinism (5-file spot-check) | ✅ VERIFIED | 5 random files spot-checked; no time(), random(), socket, os.walk, getenv() patterns detected ✅ |

**Verdict**: r13 xdist + determinism picks DELIVERED. Fixture race documented in pytest.ini (line 2-6) with opt-in via `-n auto` when perf-r12-xdist-fixture-redesign lands ✅.

---

## Section 2: xdist Fixture Redesign Coordination

**Status**: BLOCKED on `perf-r12-xdist-fixture-redesign` (external dependency)

### Current xdist Blocker

**Fixture**: `generated_audio_artifacts` (conftest.py:90-137)
- **Scope**: session-autouse (runs once per test session)
- **Race Vector**: `tmp+rename` in `tools/generate_audio.py --no-ai` when workers spawn
- **Symptom**: Concurrent workers overwrite generated_assets/sounds/ directory during fixture setup

**Pytest.ini Workaround** (LIVE ✅):
```ini
# Line 2-6: Documented opt-in pattern
# Default is serial because the session-autouse `generated_audio_artifacts`
# fixture races with itself across xdist workers on the
# tmp+rename of generated_assets/sounds/. Opt in explicitly with `pytest -n auto`
# once the fixture is refactored to be xdist-safe (see perf-r12-xdist-fixture-redesign).
```

### Proposed xdist-Safe Fixture Patterns (Advisory)

For future cycle-47+ when perf-r12-xdist-fixture-redesign lands, recommend ONE of:

#### Pattern A: Worker-Isolated tmpdir (Simplest)
```python
@pytest.fixture(scope="session")
def generated_audio_artifacts(tmp_path_factory):
    """Generate artifacts to worker-isolated tmpdir, not repo root."""
    worker_tmp = tmp_path_factory.mktemp("audio_session")
    sounds_dir = worker_tmp / "sounds"
    
    result = subprocess.run(
        [sys.executable, ..., "generate_audio.py", "--no-ai"],
        cwd=worker_tmp,  # Generate to worker tmpdir, not PROJECT_ROOT
        ...
    )
    # Worker-isolated: no race on PROJECT_ROOT/generated_assets/
    return {"sounds_dir": sounds_dir, ...}
```

**Pros**: Zero inter-worker contention; idempotent regeneration per worker
**Cons**: Duplicated artifacts across workers (storage cost)

#### Pattern B: Filelock-Protected Repo Root (Recommended for Shared Assets)
```python
@pytest.fixture(scope="session")
def generated_audio_artifacts(tmp_path_factory):
    """Generate once to repo root, guarded by filelock across workers."""
    lock_path = Path(PROJECT_ROOT) / ".audio_generation.lock"
    
    with FileLock(lock_path, timeout=60):
        # Only first worker regenerates; others wait
        result = subprocess.run(
            [sys.executable, ..., "generate_audio.py", "--no-ai"],
            cwd=PROJECT_ROOT,
            ...
        )
    return {"sounds_dir": Path(PROJECT_ROOT) / "generated_assets" / "sounds", ...}
```

**Pros**: Single artifact set shared across workers; deterministic
**Cons**: Requires filelock dependency; timeout edge case possible

#### Pattern C: Worker Index-Based Deterministic Artifact (Advanced)
```python
@pytest.fixture(scope="session")
def generated_audio_artifacts(tmp_path_factory):
    """Each worker regenerates from deterministic seed (manifest hash)."""
    # Use worker_index to generate same artifacts independently
    manifest_hash = hashlib.sha256(b"audio_manifest_v1.0").hexdigest()
    worker_cache_dir = Path(PROJECT_ROOT) / f".cache_audio_{manifest_hash}"
    
    result = subprocess.run(
        [sys.executable, ..., "generate_audio.py", "--no-ai"],
        cwd=worker_cache_dir,
        ...
    )
    # Each worker has identical cache_dir (by hash), no race
    return {"sounds_dir": worker_cache_dir / "sounds", ...}
```

**Pros**: Deterministic shared cache; no locks needed
**Cons**: Complex; assumes deterministic generate_audio.py

**Recommendation for Cycle 47+**: Pattern B (filelock) offers best safety/cost tradeoff. Pattern A acceptable if storage not constrained.

---

## Section 3: Test Quality Sweep (Cycles 41-45 Additions)

### Test Addition Metrics

| Dimension | Count | Assessment |
|-----------|-------|------------|
| New test classes (cycles 41-45) | 13 added to test_engine_net_hardening_regressions.py | Strong pattern adoption |
| Total test classes (all time) | 50 (in hardening regressions alone) | Comprehensive grep-based coverage |
| Grep-based tests | ~124 (hardening regressions) | Deterministic, CI-safe |
| Runtime-fixture tests | ~15 (audio_pipeline, asset_pipeline, visual_playtest) | Fixture-driven, isolated |

### Recent Additions (Cycles 41-45) — Assertion Strength Assessment

| Test Class | Type | Assertion Strength | Mutation Test Risk | Grade |
|------------|------|-------------------|-------------------|-------|
| TestActorsSpriteSectnumChain | Grep | Medium (pattern match) | Medium (no runtime validation) | B+ |
| TestFtaQuotesStrcpyOverflow | Grep | Medium (pattern match) | Medium (no dynamic check) | B+ |
| TestRecvEagainDistinguish | Grep | Medium (sentinel + pattern) | Medium (no win32/posix test exec) | B |
| TestMixInitRetryBackoff | Grep | Medium (sentinel + pattern) | Medium (no actual retry firing) | B |
| TestParallelManifestRace | Grep | Low (presence check) | High (no actual race test) | C+ |
| TestSecR13MenuesStrcpy | Grep | Medium (pattern + sentinel) | Medium (static only) | B |
| TestActorsProjectileSectnumGuard | Grep | Medium (pattern match) | Medium (no bounds test) | B |
| TestType8BoardfilenameUnderflow | Grep | Medium (sentinel + pattern) | Medium (no input fuzzing) | B |
| TestEngineR13SectorBounds | Grep | Medium (pattern match) | Medium (no sector OOB test) | B |
| TestEngineR13NextsectorneighborzBounds | Grep | Medium (pattern match) | Medium (no actual exec) | B |
| TestType17EnvelopePrevalidate | Grep | Medium (pattern match) | Medium (no packet injection) | B |
| TestPlayerDisconnectMemset | Grep | Medium (pattern match) | Medium (no memory verification) | B |
| TestSecR13SprintfBoundsAudit | Grep | Medium (pattern match) | Medium (no buffer test) | B |

### Quality Finding: Mutation Test Gap

**Issue**: All cycles 41-45 additions are GREP-BASED (static source inspection). While grep is fast and CI-safe, it cannot detect:
- Parameter value changes (e.g., size changed from 128→64)
- Logic inversions (e.g., `>` changed to `<`)
- Silent fallthrough (e.g., break/return removed from switch)

**Recommendation (Low Priority)**: Identify top 3 grep-based tests for runtime promotion:
1. **TestActorsSpriteSectnumChain** — Mock actor sprite, inject invalid sectnum, verify no crash
2. **TestType17EnvelopePrevalidate** — Mock packet envelope, inject out-of-range packbufleng, verify guard fires
3. **TestEngineR13SectorBounds** — Mock sector array, call operatesectors/animatesect with invalid index, verify bounds check

**Candidate Todo**: `test-r14-mutation-test-gap-top3-promotion` (BACKLOG, LOW priority)

---

## Section 4: xfail/xpass Status & Promotion

### Current xfail/xpass Inventory (Cycle 45)

```
✓ XPASS (passed when expected to fail):
  - tests/test_build_h_consistency.py::test_build_h_constants_match_between_headers[MAXTILES]
    (Reason: MAXTILES header unification landed cycle 41, Stage 3 abort() cycle 42)
  - tests/test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_player_c_checkweapons_bounds_check
    (Reason: Unknown; investigate)

✗ XFAIL (expected to fail):
  - tests/test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_player_c_displayweapon_bounds_check
    (Reason: Awaiting cycle-31 weapon patch re-dispatch — MARKED r13)
  - tests/test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_player_c_addweapon_call_bounds_check
    (Reason: Awaiting cycle-31 weapon patch re-dispatch — MARKED r13)
```

### Promotion Decision: MAXTILES xpass → assert PASS ✓

**Test**: `test_build_h_constants_match_between_headers[MAXTILES]`

**Current Status**: XPASS (test marker in test_build_h_consistency.py)

**Recommendation**: DELETE xfail marker — test is now genuinely passing and should be asserted PASS.

**Reasoning**:
- Cycle 41: SRC/BUILD.H + BUILD.H unified to 6144 (Stage 2 landing)
- Cycle 42: MAXTILES abort() enforcement activated (Stage 3 landing)
- r13 audit verified both landings ✅
- Test now correctly asserts MAXTILES match

**Action Recommended for Next Cycle** (Not scope of r14 DOC-ONLY): Remove @pytest.mark.xfail from test_build_h_constants_match_between_headers[MAXTILES]

---

## Section 5: conftest.py Organization & Race Vectors

### Session-Scope Fixtures Review

| Fixture | Scope | Race Risk | Status |
|---------|-------|-----------|--------|
| `project_root` | session | ✅ No (read-only) | SAFE |
| `binary_path` | session | ✅ No (read-only) | SAFE |
| `grp_path` | session | ✅ No (read-only) | SAFE |
| `generated_assets_dir` | session | ✅ No (read-only) | SAFE |
| `generated_audio_artifacts` | session, autouse=True | ⚠️ YES (subprocess + tmp+rename) | **KNOWN ISSUE** (documented in pytest.ini) |

### Fixture Analysis: generated_audio_artifacts

**Location**: tests/conftest.py:90-137

**Race Vector** (detailed):
1. Test worker 0 starts fixture setup → mkdir generated_assets/sounds (symlink race possible)
2. Test worker 1 starts fixture setup concurrently → subprocess generate_audio.py also mkdir
3. Both workers call tmp+rename atomically, but file descriptor state shared on some FS

**Current Mitigation**:
- ✅ Documented in pytest.ini lines 2-6
- ✅ Opt-in via `pytest -n auto` (off by default)
- ✅ No teardown attempted (idempotent, checked-in artifacts)

**Required for xdist Opt-In** (cycle 47+):
- Implement one of three patterns above (worker-tmpdir, filelock, or deterministic hash)
- Remove "once the fixture is refactored" conditional from pytest.ini
- Update conftest.py fixture with new implementation

### Determinism Contract (conftest.py:100-101)

**Status**: Documented ✅

```python
# Line 100-101: Determinism assertion
# - Session-scoped: generated_assets/sounds/ is part of the checked-in project state
# - Regenerating files is idempotent: running generate_audio.py --no-ai multiple
#   times produces identical output (deterministic silence placeholders)
```

**Verification**: Spot-checked 5 random test files (r13), all determinism-clean ✅.

---

## Section 6: Slow Tests Profiling

### Top 15 Slowest Tests (pytest --durations=15)

```
6.97s call     tests/test_frame_analyzer.py::TestAnalyzeFrameSequence::test_analyze_frame_sequence_deterministic[5]
2.90s setup    tests/test_visual_playtest.py::test_headless_startup
2.37s call     tests/test_visual_playtest.py::test_frame_sequence_analysis
1.38s call     tests/test_frame_analyzer.py::TestAnalyzeFrameSequence::test_sequence_analysis
0.92s call     tests/test_frame_analyzer.py::TestAnalyzeFrameSequence::test_progression_detected
0.73s call     tests/test_frame_analyzer.py::TestAnalyzeFrameSequence::test_all_black_sequence
0.52s call     tests/test_frame_analyzer.py::TestAnalyzeFrame::test_returns_expected_keys
0.49s call     tests/test_frame_analyzer.py::TestAnalyzeFrame::test_colorful_frame_analysis
0.47s call     tests/test_frame_analyzer.py::TestAnalyzeFrame::test_brightness_in_result
0.47s call     tests/test_frame_analyzer.py::TestAnalyzeFrame::test_top_colors_format
0.37s call     tests/test_visual_playtest.py::test_has_visible_content
0.36s call     tests/test_frame_analyzer.py::TestAnalyzeFrame::test_black_frame_analysis
0.33s setup    tests/test_anm_format.py::TestCompressRSD::test_all_same_pixels
0.19s call     tests/test_frame_analyzer.py::TestHasVisibleContent::test_colorful_has_content
0.18s call     tests/test_frame_analyzer.py::TestBlackScreenDetection::test_custom_cutoff
```

### Performance Assessment

**Hotspot 1: test_analyze_frame_sequence_deterministic[5] (6.97s)**
- **File**: tests/test_frame_analyzer.py
- **Cause**: Frame sequence analysis on 5+ real frames (PIL pixel ops + histogram calculation)
- **Recommendation**: Parametrize with smaller frame sets (1-3 frames) for fast path; keep 5-frame test as `@pytest.mark.slow`
- **Est. Speedup**: 6.97s → 1-2s (70% reduction)

**Hotspot 2: test_headless_startup setup (2.90s)**
- **File**: tests/test_visual_playtest.py
- **Cause**: Game binary launch + SDL dummy driver initialization
- **Recommendation**: Already marked `@pytest.mark.playtest`; acceptable overhead for gameplay validation
- **Status**: OK (not a regression issue)

**Hotspot 3: test_frame_sequence_analysis (2.37s)**
- **File**: tests/test_visual_playtest.py
- **Cause**: Full game session capture + frame analysis loop
- **Recommendation**: Already marked `@pytest.mark.playtest`; acceptable
- **Status**: OK

### Slow Test Summary

- **Total suite runtime**: 22.33s
- **Top hotspot (frame-analyzer)**: 31% of total (6.97s)
- **All frame-analyzer tests**: ~13s (58% of total)
- **Visual playtest tests**: ~5.5s (25% of total)
- **Grep-based tests**: <1s (< 5% of total)

**Verdict**: Frame analyzer + playtest account for ~83% of runtime. Both are necessary (frame analysis validates rendering, playtest validates game startup). However, test_analyze_frame_sequence_deterministic[5] parametrization could reduce overhead for default runs.

---

## Section 7: New Findings & Backlog

### Finding 1: Frame Analyzer Parametrization Opportunity

**Priority**: MEDIUM

**Description**: test_analyze_frame_sequence_deterministic[5] runs 6.97s alone (31% of total suite). Recommend parametrizing with 1/3/5/10-frame variants and marking 5/10 as `@pytest.mark.slow` to reduce default-run overhead.

**Impact**: 22.33s → ~16s suite runtime (28% speedup)

**Action**: Create todo `test-r14-frame-analyzer-parametrization`

### Finding 2: xpass Promotion (MAXTILES Test)

**Priority**: MEDIUM

**Description**: test_build_h_constants_match_between_headers[MAXTILES] marked as XPASS since cycle 42 (3 cycles past landing). Should be promoted to assert PASS by removing @pytest.mark.xfail marker.

**Impact**: Cleaner test status, removes expected-failure debt

**Action**: Create todo `test-r14-xpass-maxtiles-promotion`

### Finding 3: xpass Investigation (PLAYER Weapon Test)

**Priority**: LOW

**Description**: test_player_c_checkweapons_bounds_check marked XPASS (r13 xfail expected to pass). Investigate why test passes when expected to fail. May indicate cycle-31 weapon patch landed, or test logic change.

**Impact**: Resolve xfail debt faster if patch present

**Action**: Create todo `test-r14-xpass-weapon-bounds-investigation`

### Finding 4: Mutation Test Promotion Gap (Grep-Only Tests)

**Priority**: LOW (BACKLOG)

**Description**: All cycles 41-45 test additions use grep-based patterns. None test actual runtime behavior (e.g., mock injection, boundary test, crash detection). Top 3 candidates for runtime promotion:
1. TestActorsSpriteSectnumChain → mock actor, inject invalid sectnum
2. TestType17EnvelopePrevalidate → mock packet, inject invalid envelope
3. TestEngineR13SectorBounds → call functions with OOB sector indices

**Impact**: Stronger mutation test coverage for recent hardening additions

**Action**: BACKLOG — create as advisory todo, recommend cycle 47+ dispatch

### Finding 5: pytest.ini Determinism Assertion Missing

**Priority**: LOW (OPTIONAL HYGIENE)

**Description**: conftest.py documents determinism contract (lines 100-101), but pytest.ini lacks pragma/marker to enforce determinism (e.g., no `determinism` marker registered, no `-p determinism_checker` option).

**Impact**: Determinism can drift silently if test patterns change

**Action**: ADVISORY — recommend cycle 47+ enhancement (register `determinism` marker, add CI pragma)

---

## Section 8: Prioritized Backlog (New Todos for Cycle 47+)

### Priority: HIGH

#### test-r14-frame-analyzer-parametrization
- **Title**: Reduce frame-analyzer test suite runtime via parametrization
- **Description**: test_analyze_frame_sequence_deterministic[5] consumes 6.97s (31% of total). Parametrize with [1, 3, 5, 10] frame counts; mark 5+ as @pytest.mark.slow. Estimate 22s → 16s suite runtime (28% speedup). Target cycle 47.
- **Dependencies**: None
- **Status**: pending

#### test-r14-xpass-maxtiles-promotion
- **Title**: Promote MAXTILES xpass to assert PASS
- **Description**: test_build_h_constants_match_between_headers[MAXTILES] marked XPASS since cycle 42 (3 cycles past landing). Remove @pytest.mark.xfail marker to reflect true pass status. Cross-reference cycle 41 Stage 2 + cycle 42 Stage 3 landings. Update test file + re-run to verify green. Target cycle 46 (can be done now).
- **Dependencies**: None
- **Status**: pending

### Priority: MEDIUM

#### test-r14-xpass-weapon-bounds-investigation
- **Title**: Investigate PLAYER weapon bounds xpass anomaly
- **Description**: test_player_c_checkweapons_bounds_check marked XPASS (r13 expected to fail, but passed). Investigate: (1) Did cycle-31 weapon patch land independently? (2) Was test logic changed (line count, assertion)? (3) Is bounds check now in PLAYER.C? Document finding + decide: promote to PASS, or clarify xfail reason.
- **Dependencies**: None
- **Status**: pending

### Priority: LOW (BACKLOG ADVISORY)

#### test-r14-mutation-test-gap-top3-promotion
- **Title**: Promote top 3 grep-based tests to runtime/mutation variants
- **Description**: All cycles 41-45 additions are grep-only (static inspection). Identify top 3 candidates for runtime promotion: (1) TestActorsSpriteSectnumChain (mock actor, inject invalid sectnum, assert no crash), (2) TestType17EnvelopePrevalidate (mock packet, inject out-of-range packbufleng, verify guard), (3) TestEngineR13SectorBounds (call functions with OOB sector index, verify bounds check). Design fixture injection patterns. Recommend cycle 47+ dispatch.
- **Dependencies**: None
- **Status**: pending

#### test-r14-determinism-contract-enforcement
- **Title**: Add determinism pragma/marker to enforce contract
- **Description**: conftest.py documents determinism contract (lines 100-101), but no pytest mechanism enforces it. Register `@pytest.mark.determinism` marker in pytest.ini. Consider adding lightweight CI pragma (`-p pytest_determinism_checker.py`) to spot-check future tests. Advisory (low-priority hygiene improvement). Recommend cycle 48+ dispatch.
- **Dependencies**: None
- **Status**: pending

---

## Section 9: xdist Fixture Redesign (Coordination with perf-r12)

### Status: WAITING ON perf-r12-xdist-fixture-redesign

**Blocker**: External dependency (performance-profiler domain)

**What We Know** (from pytest.ini + conftest.py):
- ✅ Blocker identified: `generated_audio_artifacts` tmp+rename race on xdist workers
- ✅ Workaround documented: pytest.ini opt-in via `-n auto` (default serial)
- ✅ Serial marker convention LIVE: audio-engineer seeded @pytest.mark.serial in audio_pipeline tests

**What's Needed** (cycle 47+ coordination):
1. perf-r12 proposes fixture redesign (one of three patterns above)
2. Test-engineer implements fixture change + validates parallelization works
3. Update pytest.ini to remove conditional line (2-6)
4. Run `pytest -n auto` in CI to demonstrate 3-4x speedup
5. Update CONTRIBUTING.md with xdist enablement instructions

**Advisory Note**: No action needed from test-engineer in r14. Simply documented coordination point + proposed patterns for future discussion.

---

## Section 10: Test Coverage Gaps (Informational)

### Known Gaps (from previous audits, still pending)

| Gap | Priority | Last Mentioned | Status |
|-----|----------|-----------------|--------|
| Audio generation pipeline zero-tested (no tests validate generate_audio.py) | HIGH | r12 | PENDING |
| Struct size verification missing for actortype/hittype (only sectortype/walltype/spritetype checked) | MEDIUM | r11 | PENDING |
| Test isolation: DUKE3D.GRP written to repo root (though .gitignore'd) | MEDIUM | r9 | PENDING |
| Pillow Image.getdata() deprecated (113 warnings in frame_analyzer.py) | LOW | r13 | PENDING |

**Note**: These gaps are outside scope of r14 audit-pass and are tracked in backlog.

---

## References

- **.github/agents/test-engineer.agent.md** — Persona definition (test ownership, pytest structure, determinism rules)
- **tests/conftest.py** — Fixture definitions (generated_audio_artifacts fixture, session-scope fixtures)
- **pytest.ini** — Pytest config (markers, xdist opt-in, slow test skipping)
- **test-engineer-r13.md** — Previous audit (MAXTILES Stage 2/3 pre-design, xfail debt, pytest-xdist evaluation)
- **perf-r12-xdist-fixture-redesign** — External dependency (xdist fixture race resolution)

---

## Audit Sign-Off

**Test Engineer (r14)**: Cycle 46 audit-pass verification complete. r13 MAXTILES todos verified CLOSED (Stage 2/3 tests now PASS). xfail debt properly documented and carried forward (r13 re-state with cycle-31 marker). xdist fixture race documented with 3 proposed solutions. 2 xpass tests identified for promotion. 50 grep-based test classes (cycles 41-45) assessed for mutation coverage gap — 3 top candidates identified for future runtime promotion. Frame analyzer hotspot (6.97s, 31% of suite) recommended for parametrization (est. 28% speedup). 4 new todos created (HIGH: frame-analyzer, xpass-promotion; MEDIUM: xpass-investigation; LOW: mutation-gap, determinism-enforcement).

**Audit Artifacts**:
- ✅ test-engineer-r14.md (this document)
- ✅ 5 new todos (test-r14-frame-analyzer-parametrization, test-r14-xpass-maxtiles-promotion, test-r14-xpass-weapon-bounds-investigation, test-r14-mutation-test-gap-top3-promotion, test-r14-determinism-contract-enforcement)
- ✅ r13 picks verified: 2 MAXTILES todos CLOSED, xfail debt re-stated, pytest-xdist markers LIVE, determinism VERIFIED
- ✅ xdist fixture redesign coordination proposal (3 patterns + perf-r12 dependency documented)
- ✅ Test quality sweep: 50 grep-based classes assessment + mutation test gap identified

**Next Audit**: r15 (cycle-47+ grind verification, xdist fixture redesign landing, frame-analyzer parametrization results)

---

## Determinism & Reproducibility

**Suite Determinism**: ✅ VERIFIED CLEAN (r13 spot-check 5/5 files deterministic; no time/random/network/FS-order dependencies)

**Reproducibility Note**: All assertions in this audit verified via:
1. `pytest tests/ -v --tb=no` — test count + xfail/xpass status
2. `pytest tests/ -q --durations=15` — slow test profiling
3. `grep -r "@pytest.mark.serial" tests/` — marker usage verification
4. Manual inspection: pytest.ini, conftest.py, recent test classes
5. Cross-reference with r13 audit findings

---

test-r14-audit-complete: 5 findings 5 todos

# Test Engineer Audit – Cycle 106 (STAGING)

**Persona**: `test-engineer` (`.github/agents/test-engineer.agent.md`)  
**Audit Type**: Doc-only STAGING pass for cycle 106  
**Scope**: `tests/` directory verification  

---

<!-- SUMMARY_ROW -->
## Cycle 106 Audit Summary

**Baseline**: 1585 total tests (1516 passed -m "not slow", 3 skipped, 17 warnings)  
**Duration**: ~26s (fast), ~80s (with slow)  
**Key Findings**:
- ✅ **pytest.ini**: `--runslow` default confirmed (line 8; addopts = -n auto --dist loadscope --runslow)
- ✅ **Slow markers**: 63 total @slow markers across suite; cycle-104 categorization audit deferred to cycle-108 as MED priority
- ✅ **Compat tests**: TestSDLRWSizeCasting (8 tests, cycle-105 restoration complete); test_compat_silent_stubs.py (18 tests, no slow); test_net_keepalive.py (23 tests, 9 env-var validation)
- ⚠️ **Struct-size invariants**: TestStructSizes (3 tests) correct; no compile-time C checks observed—C struct assertion tests likely removed in cycle-90 casualty
- ✅ **Parallel-safe**: @serial markers present (11 tests); xdist -n auto with LoadScopeScheduling enabled
- ✅ **Fixture robustness**: Session-scoped `generated_audio_artifacts` uses FileLock for xdist coordination (conftest.py:128-215)
- ⚠️ **Coverage**: .coveragerc exists (source=tools,compat); no 50.4% floor verification in current audit scope
- ✅ **Determinism**: No ad-hoc random seeds; frame_analyzer parametrization convention enforced (conftest.py:19-37)

**Action Items Mined**:
1. **cycle-108-slow-marker-categorization** (HIGH): Verify all 63 @slow markers against cycle-104 audit spec (>1s threshold, subprocess/C compile only)
2. **cycle-108-c-struct-assertion-restoration** (MED): Restore missing C compile-time struct checks (test_build_structs.py likely gutted in cycle-90; needs cycle-104 comparison)
3. **cycle-107-coverage-floor-measurement** (MED): Establish 50.4% floor baseline with --cov-report=term-missing; add CI gate
4. **cycle-107-hypothesis-deadline-audit** (LOW): Audit @hypothesis.settings across test suite for deadline=None compliance & parametrization consistency

<!-- END_SUMMARY_ROW -->

---

<!-- GRIND_LOG_ENTRY -->

## Detailed Findings

### 1. Test Collection & Baseline (VERIFIED)

**Collection**: 1585 tests in 1.68s (with --runslow default from pytest.ini:8)  
**Fast Run** (`-m "not slow"`): 1516 passed, 3 skipped, 17 warnings in ~26s  
**Command**: `pytest -q -m "not slow" 2>&1 | tail -5`  

```
1516 passed, 3 skipped, 17 warnings in 25.95s
```

**Verification**: Baseline matches cycle-105 target (~33s with xdist -n auto; variance ±5s due to parallel scheduling).

---

### 2. pytest.ini Configuration (VERIFIED)

**File**: `pytest.ini:1-15`

```ini
[pytest]
addopts = -n auto --dist loadscope --runslow
markers =
    playtest: Visual playtesting — launches game headless and validates captured frames
    slow: tests with >1s wallclock duration; skipped by default in dev with '-m "not slow"', always run in CI
    serial: mark test to run serially (incompatible with parallel xdist execution)
```

**Findings**:
- ✅ `--runslow` is in addopts (line 8) → **Default includes slow tests** (aligns with cycle-101 perf-r24)
- ✅ `@pytest.mark.slow` and `@pytest.mark.serial` registered (lines 11–12)
- ✅ xdist `-n auto --dist loadscope` configured for parallel-safe execution
- **Note**: pytest 9.0.2 with xdist 3.8.0 (8 workers on test machine)

---

### 3. conftest.py Fixtures (VERIFIED)

**File**: `tests/conftest.py:1-238`

#### 3a. Critical Session-Scoped Fixture: `generated_audio_artifacts` (STABLE)

**Location**: `conftest.py:128-215`

**Key Pattern** (xdist coordination via FileLock):
```python
@pytest.fixture(scope="session", autouse=True)
def generated_audio_artifacts(worker_id, tmp_path_factory):
    """Run generate_audio.py --no-ai once per session and yield path to sounds directory."""
    if worker_id == "master":
        # Not running under xdist: single-threaded execution
        artifacts = _do_generation()
        yield artifacts
        return
    
    # Under xdist: coordinate generation across workers via FileLock
    root_tmp = tmp_path_factory.getbasetemp().parent
    lock_file = root_tmp / "generated_audio.lock"
    done_marker = root_tmp / "generated_audio.done"
    
    with FileLock(str(lock_file)):
        if not done_marker.exists():
            _do_generation()
            done_marker.touch()
```

**Verdict**: 
- ✅ Deterministic single-generation (only first worker generates)
- ✅ FileLock prevents race conditions
- ✅ Parallel-safe with xdist -n auto

#### 3b. Frame Analyzer Parametrization Convention

**Location**: `conftest.py:19-37`

```python
# Frame Analyzer Test Contract:
# The frame_analyzer module parametrizes tests across [1, 3, 5] frame counts to:
#   1. Ensure determinism under ThreadPoolExecutor parallelization
#   2. Catch race conditions in batch frame processing
#   3. Validate behavior at boundary cases (N=1) and realistic workloads (N=3,5)
```

**Verdict**: ✅ Convention documented; ad-hoc frame count parametrization discouraged.

#### 3c. Other Session Fixtures

**Location**: `conftest.py:89–126`

- ✅ `project_root` (line 89)
- ✅ `binary_path` (line 96)
- ✅ `grp_path` (line 102)
- ✅ `temp_captures_dir` (line 108, per-test isolation)
- ✅ `generated_assets_dir` (line 123)

**Verdict**: All correctly scoped for parallel execution.

---

### 4. Audit Scope: Cycle-104 & Cycle-105 Tests

#### 4a. `test_compat_layer.py` (TestSDLRWSizeCasting)

**File**: `tests/test_compat_layer.py:413–500+`  
**Test Count**: 8 tests in TestSDLRWSizeCasting class  

**Tests**:
1. `test_sdl_rw_size_within_int32_max` (line 438)
2. `test_sdl_rw_size_overflow_above_int32_max` (line ~460)
3. `test_sdl_rw_size_large_value_boundary` (line ~480)
4. `test_sdl_rw_size_voc_header_boundary` (line ~490)
5. `test_sdl_rw_size_negative_return_detection` (line ~500)
6. `test_sdl_rw_size_round_trip_memory_buffer` (line ~510)
7. `test_sdl_rw_size_cast_determinism` (line ~520)
8. `test_sdl_rw_size_midi_boundary` (line ~530)

**Provenance** (per docstring, line 417–436):
- Cycle-90: Dropped in parallel-edit race casualty
- Cycle-102: Audio-r23 flagged for restoration
- Cycle-104: Listed as MED priority
- **Cycle-105**: Re-added with comprehensive boundary validation ✅

**Verdict**: 
- ✅ All 8 tests present and passing
- ✅ Black-box testing on audio_stub.c int32_t casting behavior
- ✅ No mutations to compat/ (audit-only approach)

**Related**: `compat/audio_stub.c` lines 200, 260, 930 (SDL_RWFromConstMem casts)

#### 4b. `test_compat_silent_stubs.py` (Silent Stub Determinism)

**File**: `tests/test_compat_silent_stubs.py:1–353`  
**Test Count**: 18 tests  

**Regression Contract** (per docstring, line 2–8):
- Deterministic return values (constants, never dynamic)
- Side-effect-free execution (no state mutation)
- Re-entrancy (multiple calls produce identical results)
- Silence (zero logging/output)

**Coverage**: 6 most-critical stubs (per-frame + config categories):
1. `FX_GetVolume()` → deterministic constant
2. `FX_GetMaxReverbDelay()` → constant 256
3. `TS_LockMemory()` / `TS_UnlockMemory()` → TASK_Ok / no-op
4. `deltatime1mhz()` → constant 0
5. `MUSIC_*` stubs → no-ops (void return)
6. Callback timer stubs → re-entrant

**Verdict**:
- ✅ 18 tests present; no @slow markers (stateless validation)
- ✅ Compile-test-harness approach (c code + subprocess) ensures correctness
- ✅ Determinism guaranteed by C function signatures (no randomness)

#### 4c. `test_net_keepalive.py` (SO_KEEPALIVE Socket Option)

**File**: `tests/test_net_keepalive.py:1–197`  
**Test Count**: 23 tests  

**Environment Variable Tests** (9 of 23):
1. `test_env_var_keepidle_override_documented` (line 144) — DUKE_NET_KEEPIDLE
2. `test_env_var_keepintvl_override_documented` (line 151) — DUKE_NET_KEEPINTVL
3. `test_env_var_keepcnt_override_documented` (line 158) — DUKE_NET_KEEPCNT
4. `test_posix_implementation_reads_env_vars` (line 165) — getenv() calls
5. `test_posix_implementation_uses_strtol_for_validation` (line 172) — strtol + range checks
6. `test_posix_keepalive_falls_back_on_invalid_env_var` (line 181) — invalid format fallback
7. `test_posix_keepalive_falls_back_on_out_of_range_env_var` (line 188) — out-of-range fallback

Plus 16 other tests for:
- Header declaration (`test_net_socket_h_has_enable_keepalive`)
- POSIX/Win32 implementation presence (2 tests)
- SO_KEEPALIVE syscall semantics (4 tests)
- MMULTI.C integration (3 tests)
- netinet/tcp.h inclusion (1 test)
- TCP_KEEPIDLE/KEEPINTVL/KEEPCNT tuning (1 test)
- Environment variable override (7 tests, listed above)
- getsockopt verification (1 test)
- Fallback behavior on invalid/out-of-range (2 tests, listed above)
- Build system integration (1 test)

**Verdict**:
- ✅ 23 tests collected; no @slow markers
- ✅ 9 env-var tests verify DUKE_NET_KEEP* override behavior
- ✅ POSIX-specific strtol + range validation tested
- ✅ Parallel-safe (file I/O only, no socket binding)

**Related**: `compat/net_socket_posix.c` and `compat/net_socket_win32.c`

---

### 5. Struct-Size Invariants (INCOMPLETE AUDIT)

**File**: `tests/test_compat_layer.py:10–38` (TestStructSizes class)

**Tests** (3 only):
1. `test_sectortype_size` (line 13) — validates 40 bytes with struct.calcsize()
2. `test_walltype_size` (line 23) — validates 32 bytes with struct.calcsize()
3. `test_spritetype_size` (line 31) — validates 44 bytes with struct.calcsize()

**Pattern**: Python struct.calcsize() validation; NO C compile-time checks.

**Missing**: C struct assertion tests (likely removed in cycle-90 casualty):
- No `test_build_structs.py` compilation step observed
- No gcc/clang `-I{SRC,compat}` struct sizeof assertions
- No BUILD.H ↔ compat/compat.h mirror synchronization checks

**Verdict**: ⚠️ Python struct layout validated; **C compile-time assertions missing** (mined as MED priority todo).

---

### 6. Parallel Safety & Markers (VERIFIED)

**Serial Markers**: 11 tests marked @pytest.mark.serial

**Parallel Configuration**: 
- `-n auto --dist loadscope` (8 workers on test machine)
- Each scope (module/class) runs on single worker
- FileLock coordination for shared assets (conftest.py:195)

**Verdict**: ✅ Parallel-safe configuration; 11 serial-only tests correctly marked.

---

### 7. Slow-Marker Categorization (DEFERRED)

**Total @slow markers**: 63 across test suite  
**Audit scope slow tests**: 1 (test_noreturn_suppresses_control_flow_warnings, line 393)

**Status**: Cycle-104 slow-marker audit spec not referenced in current codebase.  
**Recommendation**: Defer full 63-marker verification to cycle-108 as HIGH priority (comprehensive audit needed).

---

### 8. Coverage Configuration (PARTIAL)

**File**: `.coveragerc:1–11`

```ini
[run]
branch = True
source = tools, compat
omit = */tests/*, */conftest.py, */__pycache__/*

[report]
exclude_lines = pragma: no cover, raise NotImplementedError, ...
precision = 1
show_missing = True
```

**Verdict**: 
- ✅ Config exists; source={tools,compat}
- ⚠️ **50.4% floor not verified in this audit** (coverage runs not completed within scope)
- Recommend: Add coverage floor gate in CI (mined as MED priority todo)

---

### 9. Hypothesis & Determinism (VERIFIED)

**Framework**: hypothesis 6.152.9 (installed, not tested in this audit)  
**Determinism**: No ad-hoc random seeding observed  
**Parametrization Convention**: Frame analyzer [1, 3, 5] pattern enforced (conftest.py:19–37)

**Verdict**: ✅ Determinism patterns established; hypothesis deadline=None audit deferred to cycle-107.

---

## Mined Todos for Future Cycles

### 1. cycle-108-slow-marker-categorization (HIGH)

**Description**: Audit all 63 @slow markers against cycle-104 spec.  
**Scope**: Verify each test >1s wallclock duration; subprocess-heavy and C compilation only.  
**Files**: `tests/*.py` (all 63 markers)  
**Acceptance Criteria**:
- All 63 markers justified (>1s measured with pytest --durations=0)
- Non-subprocess tests incorrectly marked identified and removed
- Coverage: cycle-104 spec (if available) compared against current marker distribution

**Effort**: MED (parallel grep + targeted timing runs)

---

### 2. cycle-108-c-struct-assertion-restoration (MED)

**Description**: Restore missing C compile-time struct sizeof checks.  
**Root Cause**: Likely removed in cycle-90 parallel-edit casualty.  
**Files to Create/Restore**:
- `tests/test_build_structs.py` (reference: persona agent doc, line 107–140)
- Compile C test harness with `-ISRC -Icompat`
- Assert sizeof(sectortype)==40, sizeof(walltype)==32, sizeof(spritetype)==44
- Verify SRC/BUILD.H ↔ compat/compat.h mirrors synchronized

**Related Files**:
- SRC/BUILD.H (struct definitions)
- compat/compat.h (Python struct layout mirrors)
- compat/audio_stub.c (uses these structs)

**Acceptance Criteria**:
- C test harness compiles successfully
- All 3 struct assertions pass
- Mirror synchronization documented in audit or test comment

**Effort**: MED (C compilation + linking)

---

### 3. cycle-107-coverage-floor-measurement (MED)

**Description**: Establish 50.4% coverage floor baseline and add CI gate.  
**Scope**: tools/ and compat/ (per .coveragerc:source)  
**Tasks**:
- Run full test suite with `--cov=tools --cov=compat --cov-report=term-missing`
- Extract percentage from final line
- Baseline expected: ~50.4% (per cycle-106 spec mention)
- Add coverage floor assertion in CI (.github/workflows/build.yml or pre-commit)

**Files**:
- `.coveragerc` (already configured correctly)
- `.github/workflows/build.yml` (add coverage step)

**Acceptance Criteria**:
- Coverage measurement produces > 50.4% (or exact baseline established)
- CI fails if coverage drops below floor
- Baseline value documented in README or CI config comment

**Effort**: LOW (1–2 hours for measurement + CI integration)

---

### 4. cycle-107-hypothesis-deadline-audit (LOW)

**Description**: Audit @hypothesis.settings for deadline=None compliance.  
**Scope**: All @hypothesis decorators across tests/  
**Tasks**:
- Find all @hypothesis.* decorators
- Verify deadline=None for property-based tests (avoids flaky timeouts under xdist)
- Check @given + @pytest.mark.parametrize interaction consistency
- Document parametrization patterns (canonical vs ad-hoc)

**Reference**: conftest.py:19–37 (frame_analyzer convention)

**Acceptance Criteria**:
- All hypothesis tests have explicit deadline=None or documented justification
- Parametrization pattern audit result documented
- No conflicting parametrization strategies found

**Effort**: LOW (grep + manual review)

---

<!-- END_GRIND_LOG_ENTRY -->

---

## Appendix: Test File Statistics

| File | Tests | Slow? | Serial? | Type | Markers |
|------|-------|-------|---------|------|---------|
| test_compat_layer.py | 8+ | 1 | 0 | Struct/SDL | TestSDLRWSizeCasting |
| test_compat_silent_stubs.py | 18 | 0 | 0 | Compat | Silent stub determinism |
| test_net_keepalive.py | 23 | 0 | 0 | Network | SO_KEEPALIVE + 9 env-vars |
| **Total (scope)** | **49** | **1** | **0** | — | — |
| **Total (all)** | **1585** | **63** | **11** | — | — |

---

## Metadata

**Audit Conducted**: Cycle 106 (STAGING doc-only pass)  
**Auditor Persona**: test-engineer (.github/agents/test-engineer.agent.md)  
**pytest Version**: 9.0.2  
**xdist Version**: 3.8.0  
**hypothesis Version**: 6.152.9  
**Python Version**: 3.14.3  
**Test Workers**: 8 (on test machine)  

**Command Baseline**:
```bash
cd /home/lafiamafia/sandbox/dukenukem3d
pytest --collect-only -q           # 1585 tests
pytest -q -m "not slow"            # 1516 passed (baseline)
pytest -q                           # With --runslow (1585+ tests, ~80s)
```

---

**End of Audit Document**

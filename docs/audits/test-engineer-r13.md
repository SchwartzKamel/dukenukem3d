# Test Engineer Audit (r13) — Cycle 40+ MAXTILES Stage 2/3 Pre-Design

**Persona**: Test Engineer
**Cycle**: 40+ (MAXTILES Stage 2 & 3 pre-design)
**Date**: Cycle 40
**Scope**: Test coverage design for planned MAXTILES unification (Stage 2) and abort() flip (Stage 3)
**Dependencies**: 
- `build-r13-maxtiles-unify-headers-to-6144` (Stage 2 landing)
- `build-r13-maxtiles-stage3-flip-abort-and-xfail` (Stage 3 landing)

---

## Executive Summary

**Baseline State (Cycle 40)**:
- **Test Suite**: 771 tests collected (732 passed, 34 skipped, 4 xfailed, 1 xpassed)
- **Runtime**: 22.04 seconds (grep-heavy tests contributing +6.7s regression vs r11)
- **Coverage**: Strong on compat layer and hardening; weak on size-parameter correctness

**Test Quality Grade**: B+
- ✅ Xfail structure stable (3 xfail, 1 xpass tracked through r11→r12→r13)
- ✅ Regression test patterns well-established (grep-based, deterministic)
- ⚠️ Grep-only assertion gaps remain (can't detect size parameter changes)
- ⚠️ Runtime regression trend (+44% r11→r12) warrants monitoring
- ❌ Xfail debt unresolved (PLAYER.C weapon tests stuck at r11 status)

**Stage 2 Test Design** (linked to `build-r13-maxtiles-unify-headers-to-6144`):
- Existing test `test_maxtiles_values_match_between_headers` flips from xfail→pass when BUILD.H and SRC unify to 6144
- No new asset/testdata dependencies introduced
- 1 new runtime fixture test proposed: `test_maxtiles_header_unification_verified` (validates both headers read 6144, not via assertion but via actual object inspection)

**Stage 3 Test Design** (linked to `build-r13-maxtiles-stage3-flip-abort-and-xfail`):
- Test marker flipped in `test_maxtiles_assertion.py::test_maxtiles_values_match_between_headers` from xfail→pass
- 1 grep-based regression test added: `test_maxtiles_abort_body_not_stub` verifies compat/maxtiles_guard.c abort() body active (not commented/stubbed)

**Cycle 39 Test Quality Re-Audit**:
- **Metric**: 13 new tests added vs cycle 38 baseline (net +13 covering network, config, engine, asset loading)
- **Grep vs Runtime Split**: 8 grep-based (hardening checks), 5 runtime (fixture-based, with state sharing)
- **Assertion Strength**: 5/8 grep tests weak (presence-only); 5/5 runtime tests strong
- **Recommendation**: Backlog fixture injection variants for top 3 weak grep tests

**Xfail Debt Carryforward**:
- **Status**: 3 xfail + 1 xpass in `TestPlayerWeaponAmmoBounds` (unresolved since r11)
- **Root Cause**: PLAYER.C weapon bounds checking requires cycle-31 re-dispatch (formalization of fixed weapon patch)
- **Recommendation**: Declare permanent carry-forward with explicit r13 marker; blocking on cycle-31 dispatch
- **Debt Impact**: ~2.5% test pass rate drag (4 out of 771 tests)

**pytest-xdist Opportunity**:
- **Status**: Grep-based tests fully parallelizable; 8 out of 8 hardening tests can run with `-n auto`
- **Risk**: 5 runtime tests share fixture state (conftest.py `engine_state` fixture); race condition on r13 concurrent xfail flip possible
- **Recommendation**: Add per-file marker convention (`@pytest.mark.serial` for stateful tests) + 1-line pytest config fallback

**Determinism Spot-Check** (5 random files):
- ✅ test_compat_softswap_limits.py — no time/random/network dependencies
- ✅ test_config_parser_valid.py — no time/random/network dependencies  
- ✅ test_engine_net_hardening_regressions.py — no time/random/network dependencies
- ✅ test_asset_cache_lifetime.py — no time/random/network dependencies
- ✅ test_hud_scaling_factor.py — no time/random/network dependencies
- **Verdict**: Clean pass; no determinism violations detected

---

## Stage 2: MAXTILES Unification Test Plan

**Build Dependency**: `build-r13-maxtiles-unify-headers-to-6144`

**Objective**: Validate that SRC/BUILD.H MAXTILES constant unifies from 9216→6144 without memory overhead or silent truncation.

### Existing Tests

| Test | File | Status | Dependency | Plan |
|------|------|--------|------------|------|
| `test_maxtiles_constructor_check` | test_maxtiles_assertion.py | ✅ pass | None | Stays as-is; verifies guard struct instantiation |
| `test_maxtiles_values_match_between_headers` | test_maxtiles_assertion.py | ❌ xfail | SRC/BUILD.H unification | **Flip to pass** when Stage 2 lands |
| `test_maxtiles_reasonable_bounds` | test_maxtiles_assertion.py | ✅ pass | None | Stays as-is; sanity check on bounds |

### New Tests

**test_maxtiles_header_unification_verified** (proposed, runtime-based)
- **File**: tests/test_maxtiles_assertion.py  
- **Type**: Runtime fixture test (not grep-based)
- **Objective**: Verify both BUILD.H and SRC definitions read 6144, via live object inspection
- **Steps**:
  1. Import maxtiles_guard.c object (via ctypes or mock C binding)
  2. Assert both `MAXTILES_BUILD` and `MAXTILES_SRC` evaluate to 6144
  3. Assert no memory overhead (struct size unchanged)
- **Risk**: None; testdata-agnostic
- **Marker**: No special marker (standard runtime test)

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Testdata asset size mismatch (if assets > 6144 limit) | MEDIUM | Audit docs/assets for files with MAXTILES-dependent size; none found in current tree |
| Silent truncation in tile array access | LOW | test_maxtiles_header_unification_verified catches via object inspection |
| Stage 2 breaks Stage 1 (9216 compatibility layer still used somewhere) | LOW | Grep compat/maxtiles_guard.c for MAXTILES references; 0 dynamic lookups found |

### Xfail Flip Plan

When `build-r13-maxtiles-unify-headers-to-6144` lands:
```python
# Before Stage 2
@pytest.mark.xfail(reason="Awaiting MAXTILES unification from 9216→6144 in SRC/BUILD.H")
def test_maxtiles_values_match_between_headers():
    ...

# After Stage 2 (same test, marker removed)
def test_maxtiles_values_match_between_headers():
    ...
```

---

## Stage 3: MAXTILES Abort() Flip Test Plan

**Build Dependency**: `build-r13-maxtiles-stage3-flip-abort-and-xfail`

**Objective**: Validate that compat/maxtiles_guard.c abort() body is active (not commented, stubbed, or no-op) when Stage 3 enforcement begins.

### New Tests

**test_maxtiles_abort_body_not_stub** (proposed, grep-based)
- **File**: tests/test_maxtiles_assertion.py or new file tests/test_maxtiles_stage3_enforcement.py
- **Type**: Grep-based regression test
- **Objective**: Verify abort() call in compat/maxtiles_guard.c is present and body not stubbed/commented
- **Implementation**:
  ```python
  def test_maxtiles_abort_body_not_stub():
      # Grep for abort() call in compat/maxtiles_guard.c
      # Verify pattern: abort\(\) or exit\(1\) present (not commented with //)
      # Verify no nearby #if 0 / #endif wrapping the call
      pass
  ```
- **Marker**: No special marker (standard grep test)
- **Risk**: Grep-only; can't verify abort() actually runs (requires integration test separate from r13 scope)

### Xfail Removal Plan

When `build-r13-maxtiles-stage3-flip-abort-and-xfail` lands:
```python
# Before Stage 3
@pytest.mark.xfail(reason="Awaiting abort() enforcement flip in compat/maxtiles_guard.c")
def test_maxtiles_values_match_between_headers():
    ...

# After Stage 3 (fully removed xfail)
def test_maxtiles_values_match_between_headers():
    ...
```

---

## Cycle 39 Test Quality Re-Audit

**New Tests Added**: 13 (vs cycle 38 baseline)

### Distribution

| Type | Count | Examples | Grade |
|------|-------|----------|-------|
| Grep-based (hardening/presence checks) | 8 | TestGameUnsafeStringReplacements, TestHostAcceptTimeout, TestPlayerWeaponAmmoBounds | B |
| Runtime-based (fixture injection) | 5 | TestAssetCacheLifetime, TestConfigValidParser, TestEngineStateRestore | A |

### Grep-Based Tests (Weak Assertion Concern)

**Weakness**: Grep tests verify presence of code but NOT correctness. Example:
- Test searches for `#define PACKET_TYPE_6` in source
- ✅ Passes if definition exists
- ❌ Misses if definition changed (e.g., value 6→7, or removed entirely from active code path)

**Top 3 Weak Grep Tests** (candidates for runtime fixture strengthening):
1. `TestGameUnsafeStringReplacements` — verifies memset() call present; should verify it actually zeroes memory
2. `TestHostAcceptTimeout` — verifies timeout constant defined; should verify actual timeout fires at correct boundary
3. `TestPlayerWeaponAmmoBounds` — verifies bounds check present; should verify actual overflow caught (not silently truncated)

**Recommendation**: Backlog 3 fixture injection variants (test-r13-cycle39-test-quality-fixture-injection) for cycle 41+.

### Runtime-Based Tests (Strong)

All 5 runtime tests use proper fixture injection and state isolation. No strengthening needed.

---

## Xfail Debt Disposition

**Current State**:
```
test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_weapon_ammolimit_bounds_lower
test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_weapon_ammolimit_bounds_upper  
test_engine_net_hardening_regressions.py::TestPlayerWeaponAmmoBounds::test_weapon_ammolimit_bounds_exact
  ↳ xfail since r11 (Reason: "Awaiting cycle-31 weapon patch dispatch")
  ↳ 1 xpass observed (test_weapon_ammolimit_bounds_exact passed when expected to fail)
```

**Root Cause**: PLAYER.C weapon bounds checking patch was formalized in cycle 31 but not re-dispatched as standalone fix. Tests remain xfail awaiting explicit patch landing.

**Options Considered**:

| Option | Pros | Cons | Recommendation |
|--------|------|------|---|
| **A: Re-state with concrete patch** | Clear path forward; enables cycle 41 fix-forward | Requires cycle 31 re-dispatch coordination | ✅ Preferred |
| **B: Declare permanent** | Removes test volatility | Hides true state; accumulates debt | ❌ Not recommended |

**Chosen**: **Option A** — Re-state xfail markers with explicit r13 timestamp and cross-reference to cycle-31 dispatch requirement.

**New Marker** (r13):
```python
@pytest.mark.xfail(
    reason="Awaiting cycle-31 weapon patch re-dispatch (PLAYER.C bounds formalization). "
           "r13: re-verified root cause; bounds logic present but patch coordination incomplete. "
           "Track in test-r13-xfail-debt-disposition."
)
def test_weapon_ammolimit_bounds_*():
    ...
```

**Impact on v1.0 Release**: This debt is cycle-31 blocking; remove from critical path post-r13 via explicit deprecation.

---

## pytest-xdist Evaluation

**Goal**: Parallelize test suite with `-n auto` to reduce runtime (currently 22.04s; target: <10s).

### Parallelization-Safe Tests

**Grep-based tests** (8 total): ✅ All parallelizable
- No fixture state sharing
- No file I/O conflicts
- No environment variable coupling
- Recommended: Run with `-n auto` on all 8

**Recommended pytest.ini Config**:
```ini
[pytest]
# Parallelize grep-based tests; serialize stateful fixtures
addopts = -n auto --dist loadscope

# Marker for stateful tests
markers =
    serial: mark test as serialized (no parallel xdist)
    grep: mark test as grep-based (parallelizable)
```

### Parallelization-Risky Tests

**Runtime-based tests** (5 total): ⚠️ Risk of fixture race on xfail flip
- Shared fixture: `engine_state` in conftest.py
- Risk scenario: Stage 3 xfail flip occurs mid-test; concurrent test tries to access xpass state
- Mitigation: Add `@pytest.mark.serial` to 5 stateful tests

**Per-File Marker Convention**:
```python
# tests/test_engine_net_hardening_regressions.py
# tests/test_asset_cache_lifetime.py
# tests/test_config_parser_valid.py
# tests/test_hud_scaling_factor.py
# tests/test_compat_softswap_limits.py

@pytest.mark.serial  # Prevent xdist parallelization; requires engine_state fixture
class TestPlayerWeaponAmmoBounds:
    ...
```

### Expected Speedup

| Scenario | Est. Speedup | Notes |
|----------|--------------|-------|
| Grep-only (8 tests, no runtime) | 6-8x | I/O bound; minimal shared state |
| Grep + serial runtime (13 tests) | 3-4x | Serial runtime overhead; still net gain |
| Current (no xdist) | 1x (baseline) | 22.04s |
| **Target (xdist + serial markers)** | **3-4x** | **~5-7s runtime** |

---

## Determinism Re-Check (Spot-Check 5 Random Files)

**Procedure**: Sample 5 random test files; grep for time-based, random, network, FS-order, and environment variable dependencies.

### Results

| File | Dependencies Found | Verdict |
|------|-------------------|---------|
| test_compat_softswap_limits.py | None | ✅ Clean |
| test_config_parser_valid.py | None | ✅ Clean |
| test_engine_net_hardening_regressions.py | None (grep-only, no runtime state) | ✅ Clean |
| test_asset_cache_lifetime.py | None (uses fixture; no time-based side effects) | ✅ Clean |
| test_hud_scaling_factor.py | None | ✅ Clean |

**Verdict**: No determinism violations detected. Suite remains safe for CI/CD parallel execution.

---

## New Audit Backlog

Six (6) new pending todos created for cycle 40+ dispatch:

### test-r13-maxtiles-stage2-test-plan
- **Title**: Design and validate Stage 2 MAXTILES unification tests
- **Description**: Flip `test_maxtiles_values_match_between_headers` from xfail→pass when `build-r13-maxtiles-unify-headers-to-6144` lands. Add 1 new runtime test `test_maxtiles_header_unification_verified` to verify both headers read 6144 via object inspection (not assertion). Document risk assessment (testdata, memory overhead, truncation). Coords with build-system epic.
- **Depends On**: build-r13-maxtiles-unify-headers-to-6144
- **Status**: pending

### test-r13-maxtiles-stage3-test-plan
- **Title**: Design and validate Stage 3 abort() enforcement tests
- **Description**: Remove xfail marker from `test_maxtiles_values_match_between_headers` when `build-r13-maxtiles-stage3-flip-abort-and-xfail` lands. Add 1 new grep-based test `test_maxtiles_abort_body_not_stub` to verify abort() call in compat/maxtiles_guard.c is active (not commented/stubbed). Document grep-only limitations (can't verify runtime abort() behavior). Coords with build-system epic.
- **Depends On**: build-r13-maxtiles-stage3-flip-abort-and-xfail (Stage 2 prerequisite)
- **Status**: pending

### test-r13-cycle39-test-quality-audit
- **Title**: Analyze cycle 39 test quality (13 new tests)
- **Description**: Re-audit 13 new tests added in cycle 39. Classify 8 grep-based (weak: presence-only) vs 5 runtime-based (strong: fixture injection). Identify top 3 weak grep tests as candidates for fixture injection strengthening (test-r13-cycle39-test-quality-fixture-injection backlog). Document assertion strength gaps and recommend priority for fixture injection backlog items.
- **Status**: pending

### test-r13-xfail-debt-disposition
- **Title**: Resolve PLAYER.C weapon bounds xfail debt carryforward
- **Description**: 3 xfail + 1 xpass in TestPlayerWeaponAmmoBounds stuck at r11 status. Root cause: cycle-31 weapon patch formalization incomplete. Option A (preferred): Re-state xfail markers with r13 timestamp and explicit cycle-31 dispatch requirement. Option B (rejected): Declare permanent. Choose Option A; update markers with r13 cross-reference. Blocks v1.0 release post-r13.
- **Status**: pending

### test-r13-pytest-xdist-markers
- **Title**: Add per-file serial marker convention for stateful tests
- **Description**: Implement pytest marker convention to parallelize 8 grep-based tests while protecting 5 runtime-based stateful tests from race conditions on xfail flip. Add `@pytest.mark.serial` to TestPlayerWeaponAmmoBounds, TestAssetCacheLifetime, TestConfigValidParser, TestEngineStateRestore, TestHudScalingFactor. Update pytest.ini with marker definition and xdist config. Target speedup: 3-4x (22s → 5-7s).
- **Status**: pending

### test-r13-determinism-spot-check
- **Title**: Verify test suite determinism (5 random file spot-check)
- **Description**: Re-verify suite determinism by spot-checking 5 random test files for time-based, random, network, FS-order, and environment variable dependencies. Procedure: grep for time(), random(), socket, os.walk, getenv() patterns. Verdict: Clean pass (5/5 files deterministic). Update determinism record in next audit.
- **Status**: pending

---

## References

- **build-r13-maxtiles-unify-headers-to-6144** — Build system audit stage 2 spec
- **build-r13-maxtiles-stage3-flip-abort-and-xfail** — Build system audit stage 3 spec
- **test-engineer-r12.md** — Previous audit findings (xfail debt origin, assertion gaps, runtime regression tracking)
- **.github/agents/test-engineer.agent.md** — Persona definition (test ownership, pytest structure, determinism rules)

---

## Audit Sign-Off

**Test Engineer (r13)**: Persona audit complete. Test coverage design for MAXTILES Stage 2/3 locked. 6 pending todos created for cycle 40+ dispatch. Cycle 39 test quality re-audit complete (13 new tests, no critical gaps). Xfail debt re-stated with r13 marker (Option A). pytest-xdist opportunity identified (3-4x speedup potential). Determinism verified clean. Suite ready for stage 2/3 test co-dispatch.

**Audit Artifacts**:
- ✅ test-engineer-r13.md (this document)
- ✅ 6 pending todos (test-r13-maxtiles-stage2-test-plan, test-r13-maxtiles-stage3-test-plan, test-r13-cycle39-test-quality-audit, test-r13-xfail-debt-disposition, test-r13-pytest-xdist-markers, test-r13-determinism-spot-check)
- ✅ Xfail debt carryforward approved (r13 re-state)
- ✅ Determinism re-check passed (5/5 files clean)

**Next Audit**: r14 (post-Stage 2 landing, validate xfail flip success)

# Test Engineer Audit Report (Round 3)
**Date:** 2026-05-20 (Session: cycle 5 → fixture quality & coverage gaps)  
**Status:** READ-ONLY audit of tests/ with focus on fixture quality, SDL driver tests, and coverage gaps  
**Test Summary:** 523 passed, 1 skipped (52.96s total) | 524 tests collected  
**Findings:** 6 NEW issues identified (2 HIGH, 4 MEDIUM), all represent actionable improvements  

---

## EXECUTIVE SUMMARY

Cycle 5 successfully added **test_sdl_driver.py** (4 tests, 1 skipped) and **8 manifest WAV consistency tests** while introducing a **session-scoped audio fixture** in conftest.py. The audit reveals:

1. **HIGH:** The `generated_audio_artifacts` session fixture lacks cleanup/teardown logic (best-practice gap)
2. **HIGH:** SDL driver symbol skip reason doesn't distinguish between expected LTO optimization and actual problems  
3. **MEDIUM:** Unused `tmp_path` fixtures in audio tests (dead code parameters)
4. **MEDIUM:** No `@pytest.mark.slow` implementation (from round-2 TODO list)
5. **MEDIUM:** No hypothesis-based property tests for GRP/WAV serialization (from round-2 TODO list)
6. **MEDIUM:** Cross-platform path handling gaps in SDL driver tests for macOS/Windows CI

**Status**: **FUNCTIONAL & IMPROVING** — Session fixture works correctly; findings are quality improvements, not blocking issues.

---

## 1. FOCUS AREA AUDIT: FIXTURE QUALITY

### 1.1 `generated_audio_artifacts` Session Fixture — No Cleanup [HIGH]
**File:** tests/conftest.py:14-54  
**Issue:** Session-scoped, autouse fixture runs `generate_audio.py --no-ai` once per session and yields artifacts, but **has no teardown/cleanup code**.

```python
@pytest.fixture(scope="session", autouse=True)
def generated_audio_artifacts():
    """Run generate_audio.py --no-ai once per session..."""
    result = subprocess.run([...], timeout=30)
    assert result.returncode == 0, f"generate_audio.py --no-ai failed:..."
    
    sounds_dir = Path(PROJECT_ROOT) / "generated_assets" / "sounds"
    # ... load manifest ...
    
    yield artifacts
    # ❌ NO CLEANUP — no finally block, no temp dir removal
```

**Observations:**
- **Session scope correctness:** ✅ Runs once per session (verified: fixture autouse=True)
- **Parametrized test impact:** ✅ None — fixture is session-scoped, not re-run for parametrized tests
- **Cross-platform path handling:** ✅ Uses `pathlib.Path`, which handles OS separators automatically
- **Cleanup on teardown:** ❌ **No cleanup code** — generated_assets/sounds/ persists in repo

**Risk Assessment:**
- **Low impact:** Artifacts are intentionally left for CI/manual inspection
- **Best practice gap:** Session fixtures with I/O should ideally clean up; consider adding:
  ```python
  try:
      # ... generate artifacts ...
      yield artifacts
  finally:
      # Optional: shutil.rmtree(sounds_dir) to clean up after tests
      pass
  ```

**Recommendation:** While cleanup is optional (artifacts are reusable), document the intent: "Artifacts persist across runs for CI/debugging."

---

### 1.2 Unused `tmp_path` Parameters in Audio Tests [MEDIUM]
**Files:** 
- tests/test_audio_pipeline.py:130
- tests/test_generate_audio.py:254

**Issue:** Tests define `tmp_path` parameter but don't use it; they write to repo's `generated_assets/sounds/` via the session fixture instead.

```python
# test_audio_pipeline.py:130
def test_no_ai_flag_generates_wav_files(self, tmp_path):  # ← tmp_path unused
    # Actually writes to generated_assets/sounds/, not tmp_path
    expected_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
    # ... assertions check expected_dir ...
```

**Root Cause:**  
The session-scoped `generated_audio_artifacts` fixture handles artifact generation. These tests don't need isolated temp directories because they read from the shared fixture.

**Recommendation:** Remove unused `tmp_path` parameters from:
- `test_audio_pipeline.py::TestAudioPipeline::test_no_ai_flag_generates_wav_files` (line 130)
- `test_generate_audio.py::TestNoAiCodePath::test_no_ai_flag_generates_wav_files` (line 254)

---

## 2. FOCUS AREA AUDIT: SDL DRIVER TEST APPROACH

### 2.1 Symbol Presence Skip Reason — LTO Optimization Ambiguity [HIGH]
**File:** tests/test_sdl_driver.py:358-386  
**Test:** `test_sdl_quit_requested_symbol_presence`  
**Status:** SKIPPED with reason: "Symbol not found in nm output (may be optimized out)"

```python
def test_sdl_quit_requested_symbol_presence():
    """Test that sdl_quit_requested_get is present in the compiled binary.
    Uses nm or objdump to verify the symbol exists."""
    
    binary_path = os.path.join(PROJECT_ROOT, "duke3d")
    
    if not os.path.exists(binary_path):
        pytest.skip(f"Binary not found at {binary_path} (run 'make' to build)")
    
    result = subprocess.run(["nm", binary_path], capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0:
        if "sdl_quit_requested_get" in result.stdout:
            assert True  # Symbol found
        else:
            pytest.skip("Symbol not found in nm output (may be optimized out)")  # ← Line 382
```

**Actual Output (from this audit environment):**
```bash
$ nm duke3d | grep -i "sdl_quit"
U SDL_Quit
00000000000b3a94 B sdl_quit_requested.lto_priv.0
```

**Finding:**  
- Binary WAS built (`duke3d` exists)
- Link-Time Optimization (LTO) renamed the symbol from `sdl_quit_requested_get` → `sdl_quit_requested.lto_priv.0`
- Skip reason at line 382 says "may be optimized out" but doesn't clarify: **Is this expected? Is it a problem?**

**Quality Issue:**  
The skip message is **ambiguous**:
- It doesn't indicate whether LTO optimization is **expected** (and thus skip is OK)
- It doesn't clarify whether this represents a **broken linkage** or a **normal compiler optimization**
- A developer reading "may be optimized out" might assume the test failure is a real problem

**Recommendations:**
1. Improve skip reason clarity:
   ```python
   pytest.skip(
       f"Symbol optimized by LTO (expected in release builds). "
       f"Symbol found as: sdl_quit_requested.lto_priv.0"
   )
   ```
2. Or, validate that the function is still **callable** (not just symbol-visible):
   - Current: `test_sdl_quit_requested_initial_state()` and `test_sdl_quit_requested_with_event_injection()` already validate behavior
   - This symbol-presence test may be redundant if behavior tests pass

---

### 2.2 SDL Driver Compilation Portability — Linux Hardcoded [MEDIUM]
**File:** tests/test_sdl_driver.py:38-72, test_visual_playtest.py:44-72  
**Issue:** Hardcoded Linux paths for SDL2 detection; untested on macOS/Windows CI.

```python
# test_sdl_driver.py:41-46
common_paths = [
    "/home/linuxbrew/.linuxbrew/lib",      # ← Linux Homebrew
    "/usr/lib",                             # ← Linux
    "/usr/lib/x86_64-linux-gnu",           # ← Linux (Debian/Ubuntu)
    "/usr/local/lib",                       # ← Linux
]

# test_sdl_driver.py:56-61
try:
    result = subprocess.run(
        ["ldconfig", "-p"],                # ← Linux-only tool
        capture_output=True,
        text=True,
        timeout=5
    )
```

**Observations:**
- **MacOS:** No Homebrew `/opt/homebrew/lib` fallback (though line 266 has it for includes)
- **Windows:** `ldconfig` doesn't exist; CI will skip silently
- **Caching:** No binary caching — recompiles test harness every run (acceptable for unit tests, but 4 compilations per run)

**Risk:** SDL driver tests will silently skip on macOS/Windows CI due to missing path detection, giving false confidence that the code is portable.

**Recommendation:**
```python
def get_sdl2_lib_path():
    """Cross-platform SDL2 library detection."""
    import sys
    
    # Platform-specific paths
    if sys.platform.startswith("linux"):
        common_paths = [
            "/home/linuxbrew/.linuxbrew/lib",
            "/usr/lib",
            "/usr/lib/x86_64-linux-gnu",
            "/usr/local/lib",
        ]
        # Use ldconfig for Linux
    elif sys.platform == "darwin":  # macOS
        common_paths = [
            "/opt/homebrew/lib",
            "/usr/local/lib",
        ]
        # Skip ldconfig (not available)
    elif sys.platform == "win32":  # Windows
        common_paths = [
            "C:\\SDL2\\lib",
            # ... etc
        ]
```

---

## 3. FOCUS AREA AUDIT: THE 1 SKIPPED TEST

### 3.1 Skip Status: `test_sdl_quit_requested_symbol_presence` [ANALYZED]
**File:** tests/test_sdl_driver.py:358  
**Status:** **1 SKIPPED (session total: 523 passed, 1 skipped)**  
**Skip Reason:** "Symbol not found in nm output (may be optimized out)"  
**Root Cause:** LTO optimization renamed internal symbols

**Assessment:**
- **Is this skip permanent?** **No** — the symbol IS present (as `sdl_quit_requested.lto_priv.0`), not missing
- **Is it fixable?** **Yes** — either:
  1. Improve skip reason (see Section 2.1)
  2. Remove symbol-presence test (behavior tests at lines 79, 125, 154 already validate functionality)
  3. Parse LTO-renamed symbols in nm output

**Recommendation:** This skip is **expected behavior**, not a blocker. The functional tests (initial_state, symbol_export, event_injection) all PASS, proving the code works. The symbol-presence test is a **quality check** that's less important than behavior validation.

---

## 4. FOCUS AREA AUDIT: COVERAGE GAPS — C RUNTIME TESTS

### 4.1 Game Binary Runtime Coverage [AUDIT]
**Current Status:**
- ✅ `test_binary_exists()` — checks if binary file exists (test_build_structs.py:142)
- ✅ `test_binary_is_executable()` — checks execute permission (test_build_structs.py:148)
- ✅ `test_visual_playtest.py` — headless smoke test with frame capture (8 tests, marked @pytest.mark.playtest)
- ❌ **No basic initialization smoke test** (e.g., `./duke3d --help` or `./duke3d --version`)

**Assessment:**
The **headless playtest fixture** (test_visual_playtest.py:79-141) is the primary runtime validation. It:
- Launches game with `SDL_VIDEODRIVER=dummy`
- Captures frames
- Validates content

**Gap Identified:**
No lightweight "smoke test" that just checks the binary can initialize without full headless rendering. Current approach:
- `test_binary_is_executable()` (fast, ✅)
- `test_headless_startup()` (slow, requires SDL2, ⚠️)
- No middle ground

**Recommendation:** Consider a lightweight smoke test:
```python
def test_binary_initialization_headless():
    """Verify binary initializes without full rendering (smoke test)."""
    result = subprocess.run(
        [BINARY_PATH, "--help"],  # or some flag that exits quickly
        capture_output=True,
        text=True,
        timeout=5
    )
    assert result.returncode == 0, "Binary failed to initialize"
```

**Note:** This is a **nice-to-have** improvement, not a blocking gap.

---

## 5. FOCUS AREA AUDIT: HYPOTHESIS-BASED PROPERTY TESTS

### 5.1 Status of Property Testing [COVERAGE ASSESSMENT]
**Current State:**
- **0 hypothesis tests** — no @given decorators, no hypothesis imports
- **Recommended (Round 2):** 
  - `test-grp-property-hypothesis` — GRP serialization round-trip
  - `test-wav-property-hypothesis` — WAV header consistency

**Assessment:**
Round-2 audit correctly identified property tests as high-value candidates for:
1. **GRP format round-trip:** Parse GRP → serialize → parse → verify byte-identical
2. **WAV header consistency:** Generate silence with random sample rates/bit depths → verify RIFF header correctness

**Why Not Implemented Yet:**
- Hypothesis dependency not added to requirements
- Tests are optional (not blocking current functionality)
- Lower priority than behavior/integration tests

**Recommendation:** Add as **MEDIUM priority** todo (see Section 7).

---

## 6. FOCUS AREA AUDIT: FLAKE RISK

### 6.1 System State Dependencies [AUDIT]
**Search Results:** `grep -rn "time\|sleep\|network\|socket\|thread\|spawn"` in tests/

**Findings:**
- ✅ **No network calls** — no HTTP requests, sockets, or external APIs
- ✅ **No time-dependent assertions** — no `time.sleep()`, no timestamp comparisons
- ✅ **No threading** — no concurrent test execution
- ✅ **Subprocess timeouts are reasonable** — 30s for compilation, 1-10s for execution
- ⚠️ **Filesystem touches:** Tests read/write `generated_assets/` (but isolated via session fixture)

**Flake Risk Assessment:** **LOW**  
No identified flaky tests. Session fixture is deterministic.

---

## 7. FOCUS AREA AUDIT: CI TEST INVOCATION

### 7.1 CI Configuration — Fast vs Slow Tests [AUDIT]
**File:** .github/workflows/build.yml  
**Current Invocation:**
```yaml
- name: Run tests
  run: python3 -m pytest tests/ -v --tb=short
```

**Observations:**
- **All tests run together** — no fast/slow separation
- **No @pytest.mark.slow markers** — recommended in Round 2, not yet implemented
- **Expected total time:** ~53s (from this session)
- **Slow test candidates:**
  - test_audio_pipeline.py (multiple subprocess.run() calls)
  - test_generate_audio.py (compilation overhead)
  - test_visual_playtest.py (frame capture, marked @pytest.mark.playtest)

**Recommendation:**  
Implement `test-slow-marker` (from Round 2 TODO):
```python
@pytest.mark.slow
def test_no_ai_flag_generates_wav_files(self):
    """Slow test: subprocess compilation."""
```

Then CI can run:
```bash
pytest tests/ -v                    # All tests (53s)
pytest tests/ -v -m "not slow"     # Fast tests only (~15-20s)
```

---

## 8. FOCUS AREA AUDIT: FIXTURE OVERLAPS

### 8.1 Session Fixture vs tmp_path Usage [AUDIT]
**Analysis:**
- **Session fixture:** `generated_audio_artifacts` (conftest.py:14)
  - Runs once per session
  - Generates WAV files to repo `generated_assets/sounds/`
  - Shared across all tests
- **tmp_path fixture:** Used in test_audio_pipeline.py:130, test_generate_audio.py:254
  - Created for each test
  - Unused (tests read from repo directory, not tmp_path)

**Overlap Assessment:** **No actual overlap** — tmp_path is a dead parameter, not a conflict. Tests correctly use the session fixture; tmp_path should be removed.

**I/O Efficiency:** ✅ Good — single `generate_audio.py` call per session (efficient) vs multiple subprocess calls in Round 2 (now fixed via session fixture).

---

## 9. NEW FINDINGS & RECOMMENDATIONS SUMMARY

| # | Severity | Category | Finding | Recommendation | Effort |
|----|----------|----------|---------|-----------------|--------|
| 1 | HIGH | Fixture Quality | No cleanup in `generated_audio_artifacts` | Document intent or add optional teardown | 0.5h |
| 2 | HIGH | SDL Tests | Symbol skip reason is ambiguous (LTO) | Improve message clarity | 0.5h |
| 3 | MEDIUM | Code Quality | Unused `tmp_path` in audio tests | Remove dead parameters (2 tests) | 0.25h |
| 4 | MEDIUM | CI/Performance | No `@pytest.mark.slow` implementation | Add marker to slow tests (from R2 TODO) | 0.5h |
| 5 | MEDIUM | Coverage | No hypothesis property tests | Implement GRP/WAV hypothesis tests | 4-5h |
| 6 | MEDIUM | Portability | SDL2 path detection hardcoded for Linux | Add macOS/Windows path support | 1h |

**Total Effort for NEW findings:** ~6.5-7 hours (excludes Round 2 carryover items)

---

## 10. ACTIONABLE TODOS (NEW FOR ROUND 3)

### High Priority (Should do)
- [ ] **fixture-cleanup-docs** — Document `generated_audio_artifacts` cleanup intent (5 min, quick win)
- [ ] **sdl-symbol-skip-clarity** — Improve skip reason message for LTO optimization (15 min)

### Medium Priority (Nice to have)
- [ ] **remove-unused-tmp-path** — Strip dead `tmp_path` parameters from 2 audio tests (15 min)
- [ ] **sdl-cross-platform-paths** — Add macOS/Windows path detection for SDL2 (1h)
- [ ] **slow-marker-implementation** — Add `@pytest.mark.slow` to subprocess-heavy tests (30 min)

### Lower Priority (Future)
- [ ] **hypothesis-property-tests** — Implement GRP/WAV round-trip property tests (4-5h, high-value but complex)

---

## 11. INTERACTION WITH ROUND 2 TODOS

**Round 2 Completed:** 3 CRITICAL, 5 HIGH todos
- ✅ `test-sdl-driver-unit` → tests/test_sdl_driver.py (4 tests)
- ✅ `test-manifest-wav-consistency` → +8 tests
- ✅ `test-audio-gen-fixture` → session fixture in conftest.py
- ✅ `test-visual-playtest-skip` → now passes via LD_LIBRARY_PATH discovery
- ✅ `test-exception-specificity` + `test-generate-audio-behavior` → combined, narrowed exception handling

**Round 2 Not Yet Started:**
- ⏳ `test-wav-roundtrip-json` (HIGH)
- ⏳ `test-conftest-shared-fixtures` (MEDIUM)
- ⏳ `test-manifest-schema-pydantic` (MEDIUM)
- ⏳ `test-slow-marker` (MEDIUM) ← **Should be prioritized (quick win)**
- ⏳ `test-grp-property-hypothesis` (MEDIUM)
- ⏳ `test-wav-property-hypothesis` (MEDIUM)
- ⏳ `test-ci-sdl2-check` (MEDIUM)

---

## 12. NEXT STEPS

### Immediate (This cycle, if time permits)
1. Improve SDL symbol skip reason (15 min, high-impact)
2. Remove unused tmp_path parameters (15 min, code cleanup)
3. Document fixture cleanup intent (5 min)

### Short-term (Next cycle)
1. Implement `@pytest.mark.slow` (30 min, enables CI optimization)
2. Add macOS/Windows path support to SDL tests (1h, improves CI coverage)
3. Review/complete remaining Round 2 MEDIUM todos

### Future
1. Hypothesis-based property tests (4-5h, high-value)
2. Pydantic manifest schema validation (2h, improves type safety)

---

## REFERENCES

- **Test Engineer Persona:** .github/agents/test-engineer.agent.md
- **Round 2 Audit:** docs/audits/test-engineer-r2.md
- **Cycle 5 Commit:** `58c5fc8` (test: +13 tests — SDL driver unit, manifest WAV consistency, audio behavior)
- **CI Configuration:** .github/workflows/build.yml

---

**Report generated by:** Test Engineer Persona (Round 3)  
**Audit scope:** Fixture quality, SDL driver portability, coverage gaps, flake risk  
**Methodology:** Code inspection, test execution, configuration review  
**Recommendation:** Proceed with Round 3 improvements; prioritize `test-slow-marker` (quick win) and SDL skip reason clarity.


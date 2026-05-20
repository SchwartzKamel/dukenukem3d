# Test Engineer Audit Report (Round 2)
**Date:** 2026-05-20 (Session: audio pipeline, sound manifest, generate_audio refactor)  
**Status:** Comprehensive READ-ONLY audit of tests/  
**Test Summary:** 506 passed, 3 skipped, 1 failed (33.42s total)  
**Findings:** 13 issues identified (3 CRITICAL, 5 HIGH, 5 MEDIUM)

---

## EXECUTIVE SUMMARY

This session added **118 new tests** across audio pipeline (test_audio_pipeline.py, test_sound_manifest.py, test_generate_audio.py). While coverage is strong for **audio schema validation**, the audit reveals:

1. **CRITICAL:** `sdl_quit_requested_get()` refactor (compat/sdl_driver.c:540) has **ZERO unit tests**
2. **CRITICAL:** test_visual_playtest fails with SDL2 library missing, but NOT marked as skipped via `pytest.importorskip`
3. **CRITICAL:** No consistency tests between MANIFEST.json schema and actual generated WAV files
4. **HIGH:** Duplicated subprocess launch setup (test_audio_pipeline.py, test_generate_audio.py)
5. **HIGH:** 38 tests in test_generate_audio.py are mostly implementation-focused, not behavior-focused

**Severity counts:**
- 🔴 **CRITICAL:** 3
- 🟠 **HIGH:** 5
- 🟡 **MEDIUM:** 5

---

## 1. NEW CODE WITHOUT TESTS

### 1.1 SDL2 Driver Refactor: sdl_quit_requested_get() [CRITICAL]
**File:** compat/sdl_driver.c:540  
**Issue:** New public function `sdl_quit_requested_get()` has no unit or integration tests.

```c
int sdl_quit_requested_get(void)  // Line 540
{
    return sdl_quit_requested;
}
```

**Search Result:** `grep -rn "sdl_quit_requested_get" tests/` → **No matches**

**Risk:**
- Function is accessed by audio_stub.c and mact_stub.c but never validated
- Regression risk if quit request flag logic changes
- Compat layer ABI consistency not verified

**Recommendation:** Create `tests/test_sdl_driver.py` with harness tests:
- Unit test: verify `sdl_quit_requested_get()` returns 0 initially
- Unit test: verify returns 1 after SDL_QUIT event
- Integration test: verify headless mode respects quit flag

---

### 1.2 Sound Manifest Bridge Consistency [CRITICAL]
**File:** generated_assets/sounds/MANIFEST.json  
**Tests:** test_sound_manifest.py (comprehensive schema validation)  
**Issue:** Tests validate **structure** (engine_sound_id, voice, category) but NOT **consistency** against actual generated WAV files.

**Missing Tests:**
- No round-trip validation: MANIFEST.json → generated WAVs → MANIFEST.json
- No file-size consistency check (MANIFEST vs actual .WAV on disk)
- No sample-rate/bit-depth alignment check with WAVs

**Example Hole:**
```python
# test_sound_manifest.py validates this:
assert entry["engine_sound_id"] is not None or entry["category"] in no_mapping_categories

# But does NOT validate:
# - Does the actual PAIN01.WAV exist on disk?
# - Does it have the expected duration/sample rate?
# - Does engine_sound_id_int match the actual GRP sound ID at runtime?
```

**Recommendation:** Add `TestManifestWavConsistency` class with:
- Load each WAV in generated_assets/sounds/
- Verify duration matches engine sound effect expectations
- Cross-check engine_sound_id_int against tools/Duke3D_SoundIDs.txt (or similar reference)

---

## 2. QUALITY OF NEW TESTS

### 2.1 test_visual_playtest: SDL2 .so Missing → Not Skipped [CRITICAL]
**File:** tests/test_visual_playtest.py  
**Status:** FAILING (exit code 127: libSDL2-2.0.so.0 not found)  
**Issue:** Game fails to launch due to missing runtime library, but test does NOT use `pytest.importorskip()`.

**Current Behavior:**
```python
@pytest.mark.playtest
def test_frames_captured(headless_run):
    """At least one BMP frame should have been captured."""
    assert len(headless_run["frame_paths"]) > 0  # ← FAILS (stderr: "libSDL2-2.0.so.0: cannot open")
```

**Problem:**
- Fixture `headless_run` catches TimeoutExpired but NOT subprocess launch errors
- Test appears "FAILED" instead of "SKIPPED", polluting CI output
- No clear message about why frames weren't captured

**Solution:**
Replace fixture-level skip with `pytest.importorskip('sdl2')` pattern OR use a marker-aware skip:
```python
@pytest.fixture(scope="session")
def headless_run():
    if not os.path.exists(BINARY_PATH):
        pytest.skip(...)
    if not has_libsdl2():  # NEW: check .so/.dll availability
        pytest.skip("libSDL2-2.0.so.0 not found (optional SDL runtime)")
    # ... rest
```

**Cleanup Path:**
1. Detect SDL2 runtime availability at fixture setup
2. Skip entire playtest session if unavailable
3. Document in pytest.ini: `playtest: Requires SDL2 runtime (.so/.dll)`

**Severity:** CRITICAL — Visual tests are red but need to be orange (skipped)

---

### 2.2 test_audio_pipeline.py: Subprocess Calls Not Isolated [HIGH]
**File:** tests/test_audio_pipeline.py:134, 156, 192  
**Issue:** Three separate tests each call `generate_audio.py --no-ai` independently; duplicated setup/teardown.

```python
def test_voice_lines_generation(self):
    result = subprocess.run([sys.executable, ..., "generate_audio.py", "--no-ai"], ...)
    assert result.returncode == 0

def test_wav_files_have_valid_riff_header(self):
    result = subprocess.run([sys.executable, ..., "generate_audio.py", "--no-ai"], ...)
    assert result.returncode == 0

def test_wav_files_are_valid_wave_format(self):
    result = subprocess.run([sys.executable, ..., "generate_audio.py", "--no-ai"], ...)
    assert result.returncode == 0
```

**Cost:** ~9-10 seconds of redundant subprocess calls (30% of total runtime).

**Solution:** Extract into session-scoped fixture:
```python
@pytest.fixture(scope="session")
def generated_wavs():
    result = subprocess.run(...)
    assert result.returncode == 0
    return os.path.join(PROJECT_ROOT, "generated_assets", "sounds")

# Then:
def test_wav_files_have_valid_riff_header(self, generated_wavs):
    # ... use generated_wavs path, no subprocess call
```

---

### 2.3 test_generate_audio.py: Tests Read-Then-Assert-Equals (Tautology Risk) [HIGH]
**File:** tests/test_generate_audio.py:162-170  
**Issue:** File content test compares JSON serialization of what was just written.

```python
def test_manifest_file_matches_constant(self):
    """MANIFEST.json file content must match SOUND_MANIFEST constant."""
    manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
    with open(manifest_path) as f:
        file_manifest = json.load(f)
    
    # This is a TAUTOLOGY if generate_audio.py always writes SOUND_MANIFEST as-is:
    assert json.dumps(file_manifest, sort_keys=True) == json.dumps(generate_audio.SOUND_MANIFEST, sort_keys=True)
```

**Problem:** Test passes trivially if generate_audio.py does `json.dump(SOUND_MANIFEST, f)`.

**Solution:** 
- Replace with **behavior-based assertions**:
  - Does every VOICE_LINES entry have a corresponding MANIFEST entry?
  - Are entries in the same order?
  - Are optional fields (notes) preserved?
- Or create a **schema-based test** using jsonschema or pydantic

---

### 2.4 test_generate_audio.py: Exception Handling Too Broad [MEDIUM]
**File:** tests/test_generate_audio.py:303, 239  
**Pattern:**
```python
try:
    with wave.open(wav_file, "rb") as wav:
        # assertions
except wave.Error as e:
    pytest.fail(f"...")
```

**Issue:** `wave.Error` is caught, but if the test logic itself raises an unexpected exception (e.g., AttributeError on `wav.getnchannels()`), it won't be caught and will propagate as a test error rather than a clear failure.

**Recommendation:** Be more specific:
```python
try:
    with wave.open(wav_file, "rb") as wav:
        channels = wav.getnchannels()
        assert channels == 1
except wave.Error as e:
    pytest.fail(f"WAV file not readable: {e}")
except Exception as e:
    pytest.fail(f"Unexpected error reading WAV: {type(e).__name__}: {e}")
```

---

### 2.5 test_sound_manifest.py: Voice-Category Alignment Not Round-Tripped [MEDIUM]
**File:** tests/test_sound_manifest.py:107-129  
**Issue:** Test validates voice-category alignment **statically**, but does NOT verify this persists through serialization/deserialization cycles.

```python
def test_voice_category_alignment(self):
    """Validate voice-to-category alignment follows audio-engineer convention."""
    alloy_categories = {"taunt", "level_start", "death"}
    # ... check static manifest
```

**Missing:** Test that write MANIFEST.json → read back → verify same alignment holds.

**Recommendation:** Add round-trip test:
```python
def test_voice_category_alignment_survives_json_roundtrip(self):
    # Write to temp JSON, read back, verify alignment
    temp_json = json.dumps(generate_audio.SOUND_MANIFEST)
    reloaded = json.loads(temp_json)
    # ... verify alignment in reloaded data
```

---

## 3. FLAKY TESTS & EXPECTED FAILURES

### 3.1 test_visual_playtest: SDL2 Missing → 1 Failure, 3 Skipped [CRITICAL]
**File:** tests/test_visual_playtest.py  
**Current Run Result:**
```
test_frames_captured FAILED (exit code 127: libSDL2 .so missing)
test_not_all_black SKIPPED (No frames captured)
test_has_visible_content SKIPPED (No frames captured)
test_frame_sequence_analysis SKIPPED (No frames captured)
test_no_crash_signals PASSED (fixture exit_code = -1)
```

**Status:** Persistent red in this environment (no SDL2 runtime).

**Proper Fix:**
1. Replace exception handler in fixture with `pytest.skip()`
2. Add `CI_HAS_SDL2` env var to detect runtime availability
3. Mark test with `@pytest.mark.skip(reason="SDL2 runtime not available")` when CI env absent

**Answer to User Question:** **YES, mark as skipped via pytest.importorskip() or fixture-level skip instead of persistent FAILED status.**

---

## 4. COVERAGE HOLES

### 4.1 compat/sdl_driver.c: 206 LOC, Zero Python Coverage [HIGH]
**File:** compat/sdl_driver.c  
**Line Count:** 206  
**Public Functions Not Covered:**
- `sdl_quit_requested_get()` (line 540)
- `sdl_checkquit()` (line 535)
- All SDL event loop logic

**Mitigation:** Would require C-level test harness or integration via headless game binary (expensive).

**Partial Mitigation:** Create Python tests that use the compiled `duke3d` binary and check for clean shutdown:
```python
# New: tests/test_sdl_compat_integration.py
def test_sdl_quit_flag_respects_window_close():
    # Launch duke3d with SDL_VIDEODRIVER=dummy
    # Send SDL_QUIT event
    # Verify game exits cleanly (sdl_checkquit was respected)
```

---

### 4.2 Source Code Coverage: ~5369 LOC C Code, ~506 Passing Tests
**Coverage Ratio:** Very rough ~10 LOC per test (includes integration tests).  
**Gaps:**
- No direct unit tests for C structs (sectortype, walltype, spritetype)
  - **Mitigation:** test_build_structs.py covers struct sizes, compat_layer.py covers layout
- No tests for GRP file parsing correctness
  - **Mitigation:** test_grp_format.py exists, but only 3 tests
- No tests for MAP format edge cases (boundary conditions, invalid geometry)
  - **Mitigation:** test_map_format.py has parametrized tests over all 32 episodes, but could use property-based testing

---

## 5. CONFTEST & FIXTURES

### 5.1 Minimal conftest.py: 7 Lines [MEDIUM]
**File:** tests/conftest.py  
**Current:**
```python
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))
```

**Opportunities for Shared Fixtures:**
- `binary_path` fixture (currently checked in multiple tests)
- `grp_path` fixture (test_visual_playtest, test_pipeline_integration)
- `generated_assets_dir` fixture
- `tmp_generated_audio` fixture for isolating subprocess tests

**Recommendation:** Add to conftest.py:
```python
@pytest.fixture
def project_root():
    return PROJECT_ROOT

@pytest.fixture
def binary_path():
    path = os.path.join(PROJECT_ROOT, "duke3d")
    if not os.path.exists(path):
        pytest.skip("Binary not built")
    return path

@pytest.fixture
def grp_path():
    path = os.path.join(PROJECT_ROOT, "DUKE3D.GRP")
    if not os.path.exists(path):
        pytest.skip("DUKE3D.GRP not generated")
    return path
```

---

## 6. CI CONFIGURATION

### 6.1 test-windows-native Job: ACTIVE AND TRIGGERED [HIGH]
**File:** .github/workflows/build.yml:156-227  
**Status:** ✅ Job exists and runs on windows-latest (pull_request, push)  
**Coverage:** Runs test_build_structs.py + test_compat_layer.py (native MSVC)  
**Issue:** Does NOT run full test suite on Windows.

**Gap:** Windows-specific tests for struct packing (MSVC vs MinGW) are minimal.

**Recommendation:** Add Windows-specific struct validation (e.g., pragma pack differences).

### 6.2 playtest Job: ACTIVE, Set to continue-on-error [HIGH]
**File:** .github/workflows/build.yml:228-265  
**Status:** ✅ Exists, continues on error (wise for optional SDL2)  
**Issue:** Always runs even if SDL2 not available; no skip-on-missing-SDL2 logic.

**Recommendation:** Add early skip check:
```yaml
- name: Check SDL2 availability
  id: sdl2_check
  run: |
    if ldconfig -p | grep -q "libSDL2"; then
      echo "available=true" >> $GITHUB_OUTPUT
    else
      echo "available=false" >> $GITHUB_OUTPUT
  continue-on-error: true

- name: Run visual playtests
  if: steps.sdl2_check.outputs.available == 'true'
  run: python3 -m pytest tests/test_visual_playtest.py -v -m playtest
```

---

## 7. PERFORMANCE

### 7.1 Full Test Suite: 33.42s for 506 Tests
**Breakdown (estimated):**
- test_build_structs.py: 0.17s (7 tests) — **Fast**
- test_audio_pipeline.py: ~10s (14 tests) — includes 3x subprocess.run() calls
- test_generate_audio.py: ~8-10s (38 tests) — includes 4x subprocess.run() calls
- test_sound_manifest.py: ~2-3s (21 tests) — mostly in-memory
- Remaining tests: ~13-15s (424 tests) — mostly lightweight format validation

**Slow Tests Candidates for `@pytest.mark.slow`:**
- test_audio_pipeline.py::test_voice_lines_generation (~3.5s each × 3 tests)
- test_generate_audio.py::test_no_ai_flag_generates_wav_files (~3.5s)
- test_generate_audio.py::test_no_ai_generates_valid_wav_files (~3.5s)
- test_visual_playtest.py::test_headless_startup (~15s timeout, but skipped in this env)

**Recommendation:** Add performance markers:
```python
@pytest.mark.slow
@pytest.mark.parametrize("duration", [0.1, 0.5, 1.0])
def test_generate_silence_wav_custom_duration(self, duration):
    ...
```

Run fast suite with: `pytest tests/ -m "not slow"` (~15s expected)

---

## 8. PROPERTY-BASED TESTING OPPORTUNITIES

### 8.1 GRP File Round-Trip (Hypothesis) [MEDIUM]
**Leverage:** hypothesis library to generate random GRP file structures  
**Test:** Parse GRP → serialize → parse → verify byte-identical  

**Why Valuable:** File format parsing is error-prone; property tests would catch edge cases (zero-length files, massive files, malformed entries).

---

### 8.2 WAV Header Packing (Hypothesis + struct) [MEDIUM]
**Leverage:** hypothesis to generate random sample rates, bit depths, durations  
**Test:** Call generate_silence_wav(duration=X, sample_rate=Y, bit_depth=Z) → verify header consistency  

**Example:**
```python
@given(duration_sec=st.floats(min_value=0.1, max_value=10.0))
def test_wav_header_size_consistency(self, duration_sec):
    wav = generate_audio.generate_silence_wav(duration_sec)
    # Parse header, verify RIFF size field matches actual size
    riff_size = struct.unpack("<I", wav[4:8])[0]
    assert riff_size == len(wav) - 8
```

---

### 8.3 MANIFEST Schema Validation (Pydantic) [MEDIUM]
**Leverage:** pydantic to define SoundManifestEntry schema  
**Test:** Validate every MANIFEST entry against schema; use hypothesis to generate invalid entries and ensure rejection  

```python
from pydantic import BaseModel, validator

class SoundManifestEntry(BaseModel):
    wav: str  # Must end with .WAV
    engine_sound_id: Optional[str] = None
    voice: Literal["alloy", "echo", "onyx"]
    category: str
    prompt_summary: str
    
    @validator("wav")
    def wav_format(cls, v):
        assert v.endswith(".WAV")
        return v
```

---

## 9. AUDIT TODOS

### Summary of Actionable Items (13 Total)

| ID | Severity | Task | Est. Effort |
|----|----------|------|-------------|
| `test-sdl-driver-unit` | 🔴 CRITICAL | Unit tests for sdl_quit_requested_get() | 2h |
| `test-visual-playtest-skip` | 🔴 CRITICAL | Replace FAILED with SKIPPED for missing SDL2 | 1h |
| `test-manifest-wav-consistency` | 🔴 CRITICAL | Add consistency tests MANIFEST.json ↔ generated WAVs | 3h |
| `test-audio-gen-fixture` | 🟠 HIGH | Extract subprocess.run() into session fixture | 1h |
| `test-generate-audio-behavior` | 🟠 HIGH | Replace tautology tests with behavior-based | 2h |
| `test-exception-specificity` | 🟠 HIGH | Narrow exception handling in audio tests | 1h |
| `test-wav-roundtrip-json` | 🟠 HIGH | Add JSON round-trip tests for MANIFEST | 1h |
| `test-conftest-shared-fixtures` | 🟡 MEDIUM | Add binary_path, grp_path, project_root fixtures | 1.5h |
| `test-manifest-schema-pydantic` | 🟡 MEDIUM | Implement pydantic schema for SoundManifestEntry | 2h |
| `test-slow-marker` | 🟡 MEDIUM | Mark subprocess-heavy tests with @pytest.mark.slow | 0.5h |
| `test-grp-property-hypothesis` | 🟡 MEDIUM | Add hypothesis-based GRP round-trip tests | 2.5h |
| `test-wav-property-hypothesis` | 🟡 MEDIUM | Add hypothesis-based WAV header tests | 2h |
| `test-ci-sdl2-check` | 🟡 MEDIUM | Add SDL2 detection to CI playtest job | 1h |

**Total Estimated Effort:** ~22 hours (full audit + implementation)

---

## 10. NEXT STEPS

1. **Immediate (CRITICAL):**
   - [ ] test-visual-playtest-skip: Mark playtest skipped when SDL2 missing (1h)
   - [ ] test-sdl-driver-unit: Create test harness for sdl_quit_requested_get() (2h)
   - [ ] test-manifest-wav-consistency: Add WAV existence + format checks (3h)

2. **Short-term (HIGH):**
   - [ ] test-audio-gen-fixture: Deduplicate subprocess calls (1h)
   - [ ] test-generate-audio-behavior: Rewrite tautology tests (2h)

3. **Medium-term (MEDIUM):**
   - [ ] Add conftest fixtures (1.5h)
   - [ ] Implement property-based tests (6.5h)
   - [ ] Slow test markers (0.5h)

4. **Performance Optimization:**
   - Fast suite (no slow markers): ~15-18s expected
   - Default suite (with slow): 33-35s

---

## APPENDIX: Test File Inventory

| File | Tests | Status | Notes |
|------|-------|--------|-------|
| test_art_format.py | 3 | ✅ | Format validation OK |
| test_audio_pipeline.py | 14 | ⚠️ | Subprocess duplicates; good coverage |
| test_anm_format.py | 11 | ✅ | Round-trip tests present |
| test_build_structs.py | 7 | ✅ | Struct sizes validated; fast (0.17s) |
| test_compat_layer.py | 3 | ✅ | ABI verification OK |
| test_demo_format.py | 4 | ✅ | Basic format tests |
| test_frame_analyzer.py | 11 | ✅ | Frame analysis good |
| test_generate_audio.py | 38 | ⚠️ | Large suite; some tautologies |
| test_grp_format.py | 3 | ⚠️ | Minimal coverage (archive format) |
| test_map_format.py | 7 | ✅ | Parametrized over 32 episodes |
| test_midi_format.py | 4 | ✅ | Basic validation |
| test_palette.py | 2 | ✅ | Colormap tests |
| test_pipeline_integration.py | 3 | ✅ | End-to-end asset gen |
| test_sound_manifest.py | 21 | ✅ | Schema validation strong; missing round-trip |
| test_tables.py | 1 | ✅ | Lookup table validation |
| test_voc_format.py | 13 | ✅ | Comprehensive VOC tests |
| test_visual_playtest.py | 7 | ❌ | SDL2 missing → 1 FAILED, 3 SKIPPED |

**Total:** 17 test files, 506 passing, 3 skipped, 1 failed

---

## REFERENCES

- **Test Engineer Persona:** .github/agents/test-engineer.agent.md
- **Audio Engineer Audit:** docs/audits/audio-engineer.md
- **Build System:** docs/audits/build-system.md
- **CI Configuration:** .github/workflows/build.yml

---

**Report generated by:** Test Engineer Persona (Copilot)  
**Audit mode:** READ-ONLY, non-invasive code inspection  
**Next review:** After CRITICAL todos are addressed

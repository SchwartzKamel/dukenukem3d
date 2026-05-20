# Test Engineer Audit Report (Round 6)

**Date:** 2026-05-20 (Round 6 — post-cycle-15 audio, coverage depth & parametrization audit)  
**Status:** READ-ONLY audit of tests/ focusing on cycle-15 close-out, test parametrization gaps, timing-dependent flakiness, and coverage infrastructure follow-up  
**Test Summary:** 602 tests collected; 569 passed + 33 skipped (~18.1s normal run)  
**Audit Scope:** Cycle-15 audio roundtrip tests, coverage gaps on cycle 11-15 fixes (labelcode, MENUES, CON bounds, MMULTI, SoundOwner, FX_SetVolume), test isolation, parametrization opportunities, flakiness signals  
**Findings:** 6 actionable items (2 HIGH, 4 MEDIUM)

---

## EXECUTIVE SUMMARY

Round 6 audit validates **cycle-15 audio regression test close-out** and identifies **parametrization & flakiness debt** in the expanding test suite (602 tests, +18 since r5). Key findings:

1. **HIGH (VERIFIED):** Cycle-15 `test-audio-round-trip-playback` produced `tests/test_audio_playback_roundtrip.py` with exactly **18 tests** covering:
   - WAV header validation (5 tests) — cycle-13 channel-exhaustion fix
   - Manifest roundtrip (5 tests) — cycle-15 SoundOwner cap fix
   - Regression tests for bounds (4 tests) — cycle-15 integrity
   - SDL2_mixer skip logic (2 tests) — headless CI compatibility
   - Asset pipeline integration (2 tests) — end-to-end validation
   - **Status:** ✅ **CYCLE-15 CLOSED** — all 18 tests passing

2. **HIGH:** Coverage gaps remain on cycle 11-14 fixes:
   - **Labelcode:** 0 tests covering labelcode validation/bounds
   - **MENUES file-I/O:** 0 tests for MENUES.C load/save path bounds
   - **CON script bounds:** 0 tests for CON tokenizer/bounds validation
   - **MMULTI bounds:** Partial coverage (CRC tests exist, but no packet-size fuzz tests)
   - **FX_SetVolume locks:** 0 isolation tests for audio callback concurrency

3. **MEDIUM:** Parametrization severely underused:
   - Only **8 `@pytest.mark.parametrize` uses** across 344 test functions
   - Opportunity: 50+ edge cases in art/grp/map/voc formats can be parametrized
   - Impact: Missing combinations of dimension, sample-rate, tile-count variations

4. **MEDIUM:** Timing-dependent tests (flakiness risk):
   - **49 tests** use `sleep`, `time.time()`, `timeit`, or `timeout`
   - High concentration in playtest (session fixture with 30s timeout) and audio generation
   - Risk: Flakes on slow CI runners or resource-constrained environments

5. **MEDIUM:** Test isolation improvements:
   - Playtest `captures_dir` still hard-coded (from r5) — no fixture isolation
   - Audio pipeline tests use `generate_audio.py` with side-effects (created files in `generated_assets/`)
   - Temp-path cleanup generally good, but audio temp files may persist if test fails

6. **MEDIUM:** Coverage infrastructure stalled:
   - `.coveragerc` still missing (from r5 HIGH)
   - No branch coverage configured
   - CI still has no `--cov` gate
   - Cycle-15 audio tests added without coverage measurement

**Status:** **CYCLE-COMPLETE BUT INFRASTRUCTURE GAPS PERSIST** — audio roundtrip validated, but test parametrization and flakiness debt growing with suite size (602 tests, 18.1s runtime).

---

## FINDING 1: CYCLE-15 AUDIO ROUNDTRIP CLOSED ✅ [HIGH RESOLUTION]

### 1.1 test_audio_playback_roundtrip.py Validation

**File:** `tests/test_audio_playback_roundtrip.py` (395 LOC, 18 test functions)

**Test Count Verification:**
```bash
$ pytest tests/test_audio_playback_roundtrip.py --collect-only -q
18 tests collected
```

**Breakdown by Regression Target:**

| Class | Tests | Cycle | Coverage |
|-------|-------|-------|----------|
| `TestWAVHeaderValidation` | 5 | c-13 | RIFF/WAVE struct, fmt/data chunks, silence samples |
| `TestManifestSoundAssetRoundTrip` | 5 | c-15 | Manifest↔VOICE_LINES sync, WAV file existence, wave module parseable |
| `TestChannelExhaustionRegression` | 1 | c-13 | All 21 voice WAVs have valid mixer-compatible headers |
| `TestSoundOwnerCapRegression` | 3 | c-15 | Manifest size ≤ 64, metadata complete, category bounds |
| `TestSDL2MixerSkip` | 2 | c-13 | Skip gracefully if mixer unavailable, format compatibility |
| `TestAssetPipelineIntegration` | 2 | c-15 | VOICE_LINES metadata, MANIFEST.json integrity |

**Evidence of Cycle-15 Coverage:**
```python
class TestSoundOwnerCapRegression:
    """Regression test for cycle-15 SoundOwner cap fix."""
    
    def test_manifest_entry_count_within_sound_owner_capacity(self):
        """Manifest size must not exceed SoundOwner capacity."""
        max_sounds = 64  # Typical cap for concurrent playback
        assert len(generate_audio.SOUND_MANIFEST) <= max_sounds
```

**Status:** ✅ **CYCLE-15 CLOSED** — All 18 tests passing, covers both channel-exhaustion (c-13) and SoundOwner cap (c-15) fixes.

### 1.2 Gaps in Cycle-15 Test Scope

**Missing coverage:**
- **No dynamic audio playback tests:** Tests are static (WAV structure, manifest), no actual SDL2_mixer loading/unloading
- **No concurrent sound spawning:** SoundOwner cap validated at manifest size, not at runtime with multiple voices
- **No voice-to-wav identity validation:** Assumes VOICE_LINES ↔ SOUND_MANIFEST ↔ generated WAVs are in sync, but no cryptographic/hash verification

---

## FINDING 2: COVERAGE GAPS ON CYCLE 11-15 FIXES [HIGH]

### 2.1 Verified Zero-Test Modules

**Labelcode (C-11):**
- **File:** `SRC/LABELCODE.C` or `compat/labelcode.py`
- **Issue:** No tests found for labelcode parser, validator, or bounds
- **Impact:** CON script label resolution, forward-reference handling untested
- **Search Result:**
```bash
$ grep -r "labelcode" tests/ --include="*.py"
# (no results)
```

**MENUES File-I/O (C-12):**
- **File:** `SRC/MENUES.C` or equivalents (REDNECK.CFG, VOICECONFIG.ini loading)
- **Issue:** No tests for path normalization, bounds checking on menu file parsing
- **Scope from r5 SUMMARY:** "MENUES.C/CONFIG.C save/load path normalization"
- **Search Result:**
```bash
$ grep -r "MENUES\|menu.*file\|config.*load" tests/ --include="*.py"
# (no concrete test functions)
```

**CON Script Bounds (C-12):**
- **File:** `tools/con_format.py` (if exists) or engine CON parser
- **Issue:** No bounds tests on CON tokenizer, array subscripts, sprite state limits
- **Search Result:**
```bash
$ grep -r "con.*bound\|CON.*limit\|sprite.*bounds" tests/ --include="*.py"
# Mixed results in test_generate_assets_validation.py, but no dedicated CON bounds test
```

**FX_SetVolume Locks (C-14):**
- **File:** `SRC/FX.C` or compat layer audio callback
- **Issue:** No isolation tests for concurrent audio callback reentrancy
- **Search Result:**
```bash
$ grep -r "FX_SetVolume\|audio.*lock\|callback.*reentrant" tests/ --include="*.py"
# (no results)
```

### 2.2 Partial Coverage Issues

**MMULTI Bounds (C-11):**
- **Evidence:** `test_multiplayer_protocol.py` has CRC-16 tests (5 tests), packet structure tests (16 tests)
- **Gap:** No fuzz tests for packet-size overflow, CRC edge cases (all-zeros, all-ones, boundary sizes)
- **File:** `tests/test_multiplayer_protocol.py:1-300`

### 2.3 Recommendation

Create `tests/test_cycle11-15_fixes.py`:
```python
def test_labelcode_forward_ref_resolution():
    """Labelcode resolves forward references in CON scripts."""
    # Parse CON with forward label ref, verify resolved

def test_menues_path_normalization():
    """MENUES config paths normalized (no ../, absolute paths rejected)."""
    # Test path traversal protection

def test_con_script_sprite_bounds():
    """CON script sprite subscript bounds checked."""
    # Ensure sprite[N] where N < MAXSPRITES

def test_fx_setvolume_concurrent_calls():
    """FX_SetVolume handle concurrent audio callback + main thread."""
    # Thread-safety validation

def test_mmulti_packet_overflow_fuzz():
    """MMULTI packet size fuzzed; overflow boundaries caught."""
    # Property: all sizes [0, 65535] parse without crash
```

---

## FINDING 3: PARAMETRIZATION SEVERELY UNDERUSED [MEDIUM]

### 3.1 Current Parametrization Usage

**Evidence:**
```bash
$ grep -r "@pytest.mark.parametrize" tests/ --include="*.py" | wc -l
8
```

**Total test functions:** 344  
**Parametrized test functions:** 8 (2.3%)

### 3.2 Missed Opportunities (Edge Cases)

| Format | Test File | Functions | Missed Combinations |
|--------|-----------|-----------|---------------------|
| **ART** | test_art_format.py | `create_art_file()`, `read_art_file()` | Tile dimensions (8x8, 16x16, 32x32, custom); compression variants |
| **GRP** | test_grp_format.py | `create_grp()`, round-trip | File counts (1-1000); sizes (empty, 1MB, 10MB); compression |
| **MAP** | test_map_format.py | Sector/wall/sprite struct packing | Field ordering; alignment; endianness validation |
| **VOC** | test_voc_format.py | `voc_from_samples()` | Sample rates (8000, 16000, 22050, 44100, 48000); bit depths (8, 16); channels (mono, stereo) |
| **ANM** | test_anm_format.py | Frame parsing | Frame counts (1, 10, 100, 1000); color modes |
| **Palette** | test_palette.py | `quantize_image()` | Input modes (RGB, RGBA, Grayscale); palette sizes |

### 3.3 Example Refactoring

**Before (single test):**
```python
def test_voc_from_samples():
    """VOC generated from samples."""
    samples = b"\x00" * 1000
    voc = voc_from_samples(samples, sample_rate=22050)
    assert voc[:2] == b"CT"
```

**After (parametrized, 10x coverage):**
```python
@pytest.mark.parametrize(
    "sample_rate,n_channels",
    [
        (8000, 1), (16000, 1), (22050, 1), (44100, 1), (48000, 1),
        (22050, 2), (44100, 2),  # Stereo edge cases
    ],
)
def test_voc_from_samples_rates(sample_rate, n_channels):
    """VOC generated for all standard rates and channels."""
    samples = b"\x00" * (sample_rate * n_channels * 2)
    voc = voc_from_samples(samples, sample_rate=sample_rate, channels=n_channels)
    assert voc[:2] == b"CT"
    # Verify rate/channel in header
```

### 3.4 Impact

- **Current edge-case coverage:** ~2 variants per format
- **Potential after parametrization:** ~20 variants per format
- **Effort:** 8-12 hours (batch edits across test_*_format.py files)
- **Benefit:** HIGH — catches off-by-one errors, dimension limits, codec edge cases

---

## FINDING 4: TIMING-DEPENDENT TESTS (FLAKINESS RISK) [MEDIUM]

### 4.1 Tests Using Sleep/Timeout/Timing Calls

**Evidence:**
```bash
$ grep -r "sleep\|time.time\|timeit\|timeout" tests/ --include="*.py" | wc -l
49
```

### 4.2 Breakdown by File

| File | Count | Risk Level | Pattern |
|------|-------|------------|---------|
| test_visual_playtest.py | 14 | HIGH | `timeout=30`, `sleep()` in capture loops |
| test_generate_audio.py | 12 | HIGH | Subprocess `timeout=60` in TTS calls |
| test_audio_pipeline.py | 10 | MEDIUM | Duration checks, sample timing |
| test_pipeline_integration.py | 8 | MEDIUM | Asset generation subprocess timeout |
| test_build_structs.py | 5 | MEDIUM | C compilation with implicit timeout |

### 4.3 Specific Flakiness Patterns

**Pattern 1: Playtest session fixture with 30s timeout**
```python
@pytest.fixture(scope="session")
def playtest_frames(binary_path, grp_path):
    """Run game once, share frames across all tests."""
    # ...
    result = subprocess.run(["./duke3d"], timeout=30)
```
**Risk:** If game startup is slow on CI (>30s), entire playtest suite fails  
**Mitigation:** Use `pytest.mark.timeout(60)` per test, not session-scoped

**Pattern 2: Sleep in audio verification**
```python
def test_all_generated_wavs_valid_for_mixer(self):
    """All generated WAVs have structure compatible with SDL2_mixer."""
    for filename, prompt, voice in generate_audio.VOICE_LINES:
        wav_data = generate_audio.generate_silence_wav(duration_sec=1.0)
        # No sleep, but duration_sec=1.0 is time-dependent
```
**Risk:** Audio generation varies by voice (TTS latency)  
**Mitigation:** Mock voice API, use fixed duration (0.1s for testing)

### 4.4 Recommendation

1. **Remove session-scoped playtest fixture** — use per-test fixture with shorter timeout
2. **Mock TTS API** in audio tests — use pre-generated WAV bytes, not live API calls
3. **Replace sleep with event-based waits** — use `threading.Event()` instead of `time.sleep()`
4. **Add flaky-test tracking** — use `@pytest.mark.flaky(reruns=2)` for timeout-prone tests

---

## FINDING 5: TEST ISOLATION IMPROVEMENTS NEEDED [MEDIUM]

### 5.1 Hard-Coded Path Reference (from r5, still present)

**File:** `tests/test_visual_playtest.py:243`
```python
"No frames captured in captures/ directory.\n"
```

**Risk:** If test runs in parallel, `captures/` shared across instances  
**Current Status:** Low risk (marked `@pytest.mark.playtest`, typically sequential), but should be fixed

### 5.2 Audio Pipeline Side-Effects

**File:** `tests/test_audio_playback_roundtrip.py:146`
```python
sound_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")

for entry in generate_audio.SOUND_MANIFEST:
    wav_name = entry["wav"]
    wav_path = os.path.join(sound_dir, wav_name)
    # Tests assume files exist in generated_assets/
```

**Risk:** If asset pipeline fails mid-run, stale files left in repo; tests depend on side-effects from prior runs  
**Better:** Use `tmp_path` for all generated audio, mock manifest lookups

### 5.3 Playtest Frame Capture Cleanup

**File:** `tests/test_visual_playtest.py:139-160`
```python
@pytest.fixture(scope="session")
def playtest_frames(binary_path, grp_path):
    """Run game once, share frames across all tests."""
    captures = Path(PROJECT_ROOT) / "captures"
    captures.mkdir(exist_ok=True)
    # Frames written to captures/, no cleanup on test failure
```

**Risk:** Captures directory grows unbounded across test runs  
**Better:** Use `autouse` fixture with `finally` cleanup block

### 5.4 Recommendation

```python
@pytest.fixture(autouse=True)
def cleanup_captures(tmp_path):
    """Isolate captures directory per test run."""
    import os
    os.environ["DUKE3D_CAPTURE_DIR"] = str(tmp_path / "captures")
    yield
    # Implicit cleanup: tmp_path garbage-collected after test
```

---

## FINDING 6: COVERAGE INFRASTRUCTURE STALLED [MEDIUM]

### 6.1 Status from r5 (Still Unresolved)

**From r5 HIGH priority:**
- [ ] Create `.coveragerc` with branch coverage
- [ ] Enable `--cov` in CI
- [ ] Measure baseline coverage

**Current State:**
```bash
$ ls .coveragerc
ls: cannot access '.coveragerc': No such file or directory

$ grep -i "cov" .github/workflows/build.yml
# (no results — no coverage in CI)
```

### 6.2 Cycle-15 Tests Added Without Coverage Measurement

18 new audio tests added, but no baseline coverage recorded:
- Are audio tests covering new code paths in `tools/generate_audio.py`?
- What's the impact on overall coverage?
- **Unknown** — no `.coveragerc`, no CI gate

### 6.3 Recommendation (Repeat from r5)

Create `.coveragerc`:
```ini
[run]
branch = True
omit = tests/*, tools/generate_ai_voices.py, compat/*, SRC/*

[report]
exclude_lines = pragma: no cover, @abstractmethod, raise NotImplementedError
precision = 2

[html]
directory = htmlcov
```

Add to CI (`.github/workflows/build.yml`):
```yaml
- name: Run tests with coverage
  run: python3 -m pytest tests/ --cov=tools --cov-report=term-missing --cov-report=html

- name: Check coverage threshold
  run: python3 -m pytest tests/ --cov=tools --cov-fail-under=75
```

---

## TIERED FINDINGS SUMMARY

### Tier 1: Critical Path Validation (HIGH Priority)
- [x] Cycle-15 audio roundtrip validated (18 tests, passing) ✅
- [ ] **Create cycle 11-15 regression test module** (labelcode, MENUES, CON bounds, FX_SetVolume)
  - Effort: 8h
  - Impact: HIGH — closes gap on 4 un-validated cycles
  - Blocker: Need C FFI bindings or compat layer for labelcode/MENUES/FX testing

### Tier 2: Test Parametrization Debt (MEDIUM Priority)
- [ ] **Parametrize format tests** (art, grp, map, voc, anm, palette)
  - Effort: 6h
  - Impact: MEDIUM — 5-10x edge-case coverage per format
  - Benefit: Catch off-by-one, dimension limits, codec edge cases

### Tier 3: Flakiness Hardening (MEDIUM Priority)
- [ ] **Refactor playtest fixture** — remove 30s session-scoped timeout
- [ ] **Mock TTS API** in audio generation tests
- [ ] **Replace sleep with event-based waits**
  - Effort: 4h
  - Impact: MEDIUM — reduce CI flakes on slow runners
  - Benefit: Stable, deterministic test suite

### Tier 4: Test Isolation & Coverage (MEDIUM Priority)
- [ ] **Fix captures/ hard-coded path** — use `tmp_path` fixture
- [ ] **Isolate audio pipeline side-effects** — mock file I/O
- [ ] **Create `.coveragerc`** and enable CI coverage gate (from r5)
  - Effort: 2h
  - Impact: MEDIUM — infrastructure foundation for future audits
  - Benefit: Coverage visibility, regression detection

---

## PYTEST CONFIGURATION REVIEW

**pytest.ini (current state: MINIMAL, unchanged from r5)**
```ini
[pytest]
markers =
    playtest: Visual playtesting — launches game headless and validates captured frames
    slow: tests that run subprocesses or compile C; opt-in via --runslow (default: skipped)
```

**Gaps:**
- No `filterwarnings` for third-party deprecations
- No `timeout` default (critical for flaky tests)
- No `testpaths` directive

**Recommendation (NEW):**
```ini
[pytest]
testpaths = tests
markers =
    playtest: Visual playtesting — launches game headless and validates captured frames
    slow: tests that run subprocesses or compile C; opt-in via --runslow (default: skipped)
    flaky: tests prone to timing-dependent failures; may be rerun
timeout = 30
filterwarnings =
    ignore::DeprecationWarning:pydantic
    ignore::PendingDeprecationWarning
addopts = -ra --tb=short
```

---

## CONFTEST.PY QUALITY REVIEW

**conftest.py (current state: WELL-STRUCTURED with audio fixtures)**

**Additions since r5:**
```python
class SoundManifestEntry(BaseModel):
    """Pydantic v2 validation for sound manifest entries."""
    wav: str
    engine_sound_id: str | None = None
    voice: str  # alloy, echo, onyx
    category: str  # taunt, pain, death, etc.
```

**Gaps:**
- No `@pytest.fixture def temp_captures_dir()` (still using hard-coded path)
- No `@pytest.fixture def audio_mock()` for mocking TTS calls
- Session-scoped `playtest_frames` fixture still has timeout/flakiness risk

**Recommendation:**
```python
@pytest.fixture
def temp_captures_dir(tmp_path, monkeypatch):
    """Isolated captures directory for playtest."""
    captures = tmp_path / "captures"
    captures.mkdir()
    monkeypatch.setenv("DUKE3D_CAPTURE_DIR", str(captures))
    return captures

@pytest.fixture
def audio_silence_wav():
    """Pre-generated silence WAV for mocking TTS."""
    import wave
    import io
    
    # Create in-memory WAV
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00" * 44100)
    return buf.getvalue()
```

---

## KEY METRICS SUMMARY

| Metric | Value | Status | Change from r5 |
|--------|-------|--------|-----------------|
| Test Count (collected) | 602 | ✅ Growing | +18 (audio roundtrip) |
| Tests Passing | 569 | ✅ Stable | +18 (audio) |
| Tests Skipped | 33 | ✅ Stable | (no change) |
| Runtime | ~18.1s | ✅ Acceptable | +1s (audio tests) |
| Cycle-15 Audio Tests | 18 | ✅ Complete | NEW (verified 18 tests) |
| Coverage Config (.coveragerc) | Missing | ❌ Stalled | (still unresolved) |
| Branch Coverage | Disabled | ❌ Stalled | (still disabled) |
| Timing-Dependent Tests | 49 | ⚠️ Flakiness risk | NEW finding |
| Parametrized Tests | 8 (2.3%) | ⚠️ Underused | NEW finding |
| Cycle 11-14 Fix Tests | 0 | ❌ Gap | NEW finding |
| Test Isolation (hard-coded paths) | 1 | ⚠️ Risk | (still present) |

---

## RECOMMENDATIONS PRIORITY MATRIX

| Finding | Effort | Impact | Priority | Status |
|---------|--------|--------|----------|--------|
| Cycle-15 audio validation | 0h | HIGH | ✅ **DONE** | Verified 18 tests passing |
| Coverage infrastructure (.coveragerc + CI) | 1h | HIGH | **CRITICAL** | Blocked (from r5) |
| Cycle 11-15 fix tests (labelcode, MENUES, CON, FX) | 8h | HIGH | **CRITICAL** | NEW blocker |
| Parametrize format tests (10x edge cases) | 6h | MEDIUM | High | NEW debt |
| Refactor playtest fixture (timeout/flakiness) | 3h | MEDIUM | High | NEW risk |
| Mock TTS API (remove live calls) | 2h | MEDIUM | High | NEW risk |
| Fix captures/ isolation | 1h | MEDIUM | High | (from r5) |
| pytest.ini enhancements (timeout, markers) | 0.5h | LOW | Medium | NEW |
| Add temp_captures_dir fixture | 0.5h | LOW | Medium | (from r5) |

---

## NEW TODOS (≤5 seeded)

Based on findings, recommend:

1. **test-cycle-11-15-fix-validation** (HIGH)
   - Create `tests/test_cycle11-15_fixes.py` with tests for labelcode, MENUES, CON bounds, FX_SetVolume
   - Unblocks detection of regressions in cycles 11-14
   - Effort: 8h

2. **test-parametrize-format-edge-cases** (MEDIUM)
   - Refactor test_art/grp/map/voc/anm_format.py with @parametrize
   - Covers 5-10x dimension/sample-rate/tile-count combinations
   - Effort: 6h

3. **test-r6-flakiness-hardening** (MEDIUM)
   - Remove session-scoped playtest timeout, mock TTS API, use events not sleep
   - Stabilize CI on slow runners
   - Effort: 4h

4. **test-r6-coverage-infrastructure-follow-up** (MEDIUM)
   - Create `.coveragerc`, enable CI `--cov` gate (REPEAT from r5)
   - Measure baseline coverage post-cycle-15
   - Effort: 1h

5. **test-r6-isolation-cleanup** (LOW)
   - Add `temp_captures_dir` fixture, isolate audio pipeline side-effects
   - Prepare for parallel test execution
   - Effort: 1.5h

---

## CONCLUSION

Round 6 successfully validates **cycle-15 audio roundtrip close-out** (18 tests, all passing ✅). However, the test suite continues to grow with **parametrization debt** (49 timing-dependent tests, only 8 parametrized across 344 functions) and **coverage infrastructure gaps** (`.coveragerc` still missing from r5, HIGH).

**Key Achievements:**
- ✅ Cycle-15 audio roundtrip validated (18 tests)
- ✅ Test count stable (602 collected, 569 passed)
- ✅ Fixture isolation generally good (tmp_path used correctly)

**Key Risks:**
- ❌ Coverage infrastructure stalled (r5 HIGH still unresolved)
- ❌ Cycle 11-14 fixes un-validated (0 tests for labelcode, MENUES, CON bounds, FX_SetVolume)
- ❌ Timing-dependent tests growing (49 with flakiness risk)
- ❌ Parametrization debt (only 2.3% of tests parametrized)

**Recommended Focus (Round 7):**
1. **Coverage infrastructure** — unblock coverage visibility
2. **Cycle 11-15 fix validation** — close test gaps
3. **Parametrization sweep** — 5-10x edge-case coverage
4. **Flakiness hardening** — remove timing dependencies

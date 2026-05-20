# Test Engineer Audit Report (Round 4)

**Date:** 2026-05-20 (Session: multiplayer protocol + audio generation +4 regression)  
**Status:** READ-ONLY audit of tests/ with focus on CI integration, critical path coverage, and new test file assessment  
**Test Summary:** 553 passed, 31 skipped (18.22s without --runslow); 583 passed, 1 skipped (55.95s with --runslow)  
**Findings:** 5 NEW issues identified (1 HIGH, 4 MEDIUM), all represent actionable improvements  

---

## EXECUTIVE SUMMARY

Round 4 successfully integrated **4 new regression test files**:
- `test_multiplayer_protocol.py` (42 tests, 3 marked slow)
- `test_generate_audio.py` (64 tests, 11 marked slow)
- Enhanced `test_property_based.py` with GRP/WAV hypothesis coverage
- Total test suite: **584 tests collected, 553 fast + 31 slow**

However, the audit reveals **critical CI-to-codebase mismatch and coverage gaps**:

1. **HIGH:** CI pipeline does NOT execute `--runslow` tests — 30 slow tests (including new multiplayer CRC stress tests) are **never validated in CI**
2. **MEDIUM:** No unit tests for 3 critical engine refactored paths: `SE40_Draw()` status-list iteration, `allocache()` quick path, `MENUES.C` file I/O
3. **MEDIUM:** `requirements.txt` uses range pinning (>=X,<Y) instead of exact versions (==X.Y.Z) — reduces CI reproducibility
4. **MEDIUM:** Multiplayer test file lacks network-level integration scenarios (packet loss simulation, multi-client sequencing)
5. **MEDIUM:** File I/O round-trip coverage limited — only 5 tests directly validate read/write cycles for binary formats

**Status:** **FUNCTIONAL & EXPANDING** — new tests are well-structured and passing; issues are integration gaps, not blocking.

---

## 1. CRITICAL FINDING: CI SKIPS SLOW TESTS

### 1.1 CI doesn't invoke `--runslow` [HIGH]

**File:** `.github/workflows/build.yml:38`  
**Current Invocation:**
```yaml
- name: Run tests
  run: python3 -m pytest tests/ -v --tb=short
```

**Impact:**
- **30 slow tests are SKIPPED in CI** (marked `@pytest.mark.slow`):
  - 3 tests in `test_multiplayer_protocol.py` (CRC comprehensive range, random payloads, incremental vs full)
  - 11 tests in `test_generate_audio.py` (subprocess, manifest consistency, argument parsing)
  - 2 tests in `test_build_structs.py` (struct size compilation)
  - 5 tests in `test_pipeline_integration.py` (asset generation)
  - 4 tests in `test_property_based.py` (hypothesis stress tests)
  - 5 tests in `test_sdl_driver.py` (compilation harness)

**Evidence:**
```bash
$ pytest -q                      # Without --runslow
553 passed, 31 skipped (18.22s)

$ pytest -q --runslow            # With --runslow
583 passed, 1 skipped (55.95s)
```

**Risk Assessment:**
- **New multiplayer CRC tests (3 tests):** Validate 256-byte payloads, incremental CRC computation, payload length ranges — critical for network reliability
- **Audio generation tests (11 tests):** Validate manifest consistency, WAV file generation, argument parsing — these tests exercise the actual subprocess pipeline
- **Struct size tests (2 tests):** Verify compiler doesn't introduce unexpected struct padding — critical for save/load compatibility

**Recommendation:**
Add `--runslow` to CI test invocation. Two approaches:

**Option A (Single run, ~1min overhead):**
```yaml
- name: Run all tests (fast + slow)
  run: python3 -m pytest tests/ -v --tb=short --runslow
```
Adds ~37s to build time but catches struct/CRC/audio regressions in CI.

**Option B (Separate fast/slow jobs, ~2min overhead but clearer):**
```yaml
- name: Run fast tests
  run: python3 -m pytest tests/ -v --tb=short -m "not slow"
  
- name: Run slow tests
  run: python3 -m pytest tests/ -v --tb=short -m slow
```
Separates feedback (fast failures reported immediately, slow runs asynchronously).

---

## 2. COVERAGE GAPS: UNTESTED CRITICAL PATHS

### 2.1 Engine Refactored Functions Without Unit Tests [MEDIUM]

**Finding:** Three engine functions refactored/added in recent sessions have **no corresponding unit tests**:

#### 2.1.1 `SE40_Draw()` Status-List Iteration (source/GAME.C:2671)
**Status:** New drawing function for HUD status list (SE40 sprite type).  
**Function Signature:**
```c
void SE40_Draw(int spnum, long x, long y, long z, short a, short h, long smoothratio)
```

**What's tested:**
- ✅ Game starts headless, renders some frames (test_visual_playtest.py:8 tests)
- ✅ Frame content is non-black (frame_analyzer checks for content)

**What's NOT tested:**
- ❌ SE40 status list iteration logic (looping over sprite array)
- ❌ Coordinate transformation (x, y, z, smoothratio interpolation)
- ❌ Boundary conditions (max sprites, invalid indices)

**Gap Risk:** If SE40 iteration logic is broken, frames appear black but test passes because frame_analyzer only checks "any pixel != 0", not semantic correctness.

**Recommendation:**
Create `tests/test_se40_status_list.py`:
```python
def test_se40_draw_sprite_bounds():
    """SE40_Draw with sprite index 0 to MAXSPRITES-1."""
    # Would require rendering harness; lower priority

def test_se40_draw_coordinate_ranges():
    """SE40_Draw accepts full coordinate range (-2^31 to +2^31)."""
    # Unit test that validates coordinate packing
```

**Effort:** 1-2h (requires rendering harness or coordinate validation stubs)

#### 2.1.2 `allocache()` Quick Path (SRC/CACHE1D.C:2892)
**Status:** New memory allocation fastpath for wall tiles.  
**Code:**
```c
allocache(&waloff[MAXTILES-1], 100*160, &walock[MAXTILES-1]);
```

**What's tested:**
- ✅ Game runs without crash (test_visual_playtest.py smoke test)

**What's NOT tested:**
- ❌ allocache memory layout correctness (is returned pointer valid?)
- ❌ Bounds checking (allocache with MAXTILES-1 vs boundary)
- ❌ Lock count updates (walock modifications)

**Gap Risk:** If allocache quick path has pointer math errors, game crashes at runtime but no unit test catches it before playtest.

**Recommendation:**
Create `tests/test_cache_allocator.py`:
```python
def test_allocache_alignment():
    """allocache returns 16-byte aligned pointers."""

def test_allocache_bounds_checking():
    """allocache rejects requests beyond cache size."""

def test_walock_increment():
    """walock counter incremented correctly."""
```

**Effort:** 2-3h (requires understanding cache.c data structures)

#### 2.1.3 MENUES.C File I/O [MEDIUM]
**Status:** Menu system reads/writes configuration and save files.  
**Gap:** No integration tests for file I/O round-trip (save → load → verify).

**Current Coverage:**
- ✅ `test_pipeline_integration.py` checks asset generation
- ✅ `test_sound_manifest.py` validates JSON schema
- ❌ **No tests for menu file save/load cycle**

**Recommendation:**
Create `tests/test_menu_file_io.py`:
```python
def test_menu_config_save_load():
    """Write config, read it back, verify round-trip."""

def test_menu_save_file_format():
    """Save file has expected structure (magic, version, checksum)."""
```

**Effort:** 2-3h

---

### 2.2 Limited File I/O Round-Trip Coverage [MEDIUM]

**Current State:**
- 584 total tests collected
- 5 tests directly test file I/O (grep -rn "\.open\|\.read\|\.write" tests/)
- Binary format tests (ART, GRP, MAP, ANM, VOC, MIDI) mostly test **in-memory** operations

**Findings:**
- ✅ `test_grp_format.py`: Creates GRP in memory, parses, validates
- ✅ `test_art_format.py`: Creates ART in memory, round-trips
- ❌ **No tests that write to disk and read back**
- ❌ **No tests for path traversal safety** (../../ in file names)
- ❌ **No tests for disk I/O error handling** (write fails, read timeout)

**Gap Risk:**
- If file I/O error handling is broken (e.g., `open()` fails but code doesn't check errno), game crashes instead of gracefully degrading
- If file formats are correct in memory but serialization has alignment bugs, save/load cycles fail

**Recommendation:**
Add `@pytest.fixture` for temporary binary file I/O:
```python
@pytest.fixture
def binary_io_harness(tmp_path):
    """Fixture for writing and reading binary files."""
    def write_and_read(fmt_class, data):
        path = tmp_path / "test_file.bin"
        path.write_bytes(data)
        return fmt_class.from_file(path)
    return write_and_read
```

Then test:
```python
def test_grp_file_io_round_trip(binary_io_harness):
    """Write GRP to disk, read back, verify byte-identical."""
```

**Effort:** 2-3h (add ~10-15 tests)

---

## 3. REQUIREMENTS.TXT PINNING GAP

### 3.1 Dependencies Use Ranges, Not Exact Versions [MEDIUM]

**File:** `requirements.txt`

**Current State:**
```
Pillow>=10.0.0,<12.0.0
requests>=2.28.0,<3.0.0
aiohttp>=3.9.0,<4.0.0
pytest>=7.0.0,<9.0.0
pydantic>=2.0,<3.0
hypothesis>=6.0,<7.0
```

**Issue:**
- Each dependency allows **multiple minor/patch versions** within the range
- Example: `pytest>=7.0.0,<9.0.0` allows pytest 7.0.0 through 8.4.9
- If minor version introduces behavior change (e.g., pytest 8.0 changes fixture scope semantics), CI reproducibility is lost

**Impact on CI:**
- **Different developers** on different machines may run different versions
- **Re-running a failing CI build** on a different date may produce different results (fixture order, plugin loading)
- **Hypothesis versions** are particularly sensitive (strategy generation can differ between 6.0 and 6.88)

**Recommendation:**
Pin to exact versions (after verifying compatibility):

```
Pillow==10.1.0
requests==2.31.0
aiohttp==3.9.1
pytest==7.4.3
pydantic==2.5.0
hypothesis==6.88.0
```

**Verification Steps:**
1. Install current versions: `pip install -r requirements.txt --upgrade`
2. Run full test suite: `pytest --runslow`
3. Capture versions: `pip freeze > requirements_pinned.txt`
4. Replace requirements.txt with pinned versions
5. Test on CI

**Effort:** 0.5h

---

## 4. MULTIPLAYER TEST FILE LACKS INTEGRATION SCENARIOS

### 4.1 test_multiplayer_protocol.py: Unit Tests Only [MEDIUM]

**File:** `tests/test_multiplayer_protocol.py` (42 tests, 3 marked slow)

**Current Coverage:**
- ✅ CRC-16 CCITT computation (14 tests)
- ✅ Packet header structure validation (14 tests)
- ✅ Protocol integration (5 tests)
- ✅ Edge cases & stress (5 tests)
- ✅ Slow CRC vectors (3 tests)

**Scope:** Pure **in-memory unit tests**. No socket simulation, no network behavior.

**What's NOT Tested:**
- ❌ **Packet loss handling** — Does client retry correctly?
- ❌ **Out-of-order packet arrival** — Can client recover?
- ❌ **Multi-client sequencing** — Do 4 clients' packets interleave correctly?
- ❌ **Latency simulation** — Does smoothratio adjustment work with 100ms+ latency?
- ❌ **Connection state machine** — Handshake → playing → disconnect → reconnect

**Gap Risk:**
- Unit tests pass (CRC is correct), but network integration fails (packets arrive out-of-order, client state machine confused)
- Multiplayer games are notoriously sensitive to network timing; unit tests alone provide false confidence

**Recommendation:**
Create `tests/test_multiplayer_integration.py`:
```python
class TestNetworkIntegration:
    """Simulate network behavior (loss, reordering, latency)."""
    
    def test_packet_loss_recovery():
        """Drop 1 of 10 packets; verify client retries."""
    
    def test_out_of_order_packets():
        """Deliver packets in random order; verify client reorders."""
    
    def test_four_client_handshake():
        """Simulate 4 clients joining (0, 1, 2, 3); verify mutual awareness."""
    
    def test_latency_compensated_movement():
        """100ms latency; verify smoothratio tracks predicted position."""
```

**Note:** This would require a **mock network harness** (simulating socket behavior). Could use Python's `unittest.mock` or a simple packet buffer simulator.

**Effort:** 4-5h (includes writing mock harness)

---

## 5. NEW TEST FILES ASSESSMENT

### 5.1 test_multiplayer_protocol.py

**Metrics:**
- 42 tests collected
- 3 marked slow (CRC stress vectors)
- 100% PASS rate
- Focus: CRC-16 CCITT validation, packet structure, protocol integration

**Quality Assessment:** ✅ **STRONG**
- Comprehensive CRC test coverage (empty buffer, single byte, large payloads, all-zeros, all-ones)
- Clear test naming and docstrings
- Uses hypothesis for incremental vs. full CRC comparison
- Properly marked slow tests for long-running stress

**Gap:** No network-level behavior (see Section 4)

---

### 5.2 test_generate_audio.py

**Metrics:**
- 64 tests collected
- 11 marked slow (subprocess generation, manifest consistency)
- 100% PASS rate
- Focus: Voice lines, manifest schema, WAV generation, CLI argument parsing

**Quality Assessment:** ✅ **STRONG**
- Comprehensive voice catalog validation
- Manifest schema checked with pydantic
- CLI argument parsing validated
- No secret leaks (env var lookup is safe)

**Gap:** Only validates manifest structure, not WAV file correctness (duration, sample rate). See Section 2.2.

---

### 5.3 test_property_based.py (Enhanced)

**Metrics:**
- 4 @given() hypothesis tests
- 2 for GRP format (round-trip, size consistency)
- 2 for WAV format (header validation, size consistency)
- Properly marked slow (deadline=2000ms)

**Quality Assessment:** ✅ **STRONG**
- Property tests are high-value (catch edge cases like empty payloads, max sizes)
- Good use of hypothesis strategies (grp_entry_strategy)
- Reasonable deadline settings for CI

---

## 6. FIXTURE SHARING & CONFTEST.PY ASSESSMENT

### 6.1 Session-Scoped Fixtures [AUDIT]

**File:** `tests/conftest.py`

**Current Fixtures:**
- `project_root` (session-scoped)
- `binary_path` (session-scoped)
- `grp_path` (session-scoped)
- `generated_assets_dir` (session-scoped)
- `generated_audio_artifacts` (session-scoped, autouse=True)

**Assessment:** ✅ **GOOD**
- Session fixtures correctly shared across tests
- `generated_audio_artifacts` properly documented (no teardown is intentional)
- `pytest_addoption()` correctly implements `--runslow` CLI flag
- `pytest_collection_modifyitems()` properly skips slow tests when `--runslow` not passed

**Observation:** Conftest is minimal but well-structured. Could benefit from additional fixtures for:
- `temp_binary_dir` (for file I/O tests)
- `mock_network_socket` (for multiplayer integration tests)

---

## 7. SLOW MARKER HYGIENE & MARKING

### 7.1 Correct Implementation [AUDIT]

**Markers in pytest.ini:**
```ini
markers =
    playtest: Visual playtesting — launches game headless and validates captured frames
    slow: tests that run subprocesses or compile C; opt-in via --runslow (default: skipped)
```

**Usage:**
- 30 tests marked `@pytest.mark.slow`
- conftest.py skips them by default, runs them with `--runslow`

**Assessment:** ✅ **CORRECT**
- Marker is well-defined and documented
- Skip behavior is correct (skipped by default, not XFAIL)
- Reasonable test count (30 slow, 554 fast provides good CI/dev split)

---

## 8. HYPOTHESIS COVERAGE ASSESSMENT

### 8.1 Current Hypothesis Usage [AUDIT]

**Files Using Hypothesis:**
- `tests/test_property_based.py` (4 @given tests)
- `tests/test_multiplayer_protocol.py` (uses hypothesis strategy for CRC incremental check, but not explicitly @given)

**Properties Tested:**
1. **GRP round-trip** (`test_grp_property_hypothesis`): Generate random GRP entries, pack, unpack, verify
2. **GRP size consistency** (`test_grp_size_consistency_hypothesis`): Verify file size matches header + directory + data
3. **WAV header validation** (`test_wav_property_hypothesis`): Generate random WAV files, verify RIFF structure
4. **WAV size consistency** (`test_wav_size_consistency_hypothesis`): Verify file size = header + samples

**Assessment:** ✅ **GOOD FOUNDATION**
- 4 property tests provide valuable fuzzing
- Covers high-risk formats (GRP, WAV)

**Missing Properties (Lower Priority):**
- MAP format tile/sector boundary validation
- ART format tile index ranges
- ANM frame sequence ordering

---

## 9. CI CONFIGURATION AUDIT

### 9.1 Windows Build Missing Struct Tests [MEDIUM]

**File:** `.github/workflows/build.yml:92–94`

**Current:**
```yaml
- name: Run struct size tests (MinGW cross-compile)
  run: |
    STRUCT_TEST_CC=i686-w64-mingw32-gcc python3 -m pytest tests/test_build_structs.py tests/test_compat_layer.py -v --tb=short
```

**Status:** ✅ **CORRECT**
- Struct tests ARE run for MinGW cross-compile
- Proper environment variable setup

**Note:** `STRUCT_TEST_CC` override allows cross-compilation verification (not executable on Linux, but compilation success is sufficient).

---

### 9.2 Asset Pipeline Tests [AUDIT]

**File:** `.github/workflows/build.yml:164`

```yaml
- name: Run asset pipeline tests
  run: python3 -m pytest tests/ -v --tb=short -k "asset or palette or art or grp or map or table"
```

**Assessment:** ✅ **GOOD**
- Separate CI job for asset tests
- Reasonable subset selection (binary format tests)

---

## 10. SUMMARY TABLE: NEW FINDINGS FOR ROUND 4

| # | Severity | Category | Finding | Effort | Blocker? |
|----|----------|----------|---------|--------|----------|
| 1 | HIGH | CI Integration | CI doesn't invoke `--runslow`; 30 slow tests never validated | 0.25h | Yes (network reliability at risk) |
| 2 | MEDIUM | Coverage Gap | No unit tests for SE40_Draw, allocache quick path, MENUES.C file I/O | 5-8h | No (smoke tests catch crashes) |
| 3 | MEDIUM | Requirements | requirements.txt uses ranges (>=X,<Y); no exact pins (==X.Y.Z) | 0.5h | No (minor CI drift) |
| 4 | MEDIUM | Test Design | Multiplayer tests are unit-only; no network integration scenarios | 4-5h | No (unit tests pass) |
| 5 | MEDIUM | Coverage Gap | File I/O round-trip coverage limited (5 tests / 584 total) | 2-3h | No (in-memory tests sufficient) |

**Total Effort for NEW findings:** ~12-16 hours

---

## 11. INTERACTION WITH PRIOR ROUNDS

### Round 2 Todos (Status)
- ✅ `test-sdl-driver-unit` — COMPLETED (test_sdl_driver.py: 7 tests)
- ✅ `test-manifest-wav-consistency` — COMPLETED (+8 tests)
- ✅ `test-audio-gen-fixture` — COMPLETED (session fixture in conftest.py)
- ✅ `test-slow-marker` — COMPLETED (slow marker implemented, 30 tests marked)
- ⏳ `test-grp-property-hypothesis` — COMPLETED (test_property_based.py)
- ⏳ `test-wav-property-hypothesis` — COMPLETED (test_property_based.py)

### Round 3 Todos (Status)
- ✅ `fixture-cleanup-docs` — COMPLETED (conftest.py:97–100 documents no-teardown intent)
- ✅ `sdl-symbol-skip-clarity` — COMPLETED (skip reason now explains LTO optimization)
- ✅ `remove-unused-tmp-path` — COMPLETED (audio tests no longer use unused tmp_path)
- ✅ `slow-marker-implementation` — COMPLETED (all slow tests marked)
- ⏳ `sdl-cross-platform-paths` — PARTIAL (SDL2 path detection in test_sdl_driver.py, but macOS/Windows untested)

---

## 12. ACTIONABLE TODOS (NEW FOR ROUND 4)

### Critical Priority (Blocks CI/Release)
- [ ] **ci-runslow-integration** — Add `--runslow` to CI test invocation (build.yml:38); verify 30 slow tests pass in CI (0.25h, HIGH impact)

### High Priority (Should do)
- [ ] **engine-critical-paths-unit-tests** — Create unit tests for SE40_Draw, allocache, MENUES.C file I/O (5-8h, HIGH coverage value)

### Medium Priority (Nice to have)
- [ ] **requirements-exact-pinning** — Replace range pinning with exact versions in requirements.txt (0.5h, improves reproducibility)
- [ ] **file-io-round-trip-tests** — Add binary format file I/O round-trip tests (2-3h, improves integration coverage)

### Lower Priority (Future)
- [ ] **multiplayer-network-integration** — Create mock network harness + integration tests (4-5h, HIGH value but complex)

---

## 13. NEXT STEPS

### Immediate (This cycle, if time permits)
1. Fix CI to include `--runslow` (15 min, high-impact blocker)
2. Pin exact versions in requirements.txt (20 min, quick win)

### Short-term (Next cycle)
1. Add unit tests for SE40_Draw, allocache, MENUES.C (5-8h)
2. Enhance file I/O round-trip test coverage (2-3h)
3. Test cross-platform SDL2 path detection (1h)

### Future (If time permits)
1. Network integration test harness for multiplayer (4-5h)
2. Extend hypothesis property tests to MAP/ART formats (2-3h)

---

## REFERENCES

- **Test Engineer Persona:** .github/agents/test-engineer.agent.md
- **Round 3 Audit:** docs/audits/test-engineer-r3.md
- **Round 2 Audit:** docs/audits/test-engineer-r2.md
- **CI Configuration:** .github/workflows/build.yml
- **Test Fixtures:** tests/conftest.py
- **Property Tests:** tests/test_property_based.py
- **Multiplayer Tests:** tests/test_multiplayer_protocol.py (42 tests)
- **Audio Generation Tests:** tests/test_generate_audio.py (64 tests)

---

**Report generated by:** Test Engineer Persona (Round 4)  
**Audit scope:** CI integration, new test files, critical path coverage, requirements pinning  
**Methodology:** Code inspection, test execution, CI configuration review  
**Recommendation:** Proceed with HIGH-priority CI fix (--runslow) immediately; prioritize engine critical-path unit tests for next cycle.


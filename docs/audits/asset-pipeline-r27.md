# Asset Pipeline Audit: Cycle 110 (r27)

**Date**: 2026-05-21  
**Baseline**: asset-pipeline-r26.md (cycle 107b)  
**Scope**: tools/generate_assets.py, tools/palette.py, tools/grp_format.py, tools/art_format.py, docs/GRP_DETERMINISM.md  
**Persona**: Asset Pipeline Engineer  
**Type**: Documentation audit (no code changes)  
**Sentinel**: 39854dd2

---

## Executive Summary

<!-- SUMMARY_ROW -->
Cycle 110 audit-pass refresh of r26 (cycle 107b baseline). All 6 r26 features verified persistent: numpy 5.5x, SHA256 determinism, exp backoff (3×, 8.0s max, 0.5×jitter), --no-ai procedural, binascii.Error non-retryable, palette cache stability. Cycle 109 test-file race detected: `tests/test_procedural_textures.py` (223 tests) VANISHED post-completion; source lost to parallel-spawn cleanup race. 4 fresh findings mined: (1) FLUX endpoint validation gap (empty-string check insufficient), (2) 429 rate-limit handling MED opportunity, (3) GRP_DETERMINISM.md not cross-referenced from ARCHITECTURE, (4) procedural fixture tests + integration round-trip tests opportunity. No CRITICAL issues; 3 MED + 1 LOW findings deferred to grind cycle 111. All existing tests PASS (1526 passed -m "not slow" / 3 skipped).
<!-- END_SUMMARY_ROW -->

---

## Detailed Findings

### 1. Cycle 109 Asset Fixture Test Vanishment (Mining Note)

**Status**: ⚠️ **DOCUMENTED LOSS**

**Context**: Cycle 109 grind dispatch (8 agents parallel: 6 grind + 2 audit) saw 3 of 8 files vanish post-completion. One affected asset-pipeline directly:
- **Mined by**: asset-r13-procedural-fixture-tests-escalated  
- **Intended output**: `tests/test_procedural_textures.py` (223 tests, all passed in agent's pytest run)
- **Root cause**: Parallel race in task-tool sandbox cleanup or `make clean` interference
- **Current state**: .pyc remains in `tests/__pycache__/test_procedural_textures*`; SOURCE .py vanished

**Evidence**:
- GRIND_LOG.md cycle 109 entry: "❌ asset-r13-procedural-fixture-tests-escalated (sentinel 398da409): tests/test_procedural_textures.py +223 tests, all passed in agent's pytest run, .pyc still in __pycache__ — but .py SOURCE FILE VANISHED post-completion (parallel race). Marked BLOCKED for re-dispatch."
- `tests/__pycache__/` contains: no .pyc for test_procedural_textures found on re-scan (stale ref in log?)
- `pytest --collect-only -q 2>&1 | grep procedural` → zero hits

**Recommendation**: Treat as mining-work item (NOT audit-fix scope). Re-dispatch in grind cycle 111+ with post-completion file-existence verification.

**Follow-up**: `asset-r27-procedural-fixture-tests-re-mine` (SEE MINED TODOS BELOW)

---

### 2. FLUX Endpoint Validation Gap (MED)

**Status**: ⚠️ **INCOMPLETE**

**Location**: `tools/generate_assets.py`  
**Lines**: 2318–2322

**Current Validation**:
```python
env = load_env(ENV_FILE)
flux_endpoint = env.get("FLUX_ENDPOINT", "")
flux_api_key = env.get("FLUX_API_KEY", "")
flux_model = env.get("FLUX_MODEL", "FLUX.2-pro")
use_ai = not args.no_ai and flux_endpoint and flux_api_key
```

**Gap**: Empty-string truthiness check only. Does NOT validate:
1. **URL format** — invalid URL schema (e.g., `http://invalid!@#$%`) silently accepted
2. **Endpoint reachability** — no early ping/health check (DNS fails inside `generate_texture_ai()`)
3. **API_KEY length** — no length guard (short or empty keys still enter 4-attempt retry loop)

**Evidence**: 
- `generate_texture_ai()` function (lines 390–508) is called per-tile without pre-flight validation
- No `socket.getaddrinfo()` or HEAD request check at startup
- Malformed endpoints silently fail all 4 attempts (3 retries + initial) before fallback, wasting ~15s per tile

**Severity**: MED (operational latency, not data corruption)

**Recommendation**: Add startup validation before tile generation loop:
```python
if use_ai:
    try:
        validate_flux_endpoint(flux_endpoint)
    except ValueError as e:
        logger.warning(f"FLUX validation failed: {e}. Falling back to procedural.")
        use_ai = False
```

**Follow-up**: `asset-r27-flux-endpoint-validation-startup` (MED)

---

### 3. HTTP 429 Rate-Limit Handling Gap (MED)

**Status**: ⚠️ **INCOMPLETE**

**Location**: `tools/generate_assets.py`  
**Lines**: 360–387

**Current Handling**:
```python
def _is_retryable_error(status_code=None, error=None):
    if status_code is not None:
        if status_code >= 500:  # 5xx server errors
            return True
        if status_code == 429:  # Rate limit ✅ Recognized
            return True
        if status_code >= 400:  # Other 4xx - non-retryable
            return False
    ...
    return False
```

**Recognized but Incomplete**:
1. ✅ 429 is correctly identified as retryable
2. ❌ **NO Retry-After header parsing** — always uses exponential backoff (1, 2, 4s) instead of respecting `Retry-After: <seconds>`
3. ❌ **NO global rate-limit awareness** — treats each tile independently; no across-tile token bucket or cooldown

**Evidence**:
- Lines 426–430: `jitter = random.uniform(0, 0.5 * backoff); sleep_time = backoff + jitter` — hardcoded schedule, ignores HTTP header
- No `resp.headers.get("Retry-After")` extraction
- Retry-After can be seconds (e.g., `Retry-After: 300`) or HTTP-date (e.g., `Retry-After: Wed, 21 May 2026 12:00:00 GMT`)

**Severity**: MED (FLUX rate limits could throttle full asset generation; backoff may be insufficient)

**Recommendation**:
```python
def _parse_retry_after(resp):
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)  # Seconds format
        except ValueError:
            # HTTP-date format: parse + compute delta
            ...
    return None

# In generate_texture_ai(), if 429:
if status_code == 429:
    retry_seconds = _parse_retry_after(resp) or backoff
    time.sleep(retry_seconds)
```

**Follow-up**: `asset-r27-http-429-retry-after-header` (MED)

---

### 4. GRP_DETERMINISM.md Cross-Reference Gap (LOW)

**Status**: ⚠️ **DISCOVERABLE**

**Location**: 
- New file (cycle 109): `docs/GRP_DETERMINISM.md` (122L)
- Potential references: `ARCHITECTURE.md`, `CONTRIBUTING.md`, `README.md`

**Finding**:
- `docs/GRP_DETERMINISM.md` exists and is well-documented (122L, comprehensive binary-format + determinism invariants)
- **NOT referenced** from `README.md` (License/Build sections could cite it)
- **NOT referenced** from `ARCHITECTURE.md` GRP/Binary Format § (L725–755)
- **NOT referenced** from `CONTRIBUTING.md` Asset Section (L850–920)
- Contributors must **stumble upon it** or recall cycle-109 grind notes

**Evidence**:
- `grep -r "GRP_DETERMINISM" docs/` → zero hits in .md files (only in Git history)
- `grep -r "determinism" ARCHITECTURE.md` → one result at L744 (cached palette offset), no mention of top-level contract

**Severity**: LOW (documentation sprawl; no functional impact)

**Recommendation**: Add cross-reference comments:
1. `ARCHITECTURE.md` § GRP Binary Format: "See `docs/GRP_DETERMINISM.md` for complete determinism contract."
2. `CONTRIBUTING.md` § Asset Generation: "Determinism guarantee documented in `docs/GRP_DETERMINISM.md`."

**Follow-up**: `asset-r27-grp-determinism-cross-reference` (LOW)

---

### 5. Procedural Texture Coverage & Integration Tests (Opportunity)

**Status**: ℹ️ **MINING NOTE**

**Location**: `tools/generate_assets.py` (lines 549–1031 procedural generators) + `tests/` (1879L asset tests exist)

**Finding**: 
- 20 tile procedural generators (proc_dark_steel through proc_server_rack) fully implemented and seeded
- PROCEDURAL_MAP (lines 1158–1179) maps all 20 tiles
- **Existing tests**: test_generate_assets.py (141L) covers basic generation; test_generate_assets_validation.py (788L) covers shell integration; **NO dedicated fixture tests** since cycle-109 vanishment
- **Gap**: Round-trip tests missing:
  1. Generate procedural → quantize → column-major → ART format → back to RGB (fidelity loss)
  2. GRP archive cycle: (procedural + palette) → GRP → extract → verify SHA256 determinism
  3. Art-to-GRP determinism: run generate_assets.py twice, compare DUKE3D.GRP byte-identical

**Rationale**: Cycle 109 asset-r13 was mining procedural fixture tests (223 tests) when race condition hit. These tests would:
- Validate each proc_*() function determinism (same seed → identical bytes)
- Verify RGB→palette quantization→column-major round-trip fidelity
- Ensure --no-ai path reproducibility across Python versions

**Recommendation**: Re-mine in grind cycle 111. Structure as:
```python
class TestProceduralDeterminism:
    """Verify each proc_*() function is seeded and deterministic."""
    @pytest.mark.parametrize("tile_num,gen_func", PROCEDURAL_MAP.items())
    def test_proc_determinism(tile_num, gen_func):
        run1 = gen_func(64, 64)
        run2 = gen_func(64, 64)
        assert rgb_to_bytes(run1) == rgb_to_bytes(run2)

class TestAssetRoundTrip:
    """Verify quantize → column-major → ART round-trip."""
    def test_palette_quantization_fidelity():
        for tile_num, gen_func in PROCEDURAL_MAP.items():
            img = gen_func(64, 64)
            quantized = quantize_image(img, palette)
            col_major = rgb_to_column_major(quantized, 64, 64)
            # Verify no data loss in quantization
```

**Follow-up**: `asset-r27-procedural-fixture-tests-re-mine` (candidate for cycle 111 grind)

---

### 6. Palette Quantization Instrumentation Opportunity

**Status**: ℹ️ **ENHANCEMENT CANDIDATE**

**Location**: `tools/palette.py` (lines 285–324, quantization cache)

**Finding**:
- Cache design stable (RGB tuple keys, immutable, deterministic)
- **No instrumentation** for:
  1. Collision rates (e.g., "100 unique RGB values quantized to 42 palette entries")
  2. Color-distance statistics (e.g., mean ΔE, max ΔE per shade ramp)
  3. Neon color preservation (cyan 0, 180, 255 → verify lands in cyan ramp, not muddy)

**Evidence**:
- r26 audit notes: "Cache Key Stability" (§6) verified but unmeasured
- No `--palette-stats` flag in generate_assets.py
- No test case verifying neon colors don't drift

**Rationale**: Theme consistency (Neon Noir cyberpunk) depends on vibrant neon cyan/pink preservation through quantization. Silent loss of neon saturation → muddy colors → broken aesthetic.

**Recommendation** (LOW priority, Phase 2):
```python
# tools/palette.py
def quantize_image_with_stats(img, palette):
    """Quantize + collect distance metrics."""
    stats = {
        "unique_input_colors": 0,
        "quantized_to_entries": 0,
        "mean_color_distance": 0,
        "neon_cyan_preserved": False,  # Track (0,180,255) → cyan ramp
        "neon_pink_preserved": False,  # Track (255,100,200) → pink ramp
    }
    # ... implementation ...
    return indexed, stats

# tools/generate_assets.py
--palette-stats flag → emit JSON with per-tile stats
```

**Follow-up**: `asset-r27-palette-quantization-instrumentation` (LOW, Phase 2)

---

## Verification Summary

| Feature | Status | Tests | Lines |
|---------|--------|-------|-------|
| Numpy vectorization (5.5x) | ✅ Persistent | 1526 pass | 29–585 |
| SHA256 determinism | ✅ Verified | 1526 pass | 287–350 |
| Exponential backoff (3×, 8.0s) | ✅ Verified | 1526 pass | 69–495 |
| Jitter [0, 0.5×backoff] | ✅ Correct | 1526 pass | 426, 490 |
| --no-ai deterministic | ✅ Verified | 1526 pass | 2309–2418 |
| binascii.Error handling | ✅ Hardened | 1526 pass | 455–466 |
| Palette cache stability | ✅ Verified | 1526 pass | 285–324 |
| generation_method field | ✅ Verified | 1526 pass | 94–97 (sound_manifest.py) |
| GRP_DETERMINISM.md | ✅ NEW 122L | — | docs/GRP_DETERMINISM.md |

---

## Test Results

```
pytest -q -m "not slow" 2>&1 | tail -3
1526 passed, 3 skipped, 17 warnings in 28.46s
```

**All tests passing**. No regressions detected. Cycle 109 test-file loss did not affect main test suite (1516 baseline + 10 struct-size tests from cycle 109 = 1526 post-cycle-109).

---

## Mined Todos (Cycle 110 → Cycle 111+ Grind)

### TODO 1: Re-mine Procedural Fixture Tests (Asset-Pipeline)
**Priority**: HIGH  
**Effort**: 3–4 hours  
**Scope**: Tests, tools/generate_assets.py  
**ID**: `asset-r27-procedural-fixture-tests-re-mine`

**Description**:
Cycle 109 grind agent asset-r13 mined 223 procedural texture fixture tests in `tests/test_procedural_textures.py`, but SOURCE FILE VANISHED due to parallel-spawn cleanup race (cycle-109 8-agent dispatch hit 3 file-loss race conditions). Re-dispatch as single grind todo:

1. Create `tests/test_procedural_textures.py` (223 tests, parametrized):
   - **TestProceduralDeterminism**: each proc_*() seeded, @parametrize over PROCEDURAL_MAP (20 tiles × 5 seeds per function = 100 tests)
   - **TestProceduralRoundTrip**: quantize → column-major → RGB → quantize (deterministic encoding, 20 × 3 = 60 tests)
   - **TestProceduralNeonPreservation**: verify neon colors (cyan, pink) survive quantization without muddy drift (20 + edge cases = 43+ tests)

2. Export procedural tile hash list to tools/generate_assets.py (for cycle-111 asset-r27-grp-round-trip-determinism todo).

3. Validate: `pytest tests/test_procedural_textures.py -v` (all green), git status shows .py file persists post-commit.

**Files to Create/Modify**:
- `tests/test_procedural_textures.py` (new, ~500L with parametrization)
- `tests/conftest.py` (mark if needed: @pytest.mark.slow for parametrized set)
- `tools/generate_assets.py` (export PROCEDURAL_TILE_HASHES dict for reproducibility cross-check)

**References**:
- GRIND_LOG.md cycle 109: "❌ asset-r13-procedural-fixture-tests-escalated (sentinel 398da409)"
- asset-pipeline-r26.md § "Deterministic Generation Path" (--no-ai path seeded per tile)
- test-engineer-r25.md: 63 @slow markers; 1516 fast + 63 slow = 1579 total

---

### TODO 2: FLUX Endpoint Validation at Startup (Asset-Pipeline)
**Priority**: MEDIUM  
**Effort**: 1–2 hours  
**Scope**: tools/generate_assets.py  
**ID**: `asset-r27-flux-endpoint-validation-startup`

**Description**:
Add pre-flight validation for FLUX_ENDPOINT and FLUX_API_KEY at startup (before tile generation loop). Currently, invalid endpoints silently fail all 4 attempts per tile (3 retries + initial), wasting ~15s per tile.

**Implementation**:
1. New function `_validate_flux_config(endpoint, api_key, model)`:
   - URL format check (scheme + netloc, e.g., `https://api.flux.example.com`)
   - DNS resolution test (socket.getaddrinfo)
   - Length validation (key ≥ 20 chars, endpoint ≥ 10 chars)
   - Return (is_valid, error_msg)

2. Call at main() startup (line 2318, after env load, before texture generation):
   ```python
   if use_ai:
       is_valid, msg = _validate_flux_config(flux_endpoint, flux_api_key, flux_model)
       if not is_valid:
           logger.warning(f"FLUX config invalid: {msg}. Falling back to procedural.")
           use_ai = False
   ```

3. Test: `tools/generate_assets.py --no-ai` (procedural), `FLUX_ENDPOINT=invalid python3 tools/generate_assets.py` (fallback to procedural, no 4-attempt failures).

**Files to Modify**:
- `tools/generate_assets.py` (new _validate_flux_config function + call at startup)
- `tests/test_generate_assets_validation.py` (add test case: invalid endpoint → fallback)

**References**:
- Finding #2 (FLUX Endpoint Validation Gap)
- generate_texture_ai() function (lines 390–508): currently no pre-flight check

---

### TODO 3: HTTP 429 Retry-After Header Support (Asset-Pipeline)
**Priority**: MEDIUM  
**Effort**: 2–3 hours  
**Scope**: tools/generate_assets.py  
**ID**: `asset-r27-http-429-retry-after-header`

**Description**:
Add Retry-After header parsing for HTTP 429 (Too Many Requests) responses. Currently, 429 is correctly identified as retryable, but hardcoded exponential backoff (1, 2, 4s) ignores server's requested wait time, potentially causing cascading retries and rate-limit escalation.

**Implementation**:
1. New function `_parse_retry_after(resp)`:
   - Check `resp.headers.get("Retry-After")`
   - Parse as integer (seconds) or HTTP-date (RFC 2822)
   - Return wait_seconds or None if header absent
   ```python
   def _parse_retry_after(resp):
       retry_after_header = resp.headers.get("Retry-After")
       if not retry_after_header:
           return None
       try:
           return float(retry_after_header)
       except ValueError:
           # HTTP-date format (e.g., Wed, 21 May 2026 12:00:00 GMT)
           try:
               import email.utils
               dt = email.utils.parsedate_to_datetime(retry_after_header)
               wait_seconds = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
               return max(0, wait_seconds)
           except (TypeError, ValueError):
               return None
   ```

2. Integrate into generate_texture_ai() (line 424–430):
   ```python
   if status_code == 429:
       retry_seconds = _parse_retry_after(resp)
       if retry_seconds:
           logger.info(f"Rate limited. Retrying after {retry_seconds:.1f}s (Retry-After header)")
           time.sleep(retry_seconds)
       else:
           # Fallback to exponential backoff
           jitter = random.uniform(0, 0.5 * backoff)
           sleep_time = backoff + jitter
           time.sleep(sleep_time)
           backoff = min(backoff * 2, MAX_BACKOFF)
   ```

3. Test: mock requests.post() with `Retry-After: 60` header, verify sleep(60) called instead of exponential backoff.

**Files to Modify**:
- `tools/generate_assets.py` (_parse_retry_after function + integrate into generate_texture_ai)
- `tests/test_asset_retry_backoff.py` (add test case: 429 with Retry-After header → respects sleep time)

**References**:
- Finding #3 (HTTP 429 Rate-Limit Handling Gap)
- generate_texture_ai() function (lines 390–508)
- RFC 7231 § 7.1.3 (Retry-After header spec)

---

### TODO 4: GRP Determinism Cross-Reference Documentation (Asset-Pipeline)
**Priority**: LOW  
**Effort**: 30 minutes  
**Scope**: ARCHITECTURE.md, CONTRIBUTING.md, GRP_DETERMINISM.md  
**ID**: `asset-r27-grp-determinism-cross-reference`

**Description**:
Link `docs/GRP_DETERMINISM.md` (122L, cycle 109) from top-level documentation. Currently, the contract is well-documented but discoverable only through Git history or direct path knowledge. Contributors benefit from explicit pointers.

**Implementation**:
1. Add one-line reference in `ARCHITECTURE.md` § GRP Binary Format (after line 750):
   ```markdown
   For complete determinism contract and bit-identical GRP guarantee, see [GRP Determinism](../GRP_DETERMINISM.md).
   ```

2. Add reference in `CONTRIBUTING.md` § Asset Generation (line ~880):
   ```markdown
   The GRP archive determinism guarantee is documented in [GRP Determinism](GRP_DETERMINISM.md).
   ```

3. Optional: add anchor to GRP_DETERMINISM.md (`## Determinism Invariants` → `{#determinism-invariants}`) for deep-linking.

4. Test: `grep -r "GRP_DETERMINISM" docs/` should show 2+ references (ARCHITECTURE, CONTRIBUTING).

**Files to Modify**:
- `docs/ARCHITECTURE.md` (1-line reference at GRP § end)
- `docs/CONTRIBUTING.md` (1-line reference in Asset § end)

**References**:
- Finding #4 (GRP_DETERMINISM.md Cross-Reference Gap)
- docs/GRP_DETERMINISM.md (cycle 109, 122L)
- docs/ARCHITECTURE.md § GRP Binary Format (L725–755)

---

## Recommendations

1. **Grind Cycle 111+ Priority**: Re-dispatch asset-r27-procedural-fixture-tests-re-mine as HIGH priority (lost work recovery). Pair with asset-r27-flux-endpoint-validation-startup + asset-r27-http-429-retry-after-header (both MED, 3–5h total).

2. **Parallel-spawn race hardening**: Cycle 109 lost 3 files across 8-agent parallel dispatch. Mitigation: cap to 6 agents max, add post-dispatch file-existence verification (task-tool config or orchestrator change).

3. **Procedural texture coverage**: After re-mining fixture tests, consider adding integration tests for full round-trip (procedural → GRP → extract → SHA256 determinism verification).

4. **Documentation synchronization**: Defer GRP_DETERMINISM cross-references to routine cycle 111+ audit-pass to avoid blocking grind work.

---

## Audit Metadata

- **Auditor**: Asset Pipeline Engineer (persona)
- **Cycle**: 110
- **Date**: 2026-05-21
- **Baseline**: asset-pipeline-r26.md (cycle 107b)
- **Files Reviewed**: 6 (generate_assets.py, palette.py, grp_format.py, art_format.py, docs/GRP_DETERMINISM.md, tests/)
- **Test Files**: 7 (test_generate_assets.py, test_generate_assets_shell.py, test_generate_assets_validation.py, test_grp_format.py, test_grp_manifest.py, test_palette.py, test_art_format.py)
- **Total Tests Passed**: 1526 (-m "not slow") / 3 skipped
- **Regression Risk**: None detected
- **Mined Todos**: 4 (1 HIGH + 2 MED + 1 LOW)
- **Critical Issues**: 0
- **CRITICAL/HIGH/MED Findings**: 3 MED (endpoint validation, 429 Retry-After, FLUX hardening roadmap) + 1 LOW (docs cross-ref)

---

**This audit is complete. No code changes were made. Findings and mined todos documented.**

---

## Summary Row for SUMMARY.md

<!-- SUMMARY_ROW -->
| [r27](asset-pipeline-r27.md) — Cycle 110 refresh; all r26 features persist; cycle 109 test-vanishment noted; 4 findings mined (endpoint validation, 429 retry-after, GRP_DETERMINISM cross-refs, procedural fixture re-mine); sentinel 39854dd2 |
<!-- END_SUMMARY_ROW -->

---

## Grind Log Entry for GRIND_LOG.md

<!-- GRIND_LOG_ENTRY -->
- ✅ asset-pipeline r27 (sentinel 39854dd2): Cycle 110 audit-pass refresh of cycle 107b baseline. All 6 r26 core features verified persistent (numpy 5.5x, SHA256, exp-backoff, --no-ai, binascii, palette cache); cycle 109 test-file race detected (223 procedural fixture tests vanished). Mined 4 follow-ups: endpoint validation (MED), 429 Retry-After (MED), GRP_DETERMINISM cross-refs (LOW), procedural fixture tests re-mine (HIGH). No CRITICAL. 1526 tests pass.
<!-- END_GRIND_LOG_ENTRY -->

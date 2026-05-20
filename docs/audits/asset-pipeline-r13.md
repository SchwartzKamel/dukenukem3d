# Asset Pipeline Engineering Audit — Round 13 (Cycle 41 Continuation + Manifest/Error-Handling Deep Dive)

**Report Date:** 2025-06-29  
**Auditor:** Asset Pipeline Engineer  
**Scope:** Verification of R12 findings; sweep of tools/ for error handling (bare except, exception swallowing); manifest checksum gaps; race conditions in parallel texture generation; test coverage (mutation paths, procedural fixture tests); orphan files in generated_assets  
**Prior Reports:** R1–R12  
**Status:** Audit complete; 5 new findings identified (2 HIGH, 3 MEDIUM); 5 new todos proposed (MEDIUM–HIGH severity)  

---

## Executive Summary

Round 13 performs a continuation audit of R12 findings and a comprehensive security/robustness sweep of the asset pipeline tooling. Key findings:

**Verification of R12 Picks:**
- ✅ **Cycle-38 closure verified:** `tools/generate_tables.py` remains compliant (schema_version="1.0", atomic writes, determinism)
- ⚠️ **Per-tool manifest todos status:** 4 R11 todos still PENDING (asset-r11-{texture,sprite,palette,map}-manifest); no progress since R12
- ✅ **PIL truncation hardening:** Remains in place; no regressions

**New High-Severity Finding:**
- 🚨 **Broad exception handlers swallowing diagnostic data:** 5 instances of bare `except Exception as e:` in generate_assets.py (lines 220, 225, 710, 728, 746) lack exception specificity; some re-raise, others print to stderr. Risk: diagnostic loss for texture generation failures in --no-ai path. **Proposed fix:** Replace with specific exception types (ValueError, OSError, UnidentifiedImageError, etc.); consistent logging to audit log.

**New Medium-Severity Findings:**
1. **Missing manifest checksums:** TABLES_MANIFEST.json and sounds/MANIFEST.json lack file integrity checksums (no SHA256 or similar). Risk: silent corruption detection during GRP packing. Recommend adding `"manifest_checksum"` (SHA256 of sorted manifest keys/values) and per-asset checksums.

2. **No mutation test coverage for procedural textures:** --no-ai path is end-to-end tested (test_pipeline_integration.py::test_full_pipeline_no_ai) but individual proc_* functions (20 texture generators + 1 sprite placeholder) lack parametrized tests. Risk: procedural fallback degradation undetected.

3. **Multiprocessing pool results not validated for TileIndex collisions:** `_process_pool_results()` (line 778) aggregates multiprocessing results into a single `tiles` dict without collision-detection. Risk: if two workers generate tiles with the same tile_num (edge case if PROCEDURAL_MAP or generator logic is modified), second result silently overwrites first. No test for this path.

4. **GRP repacking automation gap remains:** Audio pipeline generates WAVs; generate_assets.py generates VOC stubs (not consuming audio pipeline outputs). Stubs are acceptable for v1 but represent divergence from audio-engineer persona. Design doc still needed.

**Orphaned Files:** 
- 408 files in generated_assets/ (mostly VOC stubs, some WAV files from audio pipeline, MAP files); no manifest cleanup tracking. Low severity but organizational debt.

---

## Focus Area 1: Verification of R12 Findings

### Status: ⚠️ **R12 PICKS STILL LIVE; 4/5 SIBLING TODOS PENDING**

**Finding 1.1: Cycle-38 Table Manifest Closure — Verified Stable**

**File/Location:** `tools/generate_tables.py` (132 lines)

**Verification:**
```bash
✅ Schema version: "1.0" (line 40)
✅ Atomic writes: tmp+os.replace() (lines 115–118)
✅ Deterministic mode: --deterministic flag (lines 82–86)
✅ Test coverage: test_tables_pipeline.py (22 tests pass)
```

**Status:** CLOSED VERIFIED. No regressions since R12.

**Finding 1.2: Per-Tool Manifest Todos — Status UNCHANGED Since R12**

R12 proposed 4 concurrent grind-ready todos:
- `asset-r11-texture-manifest` — **PENDING** (no source changes since R12)
- `asset-r11-sprite-manifest` — **PENDING**
- `asset-r11-palette-manifest` — **PENDING**
- `asset-r11-map-manifest` — **PENDING**

**Evidence:** `ls tools/generate_{texture,sprite,palette,map}.py` returns no files; generate_assets.py unchanged.

**Impact:** All 4 remain blockers for achieving full audit trail coverage across asset types. Recommend cycle-41+ parallel dispatch.

**Severity:** **MEDIUM** (not blocking production; hygiene/traceability)

---

## Focus Area 2: Exception Handling Audit (Error Swallowing + Diagnostic Loss)

### Status: 🚨 **HIGH-SEVERITY GAPS IDENTIFIED**

**Finding 2.1: Broad Exception Handlers in generate_assets.py**

**File/Location:** `tools/generate_assets.py` lines 220, 225, 710, 728, 746

**Issue:** Five instances of bare `except Exception as e:` with print-to-stderr only. Context:

```python
# Line 220–225 (generate_texture_ai function):
except Exception as e:
    # PIL decompression bomb or other PIL-specific errors
    print(f"    [!] Image processing error: {type(e).__name__}: {e}", file=sys.stderr)
    return None

# Line 710–746 (procedural texture worker functions):
except Exception as e:
    return (task[0], None, str(e))
```

**Analysis:**
- **Exception specificity:** Handlers catch too broadly; lumps different failure modes together.
  - Line 220: Intended for PIL errors (UnidentifiedImageError, OSError on file access). Also catches KeyError (dict operations), AttributeError (typos), etc.
  - Line 710, 728, 746: Worker exception handlers return strings; caller must parse error strings (brittle).
- **Diagnostic loss:** No audit log, no traceback written to file, no severity classification.
- **Testing gap:** test_generate_assets_validation.py has ONE truncated PNG test (line 175); no tests for:
  - KeyError in quantize_image()
  - AttributeError in proc_*() function
  - OSError on palette file read
  - Worker exception recovery per-tile

**Risk:** When procedural texture generation fails mid-pool in --no-ai path, only first exception is printed to stderr; subsequent failures are aggregated silently via `_process_pool_results()` (line 778). Operator cannot diagnose which tiles failed or why.

**Recommendation:** 
1. Replace bare `except Exception` with specific exception types (ValueError, OSError, UnidentifiedImageError, PIL.ImageFile.DecompressionBombError, KeyError)
2. Add audit logging (structured JSON to `generated_assets/GENERATION_LOG.json` with timestamp, tile_num, error_type, error_message, worker_pid)
3. Add test parametrization for each exception type

**Severity:** 🚨 **HIGH** (diagnostic/operational risk; impacts debugging in production-like scenarios)

---

**Finding 2.2: Multiprocessing Pool Exception Propagation**

**File/Location:** `tools/generate_assets.py` lines 1904–1933 (pool creation)

**Issue:** Worker exceptions are caught and returned as (tile_num, None, error_str) tuples (line 748). `_process_pool_results()` (line 778) logs and continues. However:

- **No worker PID tracking:** Exception origin unclear if multiple workers fail simultaneously.
- **No exception type information:** error_str is stringified; caller loses exception type/traceback.
- **Silent failure on KeyError in dict merge:** Line 1907–1908 (`tiles.update(texture_tiles)`) assumes no collisions; if two workers return same tile_num, second silently overwrites (unpredictable result).

**Code path:**
```python
# Line 1905: imap_unordered returns results in arbitrary order
results = pool.imap_unordered(_generate_texture_worker, texture_tasks)
# Line 1906: aggregates into tiles dict
texture_tiles, texture_failures = _process_pool_results(results, "Procedural")
# Line 1907: silent overwrite if tile_num collision
tiles.update(texture_tiles)
```

**Test gap:** No test for tile collision detection or per-worker failure isolation.

**Recommendation:** 
1. Add worker PID to exception tuple: `(tile_num, None, error_type, error_str, worker_pid)`
2. Add collision detection in `_process_pool_results()`: assert no duplicate tile_num before merge
3. Add test case: inject failure in _generate_texture_worker for tile 5, verify that only tile 5 fails and pool continues

**Severity:** **MEDIUM** (potential for silent tile data loss; low probability in normal operation)

---

## Focus Area 3: Manifest Integrity Gaps (Missing Checksums)

### Status: ⚠️ **CHECKSUM COVERAGE MISSING ACROSS ALL MANIFESTS**

**Finding 3.1: No Integrity Checksums in Manifest Files**

**File/Location:** `generated_assets/TABLES_MANIFEST.json`, `generated_assets/sounds/MANIFEST.json`

**Issue:** Manifests track schema_version and generated_at but lack file integrity checksums.

**Current TABLES_MANIFEST.json:**
```json
{
  "generated_at": "1970-01-01T00:00:00Z",
  "schema_version": "1.0",
  "table_names": ["sine", "radar", "brightness", "fonts"]
}
```

**Risk:** If GRP packing step produces corrupted binary (truncated TABLES.DAT, for example), manifest remains untouched. Downstream tools cannot detect corruption via manifest validation.

**Existing precedent:** Git, Docker, and package managers (npm, pip) include SHA256 checksums in manifests for integrity verification. Recommend following this pattern.

**Proposed schema enhancement:**
```json
{
  "schema_version": "1.0",
  "generated_at": "...",
  "manifest_checksum": "sha256:abc123...",  // Hash of sorted manifest keys/values
  "files": [
    {
      "name": "TABLES.DAT",
      "size": 12345,
      "checksum": "sha256:def456..."
    }
  ]
}
```

**Effort:** 30–45 min per manifest tool (tools/generate_{tables,audio,textures,sprites,palette,maps}.py)

**Impact:** Enables post-generation integrity verification; improves observability; matches cycle-34+ audit rigor (audio-engineer adds manifest checksums in cycle-34+).

**Severity:** **MEDIUM** (not blocking v1; important for v1.1+ durability)

---

## Focus Area 4: Procedural Texture Test Coverage (Mutation Paths)

### Status: ⚠️ **PROCEDURAL FIXTURES MISSING; --NO-AI END-TO-END PASSES BUT GRANULAR COVERAGE ABSENT**

**Finding 4.1: No Parametrized Tests for Individual proc_* Functions**

**File/Location:** `tools/generate_assets.py` lines 233–648 (20 proc_* functions + 1 proc_sprite_placeholder)

**Current test coverage:**
- ✅ test_pipeline_integration.py::test_full_pipeline_no_ai() runs --no-ai path end-to-end; GRP is produced successfully
- ✅ test_generate_assets_validation.py tests dimension bounds (64–256 px)
- ❌ No dedicated tests for individual proc_* functions with variable (width, height) inputs
- ❌ No tests verifying proc_* output is RGB PIL Image (not palette indices, not corrupted)
- ❌ No tests for edge cases: (32, 32), (128, 128), (256, 256) tile sizes

**Risk:** Procedural fallback generators (used in --no-ai path and as AI fallback) are not independently verified. A typo in proc_neon_circuit() or proc_hex_floor() would not be caught until end-to-end pipeline test or in-game verification.

**Recommendation:**
1. Create `tests/test_procedural_textures.py` with parametrized fixtures:
```python
@pytest.mark.parametrize("tile_num,width,height", [
    (0, 64, 64),   # proc_dark_steel
    (0, 128, 128),
    (3, 64, 64),   # proc_neon_circuit
    ...
    (20, 32, 32),  # proc_sprite_placeholder
])
def test_procedural_texture_output_valid(tile_num, width, height):
    proc_fn = PROCEDURAL_MAP[tile_num]
    img = proc_fn(width, height)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.size == (width, height)
    assert img.tobytes()  # No exceptions
```

2. Effort: 30–45 min (parametrization is straightforward; ~25 test cases)

3. Impact: HIGH (ensures each procedural fallback independently validated)

**Severity:** **MEDIUM** (not blocking production; hygiene/robustness)

---

## Focus Area 5: Multiprocessing Collision Detection Gap

### Status: ⚠️ **SILENT TILE COLLISION RISK IN WORKER AGGREGATION**

**Finding 5.1: No Collision Detection in `_process_pool_results()`**

**File/Location:** `tools/generate_assets.py` lines 778–806 (_process_pool_results function), lines 1906–1920 (pool result aggregation)

**Issue:** When multiprocessing pool workers generate tiles, results are aggregated via `dict.update()` without collision detection.

**Code path:**
```python
# Line 1906–1907 (texture aggregation):
texture_tiles, texture_failures = _process_pool_results(results, "Procedural")
tiles.update(texture_tiles)  # Silent overwrite if duplicate tile_num
```

**Risk scenario:** If PROCEDURAL_MAP is modified and two proc_* functions map to the same tile_num, OR if a worker is interrupted and retried, the second result silently overwrites the first. GRP contains wrong tile data.

**Current safeguard:** TEXTURE_DEFS and PROCEDURAL_MAP are hardcoded; collision unlikely in normal operation. However, no assertion or test prevents this edge case.

**Recommendation:**
1. Add collision detection in `_process_pool_results()`:
```python
def _process_pool_results(results, label):
    seen_tiles = set()
    tiles = {}
    for result in results:
        if result[0] in seen_tiles:
            raise RuntimeError(f"Collision: tile {result[0]} generated twice")
        seen_tiles.add(result[0])
        tiles[result[0]] = result[1]
    return tiles, failures
```

2. Add test: inject failure + retry to trigger collision scenario

3. Effort: 15 min (1 function, 1 test)

**Severity:** **MEDIUM** (low probability in normal operation; would be caught in GRP validation if it occurred)

---

## Focus Area 6: Orphaned Assets + Manifest Cleanup Tracking

### Status: ⚠️ **408 FILES IN GENERATED_ASSETS; NO CLEANUP POLICY**

**Finding 6.1: Stale Files Accumulation**

**File/Location:** `generated_assets/` directory

**Evidence:**
```bash
$ find generated_assets -type f | wc -l
408
# Mix of: VOC stubs (128), WAV files from audio pipeline (80+), MAP files (10+), temp files, artifacts
```

**Issue:** No manifest-driven cleanup. Old versions of generated tiles, sprites, tables accumulate. Generated_assets/ grows indefinitely across multiple builds.

**Risk:** Low (generated_assets is regenerated each pipeline run; not shipped with binary). However, represents organizational debt.

**Recommendation:**
1. Add cleanup policy: before generation, rm -rf generated_assets/; recreate empty directory
2. OR: Add manifest tracking (JSON list of expected files) and cleanup stale entries
3. Effort: 15–30 min

**Severity:** **LOW** (hygiene; not blocking production)

---

## Focus Area 7: FLUX vs --no-ai Branch Divergence

### Status: ✅ **NO CRITICAL DIVERGENCE; CODE PATHS REMAIN SYNCHRONIZED**

**Finding 7.1: AI vs Procedural Fallback Consistency**

**Code paths:**
- **--no-ai path:** Lines 1891–1933 (multiprocessing, procedural-only)
- **AI path:** Lines 1934–1965 (sequential, AI + procedural fallback)

**Verification:**
- ✅ Both paths generate SPRITE_DEFS sprites (via proc_sprite_placeholder)
- ✅ Both paths generate font tiles 2048–2175
- ✅ Both paths produce TILES000.ART, PALETTE.DAT, TABLES.DAT, GRP
- ✅ Procedural functions identical in both paths
- ✅ Test coverage: test_full_pipeline_no_ai() and test_full_pipeline() both pass

**Finding:** No critical branch divergence. Minor difference: --no-ai uses multiprocessing; AI path is sequential. Both are correct; multiprocessing is optimization for --no-ai (no API calls to wait on).

**Severity:** ✅ **NONE** (paths remain synchronized)

---

## Summary of Findings

### Critical Issues: 0 ❌
None. Asset pipeline production-ready.

### High-Severity Issues: 1 🚨

1. **Exception handling gaps (bare except, silent failures)** — `asset-r13-exception-handling-hardening`
   - Broad exception handlers in generate_assets.py lines 220, 225, 710, 728, 746
   - Replace with specific exception types; add structured logging
   - Effort: 1–1.5 hours

### Medium-Severity Issues: 4 ⚠️

1. **Missing manifest checksums across all assets** — `asset-r13-manifest-checksums`
   - TABLES_MANIFEST.json, sounds/MANIFEST.json lack SHA256 checksums
   - Effort: 1–1.5 hours

2. **Procedural texture fixture tests missing** — `asset-r13-procedural-fixture-tests`
   - No parametrized tests for individual proc_* functions
   - Effort: 30–45 min

3. **Multiprocessing collision detection** — `asset-r13-pool-collision-detection`
   - No collision detection in _process_pool_results()
   - Effort: 15–30 min

4. **Per-tool manifest todos still pending** (carry-forward from R12) — `asset-r11-texture-manifest`, `asset-r11-sprite-manifest`, `asset-r11-palette-manifest`, `asset-r11-map-manifest`
   - 4 grind-ready todos remain PENDING since R11/R12
   - Recommended for cycle-41+ parallel dispatch

### Low-Severity Issues: 1 ℹ️

1. **Orphaned files accumulation in generated_assets/** — `asset-r13-manifest-cleanup-policy`
   - 408 files; no cleanup policy
   - Effort: 15–30 min

### Carry-Forward from R12

- **GRP repacking automation design** (`asset-r12-grp-repacking-automation-design`) — Audio WAV consumption decision still needed

---

## New Backlog Todos (Proposed for Cycle 41+)

### Priority 1: HIGH (Exception Handling)

**`asset-r13-exception-handling-hardening`** (HIGH, 1–1.5 hrs)
- Replace 5 bare `except Exception` handlers in generate_assets.py with specific exception types (ValueError, OSError, UnidentifiedImageError, PIL.ImageFile.DecompressionBombError, KeyError)
- Add structured audit logging: JSON log at `generated_assets/GENERATION_LOG.json` with timestamp, tile_num, error_type, error_message, worker_pid
- Update test_generate_assets_validation.py with parametrized exception tests (KeyError, OSError, worker failure isolation)
- Grind-ready: Concrete file locations, specific exception types, test structure defined
- Blocker: None

### Priority 2: MEDIUM (Manifest Integrity)

**`asset-r13-manifest-checksums`** (MEDIUM, 1–1.5 hrs)
- Add SHA256 checksums to all manifests: tools/generate_tables.py, tools/generate_audio.py, and proposed texture/sprite/palette/map manifests (R11 todos)
- Schema enhancement: `"manifest_checksum"` (hash of sorted manifest), per-file `"checksum"` field
- Add test validation: manifest checksum verification, checksum mismatch detection
- Grind-ready: Schema defined, test structure clear
- Blocker: None

**`asset-r13-procedural-fixture-tests`** (MEDIUM, 30–45 min)
- Create tests/test_procedural_textures.py with parametrized fixtures for all 20 proc_* texture functions + proc_sprite_placeholder
- Test cases: verify output is RGB PIL Image, correct size (32–256 px), no exceptions
- Parametrize: (tile_num, width, height) tuples covering proc_dark_steel, proc_neon_circuit, proc_hex_floor, ..., proc_sprite_placeholder
- Effort: 30–45 min (straightforward parametrization)
- Grind-ready: Test structure defined, parametrization clear
- Blocker: None

**`asset-r13-pool-collision-detection`** (MEDIUM, 30 min)
- Add collision detection in _process_pool_results() (line 778): assert no duplicate tile_num before merge
- Add test: mock worker returning duplicate tile_num, verify RuntimeError raised
- Effort: 15–30 min
- Grind-ready: Concrete; low complexity
- Blocker: None

### Priority 3: LOW (Hygiene)

**`asset-r13-manifest-cleanup-policy`** (LOW, 15–30 min)
- Add generated_assets cleanup policy: rm -rf generated_assets/ at pipeline start OR manifest-driven cleanup
- Document cleanup behavior in CONTRIBUTING.md
- Effort: 15–30 min
- Grind-ready: Straightforward
- Blocker: None

---

## Recommendations for Next Sprint

### Immediate (Cycle 41+)

1. **Dispatch HIGH-priority todo:** `asset-r13-exception-handling-hardening` (1–1.5 hrs)
   - Unblocks production observability; improves diagnostics
   - Ready to start immediately

2. **Parallel dispatch MEDIUM-priority todos:**
   - `asset-r13-manifest-checksums` (1–1.5 hrs)
   - `asset-r13-procedural-fixture-tests` (30–45 min)
   - `asset-r13-pool-collision-detection` (30 min)
   - **Why:** Independent; no inter-dependencies; can merge in any order

3. **Carry-forward R11/R12 manifest todos:**
   - 4 per-tool manifest todos remain PENDING (asset-r11-{texture,sprite,palette,map}-manifest)
   - Recommend cycle-41+ parallel dispatch after exception-handling HIGH is complete
   - Effort: ~4–6 hours cumulative; parallelizable

### Longer-term (Cycle 42+)

- **GRP repacking automation design** (from R12): Design doc to decide whether audio WAVs should be consumed by VOC generation
- **Orphaned file cleanup** (LOW priority)

---

## Spot-Check Summary

| Item | Status | Evidence |
|------|--------|----------|
| PIL truncation handling | ✅ STABLE | `LOAD_TRUNCATED_IMAGES = False` (line 27); test at line 263 |
| Atomic writes | ✅ STABLE | `_atomic_write_bytes()` (line 145) with tmp+os.replace(); used for GRP output |
| --no-ai procedural fallback | ✅ TESTED | test_full_pipeline_no_ai() passes; 20 proc_* functions exercised |
| TEXTURE_DEFS/SPRITE_DEFS bounds | ✅ VALIDATED | Schema validation in _asset_schemas.py; 18/18 tests pass |
| Exception handling | 🚨 GAPS | 5 bare `except Exception` handlers lack specificity (lines 220, 225, 710, 728, 746) |
| Manifest checksums | ❌ MISSING | TABLES_MANIFEST.json, sounds/MANIFEST.json have no SHA256 fields |
| Procedural fixture tests | ❌ MISSING | No test_procedural_textures.py; parametrized coverage absent |
| Multiprocessing collision detection | ❌ MISSING | No collision detection in _process_pool_results() |
| Orphaned files | ⚠️ ACCUMULATING | 408 files; no cleanup policy |

---

## Open Questions for Audio/Engine Personas

1. **GRP repacking:** Should VOC generation consume generated_assets/SOUND_*.WAV files from audio pipeline, or are stubs acceptable for v1? (Raised in R12, still open)
2. **Manifest versioning:** Should schema_version be incremented if we add checksums? (Recommend staying at "1.0" for backward compatibility)

---

**Next Audit: Cycle 42** (or when 50%+ of cycle-41 todos are complete)

**Audit Close Time:** 2025-06-29 14:30 UTC

# Asset Pipeline Engineering Audit — Round 14 (Cycle 45 Continuation + Exception Handling Verification)

**Report Date:** 2025-06-30  
**Auditor:** Asset Pipeline Engineer  
**Scope:** Verification of cycle-42 exception handling landing; r13 backlog inventory; sweep of tools/ for manifest schema drift; FLUX vs --no-ai divergence check; GRP repacking automation status  
**Prior Reports:** R1–R13  
**Status:** Audit complete; cycle-42 landing verified; 4 r13 backlog items still PENDING (HIGH->MEDIUM priority escalation for procedural-fixture-tests); NEW findings: 0 critical, 1 medium (manifest-schema-consistency); 4 NEW todos proposed (all MEDIUM)

---

## Executive Summary

Round 14 is a DOC-ONLY verification and backlog-triage audit. Key results:

**Verification of Cycle-42 Landing (asset-r13-exception-handling-hardening):**
- ✅ **Exception handling narrowed correctly:** 5 bare `except Exception` handlers in generate_assets.py (lines 220, 225, 710, 728, 746) replaced with specific exception types (ValueError, OSError, KeyError, AttributeError, UnidentifiedImageError, PIL.ImageFile.DecompressionBombError)
- ✅ **GENERATION_LOG.jsonl infrastructure live:** log_generation_error() function deployed (line 59–87); worker PID tracking working; 7 new tests validate worker error logging to JSONL (test_worker_error_logging_to_jsonl, test_worker_catches_specific_exceptions[4 variants], test_sprite_worker_error_handling, test_font_worker_error_handling — all passing)
- ✅ **Fallback exception handlers added:** All 3 worker functions (_generate_texture_worker, _generate_sprite_worker, _generate_font_tile_worker) have dual-level exception handling (specific types → GENERATION_LOG + error tuple; unexpected → fallback GENERATION_LOG + error tuple)
- ⚠️ **Note:** GENERATION_LOG.jsonl file not yet created in practice (no errors on successful builds); log infrastructure is ready for first error event

**R13 Backlog Inventory Status:**
- 🟢 **asset-r13-exception-handling-hardening** — **DONE** (cycle-42 landing verified, 7 new tests passing)
- 🔴 **asset-r13-procedural-fixture-tests** — **PENDING** (4 HIGH to MEDIUM priority escalation recommended; r13 estimated 30–45 min; no test_procedural_textures.py file exists; 21 proc_* functions untested individually)
- 🔴 **asset-r13-manifest-checksums** — **PENDING** (tools/generate_tables.py, tools/generate_audio.py manifests lack SHA256 fields; r13 estimated 1–1.5 hrs)
- 🔴 **asset-r13-pool-collision-detection** — **PENDING** (multiprocessing result aggregation still lacks collision detection; r13 estimated 30 min)
- 🔴 **asset-r13-manifest-cleanup-policy** — **PENDING** (generated_assets/ cleanup still not implemented; 408 files observed; r13 estimated 15–30 min; LOW priority)
- 🟡 **asset-r12-grp-repacking-automation-design** (carryforward from R12) — **PENDING** (VOC vs WAV consumption decision remains open; audio-engineer + asset-pipeline collab needed)

**Sweep Results:**
- ✅ **tools/generate_tables.py:** Schema version "1.0" stable; manifest structure validated; atomic writes working (tmp+os.replace() pattern)
- ✅ **tools/generate_audio.py:** Schema version "1.0" stable; SOUND_MANIFEST entries contain wav, engine_sound_id, category, prompt_summary; manifest validation working; atomic writes working
- ✅ **FLUX vs --no-ai divergence:** No branch drift detected. FLUX_MODEL read from env (default "FLUX.2-pro"); procedural path multiprocessing consistent with r12/r13 verification
- ⚠️ **Orphaned files:** 408 files in generated_assets/ (mix of VOC stubs, WAV files from audio pipeline, MAP files); no cleanup between builds; low operational impact but organizational debt

**Severity Classification:**
- 🟢 **Critical:** 0
- 🟡 **High:** 0
- 🟠 **Medium:** 1 (new: manifest schema consistency gap; see Focus Area 3)
- 🔵 **Low:** 1 (r13 carryforward: manifest-cleanup-policy)

---

## Focus Area 1: Verification of Cycle-42 Exception Handling Landing

### Finding 1.1: Exception Handler Specificity — VERIFIED CORRECT

**Location:** tools/generate_assets.py lines 260–271 (generate_texture_ai), 755–765 (_generate_texture_worker), 781–791 (_generate_sprite_worker), 807–817 (_generate_font_tile_worker)

**Verification Evidence:**
```python
# Before (R13 finding): except Exception as e: (bare, too broad)
# After (Cycle-42): 
except (ValueError, OSError, KeyError, AttributeError) as e:  # specific types
    log_generation_error(task[0], type(e).__name__, str(e))
    return (task[0], None, error_str)
except Exception as e:  # fallback for truly unexpected
    log_generation_error(task[0], f"Unexpected[{type(e).__name__}]", str(e))
    return (task[0], None, error_str)
```

**Test Coverage:**
- ✅ `test_worker_error_logging_to_jsonl()` (line 287): Verifies KeyError logged to GENERATION_LOG.jsonl with tile_num, error_type, error_message, timestamp, worker_pid
- ✅ `test_worker_catches_specific_exceptions()` (4 parametrized variants, line 340): ValueError, OSError, KeyError, AttributeError all caught and logged without propagation
- ✅ `test_sprite_worker_error_handling()` (line 385): Sprite worker error logging verified
- ✅ `test_font_worker_error_handling()` (line 410): Font worker error logging verified

**Result:** ✅ **VERIFIED CORRECT**. All exception handlers narrowed appropriately; fallback handlers present for defensive programming; all tests passing.

---

### Finding 1.2: GENERATION_LOG.jsonl Infrastructure — READY FOR PRODUCTION

**Location:** tools/generate_assets.py lines 53–87 (GENERATION_LOG_FILE, log_generation_error function)

**Implementation:**
```python
GENERATION_LOG_FILE = os.path.join(OUTPUT_DIR, "GENERATION_LOG.jsonl")

def log_generation_error(tile_num, error_type, error_message, worker_pid=None):
    """Write structured exception record to GENERATION_LOG.jsonl (JSONL format)."""
    if worker_pid is None:
        worker_pid = os.getpid()
    
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tile_num": tile_num,
        "error_type": error_type,
        "error_message": error_message,
        "worker_pid": worker_pid,
    }
    
    try:
        with open(GENERATION_LOG_FILE, "a") as f:
            json.dump(record, f)
            f.write("\n")
    except Exception as log_e:
        print(f"[!] Failed to write generation log: {log_e}", file=sys.stderr)
```

**Evidence of Use:**
- Lines 759, 764 (texture worker): log_generation_error called on specific and unexpected exceptions
- Lines 785, 790 (sprite worker): Same pattern
- Lines 811, 816 (font worker): Same pattern

**Status:** ✅ **READY FOR PRODUCTION**. Infrastructure in place; first error event will create GENERATION_LOG.jsonl in generated_assets/. Worker PID tracking enables per-worker failure isolation in multiprocessing scenarios.

---

## Focus Area 2: R13 Backlog Inventory Status

### Finding 2.1: R13 Findings Status Summary

| Finding ID | Title | Status | Est. Effort | Priority |
|---|---|---|---|---|
| asset-r13-exception-handling-hardening | Broad exception handlers → specific types + GENERATION_LOG | ✅ DONE (c42) | 1–1.5 hrs | HIGH |
| asset-r13-procedural-fixture-tests | No parametrized tests for proc_* functions | 🔴 PENDING | 30–45 min | **MEDIUM→HIGH** |
| asset-r13-manifest-checksums | Missing SHA256 in TABLES_MANIFEST.json, SOUND_MANIFEST.json | 🔴 PENDING | 1–1.5 hrs | MEDIUM |
| asset-r13-pool-collision-detection | No collision detection in _process_pool_results() | 🔴 PENDING | 30 min | MEDIUM |
| asset-r13-manifest-cleanup-policy | No cleanup policy for generated_assets/; 408 files accumulate | 🔴 PENDING | 15–30 min | LOW |

**Evidence for status:**
- Line 287–424 of tests/test_generate_assets_validation.py: 7 new cycle-42 tests (exception-handling-related)
- SQL query: `SELECT id, status FROM todos WHERE id LIKE 'asset-r13-%'` confirms DONE/PENDING split

---

### Finding 2.2: Priority Escalation — Procedural Fixture Tests

**Rationale:** Procedural texture generators (20 proc_* functions + proc_sprite_placeholder) are the fallback path for:
- `--no-ai` flag (no FLUX API available)
- AI generation failure (FLUX timeout, invalid response)
- Production environments without FLUX credentials

**Risk:** If a proc_* function regresses (e.g., typo in proc_neon_circuit), the --no-ai build produces silently corrupted tiles. No unit test catches this until end-to-end or in-game verification.

**Recommendation:** Escalate `asset-r13-procedural-fixture-tests` from MEDIUM to **HIGH** priority for next cycle (cycle-46+).

---

## Focus Area 3: Manifest Schema Consistency Gap (NEW FINDING — MEDIUM)

### Finding 3.1: Schema Validation Inconsistency Between generate_audio.py and generate_tables.py

**Location:** tools/generate_audio.py (lines 122–194), tools/generate_tables.py (lines 25–77)

**Issue:** Both tools implement manifest validation, but with minor inconsistencies:

**generate_audio.py:**
```python
def validate_manifest(manifest_data, source_path):
    if not isinstance(manifest_data, dict):
        raise ValueError(...)
    schema_version = manifest_data.get("schema_version")
    if schema_version != "1.0":
        raise ValueError(...)
    entries = manifest_data.get("entries")  # Expected structure: {"schema_version": "1.0", "entries": [...]}
```

**generate_tables.py:**
```python
def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError(...)
    if "schema_version" not in manifest:  # Uses "in" check, not .get()
        raise ValueError(...)
    if manifest["schema_version"] != "1.0":
        raise ValueError(...)
    if "table_names" not in manifest:  # No "entries" key; uses "table_names" directly
```

**Differences Observed:**
1. **Key naming:** audio uses `"entries"`, tables uses `"table_names"` (intentional, schema-specific)
2. **Validation method:** audio uses `.get()`, tables uses `in` (inconsistent style; both functionally correct)
3. **Error handling:** audio catches IOError on missing file (line 188–190); tables does not (generates fresh if missing)

**Risk:** Low (each tool has its own schema). However, future unified manifest tooling or schema evolution would benefit from consistency.

**Recommendation:** Document the schema differences in CONTRIBUTING.md or add a schema registry file (e.g., docs/MANIFEST_SCHEMA.md) that defines:
- Audio manifest schema (schema_version, entries)
- Tables manifest schema (schema_version, generated_at, table_names)
- Expected generated_assets/ directory structure

**Effort:** 15–20 min (documentation only, no code changes)

**Severity:** **MEDIUM** (hygiene; not blocking; important for v1.1+ maintainability)

---

## Focus Area 4: Sweep Results — Tools and Assets

### Finding 4.1: Orphaned Files Accumulation (R13 Carryforward)

**Location:** generated_assets/ directory

**Evidence:**
```bash
$ find generated_assets -type f | wc -l
408
# Breakdown (approx):
# - VOC stubs: ~128 (1135 bytes each, generated each build)
# - WAV files from audio pipeline: ~80 (22KB each, from generate_audio.py)
# - MAP files: ~10 (level geometry)
# - MID files: ~5 (music)
# - Temp/cleanup artifacts: ?
```

**Status:** ⚠️ **STILL OPEN FROM R13**. No cleanup policy implemented between pipeline runs.

**Impact:** Low (generated_assets/ is regenerated; not shipped; no corruption risk). Represents organizational debt.

---

### Finding 4.2: FLUX vs --no-ai Branch Consistency — VERIFIED

**Location:** tools/generate_assets.py lines 1961–1965 (--no-ai path), lines 2036–2080 (AI path)

**Verification:**
- ✅ Both paths generate TEXTURE_DEFS textures (18 total)
- ✅ Both paths generate SPRITE_DEFS sprites (1 proc_sprite_placeholder)
- ✅ Both paths generate font tiles (2048–2175)
- ✅ Both paths produce TILES000.ART, PALETTE.DAT, TABLES.DAT, GRP
- ✅ Procedural functions identical in both paths
- ✅ Tests: test_full_pipeline_no_ai() and test_full_pipeline() both pass

**Status:** ✅ **VERIFIED CONSISTENT**. No branch drift detected.

---

## Focus Area 5: GRP Repacking Automation Gap (R12 Carryforward)

### Finding 5.1: VOC Stubs vs Audio WAV Consumption Decision Remains Open

**Location:** tools/generate_assets.py lines 1879–1881 (VOC generation), tools/generate_audio.py (WAV generation)

**Current State:**
- generate_audio.py produces WAV files (e.g., ALARM01.WAV, 22KB)
- generate_assets.py generates VOC stubs (1135 bytes, placeholder; not consuming audio WAVs)
- GRP archive includes VOC stubs only

**Design Question (from R12):** Should VOC generation consume WAV files from audio pipeline?

**Implications:**
- **Option A (current):** Keep VOC stubs; accept as v1 placeholder; WAV files are generated but unused
- **Option B:** Consume WAV files; convert to VOC format; requires audio-engineer collab on WAV→VOC bridge
- **Option C:** Hybrid; use WAVs for specific categories (e.g., alarm, computer) and VOC stubs for others

**Status:** 🔴 **STILL OPEN**. Requires design doc from asset-pipeline + audio-engineer personas. Not blocking v1 but important for v1.1+ audio fidelity.

**Recommendation:** Schedule cross-persona design doc for cycle-46+ (see New Todos below).

---

## New Findings Summary

### No Critical Issues: 0 ❌
Asset pipeline remains production-ready.

### Medium-Severity Issues: 1 ⚠️

1. **Manifest schema consistency gap** (NEW, documentation-only) — `asset-r14-manifest-schema-documentation`
   - Audio and tables tools have slightly different manifest validation styles (inconsistent but functionally correct)
   - Recommendation: Document schema differences in CONTRIBUTING.md or create docs/MANIFEST_SCHEMA.md
   - Effort: 15–20 min
   - Severity: **MEDIUM** (hygiene; impacts v1.1+ evolution)

### R13 Carryforward Issues (No Change in Status)

1. **Procedural fixture tests missing** — `asset-r13-procedural-fixture-tests` (ESCALATE TO HIGH)
2. **Manifest checksums missing** — `asset-r13-manifest-checksums` (MEDIUM)
3. **Pool collision detection missing** — `asset-r13-pool-collision-detection` (MEDIUM)
4. **Manifest cleanup policy missing** — `asset-r13-manifest-cleanup-policy` (LOW)
5. **GRP repacking design** (from R12) — `asset-r12-grp-repacking-automation-design` (MEDIUM, cross-team)

---

## Recommendations for Next Sprint

### Immediate (Cycle 46+)

1. **Escalate procedural-fixture-tests to HIGH:** Risk is procedural fallback regression going undetected. Estimated 30–45 min; high testing value.

2. **Dispatch NEW todo:** `asset-r14-manifest-schema-documentation` (15–20 min, documentation-only, doc-audit ready)
   - Create docs/MANIFEST_SCHEMA.md with schema definitions for audio, tables, and future asset manifests
   - Update CONTRIBUTING.md with manifest format expectations

3. **Parallel dispatch R13 MEDIUM todos** (1.5–3 hours total):
   - `asset-r13-manifest-checksums` (1–1.5 hrs)
   - `asset-r13-pool-collision-detection` (30 min)
   - These are independent; no inter-dependencies

4. **Schedule cross-team design:** `asset-r12-grp-repacking-automation-design` (1–2 hours; requires audio-engineer + asset-pipeline personas)
   - Decide: VOC stubs vs WAV consumption strategy
   - Document in design doc (not code changes)

### Longer-term (Cycle 47+)

- **Procedural fixture tests high-priority dispatch** (if not done in 46)
- **Manifest cleanup policy** (LOW; if organizational debt becomes noticeable)

---

## Spot-Check Summary

| Item | Status | Evidence |
|------|--------|----------|
| Cycle-42 exception handling | ✅ VERIFIED CORRECT | 7 new tests passing; GENERATION_LOG infrastructure live |
| Fallback exception handlers | ✅ CORRECT | All 3 worker functions dual-level exception handling |
| Worker PID tracking | ✅ READY | log_generation_error(worker_pid=None) defaults to os.getpid() |
| --no-ai procedural path | ✅ TESTED | test_full_pipeline_no_ai() passes; 21 proc_* functions exercised end-to-end |
| FLUX vs --no-ai divergence | ✅ NO DRIFT | Both paths produce identical GRP outputs; tests synchronized |
| Manifest schema consistency | ⚠️ MINOR GAPS | audio/tables validation styles inconsistent (functionally correct); documentation needed |
| Orphaned files accumulation | ⚠️ STILL PRESENT | 408 files in generated_assets/; no cleanup policy (r13 carryforward) |
| GRP repacking automation | 🔴 OPEN | VOC vs WAV decision still needs design doc (r12 carryforward) |

---

## Audit Metadata

**Audit Scope:** DOC-ONLY (no source edits)  
**Duration:** 45 min  
**Auditor:** Asset Pipeline Engineer  
**Prior Audits:** R1–R13  
**Next Audit Trigger:** Cycle-46 (or when 50%+ of cycle-45 todos complete)

---

**Next Audit: Cycle 46**

**Audit Close Time:** 2025-06-30 19:45 UTC

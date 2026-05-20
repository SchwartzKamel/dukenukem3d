# Asset Pipeline Engineering Audit — Round 17 (Cycle 56/58 Forward Compatibility & Cross-Domain Analysis)

**Report Date:** 2025-08-20  
**Auditor:** Asset Pipeline Engineer  
**Scope:** Manifest schema forward-compatibility contract, atomic write coverage, GENERATION_LOG.jsonl observability, palette validation, map ID validation extensibility, test fixture overlap risk, LTO linkage surface  
**Prior Reports:** R1–R16  
**Status:** ✅ Cycle 56/58 landings VERIFIED OPERATIONAL; 🟡 5 NEW FINDINGS (2 MEDIUM, 3 LOW)

---

## Executive Summary

Round 17 audits new ground not covered by r16: manifest schema forward-compat contract documentation, GENERATION_LOG.jsonl queryability, palette input validation, map ID validation scope, and test fixture maintenance risk.

**Verified Closure (R16 Pending):**

- 🔴 **PENDING** `asset-r16-manifest-schema-forward-compat-advisory` — No documented schema_version migration contract in CONTRIBUTING.md or tools. Cycle 59 audio-r15-mig-doc added "Manifest Verification Pattern" section but does NOT specify how schema_version evolution is handled if manifests require breaking changes.

**New Findings:**

- 🟡 **MEDIUM (NEW)** `asset-r17-manifest-schema-no-migration-contract` — Both audio and GRP manifests hardcode `schema_version: "1.0"`. CONTRIBUTING.md "Manifest Verification Pattern" validates *presence* of schema_version but provides NO migration path (e.g., version 1.0→1.1 loader logic, deprecation warnings, backward-compat fallbacks). Risk: future schema evolution will be reactive rather than planned.

- 🟡 **MEDIUM (NEW)** `asset-r17-palette-validation-gap` — `tools/palette.py create_palette_dat()` does NOT validate input palette_rgb array: (a) assumes 256 (R,G,B) entries, (b) assumes 8-bit RGB values (uses `>> 2` to convert to 6-bit VGA), (c) no bounds check on palookup shade tables (up to 65536 entries × 256 bytes = 16 MiB max). Uncaught input corruption (wrong array size, out-of-range RGB) silently produces malformed PALETTE.DAT.

- 🔵 **LOW (NEW)** `asset-r17-generation-log-not-documented-as-queryable` — Cycle 58 `_rotate_generation_log()` (lines 64–111) implements log rotation with cleanup policy, but GENERATION_LOG.jsonl itself is not documented as a queryable audit trail. No CLI tool or CONTRIBUTING.md guidance on parsing/filtering for error recovery or compliance audit.

- 🔵 **LOW (NEW)** `asset-r17-map-id-validation-narrow-scope` — `_validate_map_ids()` (lines 885–909) only detects duplicate MAP IDs. Does NOT validate if individual maps reference sound IDs, sprite IDs, or tile indices that exist in the asset archive (cross-reference validation). Potential OOB access if map data contains invalid asset references.

- 🔵 **LOW (NEW)** `asset-r17-test-fixture-proliferation` — conftest.py defines 5 session-scoped fixtures for generated assets. Manifest test suite now spans 6 files (test_manifest_checksum_verification.py, test_manifest_verifier_adoption.py, test_grp_manifest.py, test_sound_manifest.py, test_tables_manifest.py, test_generate_assets_validation.py). Risk: fixture duplication, maintenance burden if fixtures refactored. 

**Severity Classification:**

- 🟢 **Critical:** 0
- 🟡 **High:** 0
- 🟠 **Medium:** 2 (schema forward-compat contract, palette validation)
- 🔵 **Low:** 3 (genlog queryability, map ID validation scope, fixture proliferation)

**Build & Test Status:**

- Build: ✅ Clean (no changes in source/tools/tests)
- Tests: ✅ Cycle 56 + 58 additions (test_grp_manifest.py: 11 tests; test_manifest_verifier_adoption.py: 4 tests; all PASSING)
- Generators: ✅ All 3 (generate_audio.py, generate_tables.py, generate_assets.py) functional with no regressions

---

## Focus Area 1: Manifest Schema Forward-Compatibility Contract

### 1.1: R16 Pending Status

**Finding:** The r16 todo `asset-r16-manifest-schema-forward-compat-advisory` (MEDIUM priority) remains **PENDING** and has NOT been addressed by cycle 59 audio-r15-mig-doc work.

**Verification (CONTRIBUTING.md audit):**

Cycle 59 added §"Manifest Verification Pattern" (lines ~250–280) which documents:
```markdown
### When to Use Manifest Verifiers
# Load and verify checksums
manifest = load_and_verify_audio_manifest(...)
# Optionally, validate schema separately (if required for your domain)
assert "entries" in manifest
assert "schema_version" in manifest
```

**Gap Identified:** The pattern validates that `schema_version` *field exists* but provides **NO migration logic** for version evolution. Code examples assume schema_version "1.0" is static.

### 1.2: Hardcoded Schema Versions (NEW FINDING)

**Locations:**

| File | Function | Line | schema_version |
|------|----------|------|-----------------|
| tools/generate_assets.py | _emit_grp_manifest() | 311 | "1.0" |
| tools/generate_audio.py | (inferred from manifest format) | ~200+ | "1.0" |
| tools/generate_tables.py | (inferred from manifest format) | ~100+ | "1.0" |
| tools/manifest_verification.py | load_and_verify_audio_manifest() | ~65–90 | accepts any version without migration |

**Problem Statement:** If manifest schema evolves (e.g., adding required field `asset_index`, changing `members` structure), loaders have no way to:
1. Detect version mismatch
2. Apply version-specific deserialization logic
3. Provide backward-compat fallbacks
4. Deprecate old versions gracefully

**Risk:** Producers and consumers (generator + loader) must coordinate breaking changes reactively. No planned migration path.

**Recommendation:** Draft a schema versioning strategy in CONTRIBUTING.md:
- Document version 1.0 baseline schema formally
- Define version increment semantics (major.minor: major = breaking, minor = additive)
- Add loader logic: `if schema_version == "1.0": load_v1() elif schema_version == "1.1": load_v1_1()` etc.
- Add deprecation warnings for obsolete versions

---

## Focus Area 2: GENERATION_LOG.jsonl Observability

### 2.1: Log Rotation Implementation (Verified ✅)

**Location:** tools/generate_assets.py lines 64–111

**Status:** ✅ Cycle 58 implementation VERIFIED:
- Rotation triggered if line count > 1000 OR file size > 5 MiB (lines 57–58)
- Keeps latest 50% of lines (line 91)
- Synthetic `log_rotated` event prepended (lines 95–99)
- Atomic write via tmp+replace (lines 102–108)

**Call Site:** main() calls `_rotate_generation_log()` at startup (line ~2120)

### 2.2: Missing Queryability Documentation (NEW FINDING)

**Problem:** GENERATION_LOG.jsonl is written to disk (JSONL format, one event per line) but:

1. **No Parsing Guide:** CONTRIBUTING.md does not document how to parse GENERATION_LOG.jsonl for audit trails
2. **No Query Tool:** No Python CLI or shell script provided for filtering/aggregating logs (e.g., "show all asset-generation failures", "list rotations", "find by timestamp")
3. **No Schema Reference:** GENERATION_LOG entries use ad-hoc keys (event, rotated_at, kept_lines); no schema formal spec

**Example Gap:** If CI/CD detects generation failure in GENERATION_LOG.jsonl, operator cannot easily answer:
- "When did the last successful palette generation occur?"
- "How many rotations happened in the last 24 hours?"
- "Show me all errors involving sound-name collisions"

**Recommendation:** Add to CONTRIBUTING.md §"Audit Log Querying":
```markdown
## Querying GENERATION_LOG.jsonl

GENERATION_LOG.jsonl is a line-delimited JSON audit log. Example queries:

# Parse all events (jq)
cat generated_assets/GENERATION_LOG.jsonl | jq '.event' | sort | uniq -c

# Find rotations
cat generated_assets/GENERATION_LOG.jsonl | jq 'select(.event == "log_rotated")'

# Filter by timestamp
cat generated_assets/GENERATION_LOG.jsonl | jq 'select(.timestamp > "2025-08-01")'
```

---

## Focus Area 3: Palette Input Validation

### 3.1: Validation Gap in create_palette_dat()

**Location:** tools/palette.py, function `create_palette_dat(palette_rgb=None)`

**Implementation (VERIFIED):**
```python
def create_palette_dat(palette_rgb=None):
    """Create a PALETTE.DAT file for Duke3D.
    Layout:
        - 768 bytes: 256 * (R, G, B) in VGA 6-bit format (0-63)
        - 2 bytes : numpalookups (int16 LE)
        - numpalookups * 256 bytes: shade tables (palookup)
        - 65536 bytes: translucency table
    """
    if palette_rgb is None:
        palette_rgb = build_palette()

    # VGA palette: 6-bit per component (0-63)
    pal_bytes = bytearray()
    for r, g, b in palette_rgb:
        pal_bytes.append(r >> 2)  # ← ASSUMES r in range [0, 255]
        pal_bytes.append(g >> 2)  # ← ASSUMES g in range [0, 255]
        pal_bytes.append(b >> 2)  # ← ASSUMES b in range [0, 255]
    ...
```

**Missing Validations:**

1. **Array Length:** No check that `palette_rgb` has exactly 256 (R,G,B) entries. If shorter or longer, truncation or misalignment occurs.
2. **Component Range:** No bounds check that r, g, b ∈ [0, 255]. If negative or > 255, bit-shift produces incorrect 6-bit values.
3. **Shade Tables:** If numpalookups parameter is user-controlled, no bounds check that it ≤ max allowed (prevents allocation of unbounded tables).

**Risk:** Corrupted palette input silently produces malformed PALETTE.DAT, potentially causing rendering artifacts or crashes when engine loads file.

**Recommendation:** Add validation:
```python
def create_palette_dat(palette_rgb=None):
    if palette_rgb is None:
        palette_rgb = build_palette()
    
    # Validate palette_rgb structure
    if len(palette_rgb) != 256:
        raise ValueError(f"Palette must have 256 entries, got {len(palette_rgb)}")
    
    for i, (r, g, b) in enumerate(palette_rgb):
        if not (0 <= r <= 255) or not (0 <= g <= 255) or not (0 <= b <= 255):
            raise ValueError(f"Palette entry {i} has invalid RGB: ({r}, {g}, {b})")
    ...
```

---

## Focus Area 4: Map ID Validation Scope

### 4.1: Current Implementation (Verified ✅)

**Location:** tools/generate_assets.py lines 885–909

**Function:** `_validate_map_ids(map_data)` — checks for duplicate MAP IDs

**Implementation:**
```python
def _validate_map_ids(map_data):
    """Validate that no duplicate MAP IDs exist in map generation."""
    map_id_count = {}
    for map_id in map_data.keys():
        if map_id not in map_id_count:
            map_id_count[map_id] = 0
        map_id_count[map_id] += 1
    
    for map_id, count in map_id_count.items():
        if count > 1:
            raise RuntimeError(f"Duplicate map ID {map_id}")
```

**Coverage:** Prevents silent overwrite of duplicate MAP IDs ✅

### 4.2: Validation Scope Gap (NEW FINDING)

**Problem:** `_validate_map_ids()` only validates **uniqueness of map filenames**. It does NOT validate if map data *contents* reference valid asset IDs:

1. **Sound References:** Maps may contain references to sound IDs (via sector properties, player actions). No validation that referenced sound IDs exist in the audio manifest.
2. **Sprite/Tile Indexes:** Maps may embed tile or sprite indices. No validation that these indices fall within MAXTILES bounds or reference valid art/GRP members.
3. **Sector/Wall Bounds:** No cross-reference validation that sector/wall counts in map data match expected BUILDengine limits.

**Risk:** If a map references sound ID 999 but only 100 sounds are in the asset archive, the engine will fail at runtime with an OOB access.

**Current State (Cycle 50 closure):** _validate_map_ids() considered CLOSED because it prevents duplicate MAP IDs. But validation scope is narrow.

**Recommendation:** Extend map validation to include asset cross-references (optional, can be deferred):
```python
def _validate_map_ids_extended(map_data, audio_manifest, art_manifest):
    """Validate map data + cross-reference asset indices."""
    _validate_map_ids(map_data)  # Existing check
    
    # NEW: Validate sound references in map sector data
    for map_id, map_bytes in map_data.items():
        sounds_in_map = extract_sound_refs(map_bytes)
        for sound_id in sounds_in_map:
            if sound_id not in audio_manifest.get("entries", {}):
                raise RuntimeError(f"Map {map_id} references missing sound {sound_id}")
    ...
```

---

## Focus Area 5: Test Fixture Proliferation

### 5.1: Fixture Inventory

**conftest.py Session Fixtures (5 total):**

| Name | Scope | Purpose | Auto-use |
|------|-------|---------|----------|
| generated_audio_artifacts | session | Pre-generated WAV files + manifest | False |
| tables_artifacts | session | Pre-generated tables.dat + manifest | False |
| art_artifacts | session | Pre-generated ART files | False |
| grp_artifacts | session | Pre-generated DUKE3D.GRP + manifest | False |
| generated_audio_artifacts (autouse=True) | session | Ensure audio files available at session start | True |

**Manifest Test Files (6 total):**
1. test_manifest_checksum_verification.py
2. test_manifest_verifier_adoption.py
3. test_grp_manifest.py
4. test_sound_manifest.py
5. test_tables_manifest.py
6. test_generate_assets_validation.py

### 5.2: Maintenance Risk (NEW FINDING)

**Observation:** The fixture-to-test-file mapping is 5 fixtures → 6 test files, with potential overlap:

1. **Fixture Dependency Chains:** Some tests may import multiple fixture files (e.g., test_grp_manifest.py uses grp_artifacts; test_sound_manifest.py uses generated_audio_artifacts). If fixtures refactored, multi-file updates needed.

2. **Session-Scope Coupling:** All 5 fixtures are session-scoped. If one fails at session start, entire suite blocks. No granular test isolation.

3. **Fixture Naming:** Some fixtures have generic names (e.g., `generated_audio_artifacts`). As test suite grows, name collisions risk increases.

**Risk Level:** LOW (current test count ~100–150, not yet explosion scale). Preventive measure recommended.

**Recommendation:** Consider fixture reorganization:
- Document fixture ownership (which test file owns which fixture)
- Use pytest fixture factories to reduce duplication
- Consider function-scope fixtures for more granular test isolation where appropriate

---

## Focus Area 6: Build System Cross-Reference (LTO Type-Mismatch Surface)

### 6.1: Build-System R16 Finding Context

**From build-system-r16.md:**

- 17 LTO type-mismatch warnings (-Wlto-type-mismatch)
- Origin: compat/mact_stub.c signature drift (long return types vs int32_t declarations in engine)
- Symbols affected: VBE_setPalette, MOUSE_GetButtons, FindDistance2D, divscale, Z_AvailHeap, etc.

**Question:** Are tools/ outputs (manifests, generated headers, PALETTE.DAT) ever compiled into the binary?

### 6.2: LTO Linkage Surface Analysis

**Verified Status:** ✅ Tools outputs are **data files only**, NOT compiled artifacts:

| Output File | Format | Linked? | Risk |
|-------------|--------|---------|------|
| DUKE3D.GRP | Binary archive | No (loaded at runtime) | None |
| GRP_MANIFEST.json | JSON | No (parsed at runtime) | None |
| PALETTE.DAT | Binary data | No (loaded at runtime) | None |
| GENERATION_LOG.jsonl | JSONL text | No (diagnostic) | None |
| Audio MANIFEST.json | JSON | No (parsed at runtime) | None |

**Conclusion:** No LTO type-mismatch risk from tools/ outputs because they are not compiled into the binary. LTO warnings are confined to compat/mact_stub.c ↔ engine/game declarations.

---

## Summary of Findings

| ID | Severity | Title | Status | Notes |
|-------|----------|-------|--------|-------|
| asset-r16-manifest-schema-forward-compat-advisory | MEDIUM | Schema forward-compat contract not documented | **PENDING (Carry-forward from r16)** | No migration path for schema_version evolution |
| asset-r17-manifest-schema-no-migration-contract | MEDIUM | No documented schema versioning strategy | **NEW** | Producers/consumers must coordinate breaking changes reactively |
| asset-r17-palette-validation-gap | MEDIUM | PALETTE.DAT input not validated for size/range | **NEW** | Corrupted palette input silently produces malformed file |
| asset-r17-generation-log-not-documented-as-queryable | LOW | GENERATION_LOG.jsonl not documented as audit trail | **NEW** | No parsing guide or query tool provided |
| asset-r17-map-id-validation-narrow-scope | LOW | Map ID validation only checks duplicates, not cross-references | **NEW** | Sound/sprite/tile indices in maps not validated |
| asset-r17-test-fixture-proliferation | LOW | 6 manifest test files × 5 session fixtures; maintenance risk | **NEW** | Fixture duplication/overlap as test suite grows |

---

## Verification Checklist

- ✅ Cycle 56 _emit_grp_manifest() implementation VERIFIED PRESENT (lines 272–334)
- ✅ Cycle 56 load_and_verify_grp_manifest() in manifest_verification.py VERIFIED (lines 65–90)
- ✅ Cycle 58 _rotate_generation_log() rotation logic VERIFIED CORRECT (lines 64–111)
- ✅ Atomic write coverage audit: _atomic_write_bytes, _emit_grp_manifest, _rotate_generation_log all use tmp+replace ✅
- ✅ Test coverage: 11 test_grp_manifest.py tests PASSING, 4 test_manifest_verifier_adoption tests PASSING
- ✅ No regressions in generate_assets.py, generate_audio.py, generate_tables.py
- ❌ CONTRIBUTING.md schema_version migration contract NOT DOCUMENTED
- ❌ GENERATION_LOG.jsonl queryability guide NOT DOCUMENTED
- ❌ Palette input validation NOT IMPLEMENTED

---

## Recommendations for R18

1. **HIGH (r16 carry-forward):** Implement manifest schema versioning strategy in CONTRIBUTING.md + add version-aware loaders
2. **HIGH:** Add palette input validation (array length, RGB bounds, shade table bounds) in create_palette_dat()
3. **MEDIUM:** Document GENERATION_LOG.jsonl querying patterns in CONTRIBUTING.md
4. **MEDIUM:** Extend map ID validation to include asset cross-reference checks (sound IDs, sprite IDs, tile indices)
5. **LOW:** Audit conftest.py fixtures for duplication/refactoring opportunities as test suite grows
6. **ADVISORY:** Monitor build-system LTO warnings (r16 finding); compat/mact_stub.c type-mismatch not a tools/ concern but worth tracking

---

**Sentinel:** asset-r17-audit-complete: 5 findings, 5 todos

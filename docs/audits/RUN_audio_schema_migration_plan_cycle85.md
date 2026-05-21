# Audio Schema Migration Planning (v1.0 → v1.1 → v2.0)
**Cycle 85 Planning Document**  
**Owner:** Audio Engineer (asset-pipeline consult)  
**Status:** PLANNING ONLY – No implementation  
**Date:** 2025 (Cycle 85)

---

## Executive Summary

The current SOUND_MANIFEST schema v1.0 (defined in `tools/sound_manifest.py` and enforced in `tools/manifest_verification.py`) is locked to a single version. To support future schema evolution (v1.1 backward-compatible additions, v2.0 breaking changes), this document proposes an **Adapter Pattern** architecture that enables:

- **In-memory schema upgrades** at load time (auto-migrate v1.0 → current)
- **Version-agnostic pipelines** that don't break on new manifests
- **Round-trip migration tests** ensuring zero data loss
- **Deferred implementation** (ready to deploy when v1.1/v2.0 lands)

---

## 1. Current Schema v1.0 Structure

### Top-Level Keys (manifest_dict)

```json
{
  "schema_version": "1.0",           // (required) Version identifier
  "manifest_checksum": "sha256...",  // (required) Manifest integrity hash
  "entries": [
    { /* SoundManifestEntry */ },
    ...
  ]
}
```

### SoundManifestEntry Fields (v1.0)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `wav` | str | ✓ | Filename (e.g., `TAUNT01.WAV`), pattern: `^[A-Z0-9_]+\.WAV$` |
| `engine_sound_id` | str \| null | ✗ | C identifier (e.g., `DUKE_GRUNT`), pattern: `^[A-Z_][A-Z0-9_]*$` |
| `engine_sound_id_int` | int \| null | ✗ | Integer sound ID (0–1000), cross-field invariant with `engine_sound_id` |
| `voice` | str | ✓ | Enum: `"alloy"`, `"echo"`, `"onyx"` |
| `category` | str | ✓ | Enum: `"taunt"`, `"pain"`, `"death"`, `"pickup"`, `"weapon"`, `"level_start"`, `"alarm"`, `"ambient"` |
| `prompt_summary` | str | ✓ | Concise generation prompt (1–500 chars) |
| `notes` | str \| null | ✗ | Optional metadata (max 1000 chars) |
| `status` | str | ✓ | Enum: `"generated"`, `"failed"`, `"fallback"` (default: `"generated"`) |
| `generation_metadata` | dict \| null | ✗ | Optional dict (model version, confidence, etc.) |
| `generated_at` | str \| null | ✗ | ISO 8601 timestamp (e.g., `"1970-01-01T00:00:00Z"`) |
| `schema_version` | str | ✓ | Fixed to `"1.0"` in entry |

**Validation Invariants (Pydantic v2):**
- `engine_sound_id` and `engine_sound_id_int` must both be `null` OR both be set (no partial state).
- All enums are strictly enforced (ValueError if invalid).
- Cross-field consistency checked in `validate_engine_sound_id_cross_field()` model validator.

**Supported Versions (manifest_verification.py, L15):**
```python
SUPPORTED_SCHEMA_VERSIONS = ("1.0",)
```

---

## 2. Anticipated v1.1 Schema (Backward-Compatible Additions)

**Goal:** Extend v1.0 with new optional fields; manifests remain loadable without migration.

### v1.1 Proposed Additions

#### Top-Level (manifest_dict)
- **`metadata`** (dict, optional)  
  New metadata block:
  ```json
  {
    "metadata": {
      "generator_version": "1.5",      // AI model version used
      "generation_date": "2025-...",   // When entries were generated
      "pipeline_branch": "neon-noir",  // Asset pipeline variant
      "locale": "en-US"                // Optional: localization hint
    }
  }
  ```

#### Per-Entry (SoundManifestEntry)
- **`priority`** (int, optional, 0–100)  
  Playback priority for runtime scheduler. Default: 50 (medium).
  ```json
  {
    "wav": "TAUNT01.WAV",
    "priority": 80,  // High priority for taunts
    ...
  }
  ```

- **`duration_ms`** (int, optional)  
  Cached WAV duration in milliseconds. Allows fast metadata queries without decoding.
  ```json
  {
    "wav": "TAUNT01.WAV",
    "duration_ms": 2340,
    ...
  }
  ```

- **`localization_key`** (str, optional)  
  For future i18n: maps entry to localization string (e.g., `"line.taunt.01"`).
  ```json
  {
    "wav": "TAUNT01.WAV",
    "localization_key": "line.taunt.01",
    ...
  }
  ```

- **`confidence`** (float, optional, 0.0–1.0)  
  Generation confidence score. Useful for sorting/filtering regeneration candidates.
  ```json
  {
    "wav": "TAUNT01.WAV",
    "confidence": 0.92,
    ...
  }
  ```

### v1.1 Validation Rules
- All new fields are optional; entries without them default to sensible values.
- `priority` must be 0–100 if present.
- `duration_ms` must be > 0 if present.
- `confidence` must be 0.0–1.0 if present.
- `localization_key` follows pattern (e.g., `^[a-z.]+$`).
- Entry `schema_version` field may remain `"1.0"` (not updated per-entry).

---

## 3. Anticipated v2.0 Schema (Breaking Changes)

**Goal:** Restructure manifest for runtime optimization and advanced categorization.

### v2.0 Proposed Breaking Changes

#### Top-Level Restructuring
```json
{
  "schema_version": "2.0",
  "manifest_checksum": "sha256...",
  
  "metadata": {
    "generator_version": "2.0+",
    "generation_date": "...",
    "pipeline_branch": "..."
  },
  
  "categories": {
    "taunt": { "priority": 80, "voice_default": "alloy" },
    "pain": { "priority": 60, "voice_default": "onyx" },
    ...
  },
  
  "entries_by_category": {
    "taunt": [
      {
        "id": "TAUNT01",                      // (NEW) Entry ID (no .WAV extension)
        "wav": "TAUNT01.WAV",
        "engine_sound_id": "DUKE_TAUNT1",
        "voice": "alloy",
        "prompt": "...",                      // (RENAMED) prompt_summary → prompt
        "notes": "...",
        "status": "generated",
        "duration_ms": 2340,
        "confidence": 0.92,
        "localization_key": "line.taunt.01",
        "generation_metadata": { ... }
      },
      ...
    ],
    "pain": [ ... ],
    ...
  }
}
```

**Key Breaking Changes:**
1. **Entries grouped by category** (`entries` array → `entries_by_category` dict)
   - Faster runtime lookups by category
   - Simpler filtering and batch processing

2. **New `id` field per entry** (derived from filename, minus extension)
   - Stable identifier for runtime lookups, independent of filename
   - Enables filename refactoring without breaking references

3. **`prompt_summary` → `prompt`** (field rename)
   - Shorter, clearer name in a restructured schema

4. **Top-level `categories` metadata block**
   - Pre-computed category defaults (priority, voice, etc.)
   - Runtime can query category settings without scanning entries

5. **Flat entry `schema_version` removed** (moved to manifest-level only)
   - v2.0 explicitly disallows per-entry versions

---

## 4. Adapter Pattern Proposal

### Goal
Enable seamless migration across schema versions without code rewrites. Load any version (v1.0+), auto-upgrade to current runtime version, and maintain backward compatibility.

### Core Components

#### 4.1 MigrationRegistry
```python
# tools/schema_migration.py

class MigrationFunction:
    """Callable that upgrades a manifest from source_version to target_version."""
    source_version: str
    target_version: str
    func: Callable[[dict], dict]

class MigrationRegistry:
    """Registry of version migrations."""
    
    def __init__(self):
        self.migrations: Dict[Tuple[str, str], Callable[[dict], dict]] = {}
    
    def register(self, from_version: str, to_version: str) -> Callable:
        """Decorator to register a migration function."""
        def decorator(func):
            self.migrations[(from_version, to_version)] = func
            return func
        return decorator
    
    def find_path(self, from_version: str, to_version: str) -> List[str]:
        """Find shortest path from from_version to to_version (BFS)."""
        # Returns list of versions: [from_version, ..., to_version]
        # Raises ValueError if no path exists
    
    def migrate(self, manifest: dict, target_version: str) -> dict:
        """Upgrade manifest to target_version using registered migrations."""
        current_version = manifest.get("schema_version", "1.0")
        if current_version == target_version:
            return manifest
        
        path = self.find_path(current_version, target_version)
        for i in range(len(path) - 1):
            src, dst = path[i], path[i+1]
            migrate_func = self.migrations[(src, dst)]
            manifest = migrate_func(manifest)
        
        return manifest

# Global registry instance
migration_registry = MigrationRegistry()
```

#### 4.2 Migration Functions

**v1.0 → v1.1:**
```python
@migration_registry.register("1.0", "1.1")
def migrate_v1_0_to_v1_1(manifest: dict) -> dict:
    """Upgrade v1.0 manifest to v1.1 (backward-compatible).
    
    - Add optional metadata block if missing
    - Add optional fields to entries (priority, duration_ms, confidence, localization_key)
    - Preserve all v1.0 fields unchanged
    """
    manifest["schema_version"] = "1.1"
    
    # Add metadata block if not present
    if "metadata" not in manifest:
        manifest["metadata"] = {
            "generator_version": "unknown",
            "generation_date": None,
            "pipeline_branch": "unknown"
        }
    
    # Upgrade entries: add optional fields with sensible defaults
    for entry in manifest.get("entries", []):
        entry.setdefault("priority", 50)
        entry.setdefault("duration_ms", None)
        entry.setdefault("confidence", None)
        entry.setdefault("localization_key", None)
    
    return manifest
```

**v1.1 → v2.0:**
```python
@migration_registry.register("1.1", "v2.0")
def migrate_v1_1_to_v2_0(manifest: dict) -> dict:
    """Upgrade v1.1 manifest to v2.0 (breaking).
    
    - Restructure entries_by_category from flat entries array
    - Generate entry ids from WAV filenames
    - Rename prompt_summary → prompt
    - Build category metadata block
    """
    manifest["schema_version"] = "2.0"
    
    # Build category defaults from entries
    categories = {}
    for entry in manifest.get("entries", []):
        cat = entry.get("category")
        if cat and cat not in categories:
            categories[cat] = {
                "priority": entry.get("priority", 50),
                "voice_default": entry.get("voice", "alloy")
            }
    manifest["categories"] = categories
    
    # Restructure entries by category
    entries_by_category = {cat: [] for cat in categories}
    for entry in manifest.get("entries", []):
        cat = entry.get("category")
        wav = entry.get("wav", "")
        entry_id = wav.replace(".WAV", "").replace(".wav", "")
        
        # Build v2.0 entry
        v2_entry = {
            "id": entry_id,
            "wav": wav,
            "engine_sound_id": entry.get("engine_sound_id"),
            "engine_sound_id_int": entry.get("engine_sound_id_int"),
            "voice": entry.get("voice"),
            "prompt": entry.get("prompt_summary"),  # Rename
            "notes": entry.get("notes"),
            "status": entry.get("status", "generated"),
            "duration_ms": entry.get("duration_ms"),
            "confidence": entry.get("confidence"),
            "localization_key": entry.get("localization_key"),
            "generation_metadata": entry.get("generation_metadata")
        }
        # Remove None values for cleaner JSON
        v2_entry = {k: v for k, v in v2_entry.items() if v is not None}
        
        entries_by_category[cat].append(v2_entry)
    
    manifest["entries_by_category"] = entries_by_category
    del manifest["entries"]  # v2.0 no longer has flat entries
    
    return manifest
```

#### 4.3 Backward Read Compatibility

**upgrade_manifest() top-level function:**
```python
def upgrade_manifest(manifest: dict, target_version: str = "2.0") -> dict:
    """Load manifest of any version and upgrade to target_version in-memory.
    
    Args:
        manifest: Manifest dict (any supported schema version)
        target_version: Target schema version (default: "2.0")
    
    Returns:
        Upgraded manifest at target_version
    
    Raises:
        ValueError: If no migration path exists from detected version to target
    """
    current_version = manifest.get("schema_version", "1.0")
    return migration_registry.migrate(manifest, target_version)


def load_and_upgrade_audio_manifest(manifest_path: str, target_version: str = "2.0") -> dict:
    """Load audio manifest (any version) and auto-upgrade to target_version.
    
    Replaces load_and_verify_audio_manifest() as entry point.
    """
    manifest = load_and_verify_audio_manifest(manifest_path)  # Original verification
    return upgrade_manifest(manifest, target_version)
```

---

## 5. Test Plan

### 5.1 Unit Tests (test_schema_migration.py)

#### Test Fixtures
- **Minimal v1.0 manifest** (all required fields only)
- **Full v1.0 manifest** (all fields populated)
- **Malformed v1.0** (missing schema_version, invalid enum)
- **v1.1 manifest** (with new optional fields)
- **v2.0 manifest** (with category restructuring)

#### Test Cases

**Migration Path Discovery:**
- `test_find_path_v1_0_to_v1_1()` → Path exists
- `test_find_path_v1_0_to_v2_0()` → Path via v1.1 exists
- `test_find_path_unsupported_version()` → Raises ValueError

**v1.0 → v1.1 Migration:**
- `test_migrate_v1_0_to_v1_1_preserves_fields()` → All v1.0 fields unchanged
- `test_migrate_v1_0_to_v1_1_adds_defaults()` → New optional fields added with defaults
- `test_migrate_v1_0_to_v1_1_schema_version_bumped()` → schema_version = "1.1"
- `test_migrate_v1_0_to_v1_1_metadata_block_created()` → metadata block added

**v1.1 → v2.0 Migration:**
- `test_migrate_v1_1_to_v2_0_restructures_entries()` → entries → entries_by_category
- `test_migrate_v1_1_to_v2_0_generates_entry_ids()` → id field = filename without extension
- `test_migrate_v1_1_to_v2_0_renames_prompt()` → prompt_summary → prompt
- `test_migrate_v1_1_to_v2_0_builds_categories()` → categories block created from entries
- `test_migrate_v1_1_to_v2_0_removes_flat_entries()` → entries field deleted

**Round-Trip Idempotency:**
- `test_idempotent_v1_0_to_v1_1()` → upgrade(upgrade(v1_0)) == upgrade(v1_0)
- `test_idempotent_v1_1_to_v2_0()` → upgrade(upgrade(v1_1)) == upgrade(v1_1)
- `test_idempotent_v1_0_to_v2_0_via_v1_1()` → Same result as direct path (if added)

**Data Integrity:**
- `test_no_data_loss_v1_0_to_v1_1()` → All entry data preserved
- `test_no_data_loss_v1_1_to_v2_0()` → All entry data preserved (including renamed prompt)
- `test_entry_count_preserved()` → Entry count unchanged after migration

**Edge Cases:**
- `test_manifest_with_empty_entries()` → Handles empty manifest gracefully
- `test_manifest_with_null_optional_fields()` → Null fields handled correctly
- `test_manifest_already_at_target_version()` → Returns unchanged manifest

### 5.2 Integration Tests

**Load and Upgrade:**
- `test_load_v1_0_manifest_and_upgrade_to_v2_0()` → Full pipeline: load MANIFEST.json (v1.0) → verify → upgrade → valid v2.0
- `test_load_v1_1_manifest_and_upgrade_to_v2_0()` → Upgrade from intermediate version

**Backward Compatibility:**
- `test_pydantic_v1_0_models_still_validate()` → v1.0 entries validate against SoundManifestEntry
- `test_pydantic_v2_0_models_validate_upgraded_entries()` → v2.0 entries validate against new models (to be created)

### 5.3 Regression Tests

- `test_existing_pipelines_unaffected()` → Current code paths (load_and_verify_audio_manifest) continue to work
- `test_checksum_verification_before_upgrade()` → Integrity checked before migration

---

## 6. Effort Estimate

| Phase | Task | Effort | Notes |
|-------|------|--------|-------|
| **Phase 1: Infrastructure** | Define MigrationRegistry, migration functions | 2–3 days | Python, no external deps |
| | Write unit tests (15–20 test cases) | 2–3 days | High coverage essential |
| | Backward read compatibility integration | 1–2 days | Integrate with existing loaders |
| **Phase 2: v1.1 Schema** | Update Pydantic models (optional fields) | 1 day | Additive, low risk |
| | Integration tests (v1.0 → v1.1) | 1 day | Verify round-trip |
| **Phase 3: v2.0 Schema** | Define new v2.0 Pydantic models (entries_by_category) | 1–2 days | Breaking changes |
| | Implement v1.1 → v2.0 migration function | 1–2 days | Complex restructuring |
| | Rewrite dependent code (pipelines, tools) | 3–5 days | Impacts generate_assets.py, etc. |
| | Full integration + regression tests | 2–3 days | Ensure no breakage |
| **Total** | | **14–21 days** | ~3 weeks; parallelizable phases |

**Parallelization Opportunity:**
- Phase 1 (infrastructure) and Phase 2 (v1.1 models) can proceed simultaneously
- Phase 3 blocked on Phase 1 completion

---

## 7. Implementation Timeline

### Trigger Points

**Defer Implementation to:**
1. **When v1.1 schema is finalized** (product requirement)
2. **Or proactively build infrastructure** (recommended if v2.0 planned within 6 months)

**Recommendation:** Build Phase 1 (MigrationRegistry + tests) proactively **now** (Cycle 85–87). This:
- Decouples infrastructure from v1.1/v2.0 schema decisions
- Allows Phase 2/3 to execute rapidly when schemas are finalized
- Zero risk: no schema changes until Phase 2+

### Deployment Strategy

1. **Land Phase 1** in a feature branch (`feature/schema-migration-infrastructure`)
   - Add `tools/schema_migration.py`, `tests/test_schema_migration.py`
   - Update `tools/manifest_verification.py` to use `upgrade_manifest()` (opt-in)
   - No manifest/pipeline changes yet

2. **When v1.1 lands:** Activate Phase 2
   - Update Pydantic models with optional fields
   - Run full test suite
   - Merge v1.1 support

3. **When v2.0 lands:** Activate Phase 3
   - Implement v1.1 → v2.0 migration
   - Rewrite dependent code
   - Full regression testing
   - Merge v2.0 support

---

## 8. Backward Compatibility Guarantees

### Read Compatibility
- ✅ v1.0 manifests load and upgrade silently (no breaking change)
- ✅ Pipelines using `load_and_upgrade_audio_manifest()` work with any version
- ✅ Legacy code using `load_and_verify_audio_manifest()` unaffected

### Write Compatibility
- ⚠️ New manifests **written as v2.0** cannot be read by v1.0 code
  - Mitigation: pipelines emit schema_version in generated manifests
  - Unclear if v1.0 code will ever need to read new manifests

### Testing Strategy
- Round-trip tests ensure v1.0 → v1.1 → v2.0 → v1.0 (conceptual) data matches
- Idempotency tests ensure upgrade(upgrade(m)) == upgrade(m)

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Migration path wrong | Medium | High | Comprehensive unit tests; small step increments |
| Data loss in restructuring | Low | Critical | Round-trip tests; diff v1.0 vs v2.0 JSON |
| Performance regression (large manifests) | Low | Medium | Profile migration on 1000+ entry manifests |
| v1.1/v2.0 schemas change | High | Medium | Infrastructure flexible; add migrations as needed |
| Dependent code breaks on v2.0 | Medium | High | Full integration tests before merge |

---

## 10. Known Limitations & Future Work

1. **No automatic v2.0 → v1.0 downgrade** (backward write)
   - One-way migration only; v2.0 manifests cannot be written as v1.0
   - Future: add serialization adapter if needed

2. **CSV/YAML migration** not in scope
   - Current plan assumes JSON manifests only
   - Future: add format converters if pipelines adopt other formats

3. **Database schema versioning** out of scope
   - If audio catalog moves to SQLite/PostgreSQL, separate migration strategy needed

4. **Per-entry schema_version** support removed in v2.0
   - v2.0 assumes uniform manifest-level version
   - If heterogeneous entries needed, add back per-entry versions

---

## 11. Decision Points for Future Cycles

### Cycle 85–87 (Recommended)
- ✅ Approve Phase 1 (infrastructure only)
- ✅ Land MigrationRegistry + comprehensive tests
- ✅ Defer v1.1/v2.0 schema finalization

### Cycle 88+ (Product Signals)
- **If v1.1 finalized:** Activate Phase 2 (backward-compat additions)
- **If v2.0 finalized:** Activate Phase 3 (breaking restructure)
- **If neither finalized:** Extend deferral; infrastructure remains ready

---

## 12. Document Metadata

- **Author:** Audio Engineer (Cycle 85)
- **Asset Pipeline Consult:** asset-pipeline.agent.md
- **Related Tickets:** audio-r19-schema-migration-planning (MED)
- **Schema Sources:**
  - `tools/manifest_verification.py:15` (SUPPORTED_SCHEMA_VERSIONS)
  - `tools/sound_manifest.py:13–120` (SoundManifestEntry Pydantic model)
- **Next Review:** When v1.1 or v2.0 schema requirements finalized

---

**EOF: RUN_audio_schema_migration_plan_cycle85.md**

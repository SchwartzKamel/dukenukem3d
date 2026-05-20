# Audio Engineer Audit — Round 10 (Cycle 36)

**Auditor**: audio-engineer persona  
**Timestamp**: 2025-01-04 (Cycle 36)  
**Status**: ✅ R9 Todos Reviewed | 🆕 4 Actionable Findings Identified | 📋 5 New Todos Seeded

---

## Executive Summary

Round 10 audit continues from **Cycle 35 (R9)** with focus on **4 open medium/low severity todos** and **deeper schema/coverage validation**. All prior fixes (cycles 26, 33, 34) remain intact and verified. New audit scope expands to:

1. **Text field unbounded lengths** — No enforcement in validate_manifest() creates potential buffer/parsing risks
2. **Error reporting asymmetry** — MUSIC_PlaySong ignores failures unlike FX_PlaySound variants
3. **RW allocation failure coverage** — Three allocation sites lack comprehensive error logging
4. **Enum strictness in generation** — Generation code lacks explicit enum enforcement during manifest build
5. **Test coverage gaps** — Tests exist for validation but NOT for actual generation error paths

---

## REVIEW: R9 Open Todos (4 items)

### Todo 1: audio-r9-text-length (MEDIUM)

**Status**: ⚠️ **UNRESOLVED**  
**File**: `tools/generate_audio.py:145-175`

**Finding Summary**:  
`validate_manifest()` validates enum fields (voice, category, status) but does NOT enforce min/max length on text fields:
- `wav` filename: currently max 12 chars observed (8.3 format upper bound implicit)
- `prompt_summary`: currently max 62 chars observed (unbounded in code)
- `notes`: currently max 153 chars observed (unbounded in code)

**Risk Assessment**:
- **Manifest JSON bloat**: Unbounded text could inflate manifest JSON size on disk/network transfer
- **Backend constraints**: Embedded audio hardware may have fixed-size string buffers; no validation means runtime crashes possible
- **Fuzz coverage gap**: No property-based tests for text length boundaries

**Current Code Pattern** (lines 145-175):
```python
valid_voices = {"alloy", "echo", "onyx"}
valid_categories = {"taunt", "pain", "death", "pickup", "weapon", "level_start", "alarm", "ambient"}
valid_statuses = {"generated", "failed", "fallback"}

for i, entry in enumerate(entries):
    # ❌ NO LENGTH VALIDATION:
    # - entry["wav"]
    # - entry["prompt_summary"]
    # - entry["notes"]
```

**Recommended Fix**: Add length assertions in `validate_manifest()`:
```python
# Suggested constraints (need confirmation):
assert len(entry["wav"]) <= 12, f"wav filename too long: {entry['wav']}"
assert len(entry["prompt_summary"]) <= 256, f"prompt_summary too long"
assert len(entry.get("notes", "")) <= 512, f"notes too long"
```

**Action**: Remains PENDING for implementation phase.

---

### Todo 2: audio-r9-music-error-parity (MEDIUM)

**Status**: ⚠️ **UNRESOLVED**  
**File**: `compat/audio_stub.c:885-908`

**Finding Summary**:  
MUSIC_PlaySong() ignores Mix_LoadMUS_RW() failure; always returns MUSIC_Ok (success code) even on silent failure.

**Current Pattern** (lines 893-908):
```c
current_music = Mix_LoadMUS_RW(current_music_rw, 0);
if (!current_music) {
    SDL_FreeRW(current_music_rw);
    current_music_rw = NULL;
    // ❌ NO ERROR CODE RETURNED
} else {
    Mix_PlayMusic(current_music, loopflag ? -1 : 0);
}
// ...
return MUSIC_Ok;  // ❌ Always returns MUSIC_Ok!
```

**Comparison** (FX_PlaySound error handling):
```c
// mixer_play (line 184-187)
chunk = Mix_LoadWAV_RW(rw, 1);
if (!chunk) {
    SDL_FreeRW(rw);
    return -1;  // ✅ Returns -1 on failure
}
```

**Risk**:
- Caller cannot distinguish success from silent failure
- Missing music load errors NOT logged to engine error handler
- Could mask corruption/truncation of music file data
- Inconsistent error contract across audio playback layer

**Action**: Remains PENDING. Requires decision on MUSIC error enum (MUSIC_Error? MUSIC_Fail?).

---

### Todo 3: audio-r9-rw-alloc-safety (LOW)

**Status**: ⚠️ **UNRESOLVED**  
**Files**: `compat/audio_stub.c:181, 240, 891`

**Finding Summary**:  
Three SDL_RWFromConstMem() allocation sites have NULL checks but lack error diagnostics:

**Location 1 — mixer_play (line 181)**:
```c
rw = SDL_RWFromConstMem(ptr, (size_t)size);
if (!rw) return -1;  // ✅ Checked, but silent
```

**Location 2 — mixer_play_3d (line 240)**:
```c
rw = SDL_RWFromConstMem(ptr, (size_t)size);
if (!rw) return -1;  // ✅ Checked, but silent
```

**Location 3 — MUSIC_PlaySong (line 891)**:
```c
current_music_rw = SDL_RWFromConstMem(song, (size_t)size);
if (current_music_rw) {  // ✅ Checked, but silent on failure
    // ...
}
```

**Risk Assessment**:
- Allocation failures (OOM, invalid size) cause silent playback failure with no diagnostic
- Hard to debug in production: caller doesn't know if sound failed to load or just not played
- No logging means audio issues invisible to telemetry

**Recommended Fix**:
```c
if (!rw) {
    fprintf(stderr, "mixer_play: SDL_RWFromConstMem failed (size=%lu, likely OOM)\n", size);
    return -1;
}
```

**Action**: Remains PENDING. Low severity due to already-present NULL checks (no crash risk), but improves debuggability.

---

### Todo 4: audio-r9-voice-enum-strict (LOW)

**Status**: ⚠️ **UNRESOLVED**  
**Files**: `tools/generate_audio.py:95-410`

**Finding Summary**:  
`validate_manifest()` strictly enforces enums on LOADED manifests, but GENERATION code (`generate_voices()`) lacks explicit enum enforcement during SOUND_MANIFEST modification.

**Generation Sites** (lines 396-469):
```python
# Line 396-397: Status assignment
SOUND_MANIFEST[idx]["status"] = "generated"  # ✅ Literal string (valid)
SOUND_MANIFEST[idx]["status"] = "failed"     # ✅ Literal string (valid)
SOUND_MANIFEST[idx]["status"] = "fallback"   # ✅ Literal string (valid)

# Line 389-410: Voice/category assignment
# Questions:
# 1. Are voice/category always from VOICE_LINES source? (YES — hardcoded at lines 59-94)
# 2. Could voice/category be mutated dynamically? (NO — only in SOUND_MANIFEST init)
```

**Risk Assessment**:
- **LOW**: Actual risk minimal because:
  - VOICE_LINES is hardcoded (no dynamic input)
  - SOUND_MANIFEST entries initialized from VOICE_LINES
  - validate_manifest() catches errors on load
- **MEDIUM (Future-proofing)**: If VOICE_LINES becomes file-sourced or API-driven, validation gap exists during generation

**Recommendation**: Add _assert_valid_enum() helper to validate during generation:
```python
def _assert_valid_enum(entry, field_name, valid_set):
    value = entry.get(field_name)
    if value not in valid_set:
        raise ValueError(f"Invalid {field_name}: {value} not in {valid_set}")

# During generation:
for idx in range(len(SOUND_MANIFEST)):
    _assert_valid_enum(SOUND_MANIFEST[idx], "voice", valid_voices)
    _assert_valid_enum(SOUND_MANIFEST[idx], "category", valid_categories)
```

**Action**: Remains PENDING. Suitable for future VOICE_LINES externalization.

---

## NEW AUDIT AREAS (R10)

### Area 1: Test Coverage Gap — Error Path Testing

**Finding**: `test_audio_pipeline.py` has 24 test functions across 6 test classes but covers VALIDATION, not GENERATION error paths.

**Coverage Analysis**:
- ✅ `TestVoiceLinesSchema` — VOICE_LINES format (count, tuple structure, voice enum, filename format) — 6 tests
- ✅ `TestVoiceMappingConvention` — voice consistency (alloy/echo/onyx per line type) — 1 test
- ✅ `TestWAVGeneration` — WAV file generation, RIFF header validity, WAVE format — 3 tests
- ✅ `TestSecurityPractices` — No hardcoded API keys, env lookup — 3 tests
- ✅ `TestManifestValidation` — Schema version, enum field validation, category/status strictness — 5 tests
- ❌ **Missing**: Error path tests for:
  - Mix_LoadWAV_RW failure logging (has NULL check, no diagnostic log test)
  - MUSIC_PlaySong error return (no test for failure case)
  - SDL_RWFromConstMem OOM simulation (no test)
  - API timeout/retry backoff (no test for --no-ai fallback)
  - Manifest generation mutation correctness (no test for malformed SOUND_MANIFEST)

**Risk**: Generation error paths untested; regressions possible.

**Action**: 📝 New todo `audio-r10-test-error-paths` seeded (see below).

---

### Area 2: Fuzz Stability — Schema Version and Manifest Drift

**Finding**: `validate_manifest()` enforces schema_version="1.0" strictly, but version drift not tested.

**Current Pattern** (lines 131-136):
```python
schema_version = manifest_data.get("schema_version")
if schema_version != "1.0":
    raise ValueError(
        f"{source_path}: Unsupported schema_version '{schema_version}' "
        f"(expected '1.0')"
    )
```

**Stability Concerns**:
- What if manifest saved with schema_version="1.1" by future code? (validation rejects it)
- No field versioning strategy (forward/backward compat roadmap unclear)
- SOUND_MANIFEST fields are static; future expansion (e.g., new voice types) needs careful schema bump

**Question for Next Cycle**: Is schema migration strategy documented? (CONTRIBUTING.md / README.md / ARCHITECTURE.md)

**Action**: 📝 New todo `audio-r10-schema-migration-strategy` seeded (see below).

---

### Area 3: Voice Enum Expansion Readiness

**Finding**: Three hardcoded voice choices (alloy, echo, onyx) cover persona specification, but no mechanism for voice addition or fallback.

**Current Catalog** (lines 59-94):
```python
VOICE_LINES = [
    # ... 5x alloy (taunts, death)
    # ... 3x onyx (pain/death)
    # ... 10x echo (pickup, weapon, alarm, computer)
]
```

**Enum Definition** (validate_manifest):
```python
valid_voices = {"alloy", "echo", "onyx"}
```

**Expansion Risk**:
- Adding new voice (e.g., "shimmer" for future character) requires:
  - Modify VOICE_LINES entries
  - Update valid_voices set in validate_manifest()
  - Regenerate SOUND_MANIFEST
  - Update audio-engineer.agent.md docs (lines 13–16)
  - No tooling to assist (manual multi-file edits required)

**Future Enhancement**: Voice registry or config file (audio/voices.json?) would enable:
- Dynamic voice addition without code changes
- Voice library versioning
- Voice description/fallback mapping

**Action**: 📝 New todo `audio-r10-voice-registry-design` seeded (see below).

---

### Area 4: GRP Repacking Workflow Clarity

**Finding**: Audio generation workflow requires explicit GRP repacking step; automation gap identified.

**Current Workflow** (from audio-engineer.agent.md lines 67–71):
```bash
python3 tools/generate_audio.py
python3 tools/generate_assets.py --no-ai  # ← Manual step
```

**Questions**:
1. Does `generate_audio.py` ALWAYS require manual GRP repack? (YES — separate tool, separate invocation)
2. Could repack be automated as part of generate_audio.py tail? (Interdependency concern with generate_assets.py)
3. Is WAV generation output actually used by GRP packer? (Needs verification)

**Risk**: Operator forgets repacking step → generated WAVs not shipped with DUKE3D.GRP.

**Note**: Low severity (procedural, not correctness bug), but UX improvement opportunity.

**Action**: 📝 New todo `audio-r10-grp-repacking-automation` seeded (see below).

---

### Area 5: MUSIC_PlaySong State Consistency

**Finding**: MUSIC_PlaySong sets `music_playing = 1` unconditionally (line 906), even if Mix_LoadMUS_RW fails silently.

**Pattern** (lines 905-907):
```c
music_loop = loopflag;
music_playing = 1;  // ❌ Set even on silent failure!
return MUSIC_Ok;
```

**Risk**:
- Engine logic might check `music_playing` flag to gate other audio operations
- Silent failure + flag set = state machine corruption
- MUSIC_StopSong() may be called on a NULL `current_music` pointer (undefined behavior risk)

**Related**: Closely tied to todo `audio-r9-music-error-parity`; fixing return code should also fix state consistency.

**Action**: 📝 New todo `audio-r10-music-state-consistency` seeded (see below).

---

## Todos Seeded (Round 10)

5 new todos created in session database:

| ID | Priority | Title | File | Citation | Category |
|---|---|---|---|---|---|
| `audio-r10-test-error-paths` | MEDIUM | Add error path tests (Mix_LoadWAV_RW OOM, MUSIC_PlaySong failure, API timeout) | tests/test_audio_pipeline.py | Test Coverage Gap (Area 1) | Testing |
| `audio-r10-schema-migration-strategy` | MEDIUM | Document schema version migration strategy (1.0 → 1.x forward/backward compat) | docs/audits/audio-engineer.md, CONTRIBUTING.md | Fuzz Stability (Area 2) | Documentation |
| `audio-r10-voice-registry-design` | LOW | Design voice registry config (audio/voices.json) for dynamic voice addition | tools/generate_audio.py, .github/agents/audio-engineer.agent.md | Voice Enum Expansion (Area 3) | Feature |
| `audio-r10-grp-repacking-automation` | LOW | Automate GRP repacking as part of generate_audio.py tail (or document explicit requirement) | tools/generate_audio.py, CONTRIBUTING.md | GRP Repacking Workflow (Area 4) | UX/Automation |
| `audio-r10-music-state-consistency` | MEDIUM | Fix MUSIC_PlaySong state consistency: don't set music_playing=1 on Mix_LoadMUS_RW failure | compat/audio_stub.c:905-908 | MUSIC_PlaySong State (Area 5) | Correctness |

---

## Verification: Prior Cycles (26, 33, 34)

### ✅ Cycle 26: SDL_FreeRW Cleanup

All three RWops failure paths verified INTACT:
- `mixer_play` (line 186): SDL_FreeRW on Mix_LoadWAV_RW failure ✅
- `mixer_play_3d` (line 245): SDL_FreeRW on Mix_LoadWAV_RW failure ✅
- `MUSIC_PlaySong` (line 895): SDL_FreeRW on Mix_LoadMUS_RW failure ✅

### ✅ Cycle 33: Mix_Init(OGG|MP3) + Mix_Quit()

Forward-compatibility initialization verified INTACT:
- `FX_Init` (line 362): Mix_Init(MIX_INIT_OGG | MIX_INIT_MP3) with graceful fallback ✅
- `FX_Shutdown` (line 400): Mix_Quit() balances FX_Init ✅

### ✅ Cycle 34: Manifest Schema v1.0

Validation + endpoint redaction verified INTACT:
- `_redact_endpoint()` (line 24): Redacts Azure endpoint URLs in logging ✅
- `validate_manifest()` (line 118-174): Enforces schema_version="1.0" ✅
- `SOUND_MANIFEST` wrapping (line 339-341): schema_version included ✅
- Manifest loading (line 190): validate_manifest() called on load ✅

---

## Audit Rigor

- ✅ All R9 open todos **systematically reviewed** with current code citations
- ✅ 4 new audit areas identified with **file:line citations**
- ✅ 5 new todos seeded across Testing, Documentation, Feature, UX, and Correctness categories
- ✅ Prior cycle fixes (26, 33, 34) **re-verified with grep output**
- ✅ **No source edits, no commits** (audit document only)
- ✅ **No tree-cleaning commands** (working tree shared with sibling agents)

---

## Next Steps for Implementation

**Priority 1 (MEDIUM)** — Unblock error diagnostics:
- audio-r9-music-error-parity: Return error code from MUSIC_PlaySong
- audio-r10-test-error-paths: Add error path test coverage
- audio-r10-music-state-consistency: Fix state consistency on Mix_LoadMUS_RW failure

**Priority 2 (MEDIUM)** — Stabilize schema:
- audio-r9-text-length: Add length validation to validate_manifest()
- audio-r10-schema-migration-strategy: Document versioning strategy

**Priority 3 (LOW)** — Improve UX/Documentation:
- audio-r9-rw-alloc-safety: Add error logging to allocation failures
- audio-r9-voice-enum-strict: Add generation-time enum validation
- audio-r10-voice-registry-design: Design voice config extensibility
- audio-r10-grp-repacking-automation: Clarify/automate GRP workflow

---

## References

- Cycle 26: SDL_FreeRW on error paths (mixer_play, mixer_play_3d, MUSIC_PlaySong)
- Cycle 33: SDL2_mixer 3.0+ forward-compat (Mix_Init/Mix_Quit)
- Cycle 34: Manifest schema v1.0 + validate_manifest() + _redact_endpoint()
- Cycle 35 (R9): 4 new open todos (text-length, error-parity, rw-alloc-safety, voice-enum-strict)
- Cycle 36 (R10): 5 new todos (test-error-paths, schema-migration-strategy, voice-registry-design, grp-repacking-automation, music-state-consistency)

**Unique Token**: `audio-engineer-r10-MANIFEST_DRAFT_VALIDATION_AUDIT`

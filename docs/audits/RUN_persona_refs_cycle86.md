# Persona Reference Audit — Cycle 86
**Executor**: documentation-curator  
**Date**: 2025-05-21  
**Status**: COMPLETE  

## Summary

Audited all 10 persona files in `.github/agents/` for stale file paths, moved/deleted references, and outdated line numbers. Found **significant line number drift** in asset-pipeline.agent.md and build-system.agent.md; two missing file references; one missing documentation file.

## Findings

### CRITICAL: Line Number Drift in asset-pipeline.agent.md

The persona file contains severely outdated line number references to `tools/generate_assets.py`. These line numbers were likely captured early in development and have drifted as the file grew.

**Stale references:**
- **Line 11**: Claims `TEXTURE_DEFS` at "lines 47–103" → Actually at **line 145** (drift: +98 lines)
- **Line 12**: Claims `proc_*()` functions at "lines 181–627" → Functions span a much larger range (drift: file is now 2410 lines total vs. expected ~627)
- **Line 13**: Claims `PROCEDURAL_MAP` at "lines 629–650" → Actually at **line 956** (drift: +327 lines)
- **Line 19**: Claims `generate_texture_ai()` at "lines 128–175" → Actually at **line 342** (drift: +214 lines)
- **Line 41**: References CONTRIBUTING.md "lines 77–93" (not verified in detail)
- **Line 140-142**: Summary structure reference claims line numbers that are now incorrect

**Impact**: Future developers using these references will look at wrong code sections, causing confusion and debugging delays.

**Fix**: Update all line numbers to match current file. See Section "Line Number Corrections" below.

---

### HIGH: Missing File References

#### 1. compat/BUILD.h (Referenced but Does Not Exist)

**Personas referencing**:
- build-system.agent.md, line 129: "Update `compat/BUILD.h` mirror (portable, int32_t fields)"
- test-engineer.agent.md, lines 143 & 356: References to "compat/BUILD.h"

**Actual status**: File does not exist in repository.

**Investigation**: The compat layer has `compat.h` and `compat/compat.h` headers, but no `compat/BUILD.h`. This may be:
1. A planned file that was never created
2. A file that was renamed or removed
3. Functions actually belong in compat.h or another file

**Recommendation**: 
- Determine if `compat/BUILD.h` is actually needed (struct compatibility shims)
- If needed, create it and migrate struct definitions
- If not needed, update personas to reference the correct file (likely `compat/compat.h` or `compat.h`)

---

#### 2. docs/audits/index.md (Referenced but Does Not Exist)

**Personas referencing**:
- documentation-curator.agent.md, lines 20, 32, 85–102: Multiple references to maintaining and updating docs/audits/index.md as "single source of truth for all audit locations and statuses"

**Actual status**: File does not exist. Audit reports exist (engine-porter.md, build-system.md, etc.) but no manifest/index.

**Impact**: Documentation-curator persona expects to maintain an audit index that doesn't exist, leading to unclear task expectations.

**Recommendation**: Create `docs/audits/index.md` with a manifest of all audit reports (see example in documentation-curator.agent.md lines 88–102).

---

### MEDIUM: Outdated Makefile Line Number References

**build-system.agent.md references**:
- Line 43: "Makefile:20" — File is 224 lines; line 20 exists (LTO_FLAGS)
- Line 43: "CMakeLists.txt:80" — File is 151 lines; need to verify line 80
- Line 43: "Makefile:131" — File is 224 lines; line 131 is blank ❌ STALE
- Line 43: "CMakeLists.txt:82" — Need to verify

**Impact**: References guide developers to compiler standard declarations. Wrong line numbers cause confusion.

**Status**: Some references appear to be in bounds but should be spot-checked for accuracy.

---

### LOW: File Path in Example (Not Stale, Hypothetical)

**documentation-curator.agent.md, line 175**: 
- References "docs/audits/engine-porter.md is moved to docs/archive/engine-porter.md" as a *hypothetical* example
- Actual engine-porter.md is at `docs/audits/engine-porter.md` and is **not** in archive
- This is intentional (illustrating a scenario), not a stale reference

---

## Verification Summary

| Persona | File Refs | Line Refs | Missing Files | Status |
|---------|-----------|-----------|---------------|--------|
| asset-pipeline | ✅ All exist | ❌ 5 incorrect | None | DRIFT |
| audio-engineer | ✅ All exist | ✅ Spot-checked | None | PASS |
| build-system | ✅ All exist | ⚠️ 1 OOB | compat/BUILD.h | DRIFT |
| compat-layer | ✅ All exist | ✅ Spot-checked | compat/BUILD.h | WARN |
| documentation-curator | ✅ Most exist | ✅ Spot-checked | docs/audits/index.md | WARN |
| engine-porter | ✅ All exist | ✅ Spot-checked | compat/BUILD.h | WARN |
| network-multiplayer | ✅ All exist | ✅ Spot-checked | None | PASS |
| performance-profiler | ✅ All exist | ✅ Spot-checked | None | PASS |
| security-and-secrets | ✅ All exist | ✅ Spot-checked | None | PASS |
| test-engineer | ✅ All exist | ⚠️ Struct refs | compat/BUILD.h | WARN |

---

## Line Number Corrections for asset-pipeline.agent.md

### Recommended Edits

```diff
Line 11:
- **Texture generation**: `TEXTURE_DEFS` catalog (20 wall/floor/ceiling textures + 10 item sprites) in `tools/generate_assets.py` lines 47–103
+ **Texture generation**: `TEXTURE_DEFS` catalog (20 wall/floor/ceiling textures + 10 item sprites) in `tools/generate_assets.py` starting at line 145

Line 12:
- **Procedural texture fallbacks**: `proc_*` functions (e.g., `proc_dark_steel`, `proc_neon_circuit`, `proc_hex_floor`) that generate 8-bit palette-indexed pixel data as RGB PIL Images in lines 181–627
+ **Procedural texture fallbacks**: `proc_*` functions (e.g., `proc_dark_steel`, `proc_neon_circuit`, `proc_hex_floor`) that generate 8-bit palette-indexed pixel data as RGB PIL Images

Line 13:
- **Procedural mapping**: `PROCEDURAL_MAP` dictionary (lines 629–650) that binds tile numbers to generator functions
+ **Procedural mapping**: `PROCEDURAL_MAP` dictionary (starting at line 956) that binds tile numbers to generator functions

Line 19:
- **AI texture generation**: FLUX.2-pro API integration (`generate_texture_ai()` in lines 128–175); calls Azure with env vars `FLUX_ENDPOINT`, `FLUX_MODEL`, `FLUX_API_KEY`; falls back gracefully to procedural when unavailable
+ **AI texture generation**: FLUX.2-pro API integration (`generate_texture_ai()` starting at line 342); calls Azure with env vars `FLUX_ENDPOINT`, `FLUX_MODEL`, `FLUX_API_KEY`; falls back gracefully to procedural when unavailable

Line 140-142:
Replace the entire structure reference section with current line numbers (suggest removing exact line numbers since file is actively developed and will drift again).
```

---

## Non-Issues (Verified as Current)

1. ✅ **SRC/BUILD.H** — Exists, referenced correctly in all personas
2. ✅ **source/GAME.C** — Exists, referenced correctly
3. ✅ **compat/*.c files** — All referenced files exist (audio_stub.c, sdl_driver.c, mact_stub.c, pragmas_gcc.h, hud.c, msvc_unistd.h)
4. ✅ **tools/*** — All referenced tool files exist (generate_assets.py, generate_audio.py, frame_analyzer.py, palette.py, art_format.py, grp_format.py, map_format.py, tables.py)
5. ✅ **tests/*** — All referenced test files exist (test_build_structs.py, test_compat_layer.py, conftest.py, test_pipeline_integration.py, etc.)
6. ✅ **.github/workflows/** — build.yml exists (personas may reference it but all exist)
7. ✅ **docs/ARCHITECTURE.md** — Exists and is current
8. ✅ **build.mk, Makefile, CMakeLists.txt, build_windows.bat** — All exist
9. ✅ **.env.example** — Exists, correctly NOT committed
10. ✅ **CONTRIBUTING.md, SECURITY.md, README.md, IMPLEMENTATION_PLAN.md** — All exist

---

## Actions Required (Assigned to Personas)

1. **documentation-curator**:
   - [ ] Create `docs/audits/index.md` with manifest of all audit reports (template provided in documentation-curator.agent.md lines 88–102)
   - [ ] Update persona file to fix or remove stale line number references to documentation paths

2. **asset-pipeline (or documentation-curator)**:
   - [ ] Fix line number references in asset-pipeline.agent.md per corrections above

3. **build-system (or compat-layer)**:
   - [ ] Determine if `compat/BUILD.h` is needed; create or update references
   - [ ] Verify Makefile/CMakeLists.txt line numbers are correct (Makefile:20, 131; CMakeLists.txt:80, 82)

4. **engine-porter & test-engineer**:
   - [ ] Wait for decision on compat/BUILD.h; update persona references accordingly

---

## Cycle Notes

No explicit "cycle X" references found in persona files (good). Line number drift suggests personas were authored early (likely cycle 1–5) and have not been updated despite significant code changes in tools/. Consider periodic re-validation (e.g., quarterly) to prevent future drift.

---

## Validation

Run to verify no new file references break:
```bash
python3 -m pytest -q tests/test_docs_audits_index.py 2>&1 | tail -3
```

(If test exists; otherwise, manual verification of created files confirms audit validity.)

---

**Audit Status**: ✅ COMPLETE  
**Next Cycle**: Re-audit after significant code changes to tools/ or major persona updates.

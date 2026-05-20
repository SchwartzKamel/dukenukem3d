# Build System Audit Report - Round 8

**Date:** 2026-05-20  
**Auditor:** Build System Persona  
**Repo:** SchwartzKamel/dukenukem3d  
**Cycle:** 27  
**Scope:** Verification of r7 open items, cross-file #define drift, LTO optimization consistency, Make target dependency completeness, CMakeLists language attribution, cache robustness  
**Prior Round:** build-system-r7 (cycle-22)

---

## Executive Summary

Round 8 audit is an **audit-only pass** focused on verifying the status of **3 CRITICAL/HIGH items from r7** and re-auditing build system stability post-cycle-25.

**Headline:** Build system remains **STABLE**. **No new CRITICAL findings.** However:

- ✅ **MAXTILES mismatch (CRITICAL) from r7 remains OPEN** — source/BUILD.H (6144) vs SRC/BUILD.H (9216). Test marked with xfail in `tests/test_build_h_consistency.py:37-45`. Still tracking in `build-r7-lto-maxtiles-mismatch` todo.

- ✅ **Makefile race condition (HIGH) from r7 remains OPEN** — $(TARGET) rule chmod/strip not atomic. Still tracking in `build-r7-makefile-race-condition` todo.

- ✅ **Windows arch mismatch (HIGH) from r7 remains OPEN** — build_windows.bat architecture drift (i686 vs x86_64). Still tracking in `build-r7-windows-arch-mismatch` todo.

- 🔍 **NEW FINDING (MEDIUM):** CMakeLists.txt **does not enable LTO in release builds**, while Makefile explicitly sets `-flto`. This creates optimization parity gap between build systems.

- 🔍 **NEW FINDING (LOW):** CMakeLists.txt COMPILE_FLAGS redundancy (lines 78-79, 84 duplicate `-std=gnu89 -w -x c`).

- ✅ **SDL2 single-source rule VERIFIED** — build.mk:33 SDL2_VERSION=2.30.9 remains sole source; workflows parse correctly.

- ✅ **Make target dependencies VERIFIED** — All .o rules have proper order-only prerequisites (`| $(BUILD_DIR)`); no missing prereqs found.

- ✅ **CMakeLists language attribution VERIFIED** — LANGUAGE C property correctly set (line 54); no /Tc flag violations.

- ✅ **Cross-file #define drift VERIFIED** — Only MAXTILES differs (6144 vs 9216, known CRITICAL); MAXSECTORS, MAXWALLS, MAXSPRITES, MAXSTATUS, MAXPLAYERS, MAXPALOOKUPS all match perfectly. Test coverage adequate.

**Result: 0 NEW CRITICAL findings. 3 HIGH items from r7 remain OPEN (not re-seeded per audit mandate). 2 NEW MEDIUM/LOW findings suitable for backlog. Audit scope completed without regressions.**

---

## Focus Area 1: Verification of R7 Open Items

### CRITICAL: MAXTILES Bounds Mismatch

**Status: OPEN ❌** (from r7, still unresolved)

**Evidence:**
```
source/BUILD.H:33:#define MAXTILES 6144
SRC/BUILD.H:15:#define MAXTILES 9216
```

**Tracking:**
- Test marked xfail: `tests/test_build_h_consistency.py:37-45`
- Todo: `build-r7-lto-maxtiles-mismatch` (CRITICAL)
- Impact: LTO type-mismatch buffer overflow risk (documented in r7)

**Status:** Not re-seeding per audit mandate. Remains priority blocker for release.

---

### HIGH: Makefile Race Condition

**Status: OPEN ❌** (from r7, still unresolved)

**Evidence:**
```makefile
$(TARGET): $(BUILD_DIR) $(ALL_OBJS)
	$(CC) $(LTO_FLAGS) $(ALL_OBJS) -o $@ $(LIBS)
	@chmod +x $@
	@if [ "$(BUILD_TYPE)" = "release" ]; then strip -s $@; fi
	@echo "Build complete: $(TARGET) ($(BUILD_TYPE))"
```

**Issue:** chmod + strip not atomic; parallel make can cause transient `chmod: cannot access` errors.

**Tracking:**
- Operator-reported transient failures
- Todo: `build-r7-makefile-race-condition` (HIGH)
- Proposed fix: Atomic rename (e.g., link to $@.tmp, chmod $@.tmp, strip $@.tmp, mv $@.tmp $@)

**Status:** Not re-seeding per audit mandate. Affects parallel builds (`make -j$(nproc)`).

---

### HIGH: Windows Architecture Mismatch

**Status: OPEN ❌** (from r7, still unresolved)

**Evidence:**
```makefile
# Makefile:65
WIN_CC = i686-w64-mingw32-gcc  # Correct: 32-bit

# build_windows.bat:69 (MSVC path)
set SDL_LIB=/LIBPATH:"%SDL2_DIR%\lib\x64"  # x86_64 (incorrect for 32-bit)
```

**Issue:** build_windows.bat line 69 uses x64 path for x86 target; MinGW section correct (line 115 uses i686). MSVC path should use x86 or i386, not x64.

**Tracking:**
- Todo: `build-r7-windows-arch-mismatch` (HIGH)
- Makefile uses i686-w64-mingw32-gcc correctly (line 65)
- CI: build.yml Windows job uses correct MinGW

**Status:** Not re-seeding per audit mandate. Low impact (MSVC path mismatch only if user chooses MSVC; CI uses MinGW).

---

## Focus Area 2: Cross-File #define Drift Audit

**Check: All BUILD.H constants**

**Status: PASS ✅** (except known CRITICAL)

**Constants Match:**
| Constant | source/BUILD.H | SRC/BUILD.H | Match |
|----------|---|---|---|
| MAXSECTORS | 1024 | 1024 | ✅ |
| MAXWALLS | 8192 | 8192 | ✅ |
| MAXSPRITES | 4096 | 4096 | ✅ |
| MAXTILES | 6144 | 9216 | ❌ CRITICAL |
| MAXSTATUS | 1024 | 1024 | ✅ |
| MAXPLAYERS | 16 | 16 | ✅ |
| MAXXDIM | 1600 | 1600 | ✅ |
| MAXYDIM | 1200 | 1200 | ✅ |
| MAXPALOOKUPS | 256 | 256 | ✅ |
| MAXPSKYTILES | 256 | 256 | ✅ |
| MAXSPRITESONSCREEN | 1024 | 1024 | ✅ |

**Analysis:** MAXTILES mismatch tracked by xfail test. All other constants perfectly aligned. No new drift detected.

**Test Coverage:** `test_build_h_consistency.py` has 4 test functions:
- `test_maxtiles_matches_between_headers` — xfail (expected failure)
- `test_maxsectors_matches_between_headers` — passing ✅
- `test_maxwalls_matches_between_headers` — passing ✅
- `test_maxsprites_matches_between_headers` — passing ✅

**Recommendation:** Consider adding tests for remaining constants (MAXSTATUS, MAXPLAYERS, MAXPALOOKUPS, MAXPSKYTILES, MAXSPRITESONSCREEN) for completeness.

---

## Focus Area 3: LTO Optimization Consistency

**Check: Makefile vs CMakeLists.txt LTO configuration**

**Location:** Makefile:12-17 vs CMakeLists.txt (no LTO config)

**Finding: MEDIUM — LTO Parity Gap**

**Evidence:**

**Makefile (GNU/Clang):**
```makefile
ifeq ($(BUILD_TYPE),debug)
  OPT_FLAGS = -O0 -g -DDEBUG
  WARN_FLAGS = -Wall
  LTO_FLAGS =
else
  OPT_FLAGS = -O2 -DNDEBUG
  WARN_FLAGS = -w
  LTO_FLAGS = -flto         # ← Explicitly enabled in release
endif
```

**CMakeLists.txt:**
```cmake
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# ... no LTO configuration found
```

**Analysis:**
1. Makefile enables `-flto` in release builds automatically
2. CMakeLists.txt does NOT enable LTO
3. User building with `cmake . && make` (release mode) gets no LTO; user building with `make` gets LTO
4. This creates optimization variance between build systems

**Severity:** MEDIUM (correctness not affected, but performance parity broken)

**Proposed Solution:** Add LTO flag to CMakeLists.txt release builds:
```cmake
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    if(NOT MSVC)
        target_compile_options(duke3d PRIVATE -flto)
        target_link_options(duke3d PRIVATE -flto)
    endif()
endif()
```

**Note:** Keep LTO disabled in debug builds (as Makefile does) to speed up edit-compile-debug cycle.

---

## Focus Area 4: Make Target Dependency Completeness

**Check: All .o rules have proper prerequisites**

**Status: PASS ✅**

**Evidence:**
```makefile
# Order-only prerequisite pattern (| $(BUILD_DIR))
$(BUILD_DIR)/engine_ENGINE.o: SRC/ENGINE.C | $(BUILD_DIR)
$(BUILD_DIR)/engine_CACHE1D.o: SRC/CACHE1D.C | $(BUILD_DIR)
$(BUILD_DIR)/engine_MMULTI.o: SRC/MMULTI.C | $(BUILD_DIR)
$(BUILD_DIR)/game_%.o: source/%.C | $(BUILD_DIR)
$(BUILD_DIR)/compat_%.o: compat/%.c | $(BUILD_DIR)
```

**Analysis:**
1. All .o rules depend on their source .C/.c file (normal dependency)
2. All .o rules depend on $(BUILD_DIR) as order-only prerequisite ✅
3. $(BUILD_DIR) is created before any .o rules run ✅
4. No missing dependencies; race condition risk LOW

**Note:** The HIGH race condition found in r7 is at the **linking stage** ($(TARGET) rule), not the compilation stage. Compilation targets are safe.

---

## Focus Area 5: CMakeLists.txt Language Attribution

**Check: LANGUAGE C property for .C files**

**Status: PASS ✅**

**Evidence:**
```cmake
# CMakeLists.txt:54
set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS} PROPERTIES LANGUAGE C)

# CMakeLists.txt:72-75 (MSVC block)
if(MSVC)
    target_compile_options(duke3d PRIVATE /W0)
    # Note: LANGUAGE C property (line 54) handles .C → C compilation for MSVC.
    # Do NOT add /Tc flag here: it consumes the next token, triggering D8036 error.
```

**Analysis:**
1. LANGUAGE C property correctly set ✅
2. Comment documents why /Tc is NOT used ✅
3. No MSVC invariant violations ✅

**Compliance:** Invariant A (no /Tc on .C files) maintained.

---

## Focus Area 6: SDL2 Single-Source Rule Verification

**Status: PASS ✅** (verified in r7, still valid)

**Evidence:**
```makefile
# build.mk:33
SDL2_VERSION = 2.30.9
```

**Parsed By:**
1. Makefile (line 4) — `include build.mk` ✅
2. .github/workflows/build.yml (line 86) — `SDL2_VERSION=$(grep '^SDL2_VERSION' build.mk | sed 's/.*= *//')` ✅
3. .github/workflows/release.yml (line 48) — same grep pattern ✅
4. CMakeLists.txt — Uses `find_package(SDL2 REQUIRED)` (no hardcoding, correct) ✅
5. build_windows.bat — Takes SDL2_DIR from environment (no hardcoding, correct) ✅

**Regression Check:** No new hardcoding of SDL2 version found in workflows or scripts.

---

## Focus Area 7: NEW FINDING — CMakeLists.txt COMPILE_FLAGS Redundancy

**Severity:** LOW

**Evidence:**
```cmake
# CMakeLists.txt:78-79 (sets ENGINE_SRCS + GAME_SRCS)
set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
    PROPERTIES COMPILE_FLAGS "-std=gnu89 -w -x c")

# CMakeLists.txt:83-84 (sets ENGINE_SRCS again with overlapping flags)
set_source_files_properties(SRC/ENGINE.C
    PROPERTIES COMPILE_FLAGS "-std=gnu89 -w -x c -ffast-math")
```

**Issue:** Both calls set COMPILE_FLAGS on ENGINE_SRCS. The second call (line 83-84) overrides the first call (line 78-79) for SRC/ENGINE.C. This works correctly but is semantically redundant.

**Better Practice:**
```cmake
# Set base flags for all legacy sources
set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
    PROPERTIES COMPILE_FLAGS "-std=gnu89 -w -x c")

# Add -ffast-math only for ENGINE.C
set_source_files_properties(SRC/ENGINE.C
    PROPERTIES COMPILE_FLAGS "-std=gnu89 -w -x c -ffast-math")
```

**This is correct behavior, just not ideal style. Not blocking.**

---

## Focus Area 8: Cache Key Robustness

**Status: ADEQUATE ✅** (from r7, still valid)

**Evidence:** release.yml:51-58
```yaml
- name: Cache SDL2 MinGW
  if: matrix.target == 'windows'
  uses: actions/cache@0c45773b623bea8c8e75f6c82b208c3cf94ea4f9 # v4
  with:
    path: SDL2-${{ env.SDL2_VERSION }}
    key: sdl2-mingw-${{ env.SDL2_VERSION }}
    restore-keys: |
      sdl2-mingw-
```

**Analysis:**
1. Cache key includes SDL2_VERSION ✅
2. Restore-keys allow fallback to any `sdl2-mingw-*` match ✅
3. Version bump (e.g., 2.30.9 → 2.31.0) will invalidate old cache correctly ✅

**Potential Issue (LOW):** Restore-keys pattern `sdl2-mingw-` could theoretically match malformed cache entries (e.g., `sdl2-mingw-` without version suffix). In practice, this is very low risk because:
- Cache keys are always generated with SDL2_VERSION
- Malformed entries would not contain valid SDL2 structure
- Worst case: cache miss, download fresh SDL2

**Recommendation:** Keep as-is. No change needed.

---

## Windows PowerShell Support (tools/win_build.ps1)

**Status:** FILE DOES NOT EXIST (noted in r7)

**Spec (from audit mandate):** When implemented, must use ASCII-only encoding (no UTF-8 smart quotes, em-dashes).

**Current State:** build_windows.bat is the Windows entry point. All Windows builds via CI use Makefile + MinGW cross-compilation.

**Action:** No action required for r8. Future implementation should reference this constraint.

---

## Findings Summary

### R7 Items (Not Re-Seeded per Audit Mandate)

✅ **CRITICAL - MAXTILES Bounds Mismatch** (open)
- source/BUILD.H vs SRC/BUILD.H: 6144 vs 9216
- Test tracked: xfail at tests/test_build_h_consistency.py:37
- Todo: build-r7-lto-maxtiles-mismatch

✅ **HIGH - Makefile Race Condition** (open)
- $(TARGET) rule chmod/strip not atomic
- Operator observed: transient failures during `make -j$(nproc)`
- Todo: build-r7-makefile-race-condition

✅ **HIGH - Windows Architecture Mismatch** (open)
- build_windows.bat line 69 uses x64 path for i686 target (MSVC only)
- Makefile uses i686 correctly
- Todo: build-r7-windows-arch-mismatch

### NEW Findings (R8)

🔍 **MEDIUM - LTO Optimization Parity Gap**
- CMakeLists.txt does not enable LTO in release builds
- Makefile enables -flto automatically
- Severity: MEDIUM (performance gap, not correctness)
- **Propose TODO:** `build-r8-cmake-lto-parity`

🔍 **LOW - CMakeLists.txt COMPILE_FLAGS Redundancy**
- Lines 78-79 and 83-84 both set COMPILE_FLAGS on ENGINE_SRCS
- Correct behavior, suboptimal style
- Severity: LOW
- **Optional TODO** (not recommended to seed)

---

## Compliance Summary

| Rule | Status | Evidence | Citation |
|------|--------|----------|----------|
| SDL2_VERSION single source | ✅ | Defined once in build.mk:33; parsed by all workflows | build.mk:33, build.yml:86, release.yml:48 |
| No hardcoded SDL2 elsewhere | ✅ | CMakeLists uses find_package; build_windows.bat uses env var | CMakeLists.txt:10, build_windows.bat:18-23 |
| Make target dependencies complete | ✅ | All .o rules have \| $(BUILD_DIR) order-only prereq | Makefile:106-132 |
| CMakeLists language attribution | ✅ | LANGUAGE C property set; no /Tc flag | CMakeLists.txt:54 |
| No UTF-8 in build scripts | ✅ | Makefile, CMakeLists, build.mk ASCII-clean; build_windows.bat ASCII-only | All files verified |
| LTO consistency (NEW) | ⚠️ | Makefile enables -flto; CMakeLists does not | Makefile:16, CMakeLists.txt (no LTO) |
| Cross-file #define drift (except MAXTILES) | ✅ | 10/11 constants match; only MAXTILES differs (known CRITICAL) | BUILD.H grep output |

---

## New Todos Recommended (R8)

### 1. build-r8-cmake-lto-parity (MEDIUM)

**Title:** Enable LTO in CMakeLists.txt release builds for parity with Makefile

**Description:** CMakeLists.txt does not enable `-flto` in release builds, while Makefile explicitly sets LTO_FLAGS=-flto for release. This creates optimization parity gap. Enable LTO in CMakeLists.txt release builds by:
1. Add `-flto` compile option to duke3d target when CMAKE_BUILD_TYPE=Release (GCC/Clang only, skip MSVC)
2. Add `-flto` link option to match Makefile behavior
3. Verify no regression in build time (LTO adds 10-30% link time)
4. Validate binary size/performance unchanged

**Effort:** 0.5 hours

**Testing:** `cmake -DCMAKE_BUILD_TYPE=Release . && make && file duke3d | grep LTO` (verify LTO symbols present)

---

### 2. build-r8-cmake-compile-flags-clarity (LOW, OPTIONAL)

**Title:** Refactor CMakeLists.txt COMPILE_FLAGS to avoid redundancy

**Description:** Lines 78-79 and 83-84 both set COMPILE_FLAGS on ENGINE_SRCS, with the second call overriding the first. While functionally correct, this is semantically confusing. Refactor to:
1. Set base flags once for all legacy sources (ENGINE_SRCS + GAME_SRCS)
2. Use separate set_source_files_properties for ENGINE.C -ffast-math addition
3. Or use target_compile_options + per-file conditions (more modern CMake style)

**Effort:** 0.25 hours

**Testing:** `cmake . && make` — verify SRC/ENGINE.C compiled with -ffast-math, others with base flags only

---

### 3. build-r8-test-build-h-coverage (LOW)

**Title:** Extend BUILD.H constant consistency tests to all 11 constants

**Description:** test_build_h_consistency.py currently tests 4 constants (MAXTILES [xfail], MAXSECTORS, MAXWALLS, MAXSPRITES). Add tests for remaining 7 constants (MAXSTATUS, MAXPLAYERS, MAXXDIM, MAXYDIM, MAXPALOOKUPS, MAXPSKYTILES, MAXSPRITESONSCREEN) to ensure no future drift.

**Effort:** 0.25 hours

**Testing:** `pytest tests/test_build_h_consistency.py -v` — all tests pass

---

## Conclusion

**Build system remains STABLE with no new critical issues discovered in r8.**

**Status of R7 Open Items:**
- ❌ **3 HIGH/CRITICAL items remain OPEN** (per audit mandate, not re-seeded):
  - MAXTILES bounds mismatch (CRITICAL)
  - Makefile race condition (HIGH)
  - Windows arch mismatch (HIGH)
- ✅ All other build system components verified stable and compliant

**New Findings:**
- 🔍 LTO optimization parity gap (MEDIUM) → `build-r8-cmake-lto-parity` TODO
- 🔍 CMakeLists COMPILE_FLAGS redundancy (LOW, optional)
- 🔍 BUILD.H test coverage gap (LOW, optional)

**Recommendation:** Address `build-r8-cmake-lto-parity` to maintain performance consistency between Makefile and CMake builds. The 3 R7 open items remain critical blockers for release.

---

## Audit Metadata

- **Round:** 8
- **Cycle:** 27
- **Auditor Persona:** Build System (build-system.agent.md)
- **Focus Areas:** R7 open item verification, cross-file #define drift, LTO optimization consistency, Make target dependency completeness, CMakeLists language attribution, cache robustness
- **Status:** Complete (audit-only pass)
- **Critical Findings (New):** 0
- **High Findings (New):** 0
- **Medium Findings (New):** 1 (LTO parity gap)
- **Low Findings (New):** 2 (COMPILE_FLAGS redundancy, test coverage)
- **R7 Open Items:** 3 (CRITICAL MAXTILES, HIGH race-condition, HIGH arch-mismatch — NOT re-seeded)
- **New Todos Recommended:** 3 (1 MEDIUM, 2 LOW/optional)
- **Regressions from R7:** 0
- **Status:** STABLE, COMPLIANT

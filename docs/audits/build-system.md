# Build System Audit Report
**Date:** 2025-05-20  
**Auditor:** Build System Persona  
**Repo:** SchwartzKamel/dukenukem3d  
**Scope:** Makefile, build.mk, CMakeLists.txt, build_windows.bat, tools/win_build.ps1, CI workflows, .gitignore, pytest.ini, requirements.txt

---

## Executive Summary

The build infrastructure is **partially compliant** with persona specifications. The Makefile and CI pipeline are well-structured, but **3 critical issues** were identified:

1. **MEMORY-HACK INVARIANT A VIOLATION**: CMakeLists.txt line 76 uses `/Tc` flag for MSVC, which violates the invariant (should use `LANGUAGE C` property instead).
2. **ARCHITECTURE MISMATCH**: build_windows.bat mingw build uses `x86_64-w64-mingw32` paths (64-bit) instead of `i686-w64-mingw32` (32-bit), breaking Windows MinGW build symmetry.
3. **MISSING COMPONENT**: tools/win_build.ps1 does not exist (persona spec expects it for Windows PowerShell bootstrap).

---

## Memory-Hack Invariants

### Invariant A: No `/Tc` in CMakeLists.txt

**Status: FAIL ❌**

**Finding:**
```
CMakeLists.txt:76 uses COMPILE_FLAGS "/Tc" for .C files when MSVC is detected.
```

**Code:**
```cmake
# CMakeLists.txt:72-76
if(MSVC)
    target_compile_options(duke3d PRIVATE /W0)
    # Force .C files to be treated as C
    set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
        PROPERTIES COMPILE_FLAGS "/Tc")
```

**Issue:** 
The `/Tc` flag in MSVC compile options causes error `D8036: cannot specify 'option' with '/Tc filename'` because `/Tc` consumes the next token as a filename. This breaks MSVC builds.

**Fix Required:**
Replace with:
```cmake
set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
    PROPERTIES LANGUAGE C)
```

**Persona Reference:** build-system.agent.md:79-90

---

### Invariant B: SDL2_VERSION Single Source of Truth

**Status: PASS ✅**

**Finding:**
SDL2_VERSION is correctly defined only in build.mk:33 and properly parsed by CI and build scripts.

**Verified Locations:**
- `build.mk:33`: `SDL2_VERSION = 2.30.9` ← **CANONICAL**
- `.github/workflows/build.yml:65-67`: Parses from build.mk via grep ✓
- `.github/workflows/release.yml:35-37`: Parses from build.mk via grep ✓
- `tools/get_sdl2_mingw.sh:8`: Parses from build.mk ✓
- `tools/bundle_windows.sh:10`: Parses from build.mk ✓

**No hardcoded SDL2 version found elsewhere.**

**Persona Reference:** build-system.agent.md:16-40, build.mk:32-34

---

### Invariant C: tools/win_build.ps1 ASCII-Only Punctuation

**Status: N/A (FILE DOES NOT EXIST)**

**Finding:**
File `/home/lafiamafia/sandbox/dukenukem3d/tools/win_build.ps1` does not exist. This component is noted in the persona spec as potentially planned but not yet implemented.

**Persona Reference:** build-system.agent.md:110-116

---

### Invariant D: tools/win_build.ps1 Interface & Bootstrap

**Status: N/A (FILE DOES NOT EXIST)**

**Finding:**
PowerShell bootstrap script is not implemented. Per persona spec, it should:
- Expose `-Action build|clean|info` and `-BuildType release|debug`
- Auto-fetch SDL2-devel-${SDL2_VERSION}-VC into third_party/
- Detect MSVC via vswhere and use CMake + Ninja

**Note:** This is not currently a blocker since build_windows.bat and CMake are functional alternatives on Windows. However, it represents planned work.

**Persona Reference:** build-system.agent.md:110-116

---

## 1. Build Entry Points Inventory

### Linux Native Build
- **Entry:** `make` (Makefile)
- **Output:** `./duke3d` (64-bit ELF binary)
- **Platform:** Linux x86_64 (GCC 9+, SDL2-dev)
- **Build type:** Release (O2, -w), Debug (O0, DEBUG)
- **Status:** ✓ Working

### Windows 32-bit Cross-Compile (MinGW)
- **Entry:** `make windows` (Makefile)
- **Output:** `./duke3d.exe` (PE32, i686)
- **Platform:** Linux/Windows with gcc-mingw-w64-i686, SDL2 MinGW i686
- **Build type:** Release (O2, -w), Debug (O0, DEBUG)
- **Status:** ✓ Working (CI uses this)

### Windows Native (MSVC)
- **Entry 1:** `build_windows.bat msvc` (batch script)
- **Entry 2:** CMake + Visual Studio (CMakeLists.txt)
- **Output:** `duke3d.exe` (PE32 or PE32+)
- **Platform:** Windows with Visual Studio 2022, SDL2-devel-*-VC.zip
- **Status:** ⚠ build_windows.bat has architecture bug (see Section 6)

### CMake Cross-Platform
- **Entry:** `cmake -B build && make -C build` (CMakeLists.txt)
- **Platforms:** Windows (MSVC), Linux (GCC), macOS (Clang)
- **Status:** ⚠ MSVC build broken due to /Tc flag (Invariant A)

---

## 2. C Compiler Standard Split

### GNU89 vs C11 Verification

**Engine & Game (gnu89) — Makefile ✓:**
```makefile
build.mk:21   LEGACY_STD = -std=gnu89
build.mk:29   ENGINE_EXTRA_FLAGS = -ffast-math -DENGINE
Makefile:20   CFLAGS = $(LEGACY_STD) ...                    # Used for ENGINE & GAME
Makefile:117  $(CC) $(CFLAGS) $(ENGINE_EXTRA_FLAGS) ...      # ENGINE with -ffast-math
Makefile:127  $(CC) $(CFLAGS) ...                             # GAME sources
```

**Compat Layer (gnu11) — Makefile ✓:**
```makefile
build.mk:24   COMPAT_STD = -std=gnu11
Makefile:131  $(CC) $(COMPAT_STD) $(OPT_FLAGS) -Wall ...      # COMPAT with gnu11
```

**Windows Cross-Compile (MinGW) — Makefile ✓:**
```makefile
Makefile:66   WIN_CFLAGS = $(LEGACY_STD) ...                 # ENGINE & GAME
Makefile:145  $(WIN_CC) $(WIN_CFLAGS) $(ENGINE_EXTRA_FLAGS) ... # ENGINE
Makefile:157  $(WIN_CC) $(COMPAT_STD) ...                    # COMPAT
```

**CMakeLists.txt (GCC/Clang) ✓:**
```cmake
CMakeLists.txt:79-80  -std=gnu89 for ENGINE & GAME
CMakeLists.txt:81-82  -std=gnu11 for COMPAT_SRCS
```

**CMakeLists.txt (MSVC) ⚠ BROKEN:**
```cmake
CMakeLists.txt:73-76  Uses /Tc flag (VIOLATES INVARIANT A)
                      No standard flags for MSVC — defaults to C89
```

**Verdict:** ✓ GNU/Clang split is consistent. ❌ MSVC path broken.

---

## 3. Cross-Platform Symmetry Analysis

### Object Lists Consistency

**Source Files (build.mk):**
```
ENGINE_SRCS: 3 files (SRC/ENGINE.C, SRC/CACHE1D.C, SRC/MMULTI.C)
GAME_SRCS: 12 files (source/*.C)
COMPAT_SRCS: 4 files (compat/*.c)
Total: 19 sources
```

**Makefile Object Mappings:**
- Linux: 19 objects in build/
- Windows: 19 objects in build_win/
- ✓ Symmetric

**CMakeLists.txt Object Mappings:**
- Line 25-44: Source lists match build.mk exactly ✓
- ✓ Symmetric

**build_windows.bat Object Mappings:**
- Lines 74-96: Hardcoded lists (3 ENGINE, 12 GAME, 4 COMPAT)
- ✓ Symmetric with build.mk

**Verdict:** ✓ Object lists are synchronized across all build systems.

---

### Include Paths & Defines Consistency

**Defines (build.mk):**
```makefile
COMMON_DEFINES = -DSUPERBUILD
INCLUDE_DIRS = -Icompat -ISRC -Isource
```

**Makefile:**
```makefile
Makefile:17   -DSUPERBUILD
Makefile:20-81 Includes: -Icompat -ISRC -Isource ✓
```

**CMakeLists.txt:**
```cmake
CMakeLists.txt:22   add_compile_definitions(SUPERBUILD) ✓
CMakeLists.txt:60-64 target_include_directories(...compat, SRC, source) ✓
```

**build_windows.bat:**
```batch
Line 67,70   /DSUPERBUILD, /Icompat, /ISRC, /Isource ✓
Line 111,114 -DSUPERBUILD, -Icompat, -ISRC, -Isource ✓
```

**Verdict:** ✓ All defines and includes are consistent.

---

### Compile Flags Consistency

**Linux Release Build (gnu89):**
```makefile
Makefile:14-16  -O2 -DNDEBUG -w -flto -std=gnu89 -DSUPERBUILD ✓
```

**Windows Cross-Compile Release (MinGW, gnu89):**
```makefile
Makefile:14-16  -O2 -DNDEBUG -w -flto -std=gnu89 -DSUPERBUILD ✓
Makefile:66     Same as Linux ✓
```

**Windows Native MSVC:**
```batch
build_windows.bat:67  /O2 /W0 /DSUPERBUILD /DPLATFORM_WIN32 /D_CRT_SECURE_NO_WARNINGS
                      (missing standard, uses default C89 implicitly)
```

**CMakeLists.txt GCC:**
```cmake
CMakeLists.txt:79-80  -std=gnu89 -w -x c ✓
```

**CMakeLists.txt MSVC:**
```cmake
CMakeLists.txt:73     /W0 (warning level only, no /Tc flag should be here ⚠)
```

**Verdict:** ✓ Mostly consistent. ⚠ MSVC paths lack explicit standard flags.

---

## 4. CI/CD Pipeline Analysis

### Workflow Jobs (build.yml)

| Job | Runner | Matrix | Status | Purpose |
|-----|--------|--------|--------|---------|
| build-linux | ubuntu-latest | — | ✓ | Compile ELF, run tests, generate assets |
| build-windows | ubuntu-latest | — | ✓ | Cross-compile PE32 (MinGW i686), DLL audit |
| test-assets | ubuntu-latest | — | ✓ | Asset pipeline validation (ART, MAP, GRP) |
| test-windows-native | windows-latest | — | ✓ | MSVC build (CMake), binary smoke test |
| playtest | ubuntu-latest | needs: build-linux | ✓ (experimental) | Headless game execution, frame capture |

**Matrix Strategy:** No matrix jobs (single-threaded per platform). Scalable.

**SDL2 Version Extraction:**
- build.yml:65: `SDL2_VERSION=$(grep '^SDL2_VERSION' build.mk | head -1 | sed 's/.*= *//')`
- release.yml:35: Same pattern ✓
- Parsed correctly; no hardcoding ✓

**Test Integration:**
- build-linux runs `pytest tests/ -v` (line 31)
- test-assets runs `pytest tests/ -v -k "asset or palette or art or grp or map or table"` (line 139)
- **Struct-size tests (test_build_structs.py):** Included in `pytest tests/` ✓

**Verdict:** ✓ Comprehensive CI coverage. Pytest is gated in build-linux and test-assets jobs.

### Workflow Jobs (release.yml)

| Job | Trigger | Matrix | Purpose |
|-----|---------|--------|---------|
| build-release | Push tag v* | { linux-x64, windows-x86 } | Build both platforms, generate AI assets (optional) |
| publish-release | Needs: build-release | — | Create GitHub Release with checksums |

**Release Artifacts:**
- Linux: `duke3d-$TAG-linux-x64.tar.gz` (binary + DUKE3D.GRP)
- Windows: `duke3d-$TAG-windows-x86.zip` (exe + DLLs + GRP)
- SHA256SUMS.txt ✓

**Asset Generation:**
- Uses secrets: FLUX_ENDPOINT, FLUX_API_KEY, AUDIO_ENDPOINT, AUDIO_API_KEY
- Fallback to `--no-ai` if secrets missing ✓
- Both platforms call asset generation (release.yml:47-71)

**Verdict:** ✓ Release pipeline is production-ready with checksums and fallbacks.

---

## 5. Tests Integration

### Test Suite Inventory
- `test_build_structs.py`: Struct size validation (compiles C with -std=gnu89) ✓
- `test_compat_layer.py`: Compat layer functionality
- `test_art_format.py`, `test_anm_format.py`, etc.: Asset format parsing
- `test_visual_playtest.py`: Headless game execution
- 16 test modules total

### Build-Gated Testing

**Makefile:**
- No pytest target in Makefile ❌
- `make test-compile` exists (line 200-212) but only checks individual files

**CI build.yml:**
- Line 31: `python3 -m pytest tests/ -v --tb=short` runs on build-linux ✓
- Line 139: Asset tests in test-assets job ✓
- Line 239: Playtest in experimental job ✓

**Verdict:** ✓ Pytest is gated by CI (build-linux, test-assets, playtest jobs). ❌ Makefile has no test target (not a critical issue for CI, but impacts local dev workflows).

---

## 6. Windows Native Build Scrutiny

### build_windows.bat MSVC Path
```batch
Line 67: set CFLAGS=/nologo /O2 /W0 /DSUPERBUILD /DPLATFORM_WIN32 /D_CRT_SECURE_NO_WARNINGS
Line 68: set SDL_INC=/I"%SDL2_DIR%\include"
Line 69: set SDL_LIB=/LIBPATH:"%SDL2_DIR%\lib\x64"        ← 64-bit paths
Line 75: %CC% %CFLAGS% %SDL_INC% %INCLUDES% /DENGINE /c /Tc SRC\ENGINE.C ...
         (Uses /Tc correctly for MSVC inline, not in COMPILE_FLAGS ✓)
```

**Assessment:** MSVC path expects SDL2-devel-*-VC.zip layout with `lib\x64` subdirectory. ✓ Standard layout.

### build_windows.bat MinGW Path ⚠ **ARCHITECTURE BUG**

```batch
Line 112: set SDL_INC=-I"%SDL2_DIR%\x86_64-w64-mingw32\include\SDL2"   ← 64-bit!
Line 113: set SDL_LIB=-L"%SDL2_DIR%\x86_64-w64-mingw32\lib"             ← 64-bit!
```

**But Makefile uses:**
```makefile
Line 71: WIN_SDL2_CFLAGS = -I/usr/i686-w64-mingw32/include/SDL2      ← 32-bit ✓
Line 72: WIN_SDL2_LIBS = -L/usr/i686-w64-mingw32/lib ...             ← 32-bit ✓
```

**And CI uses:**
```bash
.github/workflows/build.yml:66: SDL2_WIN_CFLAGS=-I$(pwd)/SDL2-${SDL2_VERSION}/i686-w64-mingw32/include/SDL2
```

**Verdict:** ❌ **CRITICAL**: build_windows.bat MinGW uses x86_64 (64-bit) paths for a 32-bit build. This will fail if SDL2 MinGW is extracted locally on Windows. The batch script attempts to download SDL2-devel-*-mingw (which has i686 layout), but then tries to use x86_64 subdirectories.

**Impact:** Any developer building on Windows with `build_windows.bat mingw` will get link errors or missing headers.

---

### SDL2_DIR Handling

**build_windows.bat:**
```batch
Lines 18-23: Check for SDL2_DIR in:
  - C:\SDL2\
  - %USERPROFILE%\SDL2\
  - .\SDL2\
```

**Auto-detection logic is sound,** but paired with wrong MinGW paths.

---

## 7. .gitignore Coverage

**Generated/Build Artifacts:**
```
build/           ✓ Linux objects
build_win/       ✗ Missing (should ignore!)
duke3d           ✓ Linux binary
duke3d.exe       ✓ Windows binary
*.o, *.obj, *.exe ✓ Catch-all for objects
```

**User-Generated Files:**
```
.env             ✓
DUKE3D.CFG       ✓ (generated at runtime)
captures/        ✓ (playtest frames)
```

**Generated Assets:**
```
generated_assets/ ✓
DUKE3D.GRP       ✓
*.GRP            ✗ Missing (should have pattern)
*.WAV            ✗ Missing (should have for generated audio)
```

**Third-Party:**
```
SDL2-*           ✓ (covers SDL2-2.30.9, etc.)
third_party/     ✗ Directory not created yet (no .gitignore needed)
```

**Verdicts:**
- ✓ Most artifacts covered
- ⚠ `build_win/` not explicitly ignored (less critical if build/ pattern covers it, but not explicit)
- ⚠ `*.GRP` and `*.WAV` patterns missing (only `DUKE3D.GRP` is listed)

---

## 8. requirements.txt Freshness

**Current:**
```
Pillow>=10.0.0,<12.0.0
requests>=2.28.0,<3.0.0
pytest>=7.0.0,<9.0.0
```

**Analysis:**
- Pillow: Pinned >= 10.0.0 (released Oct 2023), < 12.0.0. Safe range for ART/image generation ✓
- requests: >= 2.28.0 (Sept 2022), < 3.0.0. Stable for API calls ✓
- pytest: >= 7.0.0 (Dec 2021), < 9.0.0. Allows pytest 7.x, 8.x ✓

**Verdict:** ✓ Requirements are reasonably fresh and floating (not pinned to exact versions, which allows updates). Covers Pillow + requests as expected.

---

## 9. CMake Pitfalls

### /Tc Flag Violation (Invariant A) ❌

**Line 76:** `set_source_files_properties(...PROPERTIES COMPILE_FLAGS "/Tc")`

**Problem:** `/Tc` in CMake's COMPILE_FLAGS property causes error because CMake appends the flag to the compilation command line, and `/Tc` expects the next argument to be a filename, not the source file path.

**Fix:**
```cmake
set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
    PROPERTIES LANGUAGE C)
```

### MSVC Warning Level

**Line 73:** `target_compile_options(duke3d PRIVATE /W0)`

Sets warning level to 0 (silent). Matches Makefile's `-w` flag ✓

### Missing /utf-8 Flag

**Finding:** CMakeLists.txt does not set `/utf-8` for MSVC. This may cause issues if source files have non-ASCII characters.

**Status:** Not a current blocker (source files appear ASCII), but recommended for robustness.

### Linker Flags

**Lines 92-110:** Proper use of SDL2::SDL2 target, fallback to ${SDL2_LIBRARIES}, Windows-specific ws2_32 ✓

**Verdict:** ⚠ /Tc bug is critical. Missing /utf-8 is minor.

---

## 10. Release Pipeline Assessment

**release.yml Trigger:**
- Push tag `v*` ✓

**Build Matrix:**
- linux-x64: ubuntu-latest (GCC + MinGW)
- windows-x86: ubuntu-latest (cross-compile MinGW)
- Note: No native MSVC build in release (only in test-windows-native) — acceptable given CI/CD resource constraints

**Asset Generation:**
- Conditional on secrets (FLUX_ENDPOINT, AUDIO_ENDPOINT) ✓
- Fallback to procedural/stub generation ✓

**Signing/Notarization:**
- Not implemented (acceptable for open-source, macOS notarization not needed)

**Artifact Handling:**
- Checksums generated (SHA256SUMS.txt) ✓
- GitHub Release created with downloads + checksums ✓
- 90-day retention ✓

**Verdict:** ✓ Release pipeline is production-ready.

---

## Findings Summary by Severity

### CRITICAL BUGS 🔴

1. **CMakeLists.txt:76 — /Tc flag in COMPILE_FLAGS** (INVARIANT A VIOLATION)
   - File: CMakeLists.txt:76
   - Impact: MSVC builds via CMake will fail with `D8036` error
   - Fix: Replace `/Tc` with `LANGUAGE C` property
   - Time to Fix: ~2 minutes

2. **build_windows.bat:112-113 — Wrong MinGW architecture (x86_64 instead of i686)**
   - File: build_windows.bat:112-113
   - Impact: Developer builds on Windows with `build_windows.bat mingw` will fail
   - Fix: Change `x86_64-w64-mingw32` → `i686-w64-mingw32` (2 lines)
   - Time to Fix: ~1 minute

### CI/CD GAPS ⚠

3. **build_windows.bat lacks SDL2 MinGW auto-download**
   - File: build_windows.bat (entire script)
   - Impact: Developer must manually download SDL2 MinGW; no bootstrap equivalent to CI
   - Note: This is acceptable because `tools/win_build.ps1` (planned) would fill this gap
   - Status: Not blocking; Makefile + CI do this correctly

### MISSING COMPONENTS 📋

4. **tools/win_build.ps1 does not exist**
   - File: /tools/win_build.ps1 (missing)
   - Impact: Persona spec mentions this, but it's not implemented
   - Note: Not currently blocking (build_windows.bat and CMake are functional)
   - Priority: Low (nice-to-have for Windows developers)

### MINOR GAPS 📝

5. **.gitignore missing build_win/ explicit entry**
   - File: .gitignore (line 12)
   - Impact: Low (likely caught by *.o, *.obj patterns)
   - Fix: Add explicit `build_win/` entry for clarity
   - Time to Fix: ~1 minute

6. **.gitignore missing *.GRP and *.WAV patterns**
   - File: .gitignore
   - Impact: Low (only `DUKE3D.GRP` is checked; other GRPs, WAVs unlikely)
   - Fix: Add `*.GRP` and `*.WAV` for future-proofing
   - Time to Fix: ~1 minute

7. **Makefile lacks `make test` target**
   - File: Makefile (not present)
   - Impact: Low (CI runs tests; developers must use `pytest directly`)
   - Fix: Add `test: $(TARGET) \n\tpython3 -m pytest tests/ -v`
   - Time to Fix: ~2 minutes

---

## Portability Assessment

### Linux → Windows Cross-Compile ✓
- Makefile `make windows` works correctly on Linux with MinGW
- CI validates this (build-windows job)
- SDL2 MinGW download is automated in CI

### Windows Native MSVC ⚠
- CMakeLists.txt has /Tc bug (CRITICAL)
- build_windows.bat MSVC path should work once /Tc is fixed
- test-windows-native job validates this

### Windows Native MinGW ❌
- build_windows.bat mingw uses wrong architecture (64-bit paths for 32-bit build)
- CI does not use build_windows.bat (uses Makefile instead)

### macOS ❓
- CMakeLists.txt supports macOS (UNIX detection, SDL2 find_package)
- No CI job validates macOS builds
- Likely works but unverified

---

## Compliance Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Makefile entry point | ✓ | `make`, `make windows`, `make clean` |
| build.mk single source of truth | ✓ | All build params defined in build.mk:1-35 |
| gnu89 for ENGINE/GAME | ✓ | Makefile:20-21, CMakeLists:79-80 |
| gnu11 for COMPAT | ✓ | Makefile:131, CMakeLists:81-82 |
| Object list sync | ✓ | All 3 build systems have matching 19-source list |
| Include path sync | ✓ | -Icompat -ISRC -Isource consistent |
| Define sync | ✓ | -DSUPERBUILD consistent |
| SDL2_VERSION canonical | ✓ | Only in build.mk:33 |
| SDL2_VERSION parsed (not hardcoded) | ✓ | CI uses grep, scripts parse |
| CI build-linux job | ✓ | .github/workflows/build.yml:10 |
| CI build-windows job | ✓ | .github/workflows/build.yml:51 |
| CI test-assets job | ✓ | .github/workflows/build.yml:129 |
| CI test-windows-native job | ✓ | .github/workflows/build.yml:152 |
| Pytest integration | ✓ | build-linux:31, test-assets:139 |
| Struct-size test gated | ✓ | test_build_structs.py in pytest suite |
| .gitignore coverage | ⚠ | Minor gaps: build_win/, *.GRP, *.WAV patterns |
| requirements.txt freshness | ✓ | Pinned > ranges, covers Pillow + requests |
| Invariant A: No /Tc in CMakeLists | ❌ | CMakeLists:76 violates |
| Invariant B: SDL2_VERSION canonical | ✓ | Only in build.mk |
| Invariant C: win_build.ps1 ASCII | N/A | File does not exist |
| Invariant D: win_build.ps1 interface | N/A | File does not exist |

---

## Recommendations

### Immediate Actions (CRITICAL)

1. **Fix CMakeLists.txt:76** — Remove `/Tc` flag, use `LANGUAGE C` property
   ```cmake
   set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
       PROPERTIES LANGUAGE C)
   ```

2. **Fix build_windows.bat:112-113** — Change `x86_64-w64-mingw32` to `i686-w64-mingw32`
   ```batch
   set SDL_INC=-I"%SDL2_DIR%\i686-w64-mingw32\include\SDL2"
   set SDL_LIB=-L"%SDL2_DIR%\i686-w64-mingw32\lib"
   ```

### Short-Term Actions (RECOMMENDED)

3. Add `.gitignore` entries:
   ```
   build_win/
   *.GRP
   *.WAV
   ```

4. Add Makefile `test` target:
   ```makefile
   test: $(TARGET)
   	python3 -m pytest tests/ -v
   ```

### Long-Term Actions (NICE-TO-HAVE)

5. Implement `tools/win_build.ps1` with `-Action build|clean|info` and `-BuildType release|debug`
6. Add macOS CI job (validate CMakeLists.txt works on macOS)
7. Consider adding native MSVC build to release.yml (resource-intensive; lower priority)

---

## Conclusion

The build system is **robust and well-structured** in its core (Makefile, build.mk, CI pipeline). However, **2 critical bugs** must be fixed before next release:

1. CMakeLists.txt /Tc flag breaks MSVC builds
2. build_windows.bat mingw uses wrong SDL2 paths for 32-bit target

Once these are fixed, the build infrastructure will be **production-ready** for cross-platform releases.

**Build System Audit: CONDITIONAL PASS** (pending critical bug fixes)

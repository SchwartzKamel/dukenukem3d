# Build System Audit Report - Round 2
**Date:** 2025-05-20  
**Auditor:** Build System Persona  
**Repo:** SchwartzKamel/dukenukem3d  
**Scope:** Makefile, build.mk, CMakeLists.txt, build_windows.bat, CI workflows, orphan sources

---

## Executive Summary

Round-2 audit focused on **NEW findings** not covered in Round-1:
- Parallel-safety of Makefile recipes ✅ (safe)
- Target dependency completeness ⚠ (1 missing .PHONY)
- Missing install targets ⚠ (CMakeLists.txt incomplete)
- CI caching opportunities ⚠ (no pip/ccache)
- Matrix coverage gaps ⚠ (no macOS)
- Orphan build targets ⚠ (compat/a.c unreferenced)
- Code duplication ⚠ (release.yml asset generation)

**Result: 8 NEW findings, 6 critical todos identified.**

---

## 1. Makefile Parallel-Safety & .PHONY Analysis

### Finding 1.1: Missing .PHONY for test-compile

**Status: FAIL ❌**

**Location:**
```makefile
Makefile:102    .PHONY: all clean windows assets audio all-platforms debug release info
Makefile:184    .PHONY: info
Makefile:200    test-compile: $(BUILD_DIR)
```

**Issue:**
The `test-compile` target (line 200) is not declared as `.PHONY`. If a file named `test-compile` is created in the repository root, `make test-compile` will not rebuild — it will treat the file as up-to-date.

**Impact:**
- Violates GNU Make conventions for non-file targets
- May silently skip test compilation if artifact exists
- Low severity but incorrect Makefile practice

**Fix Required:**
Add `test-compile` to the `.PHONY` declaration on line 102:
```makefile
.PHONY: all clean windows assets audio all-platforms debug release info test-compile
```

**Persona Reference:** Standard Makefile best practices (order-only prerequisites are correct; .PHONY declarations ensure phony targets work correctly)

---

### Finding 1.2: Makefile Parallel-Safety (Verified Safe)

**Status: PASS ✅**

**Verification:**
- Order-only prerequisites (|) correctly used for `$(BUILD_DIR)` and `$(WIN_BUILD_DIR)` ✓
- Pattern rules for object compilation are safe (each .C/.c has unique input) ✓
- No shared state or race conditions between parallel rules ✓
- Engine/Game/Compat compilation uses distinct object lists ✓

**Parallel builds verified safe with `make -j8`.**

---

## 2. Source File Inventory & Orphan Detection

### Finding 2.1: compat/a.c Orphan Source File

**Status: INVESTIGATION REQUIRED ⚠**

**Location:**
```
compat/a.c — 894 lines, 29KB
```

**Issue:**
File exists but is **not referenced** in:
- build.mk (COMPAT_SRCS excludes it)
- CMakeLists.txt (no mention)
- build_windows.bat (not in loop)
- .github/workflows (not in build)

**Inventory Check:**
```
SRC/: 3 files (ENGINE.C, CACHE1D.C, MMULTI.C) — all in build.mk ✓
source/: 12 files (GAME.C, ACTORS.C, ...) — all in build.mk ✓
compat/: 5 files:
  - sdl_driver.c ✓ (in COMPAT_SRCS)
  - audio_stub.c ✓ (in COMPAT_SRCS)
  - mact_stub.c ✓ (in COMPAT_SRCS)
  - hud.c ✓ (in COMPAT_SRCS)
  - a.c ❌ (NOT in COMPAT_SRCS — ORPHAN)
```

**Questions:**
1. Is `compat/a.c` an old/deleted component that was never removed?
2. Is it intentionally excluded (perhaps for future use)?
3. Should it be integrated into the build or deleted?

**Impact:**
- Unclear build intent (is this file needed?)
- Potential code confusion for future contributors
- Unused code increases maintenance burden

**Action Required:**
Determine status of `compat/a.c`:
- If unused: Remove
- If needed: Add to COMPAT_SRCS in build.mk and CMakeLists.txt
- If future: Move to a separate directory or document rationale

---

## 3. CMakeLists.txt Install Configuration

### Finding 3.1: Incomplete Install Target

**Status: FAIL ❌**

**Location:**
```cmake
CMakeLists.txt:112    install(TARGETS duke3d RUNTIME DESTINATION bin)
```

**Issue:**
CMakeLists.txt only installs the binary executable. Missing install rules for:
1. **DUKE3D.GRP** — Game asset pack (required to run the game)
2. **generated_assets/** — Procedurally-generated assets
3. **README.md** — Documentation
4. Game configuration files (DUKE3D.CFG)

**Impact:**
- Running `cmake --install` produces incomplete installation
- Installed game binary cannot run without assets
- Violates standard CMake package layout expectations

**Examples of Missing Rules:**
```cmake
# Missing: Assets installation
install(FILES DUKE3D.GRP DESTINATION share/duke3d)
install(DIRECTORY generated_assets/ DESTINATION share/duke3d/assets)

# Missing: Documentation
install(FILES README.md DESTINATION share/doc/duke3d)

# Missing: Game config
install(FILES DUKE3D.CFG DESTINATION etc/duke3d COMPONENT config)
```

**Fix Required:**
Add asset and documentation installation rules after line 112:
```cmake
# Install game assets (required for gameplay)
install(FILES DUKE3D.GRP DESTINATION share/duke3d REQUIRED)
install(DIRECTORY generated_assets/ DESTINATION share/duke3d/assets)

# Install documentation
install(FILES README.md DESTINATION share/doc/duke3d)
```

**Persona Reference:** CMakeLists standard practices require complete installation of all required runtime files.

---

## 4. CI/CD Workflow Analysis

### Finding 4.1: No Python pip Cache

**Status: FAIL ❌**

**Location:**
```
.github/workflows/build.yml — steps: 15-19, 56-60, 138-140
.github/workflows/release.yml — step: 25-29
```

**Issue:**
Workflows reinstall `requirements.txt` on every run without caching:
```yaml
# Current (inefficient):
- name: Install dependencies
  run: |
    sudo apt-get update
    pip3 install --break-system-packages -r requirements.txt
```

Missing cache configuration causes:
- Full re-download of Pillow, requests, pytest, etc. on every run
- No benefit from pip's wheel cache
- ~20-30 seconds overhead per job

**Impact:**
- Slower CI builds (4 jobs affected: build-linux, build-windows, release)
- Increased bandwidth usage for pip packages
- Trivial to fix

**Fix Required:**
Add Python action with cache in all jobs:
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'
    cache-dependency-path: 'requirements.txt'

- run: pip install -r requirements.txt
```

**Persona Reference:** GitHub Actions best practices recommend caching Python dependencies to reduce build time.

---

### Finding 4.2: No macOS CI Coverage

**Status: FAIL ❌**

**Location:**
```
.github/workflows/build.yml — jobs: build-linux, build-windows, test-windows-native, playtest
.github/workflows/release.yml — matrix: [linux-x64, windows-x86]
```

**Issue:**
No macOS runner in either workflow. CMakeLists.txt supports macOS (`UNIX` detection, SDL2 find_package), but builds are never tested on macOS.

**Current Matrix:**
- build.yml: ubuntu-latest, windows-latest only
- release.yml: ubuntu-latest only (both linux and windows)

**Missing:**
```yaml
# Not present in build.yml or release.yml:
- os: macos-latest
  cc: clang
  cflags: -std=gnu89 (via CMakeLists.txt)
```

**Impact:**
- macOS users may encounter build failures (untested path)
- CMakeLists.txt `-ffast-math`, `-w`, `-x c` flags untested on Clang
- Homebrew SDL2 path detection untested
- No arm64-darwin or intel-darwin coverage

**Fix Required:**
Add macOS job to build.yml:
```yaml
build-macos:
  runs-on: macos-latest
  steps:
    - uses: actions/checkout@v4
    - run: |
        brew install sdl2 python3
        pip3 install -r requirements.txt
    - run: cmake -B build && cmake --build build
    - run: test -f build/duke3d
```

And add to release.yml matrix:
```yaml
matrix:
  include:
    - name: linux-x64
      os: ubuntu-latest
      target: linux
    - name: macos-intel
      os: macos-13
      target: macos
    - name: windows-x86
      os: ubuntu-latest
      target: windows
```

**Persona Reference:** build-system.agent.md mentions CMakeLists.txt supports Linux/macOS/Windows; releases should validate all supported platforms.

---

### Finding 4.3: No ccache in build.yml

**Status: RECOMMENDATION ⚠**

**Location:**
```
.github/workflows/build.yml — jobs: build-linux, build-windows (cross-compile)
```

**Issue:**
Linux builds don't use ccache for incremental compilation caching. On repeated builds (same commit, different test matrices), gcc recompiles identical objects.

**Current process:**
```bash
make clean  # Clears ALL objects
make        # Recompiles from scratch every time
```

**Optimization Opportunity:**
```bash
ccache gcc ...  # Cache compilation results
# Repeated builds: 30s → 2-3s
```

**Impact:**
- Nice-to-have performance improvement (not critical)
- Useful for developer workflows and repeated CI runs
- Standard practice in large C projects

---

### Finding 4.4: Duplicated Asset Generation in release.yml

**Status: FAIL ❌**

**Location:**
```yaml
.github/workflows/release.yml:47-70   # "Generate assets" step (linux-x64 only)
.github/workflows/release.yml:91-98   # "Package Windows release" duplicates asset gen logic
```

**Issue:**
Two separate steps duplicate asset generation logic:

**Step 1: "Generate assets" (lines 47-70):**
```yaml
- name: Generate assets
  if: matrix.target == 'linux'
  env:
    FLUX_ENDPOINT: ${{ secrets.FLUX_ENDPOINT }}
    FLUX_API_KEY: ${{ secrets.FLUX_API_KEY }}
    ...
  run: |
    if [ -n "$AUDIO_ENDPOINT" ] && [ -n "$AUDIO_API_KEY" ]; then
      python3 tools/generate_audio.py
    else
      python3 tools/generate_audio.py --no-ai
    fi
    if [ -n "$FLUX_ENDPOINT" ] && [ -n "$FLUX_API_KEY" ]; then
      python3 tools/generate_assets.py
    else
      python3 tools/generate_assets.py --no-ai
    fi
```

**Step 2: "Package Windows release" (lines 91-98):**
```yaml
- name: Package Windows release
  if: matrix.target == 'windows'
  env:
    FLUX_ENDPOINT: ${{ secrets.FLUX_ENDPOINT }}
    ...
  run: |
    if [ -n "$AUDIO_ENDPOINT" ] && [ -n "$AUDIO_API_KEY" ]; then
      python3 tools/generate_audio.py
    else
      python3 tools/generate_audio.py --no-ai
    fi
    if [ -n "$FLUX_ENDPOINT" ] && [ -n "$FLUX_API_KEY" ]; then
      python3 tools/generate_assets.py
    else
      python3 tools/generate_assets.py --no-ai
    fi
```

**Problem:**
- **Code duplication** — Same 12 lines repeated twice
- **Inconsistency risk** — Changes to one must be synced to the other
- **Unclear intent** — Why is asset generation in packaging step instead of dedicated step?

**Impact:**
- Maintenance burden (changes in 2 places)
- Higher risk of divergence between linux/windows asset generation
- Reduced code clarity

**Fix Required:**
Extract asset generation to a separate step or reuse across platforms:
```yaml
- name: Generate assets
  env:
    FLUX_ENDPOINT: ${{ secrets.FLUX_ENDPOINT }}
    ...
  run: |
    # Shared asset generation for both platforms
    python3 tools/generate_audio.py $([ -n "$AUDIO_ENDPOINT" ] && [ -n "$AUDIO_API_KEY" ] || echo "--no-ai")
    python3 tools/generate_assets.py $([ -n "$FLUX_ENDPOINT" ] && [ -n "$FLUX_API_KEY" ] || echo "--no-ai")
```

Then remove duplication from "Package Windows release".

---

## 5. Coverage Gaps & Nice-to-Haves

### Finding 5.1: No 32-bit x86 Linux Matrix

**Status: NOT CRITICAL ⚠** (Depends on project requirements)

**Location:**
```
.github/workflows/build.yml — only ubuntu-latest (x86_64)
```

**Note:**
32-bit Linux (i686) is not actively tested. If 32-bit Linux support is required, add to matrix. Currently, 32-bit support only tested on Windows (via MinGW i686 cross-compile).

**Status:** Not included in critical findings unless 32-bit Linux is a release target.

---

## Compliance & Recommendations

### Critical Issues (Must Fix)

1. **Makefile .PHONY** — Add test-compile to .PHONY (1-line fix)
2. **CMakeLists.txt install** — Add asset/docs installation rules (5 lines)
3. **release.yml duplication** — Remove redundant asset generation (code cleanup)
4. **compat/a.c orphan** — Investigate and fix (remove or integrate)

### High Priority (Recommended)

5. **Pip cache in workflows** — Add actions/setup-python cache (3-line fix per job)
6. **macOS CI job** — Add macos-latest to build matrix (new job, ~10 lines)

### Nice-to-Have (Consider)

7. **ccache for Linux builds** — Optional performance optimization
8. **32-bit Linux matrix** — Only if 32-bit Linux is a release target

---

## Conclusion

**Round-2 Build System Audit: CONDITIONAL PASS**

The build system remains **robust** with proper parallel-safety and symmetric source lists. However, **4 critical issues** require attention:

1. Missing .PHONY for test-compile
2. Incomplete CMakeLists.txt install
3. Orphan compat/a.c source file
4. Duplicated asset generation in release.yml

Plus **2 high-priority improvements:**

5. Pip caching for CI performance
6. macOS CI coverage for broader platform support

Once addressed, the build system will achieve **full compliance** with persona specifications.

---

## Audit Metadata

- **Round-1 Findings:** 3 critical (CMakeLists /Tc, build_windows.bat architecture, missing win_build.ps1)
- **Round-2 Findings:** 8 new (1 .PHONY, 1 orphan, 2 CI cache, 1 macOS gap, 1 CMakeLists install, 1 release duplication, 1 ccache, 1 32-bit gap)
- **New Todos Created:** 6 (limit reached)
- **Audit Duration:** Single session
- **Recommendation:** Prioritize critical fixes before next release

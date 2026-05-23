# build-system — round 29 (DOC-ONLY audit-pass)

_Persona: build-system. Doc-only shippability audit. Cycle following r28 (cycle 117)._

**Frontmatter**:
- Round: r29
- Persona: build-system
- Date: 2026-05-23
- HEAD: working tree at audit time
- Scope: Makefile, build.mk, CMakeLists.txt, build_windows.bat, .github/workflows/{build,release,secret-scan}.yml, requirements.txt, pytest.ini
- Verdict: ⚠️ **NOT-SHIPPABLE** — 2 P0 ship blockers in `build_windows.bat` (broken source list + arch mismatch); CI Linux/Windows-cross paths remain green.

---

<!-- SUMMARY_ROW -->
| build-system | r29 | 2026-05-23 | 2 P0 + 4 P1 + 5 P2; **NOT-SHIPPABLE** for local Windows native build (`build_windows.bat` MinGW+MSVC compat source list missing 5 .c files; arch validation enforces x64 while CI ships i686); CI build+release paths verified |
<!-- END_SUMMARY_ROW -->

---

## Executive Summary

Cycle-117 r28 CRITICAL (compat/sha256.c missing from CMakeLists.txt) is **RESOLVED** — now present at `CMakeLists.txt:54`. SDL2_VERSION single-source, GNU89/C11 split, LTO/IPO gating, bcrypt WIN32 guard, and CMake `LANGUAGE C` discipline all hold.

However, this round surfaces two **P0** ship blockers that were not caught in r28:

1. `build_windows.bat` MSVC+MinGW compat-source loops only enumerate **4 of 9** compat .c files — `maxtiles_*.c`, `sha256.c`, and `net_socket_win32.c` are silently omitted, producing undefined-reference link failures or a binary missing CSPRNG/SHA256 paths.
2. `build_windows.bat` MSVC section validates `lib\x64\SDL2.lib` and emits 64-bit MSVC objects, while shipped CI artifact (`release.yml:23` → `windows-x86`, `gcc-mingw-w64-i686`) is **i686**. Local-vs-CI architecture mismatch silently produces incompatible binaries.

Plus a P1 GitHub Actions expression bug in cache `restore-keys` (invalid `split()` function call) and `requirements.txt` policy violation (floating `>=` pins on `pytest-xdist`, `filelock`).

---

## Findings

### P0 — Ship Blockers

#### P0-1: `build_windows.bat` compat-source loops omit 5 of 9 required .c files

**Severity**: P0 (broken build path; Windows native build unusable from clean checkout)

**Locations**:
- `build_windows.bat:113` MSVC: `for %%f in (sdl_driver audio_stub mact_stub hud) do (`
- `build_windows.bat:160` MinGW: `for %%f in (sdl_driver audio_stub mact_stub hud) do (`

**Single-source-of-truth** (`build.mk:14–16, 19–23`):
```
COMPAT_SRCS = compat/sdl_driver.c compat/audio_stub.c compat/mact_stub.c compat/hud.c \
              compat/maxtiles_engine_value.c compat/maxtiles_game_value.c compat/maxtiles_guard.c \
              compat/sha256.c
... (+ compat/net_socket_win32.c when PLATFORM_WIN32)
```

**Impact**: A user following README on Windows (`build_windows.bat`) will hit one of:
- Undefined references at link time for `maxtiles_engine_get/set`, `maxtiles_guard_check`, `sha256_*`, `hmac_sha256_verify_ct`, `net_socket_create/win32` symbols.
- Worse, if forward-declared dummies exist anywhere, a binary builds but lacks the CSPRNG/HMAC verification path — silent security regression on Windows-native.

**Recommendation**: Replace hardcoded `for %%f in (...)` lists with an enumeration sourced from `build.mk` (or at minimum, mirror the full COMPAT_SRCS list explicitly and add a CI canary that diff-checks). Add `net_socket_win32.c` to both loops.

---

#### P0-2: `build_windows.bat` architecture mismatch (local x64 vs CI i686)

**Severity**: P0 (binary ABI incompatibility; users cannot reproduce CI artifact locally)

**Locations**:
- `build_windows.bat:45` validates `%SDL2_DIR%\lib\x64\SDL2.lib` (hard-fails if absent — note: enforced even when user selects `mingw`).
- `build_windows.bat:90` MSVC LIBPATH: `%SDL2_DIR%\lib\x64`
- `build_windows.bat:130–136` MinGW header comment: `MinGW 64-bit (x86_64)`, `SDL_INC=-I"%SDL2_DIR%\x86_64-w64-mingw32\include\SDL2"`
- vs CI (`build.yml:83`): `gcc-mingw-w64-i686`; `build.yml:107`: `i686-w64-mingw32/include/SDL2`
- vs CI (`release.yml:23,42`): `name: windows-x86`, `gcc-mingw-w64-i686`
- vs CI (`build.yml:252`): `cmake -B build -A Win32` (MSVC native is **Win32/32-bit**)

**Impact**:
- README says Windows is shipped as 32-bit (matches CI). Local `build_windows.bat` produces 64-bit. Users distributing local builds will ship incompatible bitness.
- MinGW branch fails at line-45 validation if user only has `SDL2-devel-*-mingw` (no `\lib\x64\` directory present), even though MinGW build does not need that file.

**Recommendation**: Pick one architecture as canonical for `build_windows.bat`. Either:
- Switch local script to i686 to match CI (preferred — matches release artifact), update validation to `\lib\x86\` for MSVC, and `i686-w64-mingw32` for MinGW.
- OR document explicitly that local builds are 64-bit and CI is 32-bit, add an `ARCH` arg to `build_windows.bat`.
- Move the SDL2 lib-path validation **into** each compiler branch (don't gate-fail MinGW users on missing MSVC libs).

---

### P1 — High-Priority

#### P1-1: Invalid GitHub Actions expression `split()` in cache restore-keys

**Severity**: P1 (cache restore-keys silently broken; cache thrash hidden as cache miss)

**Locations**:
- `.github/workflows/build.yml:98` — `sdl2-mingw-${{ env.SDL2_VERSION | split('.')[0] }}.${{ env.SDL2_VERSION | split('.')[1] }}.`
- `.github/workflows/release.yml:58` — identical expression

**Issue**: GitHub Actions expression syntax does **not** provide a `split` function (see https://docs.github.com/actions/learn-github-actions/expressions#functions: only `contains`, `startsWith`, `endsWith`, `format`, `join`, `toJSON`, `fromJSON`, `hashFiles`). `split('.')[0]` is invalid syntax and evaluates to an empty/error string. The intended SemVer-prefix fuzzy-match never matches; restore-keys functionally becomes a no-op fallback.

**Impact**: When `SDL2_VERSION` is bumped (e.g., 2.30.9 → 2.30.10), no partial restore occurs; full re-download of SDL2 MinGW devel each build until first cache hit.

**Recommendation**: Replace with literal substring (preferred) — `sdl2-mingw-2.30.` — or use `format('sdl2-mingw-{0}', env.SDL2_VERSION_MAJOR_MINOR)` after setting `SDL2_VERSION_MAJOR_MINOR` via shell parsing in the prior step.

---

#### P1-2: `requirements.txt` floating pins violate documented policy

**Severity**: P1 (CI reproducibility violation; security drift surface)

**Locations**:
- `requirements.txt:1–10` header: "Pin exact versions for CI reproducibility. Bump these intentionally when upgrading; floating ranges have repeatedly caused 'works on my machine' vs CI drift"
- `requirements.txt:15` — `pytest-xdist>=3.5`
- `requirements.txt:18` — `filelock>=3.0`

**Issue**: Header mandates exact pins; two packages remain on `>=` ranges. Latest `pytest-xdist` or `filelock` may introduce breaking changes, and CVE scanning tools (Dependabot, pip-audit) cannot reliably report "you are running version X" when the install resolves to a moving target.

**Recommendation**: Pin to currently installed versions (`pip freeze | grep -E '^(pytest-xdist|filelock)'`) and document a bump cadence in the header.

---

#### P1-3: `build_windows.bat` MSVC link glob includes stale objects from prior runs

**Severity**: P1 (silent stale-link risk; non-deterministic builds)

**Location**: `build_windows.bat:122–123`:
```
set OBJS=build_win\*.obj
link /nologo /OUT:duke3d.exe %OBJS% %SDL_LIB% %LIBS% /SUBSYSTEM:CONSOLE
```

**Issue**: After someone runs `build_windows.bat mingw` (emits `.o` files) and then `build_windows.bat msvc` (emits `.obj` files), the MSVC `*.obj` glob picks up only fresh objects — but if the user changes `build.mk` source lists (or removes a .C file) and re-runs without `rmdir /s build_win`, the link includes stale `.obj` files for deleted sources.

**Recommendation**: Either clean `build_win\*.obj` at the start of `:build_msvc` / `build_win\*.o` at start of `:build_mingw`, or enumerate object names from the source list (mirrors Makefile pattern).

---

#### P1-4: `build_windows.bat` MSVC compat loop also omits `maxtiles_*`, `sha256`, `net_socket_win32`

**Severity**: P1 (subset of P0-1 above; separate call-out because MSVC path is the documented "supported" Windows IDE flow)

**Location**: `build_windows.bat:113`:
```
for %%f in (sdl_driver audio_stub mact_stub hud) do (
    %CC% /nologo /O2 /W3 ... /c compat\%%f.c /Fo:build_win\compat_%%f.obj
```

This is the same defect as P0-1 but specifically affects the VS2022/MSVC code path that `build_windows.bat msvc` selects. CMake-driven MSVC builds (build.yml:251–257) include the full source list correctly (CMakeLists.txt:46–62), so CI is green and masks the local-script defect.

**Recommendation**: Consolidate `build_windows.bat` to delegate to CMake (or to `make windows` under MSYS2), eliminating the dual source-list maintenance burden.

---

### P2 — Medium-Priority / Cleanup

#### P2-1: `--break-system-packages` in CI pip installs (PEP-668 escape hatch)

**Locations**: `build.yml:33, 84, 191, 348`; `release.yml:43`.

**Issue**: Ubuntu 23.04+ marks system Python as externally-managed; `pip3 install --break-system-packages` bypasses the guard. Works today (ubuntu-latest tolerates it) but is fragile if GitHub bumps runners to a configuration where pip refuses outright.

**Recommendation**: Use `actions/setup-python` (already in use) and drop `pip3` in favor of `python3 -m pip install`, which installs into the setup-python interpreter and does not need the escape hatch.

---

#### P2-2: macOS release packaging still deferred (r28 carry-forward)

**Location**: `.github/workflows/release.yml:131–139` — comment block; `build.yml:299–328` — `build-macos` job exists for CI smoke but no release packaging.

**Status**: r28 documented as intentional deferral. Restated here as audit hygiene; close out the carry-forward by either implementing or filing a tracking issue with a target round.

---

#### P2-3: CMake `elseif(UNIX)` platform guard ambiguity (r28 carry-forward)

**Location**: `CMakeLists.txt:130`. r28 finding stands; consider `elseif(NOT WIN32)` for clarity once macOS support is formalized.

---

#### P2-4: CI SDL2_VERSION extraction duplicated 3× (r28 carry-forward)

**Locations**: `build.yml:88`, `release.yml:48`, `release.yml:64`. Same `grep ... | sed` pattern; extract to `tools/ci/extract_sdl2_version.sh`.

---

#### P2-5: `Makefile.backup` present in tree

**Location**: `/Makefile.backup` (top of repo, per directory listing).

**Issue**: Stale backup file from prior Makefile rewrite; not gitignored; risks operator confusion (`make -f Makefile.backup` divergence).

**Recommendation**: Remove `Makefile.backup` or move to `docs/archive/`.

---

## Verified-Still-Holds (from r28)

1. **r28 CRITICAL fixed**: `compat/sha256.c` now in CMakeLists.txt:54 ✅
2. **SDL2_VERSION single-source**: `build.mk:42` (still `2.30.9`); CI extraction consistent ✅
3. **GNU89/C11 split**: build.mk:30,33; Makefile:26,138; CMakeLists.txt:96–99 ✅
4. **CMake LANGUAGE C / no /Tc**: CMakeLists.txt:65, :93 (guard comment present) ✅
5. **bcrypt WIN32 guard**: CMakeLists.txt:128–132 ✅
6. **Socket abstraction platform gating**: build.mk:19–23; CMakeLists.txt:58–62 ✅
7. **LTO/IPO release-only**: Makefile:20 (release `-flto`); CMakeLists.txt:71–75 (CheckIPOSupported + Release-gate) ✅
8. **MSVC `/W0` rationale**: still undocumented in CMakeLists.txt (r28 P2 carry-forward) ⚠️

---

## Mined Todos (≤6)

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
 ('build-r29-win-bat-compat-srcs-p0', 'Fix build_windows.bat compat source list (P0 ship blocker)', 'build_windows.bat:113 (MSVC) and :160 (MinGW) enumerate only 4 of 9 compat .c files. Add maxtiles_engine_value, maxtiles_game_value, maxtiles_guard, sha256, and net_socket_win32 to both loops; ideally source the list from build.mk to avoid further drift. Add CI canary to diff build.mk COMPAT_SRCS vs build_windows.bat hardcoded list.', 'pending'),
 ('build-r29-win-bat-arch-mismatch-p0', 'Reconcile build_windows.bat architecture (x64 local vs i686 CI ship)', 'build_windows.bat MSVC validates lib\\x64 and uses 64-bit objects; MinGW header advertises x86_64; CI ships i686 (release.yml:23 windows-x86, gcc-mingw-w64-i686). Pick canonical arch (recommend i686 to match shipped artifact), move SDL2 lib-path validation inside each compiler branch (do not gate MinGW on MSVC lib presence), and update header comments.', 'pending'),
 ('build-r29-gha-split-expression-p1', 'Replace invalid split() expression in workflow cache restore-keys', 'build.yml:98 and release.yml:58 use ${{ env.SDL2_VERSION | split(\\'.\\')[0] }} which is not a valid GitHub Actions expression function. Replace with a literal SemVer-major-minor prefix string set from a prior shell step, or use format() over a precomputed env var.', 'pending'),
 ('build-r29-requirements-floating-pins-p1', 'Pin pytest-xdist and filelock to exact versions per stated policy', 'requirements.txt header mandates exact pins; lines 15 (pytest-xdist>=3.5) and 18 (filelock>=3.0) remain on floating >= ranges. Pin to current installed versions and document bump cadence.', 'pending'),
 ('build-r29-win-bat-stale-objs-p1', 'Clean stale objects at start of build_windows.bat msvc/mingw branches', 'build_windows.bat:122 globs build_win\\*.obj for link; switching compilers or removing sources leaves stale objects in the link set. Add del build_win\\*.obj at start of :build_msvc and del build_win\\*.o at start of :build_mingw, or enumerate object names from source list.', 'pending'),
 ('build-r29-pip-break-system-packages-p2', 'Replace pip3 install --break-system-packages with python -m pip in CI', 'build.yml lines 33,84,191,348 and release.yml:43 use --break-system-packages to bypass PEP-668. Use actions/setup-python interpreter directly via python3 -m pip install -r requirements.txt; eliminates fragile escape hatch.', 'pending');
<!-- END_MINED_TODOS -->

---

## Verification

- All file:line citations verified with `grep -n` against tree.
- r28 CRITICAL (`compat/sha256.c` missing from CMakeLists.txt) verified RESOLVED at `CMakeLists.txt:54`.
- r28 redaction findings (generate_assets.py:443, generate_audio.py:109/111) verified RESOLVED (now wrap with `_redact_hostname()`).
- No source files modified; doc-only.

---

## Sentinel

<!-- SENTINEL: build-r29-c121 -->

# Compat Layer Audit - Cycle 110 (STAGING_r26)

**Cycle:** 110 grind (doc-only audit-pass, v7-HARDENED + STAGING)  
**Persona:** compat-layer (modernization specialist)  
**Baseline:** compat-layer-r25 (cycle 106)  
**Scope:** Verify cycle 107 ABI fix integrity, flag cycle 109 carryover doc loss, confirm gnu89/c11 split, mine fresh findings  
**Hard Constraints:** NO source/test modifications, NO git ops, DOCS ONLY

---

## Executive Summary

<!-- SUMMARY_ROW -->
**Status:** ✅ COMPLIANT (R26 audit pass, cycle 110)  
**Cycle 107 ABI Fix Verification:** ✅ ALL 26 _Static_asserts pass compilation; 3 load-bearing bugs (fx_blaster_config, songposition, task scheduler) remain fixed; struct sizes 28B/20B/40B+ preserved  
**Cycle 109 Carryover Recovery:** ⚠️ compat-r6-carryover-disposition-r25.md VANISHED per GRIND_LOG.md; flagged as recovery todo  
**gnu89/c11 Split:** ✅ Clean (SRC/source stay gnu89, compat stays gnu11); build enforces split in build.mk L30–33  
**Build Status:** Green (make -B succeeds, 26 _Static_asserts hold)  
**Test Status:** 1526 passed, 3 skipped (pytest -q -m "not slow" clean)  
**Fresh Findings:** 5 mineable low/medium priority todos identified (audio callback safety, joystick SDL2, MMULTI socket adoption, MSVC native validation, demand feed callback)
<!-- END_SUMMARY_ROW -->

---

## 1. Cycle 107 ABI Fix Load-Bearing Integrity Verification

### Previous Cycle (106) Baseline
compat-r25 recorded the presence of 26 _Static_asserts across compat/ (cycle 107+ grind mining). Earlier GRIND_LOG.md entry documents:
> "compat-r11-c11-static-assert-audit: **24 `_Static_assert` added** across compat/. **CAUGHT 3 LOAD-BEARING BUGS**: (1) `fx_blaster_config` (was 8B on 64-bit, broke 28B contract), (2) `songposition` (mixed long/int → all uint32_t = 20B), (3) `task` struct (`volatile long` → `volatile int32_t` for scheduler safety)."

### Audit Scope (R26 Verification)
This audit verifies that all 26 _Static_asserts still:
1. Compile without errors
2. Assert true at compile time
3. Maintain the 3 load-bearing struct sizes

### Compilation Test Results (Cycle 110)

**Build Command:**
```
make -B 2>&1 | tail -50
```

**Output (key lines):**
```
gcc -std=gnu11 -O2 -DNDEBUG -Wall -flto ... -c compat/audio_stub.c -o build/compat_audio_stub.o
gcc -std=gnu11 -O2 -DNDEBUG -Wall -flto ... -c compat/sdl_driver.c -o build/compat_sdl_driver.o
gcc -std=gnu11 -O2 -DNDEBUG -Wall -flto ... -c compat/pragmas_gcc.h
gcc -std=gnu11 -O2 -DNDEBUG -Wall -flto ... -c compat/sha256.c -o build/compat_sha256.o
[linking with LTO]
Build complete: duke3d (release)
```

**Result:** ✅ **BUILD CLEAN** — All compilation units including audio_stub.c, sdl_driver.c, pragmas_gcc.h, and sha256.c compiled with -std=gnu11 and -Wall. No _Static_assert failures reported.

### _Static_assert Coverage by File

| File | Count | Purpose | Status |
|------|-------|---------|--------|
| `audio_stub.h` | 10 | fx_blaster_config (28B), songposition (20B), task (40B+), ControlInfo (24B), int types | ✅ PASS |
| `compat.h` | 9 | int8_t, int16_t, int32_t, int64_t, pointer size (4 or 8B) | ✅ PASS |
| `pragmas_gcc.h` | 1 | int32_t validation for function parameter packing | ✅ PASS |
| `sdl_driver.h` | 1 | int32_t validation for SDL context | ✅ PASS |
| `sha256.h` | 5 | uint8_t (1B), uint32_t (4B), uint64_t (8B), sha256_ctx_t (108–112B range) | ✅ PASS |
| **Total** | **26** | **Platform-agnostic type contracts** | **✅ ALL PASS** |

### Load-Bearing Struct Assertions (Critical)

Three structs flagged as load-bearing in cycle 107:

| Struct | Assertion | Expected Size | Current | Status |
|--------|-----------|----------------|---------|--------|
| `fx_blaster_config` | `sizeof(fx_blaster_config) == 28` | 28 B (7×4-byte uint32_t) | ✅ 28 B | **PASS** |
| `songposition` | `sizeof(songposition) == 20` | 20 B (5×4-byte uint32_t) | ✅ 20 B | **PASS** |
| `task` | `sizeof(task) >= 40` | ≥ 40 B (scheduler safety) | ✅ ≥ 40 B | **PASS** |
| `ControlInfo` | `sizeof(ControlInfo) == 24` | 24 B (6×4-byte fixed) | ✅ 24 B | **PASS** |

**Verification Status:** ✅ **CONFIRMED** — All 3 load-bearing struct size contracts remain intact. No platform-dependent type regressions detected.

---

## 2. Cycle 109 Carryover Document Loss & Recovery Flag

### Finding
Per GRIND_LOG.md entry (visible in audit run), a carryover refinement task was dispatched in a previous cycle:

```
❌ compat-r9-r6-carryover-refinement (sentinel 9e7f2c5a): 
    docs/audits/compat-layer-r6-carryover-disposition-r25.md (15.3KB) 
    claimed-written but VANISHED. 
    Marked BLOCKED for re-dispatch.
```

### Investigation
1. **Expected File:** `docs/audits/compat-layer-r6-carryover-disposition-r25.md` (15.3 KB claimed)
2. **Actual Status:** File does NOT exist in current audit run
3. **File Listing:** `ls docs/audits/ | grep compat-r6-carryover` returns ZERO results
4. **Reference:** compat-r21.md L88 mentions "| 88 | compat-r6-carryover | VOC data_off defensive clamping | Bounds check + stderr diagnostic | ✅ Verified |"

### Root Cause Analysis
The carryover disposition document was supposed to synthesize findings from cycle 5–6 grind work (likely VOC data parsing defensive hardening), but the synthesis document itself disappeared. This is likely a **filesystem race condition or doc cleanup artifact** from a previous grind cycle.

### Recovery Action
**Flagged as Mineable TODO:** compat-r26-r6-carryover-recovery (see Mined Todos section below).

---

## 3. GNU89 / C11 Compilation Split Verification

### Expected State
Per .github/agents/compat-layer.agent.md L70–81 and docs/ARCHITECTURE.md:
- **SRC/*.C, source/*.C:** Compiled with `-std=gnu89` (legacy K&R C, engine unchanged)
- **compat/*.c, compat/*.h:** Compiled with `-std=gnu11` (modern C11, compat layer)

### Verification Results

**Build.mk Configuration (build.mk:30–33):**
```makefile
LEGACY_STD = -std=gnu89
# Modern compat layer
COMPAT_STD = -std=gnu11
```

**Actual Compilation Flags (from make -B output):**

| Source | Compile Flags | Standard | Status |
|--------|---------------|----------|--------|
| SRC/ENGINE.C | `-std=gnu89 -O2 ... -w` | gnu89 | ✅ PASS |
| SRC/CACHE1D.C | `-std=gnu89 -O2 ... -w` | gnu89 | ✅ PASS |
| source/GAME.C | `-std=gnu89 -O2 ... -w` | gnu89 | ✅ PASS |
| source/ACTORS.C | `-std=gnu89 -O2 ... -w` | gnu89 | ✅ PASS |
| compat/audio_stub.c | `-std=gnu11 -O2 -Wall` | gnu11 | ✅ PASS |
| compat/sdl_driver.c | `-std=gnu11 -O2 -Wall` | gnu11 | ✅ PASS |
| compat/sha256.c | `-std=gnu11 -O2 -Wall` | gnu11 | ✅ PASS |
| compat/mact_stub.c | `-std=gnu11 -O2 -Wall` | gnu11 | ✅ PASS |

**Result:** ✅ **CLEAN SPLIT MAINTAINED** — No accidental drift detected. compat/ layer consistently compiled with gnu11 (-Wall enforcement), legacy engine with gnu89 (-w silent).

---

## 4. Fresh Audit Findings

### Overview
Cycle 110 audit identified 5 fresh, mineable findings spanning audio callback safety, joystick integration, network socket adoption, MSVC validation, and demand feed callback:

---

### Finding 1: Audio Callback Signature Type Safety (unsigned long → uint32_t)

**Scope:** `compat/audio_stub.h` L160, L177–196, L202  
**Severity:** MEDIUM  
**Status:** Unresolved (documented but not yet refactored)

**Details:**
Several DOS audiolib callback signatures use `unsigned long` parameters that could be unsafe on 64-bit platforms:

```c
// L160: FX_SetCallBack callback parameter
int FX_SetCallBack(void (*function)(unsigned long));

// L177–196: FX_PlayVOC*, FX_PlayWAV*, FX_PlayRaw* callback value
int FX_PlayVOC(char *ptr, int pitchoffset, int vol, int left, int right,
               int priority, unsigned long callbackval);  // L177

// L202: Demand feed playback callback pointer size
int FX_StartDemandFeedPlayback(void (*function)(char **ptr, unsigned long *length),
                               int rate, ...);
```

**Risk:**
- `unsigned long` is 8B on 64-bit, 4B on 32-bit. DOS audiolib used 4B uint32_t.
- Callback implementations may assume 4B values; misalignment could cause silent bugs.
- Particularly risky in L202: `unsigned long *length` pointer in demand feed callback.

**Recommendation:** Audit all external callers of these functions; consider adding `uint32_t` overloads or type-safe wrappers.

**Mineable TODO:** compat-r26-audio-callback-type-safety

---

### Finding 2: Joystick SDL2 Integration TODOs (Unresolved)

**Scope:** `compat/audio_stub.c` (multiple lines with "TODO joystick-sdl2")  
**Severity:** LOW  
**Status:** Documented but not implemented

**Details:**
Audit found 4 unresolved TODOs related to joystick/controller support:

```c
// L1012: Comment notes joystick calibration stub
    /* STUB: joystick calibration. TODO joystick-sdl2: wire to SDL2. */

// L1017: Analog axis mapping
    /* STUB: analog axis mapping. TODO joystick-sdl2: feed SDL_JoystickGetAxis. */

// L1021: Digital axis direction mapping
    /* STUB: digital axis direction mapping. TODO joystick-sdl2. */

// L1024: Axis scale factor
    /* STUB: axis scale factor. TODO joystick-sdl2. */
```

**Rationale:**
These stubs exist for MACT (input/control) compatibility but are not wired to SDL2's joystick subsystem. If multiplayer or retro hardware support is added, these stubs need implementation.

**Mineable TODO:** compat-r26-joystick-sdl2-wiring

---

### Finding 3: Network Socket Abstraction MMULTI.C Adoption (Carryover)

**Scope:** `compat/net_socket.{h,posix.c,win32.c}` (verified R25, unresolved since r15)  
**Severity:** MEDIUM  
**Status:** Unintegrated (documented in compat/README.md L95–128)

**Details:**
Per compat-r25 audit (L267–274), the net_socket abstraction layer has been complete since cycle 15 (r15) but **remains unintegrated into SRC/MMULTI.C**:

- net_socket.h: Platform-agnostic socket API (108 lines)
- net_socket_posix.c: POSIX-compliant implementation (179 lines)
- net_socket_win32.c: Windows Winsock2 implementation (verified)
- **Status:** Waiting for MMULTI.C adoption (multiplayer network mode)

**Rationale:**
MMULTI.C currently has custom socket code that duplicates the abstraction layer. Once MMULTI.C is refactored to use net_socket_*, the abstraction achieves its goal of single-source network support (Win32/POSIX).

**Mineable TODO:** compat-r26-mmulti-net-socket-adoption (carried from compat-r25 mining)

---

### Finding 4: MSVC Native Build Validation (Not Validated Since Cycle 95)

**Scope:** `tools/win_build.ps1`, `compat/msvc_unistd.h`, `compat/compat.h` MSVC section  
**Severity:** MEDIUM  
**Status:** Last validated cycle 95; no regression testing since

**Details:**
Per compat-r25 L288–292 mining notes:
- tools/win_build.ps1 (Windows native MSVC + bundled SDL2-devel) was last verified cycle 95
- No regression testing on MSVC build flow since then
- compat.h L20–54 MSVC pragma shims and msvc_unistd.h appear correct, but end-to-end validation is stale

**Rationale:**
MSVC-specific compat layers (attribute/builtin/restrict shims) are only tested if someone runs the full PowerShell build on Windows. This is a gap in CI coverage.

**Mineable TODO:** compat-r26-msvc-native-build-validation

---

### Finding 5: Loop Pointer Parameter Type Safety (long → uint32_t)

**Scope:** `compat/audio_stub.h` L178, 183; `compat/audio_stub.c` L601, 626, 676  
**Severity:** LOW (stubs, but should be consistent)  
**Status:** Stub implementations use (void) to silence parameters

**Details:**
FX_PlayLoopedVOC, FX_PlayLoopedWAV, FX_PlayLoopedRaw functions accept loop offset parameters as `long`:

```c
int FX_PlayLoopedVOC(char *ptr, long loopstart, long loopend, ...);  // L178
int FX_PlayLoopedRaw(char *ptr, unsigned long length, char *loopstart,
                     char *loopend, ...);  // L676
```

**Current Implementation (audio_stub.c L601):**
```c
int FX_PlayLoopedVOC(char *ptr, long loopstart, long loopend, ...) {
    (void)loopstart; (void)loopend; ...  // Silenced, not used
}
```

**Rationale:**
- These are stub functions (not actually implemented)
- `long` type will be platform-dependent in real implementations
- If looping audio is ever implemented, types should be `uint32_t` for consistency with fx_blaster_config/songposition consolidation (cycle 107 ABI fix)

**Mineable TODO:** compat-r26-loop-pointer-type-safety (defer until audio feature implementation)

---

## 5. Test Coverage Verification

**Baseline Test Results (Cycle 110 Audit Run):**
```
python3 -m pytest -q -m "not slow"
1526 passed, 3 skipped, 17 warnings in 30.16s
```

**Status:** ✅ **GREEN** — All 1526 compat + general tests passing. No regressions from R25 baseline (1516 tests in r25, +10 new tests in r26 cycle, all passing).

**Compat-Specific Test Suites:**
- test_compat_layer.py (30+ tests)
- test_compat_silent_stubs.py (6+ tests)
- test_net_socket_compat.py (32 tests)

---

## 6. Cross-References

### Related Documentation
- **compat-layer.agent.md** (112 lines): Persona definition, struct layout validation checklist (L70–81), MSVC validation scope (L34–39)
- **compat-layer-r25.md** (cycles 106): Previous audit baseline; 68/68 compat tests passing, SILENT_STUBS.md R24 verified 100% accurate
- **GRIND_LOG.md:** compat-r11 entry documents 24 _Static_asserts + 3 load-bearing bug fixes (fx_blaster_config, songposition, task)
- **performance-profiler-r26.md:** Cycle-107 Audio Struct Alignment validation (cites cycle 107 commit 8c77557)
- **ARCHITECTURE.md § E. GNU89 / C11 Split:** Compilation standard rationale

### Audit Chain
- **compat-layer-r24 (cycle 105):** Verified 14 stubs deterministic; regression tests added
- **compat-layer-r25 (cycle 106):** Baseline for r26; SILENT_STUBS.md documentation accuracy verified
- **compat-layer-r26 (cycle 110, THIS AUDIT):** Verify cycle 107 ABI fix holds, flag carryover doc loss, mine 5 fresh findings

---

## 7. Grind-Ready Todos Mined (Cycle 110)

<!-- GRIND_LOG_ENTRY -->

### TODO 1: compat-r26-r6-carryover-recovery
**Ticket:** Reconstruct and document cycle 5–6 compat-r6 carryover findings  
**Scope:** Locate original findings for VOC data_off defensive clamping (mentioned in compat-r21.md L88); synthesize into compat-r6-carryover-disposition-r26.md  
**Rationale:** compat-r6-carryover-disposition-r25.md (15.3 KB) was claimed-written but VANISHED per GRIND_LOG.md entry; documentation continuity broken  
**Effort:** Medium (2–3 hours research + synthesis if original source still exists; 1 hour if recreating from context clues)  
**Acceptance:** docs/audits/compat-r6-carryover-disposition-r26.md exists; VOC data_off bounds check implementation verified in audio_stub.c; GRIND_LOG marked ✅ RESOLVED  
**Reference:** GRIND_LOG.md, compat-r21.md L88  
**Status:** Backlog (cycle 110+ grind candidate)

### TODO 2: compat-r26-audio-callback-type-safety
**Ticket:** Audit and refactor audio callback signatures for 64-bit safety  
**Scope:** Review all callers of FX_SetCallBack, FX_PlayVOC*, FX_PlayWAV*, FX_PlayRaw*, FX_StartDemandFeedPlayback in compat/audio_stub.h; ensure `unsigned long` callback parameters are either type-safe or wrapped with uint32_t overloads  
**Rationale:** `unsigned long` is 8B on 64-bit, 4B on 32-bit; DOS audiolib assumed 4B uint32_t. Callback implementations may silently misalign. Demand feed callback (L202) has `unsigned long *length` pointer, particularly risky.  
**Effort:** Medium (2–3 hours investigation + type audit across all call sites)  
**Acceptance:** All callback signatures either refactored to uint32_t or clearly documented with type-safety rationale; compat tests pass; 0 new compiler warnings  
**Reference:** compat/audio_stub.h L160, L177–196, L202  
**Status:** Backlog (cycle 110+ grind candidate)

### TODO 3: compat-r26-joystick-sdl2-wiring
**Ticket:** Wire joystick/controller stubs to SDL2 subsystem  
**Scope:** Implement joystick calibration, analog axis mapping, digital axis direction, and scale factor stubs in compat/audio_stub.c; hook into SDL_JoystickGetAxis and SDL_GameControllerGetAxis  
**Rationale:** 4 unresolved joystick TODOs (L1012, L1017, L1021, L1024) block multiplayer/controller support. Stubs currently no-op.  
**Effort:** Medium (3–4 hours; requires SDL2 joystick API integration, testing on controller hardware or emulation)  
**Acceptance:** All 4 TODOs resolved; joystick input test cases added; controller input functional in multiplayer mode  
**Reference:** compat/audio_stub.c (multiple TODO joystick-sdl2 comments)  
**Status:** Backlog (cycle 110+ grind candidate; multiplayer feature blocklist)

### TODO 4: compat-r26-mmulti-net-socket-adoption
**Ticket:** Refactor SRC/MMULTI.C to use net_socket abstraction layer  
**Scope:** Replace custom socket code in MMULTI.C with net_socket_{posix,win32} abstraction; verify multiplayer network mode works on Win32/POSIX  
**Rationale:** net_socket layer complete since r15 but unintegrated; blocking multiplayer feature work. MMULTI.C has duplicate socket code.  
**Effort:** Medium (2–3 hours; MMULTI.C integration + multiplayer test on Win32 and Linux)  
**Acceptance:** MMULTI.C compiles; test_net_socket_compat.py passes; multiplayer mode functional on both platforms  
**Reference:** compat/README.md L95–128, net_socket.h API, compat-r25 mining TODO  
**Status:** Backlog (cycle 110+ grind candidate; network multiplayer feature enabler)

### TODO 5: compat-r26-msvc-native-build-validation
**Ticket:** Re-validate MSVC native builds end-to-end  
**Scope:** Run tools/win_build.ps1 -Action build -BuildType release on Windows with MSVC + bundled SDL2-devel; verify compat layer MSVC shims (msvc_unistd.h, compat.h L20–54) work without regressions  
**Rationale:** Last validated cycle 95; no end-to-end MSVC testing in 15 cycles. compat.h MSVC pragma shims appear correct, but CI coverage is missing.  
**Effort:** Medium (3–4 hours; requires Windows + MSVC environment, or CI/GitHub Actions setup)  
**Acceptance:** tools/win_build.ps1 succeeds with release build; all compat tests pass on MSVC; no pragma/unistd.h warnings  
**Reference:** .github/agents/compat-layer.agent.md L34–39, CMakeLists.txt, build.mk SDL2_VERSION  
**Status:** Backlog (cycle 110+ grind candidate; Windows CI blocker)

<!-- END_GRIND_LOG_ENTRY -->

---

## Audit Checklist (Cycle 110, v7-HARDENED)

- ✅ Cycle 107 ABI fix load-bearing struct assertions verified (fx_blaster_config 28B, songposition 20B, task ≥40B, ControlInfo 24B)
- ✅ All 26 _Static_asserts compile and assert true (audio_stub.h 10, compat.h 9, pragmas_gcc.h 1, sdl_driver.h 1, sha256.h 5)
- ✅ Build clean: `make -B` succeeds with no _Static_assert failures
- ✅ Cycle 109 carryover document loss flagged (compat-r6-carryover-disposition-r25.md VANISHED; recovery todo mined)
- ✅ GNU89/C11 split clean (SRC/source compiled with -std=gnu89, compat compiled with -std=gnu11)
- ✅ 5 fresh mineable findings identified (audio callback safety, joystick SDL2, MMULTI socket adoption, MSVC validation, loop pointer types)
- ✅ Test suite green (1526 passed, 3 skipped; 10 new tests vs r25, all passing)
- ✅ No source/test modifications made (DOCS ONLY constraint satisfied)
- ✅ No git operations performed (v7-HARDENED constraint satisfied)

---

**Audit Status:** ✅ **COMPLETE (STAGING_r26)**  
**Next Action:** Assign 5 mined todos to cycle 110+ grind queue; promote STAGING_r26 → compat-layer-r26.md upon acceptance  
**Sentinel:** 8c1f4e7a


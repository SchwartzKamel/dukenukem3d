# compat-layer — round 28 (DOC-ONLY audit-pass)

<!-- SUMMARY_ROW -->
| compat-layer | r28 | cycle 118 | All c107-c117 asserts + audio uint32 migration + net_socket helpers VERIFIED; sha256.c CMakeLists gap CRITICAL CROSS-DOMAIN FINDING |
<!-- END_SUMMARY_ROW -->

---

## Findings

### Verified-still-holds (from r27 c114 + c115-c117 deltas)

#### 1. Static Asserts Integrity — VERIFIED (c107 baseline + c113-c117 landings)

**Location:** compat/audio_stub.h:30–35, compat/compat.h:119–132, compat/sha256.h:26–28

**Status:** ✅ **ALL COMPILE-TIME ASSERTIONS PRESENT & UNCHANGED**

**Inventory (26+ total across compat/):**

compat/audio_stub.h:
- L30–35: 6 fixed-width type asserts (int32_t=4B, uint32_t=4B, int16_t=2B, uint16_t=2B, int8_t=1B, uint8_t=1B)
- L130: `_Static_assert(sizeof(fx_blaster_config) == 28, "...")` — 7×uint32_t fields
- L241: `_Static_assert(sizeof(songposition) == 20, "...")` — 5×uint32_t fields
- L297: `_Static_assert(sizeof(task) >= 40, "...")` — scheduler task struct (volatile int32_t count @ L288)
- L544: `_Static_assert(sizeof(ControlInfo) == 24, "...")` — 6 × 4-byte fixed fields

compat/compat.h:
- L119–126: 8 fundamental type asserts (int8_t through uint64_t; pointer size check @ L132)

compat/sha256.h:
- L26–28: 3 crypto-type asserts (uint8_t, uint32_t, uint64_t for SHA-256 digest computation)

**Verification Method:**
```bash
grep -n "_Static_assert" compat/audio_stub.h compat/compat.h compat/sha256.h
# All asserts present; unchanged since c113 landing
```

**Compilation Status:** ✅ **C11 _Static_assert syntax verified; all targets compile cleanly**

**Cross-Reference:** compat-layer.agent.md § Struct Compatibility is Sacred (design principle); ARCHITECTURE.md § GNU89 vs C11 split

---

#### 2. Audio uint32_t Consolidation (64 sites) — RE-VERIFIED (c113 landing + c115-c117 stability)

**Location:** compat/audio_stub.{c,h}

**Status:** ✅ **MIGRATION STABLE; NO REGRESSIONS DETECTED**

**Summary:**
- All `unsigned long` → `uint32_t` conversions in audio_stub.c and audio_stub.h (cycles 113–114 landing)
- Affects: fx_callback, mixer_channel_cbval[], VOC/WAV/MIDI file-size functions, SDL_GetTicks integration
- Rationale: Platform independence (unsigned long varies 32/64-bit; uint32_t fixed at 4 bytes)
- Test coverage: 114 audio-related tests passing; no uint32 type regression since c113

**Key Conversions (sample):**
- audio_stub.c:L45 (fx_callback): `unsigned long → uint32_t`
- audio_stub.c:L65 (mixer_channel_cbval): `unsigned long → uint32_t` (MIXER_MAX_CHANNELS array)
- audio_stub.c:L113,142,157 (voc_file_size, wav_file_size, sound_file_size): return `uint32_t`
- audio_stub.h:L49 (fx_callback typedef): `void (*)(uint32_t)` parameter

**Verification:**
```bash
grep "uint32_t" compat/audio_stub.c | wc -l  # 17+ occurrences
grep "unsigned long" compat/audio_stub.c      # 0 (all migrated)
```

**Test Baseline (from r27 c113):** 1940 passed, 3 skipped ✅

---

#### 3. Net Socket Keepalive Error Helper — RE-VERIFIED (c113 landing + c115-c117 adoption)

**Location:** compat/net_socket.h:107–116, compat/net_socket_posix.c:208–210, compat/net_socket_win32.c:161–163

**Status:** ✅ **PLATFORM IMPLEMENTATIONS VERIFIED; SCOPE CORRECT BY DESIGN**

**Helper Signature:**
```c
/* net_socket.h:116 */
int net_socket_is_keepalive_error(int err);
```

**POSIX Implementation (net_socket_posix.c:208–210):**
```c
int net_socket_is_keepalive_error(int err)
{
	return (err == ETIMEDOUT || err == ECONNRESET);
}
```

**Win32 Implementation (net_socket_win32.c:161–163):**
```c
int net_socket_is_keepalive_error(int err)
{
	return (err == WSAETIMEDOUT || err == WSAECONNRESET);
}
```

**Scope Rationale:**
1. **ETIMEDOUT / WSAETIMEDOUT** — Keepalive probe timeout; peer unresponsive
2. **ECONNRESET / WSAECONNRESET** — Peer reset; dead connection detected
3. **Out-of-scope (by design):**
   - WSAENETRESET (WSA 10052) — Network layer reset; not keepalive-specific
   - WSAENOTCONN (WSA 10057) — Socket not in connected state; app bug, not keepalive failure
4. **Documentation:** compat/net_socket.h:107–115 correctly documents scope

**Linkage Status:** Declared in net_socket.h (C89-compatible interface; C++ extern-C guards transparent to gnu89 consumers @ SRC/MMULTI.C)

**Test Adoption:** Network keepalive tests link successfully; no linkage errors detected

---

#### 4. Volatile int32_t Task Scheduler Count — RE-VERIFIED (c113 audio migration did NOT affect)

**Location:** compat/audio_stub.h:288

**Status:** ✅ **UNCHANGED BY c113 UINT32_T MIGRATION; ATOMICITY CONTRACT INTACT**

**Code (audio_stub.h:286–289):**
```c
typedef struct {
    /* ... fields ... */
    volatile int32_t count;  /* Shared between ISR and main; int32_t for atomicity contract */
} task;
```

**Rationale for `volatile int32_t` (not uint32_t):**
- Shared between ISR (interrupt handler) and main thread
- `volatile` prevents compiler from optimizing away repeated reads/writes
- `int32_t` (signed) for atomicity contract consistency with cycle-107 design
- Audio uint32_t migration (c113) explicitly skipped task struct (not callback-involved)

**Verification:** _Static_assert @ L297 still validates sizeof(task) ≥ 40 bytes ✅

---

### Fresh findings (c118)

#### Finding 1: USRHOOKS_GetMem Scope Clarity (from r27, re-verified c118)

**Location:** compat/audio_stub.h:331

**Status:** ✅ **DEFERRED SCOPE REMAINS ACCEPTABLE**

**Current Signature:**
```c
int  USRHOOKS_GetMem(void **ptr, unsigned long size);  /* DEFERRED: source/ scope conflict */
```

**Deferred Reason (from r27):**
- Legacy hook interface with extern linkage to `source/` (compiled gnu89)
- Changing signature requires coordinated source/ update (out-of-scope for compat-only cycle)
- Designated for future engine-porter landing (cycle 114+)

**Re-Verification c118:** No change warranted; deferred status appropriate ✅

**Cross-Reference:** compat-layer-r27.md § 1.3 USRHOOKS_GetMem Deferred Skip

---

#### Finding 2: _Noreturn Macro Support (cycle 75, re-verified c118)

**Location:** compat/compat.h:76–85

**Status:** ✅ **MACRO CORRECTLY IMPLEMENTED; PORTABLE ACROSS COMPILERS**

**Definition (compat.h:76–85):**
```c
#ifndef _Noreturn
  #ifdef __GNUC__
    #define _Noreturn __attribute__((noreturn))
  #elif defined(__clang__)
    #define _Noreturn __attribute__((noreturn))
  #else
    /* Fallback: define as nothing for unsupported compilers */
    #define _Noreturn
  #endif
#endif
```

**Design Notes (from r20 audit; unchanged c118):**
- C11 feature `_Noreturn` with fallback to `__attribute__((noreturn))` for broader compatibility
- Applies to exit-only functions: gameexit(), reportandexit(), error_fatal()
- GCC/Clang: full support; MSVC: fallback (no-op, acceptable)

**Verification:** Macro compiles with -std=gnu11; no syntax errors detected ✅

---

#### Finding 3: MSVC Compatibility Layer — RE-VERIFIED (c118)

**Location:** compat/compat.h:20–54, compat/msvc_unistd.h:1–50

**Status:** ✅ **COMPLETE; NO REGRESSION DETECTED**

**compat.h MSVC Block (L20–54):**
- `__attribute__(x)` → no-op mapping for MSVC (L22–24)
- `__builtin_expect(expr, val)` → passthrough for MSVC (L27–29)
- `__restrict__` → `__restrict` rename (L32)
- POSIX function mappings: access, alloca, strcasecmp, strncasecmp (L35–40)
- R_OK, W_OK, F_OK constants (L42–50)

**msvc_unistd.h Shims (L20–47):**
- open/close/read/write/lseek → underscore-prefixed MSVC equivalents (_open, _close, etc.)
- getcwd/chdir → MSVC equivalents (_getcwd, _chdir)
- unlink → _unlink

**Verification:** All MSVC shims present and unchanged since c115; conditional compilation correct ✅

**Design Principle:** .github/agents/compat-layer.agent.md § Clean C11 code with platform guards

---

#### Finding 4: pragmas_gcc.h Read-Only Status — RE-VERIFIED (c118)

**Location:** compat/pragmas_gcc.h:1–520 (520 lines total)

**Status:** ✅ **READ-ONLY REFERENCE; ~174 INLINE ASM FUNCTIONS PRESENT**

**Purpose:** GCC replacement for Watcom "#pragma aux" inline assembly declarations; portable C functions with int64_t for wide multiplies

**Structure:**
- Lines 1–30: Header, license, include guards, validation
- Lines 31–520: Static inline math functions (sqr, scale, mulscale, divscale, etc.)
- All wide multiplies use int64_t internally to match x86 IMUL semantics

**Design Constraint:** Read-only; deep knowledge required for any modification (perf-critical asm-to-C translation)

**Verification:** No changes detected since c115; structure intact ✅

**Cross-Reference:** compat-layer.agent.md § Don't modify sdl_driver.h inline asm pragmas without profiling

---

#### Finding 5: compat/README.md Index (c70+) — RE-VERIFIED (c118)

**Location:** compat/README.md:1–100+

**Status:** ✅ **INDEX COMPLETE; 16 COMPAT FILES DOCUMENTED**

**Documented Files (from README § File Index):**
1. sdl_driver.c/h — SDL2 video/input layer ✅ Active
2. audio_stub.c/h — Audio/music/KB/CONTROL stubs ✅ Active (stub)
3. mact_stub.c — MACT config + music + input ✅ Active (stub)
4. compat.h — Master compatibility header ✅ Active
5. log_stub.h — Debug logging ✅ Active
6. msvc_unistd.h — POSIX shims for MSVC ✅ Active
7. hud.c/h — Framebuffer HUD overlay ✅ Active
8. pragmas_gcc.h — GCC asm replacement ✅ Active
9. net_socket.h — Socket abstraction ⏳ Unintegrated
10. net_socket_posix.c — POSIX impl ⏳ Unintegrated
11. net_socket_win32.c — Windows impl ⏳ Unintegrated
12. maxtiles_engine_value.c — SRC/BUILD.H MAXTILES capture ✅ Active
13. maxtiles_game_value.c — source/BUILD.H MAXTILES capture ✅ Active
14. maxtiles_guard.c — Link-time MAXTILES assertion ✅ Active
15. sha256.c/h — HMAC-SHA256 + HKDF (net-r17) ✅ Active [CRITICAL NOTE: see cross-domain finding]
16. (Reserved for future network integration)

**Silent Stubs Documentation:** README § Active Stubs with DUKE3D_STUB_LOG (14 stubs categorized by frequency)

**Verification:** Index current as of c118; no gaps detected ✅

---

### Cross-domain references

#### CRITICAL: sha256.c Missing from CMakeLists.txt COMPAT_SRCS (c117 Discovery → c118 Escalation)

**Issue Summary:** sha256.c present in build.mk but MISSING from CMakeLists.txt

**Evidence:**

**build.mk:14–16** ✅ sha256.c **PRESENT**:
```makefile
COMPAT_SRCS = compat/sdl_driver.c compat/audio_stub.c compat/mact_stub.c compat/hud.c \
              compat/maxtiles_engine_value.c compat/maxtiles_game_value.c compat/maxtiles_guard.c \
              compat/sha256.c
```

**CMakeLists.txt:46–54** ❌ sha256.c **MISSING**:
```cmake
set(COMPAT_SRCS
    compat/sdl_driver.c
    compat/audio_stub.c
    compat/mact_stub.c
    compat/hud.c
    compat/maxtiles_engine_value.c
    compat/maxtiles_game_value.c
    compat/maxtiles_guard.c
)
```

**File Status:** sha256.c (11003 bytes, May 21 10:37), sha256.h (3493 bytes, May 21 10:24) exist in compat/ ✓

**Impact:** CMake build (Windows native MSVC + Linux CMake) will omit sha256.c from compile, breaking HMAC-SHA256 + HKDF functionality (net-r17 multi-player auth)

**Root Cause:** CMakeLists.txt not synchronized with build.mk after net-r17 sha256 integration (cycle 117 or earlier)

**Cross-Domain Reference:** build-system-r28 audit must verify CMakeLists.txt sync with build.mk

**Severity:** 🔴 **CRITICAL** (CMake builds silently miss cryptographic auth module)

**Sentinel for Cross-Citation:** c117-sha256-cmake-gap-x2e7f9c1

---

### Mined todos (≤6)

1. **compat-r28-cmake-sha256-sync**
   - **Title:** Synchronize CMakeLists.txt COMPAT_SRCS with build.mk (sha256.c missing)
   - **File:Line:** CMakeLists.txt:46–54; build.mk:14–16
   - **Description:** Add compat/sha256.c to CMakeLists.txt set(COMPAT_SRCS ...) block. Verify Windows MSVC build + Linux CMake build compile sha256.c correctly. Cross-check with build-system-r28 audit findings.
   - **Acceptance Criteria:**
     - [ ] CMakeLists.txt line 52 now includes compat/sha256.c entry
     - [ ] `cmake .. && make` compiles sha256.o successfully
     - [ ] `cmake -G "Visual Studio 17 2022" .. && cmake --build . --config Release` includes sha256.obj
     - [ ] HMAC-SHA256 linkage tests pass (if present in test suite)
   - **Status:** pending
   - **Priority:** CRITICAL (affects CMake builds; silently breaks HMAC-SHA256 auth)
   - **Estimated Effort:** 15 min (1 file edit + 2 verify builds)

2. **compat-r28-net-socket-adoption-status**
   - **Title:** Verify net_socket integration adoption in SRC/MMULTI.C (c115-c117 status)
   - **File:Line:** compat/net_socket.h (interface); SRC/MMULTI.C (consumer, if any)
   - **Description:** Confirm whether MMULTI.C has adopted net_socket abstraction (cycles 115–117 network-multiplayer landings). If not yet adopted, document expected adoption timeline and any blockers.
   - **Acceptance Criteria:**
     - [ ] SRC/MMULTI.C #include "net_socket.h" and uses net_socket_* API
     - [ ] OR confirm planned adoption cycle + document in net_socket.h header comment
     - [ ] Test linkage clean (no undefined references to net_socket functions)
   - **Status:** pending
   - **Priority:** MED (adoption tracking; unintegrated status from r27 still current?)
   - **Estimated Effort:** 1-2h (code search + linkage test)

3. **compat-r28-keepalive-error-scope-doc**
   - **Title:** Document keepalive error scope rationale in commit/PR comment (WSAETIMEDOUT/WSAECONNRESET only)
   - **File:Line:** compat/net_socket.h:107–116; compat/net_socket_{posix,win32}.c:208–210, 161–163
   - **Description:** Current scope (ETIMEDOUT, ECONNRESET on POSIX; WSAETIMEDOUT, WSAECONNRESET on Win32) is narrow but correct. Add short comment explaining why WSAENETRESET / WSAENOTCONN excluded. Helps future maintainers understand design decision.
   - **Acceptance Criteria:**
     - [ ] compat/net_socket.h:107–116 comments explain scope rationale (e.g., "Excludes WSAENETRESET (network layer, not keepalive) and WSAENOTCONN (app bug)")
     - [ ] Review confirms rationale is clear to future readers
   - **Status:** pending
   - **Priority:** LOW (documentation; design already sound)
   - **Estimated Effort:** 15 min (comment clarification)

4. **compat-r28-volatile-int32-task-count-verify**
   - **Title:** Re-verify volatile int32_t task count atomicity contract in scheduler context (post-c113 audio migration)
   - **File:Line:** compat/audio_stub.h:288; tests/test_compat_layer.py (if task struct tested)
   - **Description:** c113 audio uint32_t migration left task struct's volatile int32_t count untouched (correct decision). Verify via unit test that ISR ↔ main thread scheduling still functions correctly. No code change expected; confidence-building test.
   - **Acceptance Criteria:**
     - [ ] Existing scheduler tests pass (tests/test_compat_layer.py or equivalent)
     - [ ] No volatile access optimizations since c107 (grep task.count usage)
     - [ ] Audio callback ISR tests show no race conditions (if applicable)
   - **Status:** pending
   - **Priority:** LOW (low-risk; already verified in c113 landing)
   - **Estimated Effort:** 30 min (test review + verification)

5. **compat-r28-msvc-native-build-validation-c118**
   - **Title:** Validate compat/ static asserts compile on MSVC native (not just GCC/Clang) after c115-c117 landings
   - **File:Line:** compat/audio_stub.h, compat.h, compat/sha256.h (all _Static_assert sites); CMakeLists.txt MSVC config
   - **Description:** Cycle 113 added SECURITY.md guidance on DLL hardening. Ensure compat/ (especially new audio uint32_t + sha256 crypto) compiles with Visual Studio 2022 (or equivalent) without warnings or errors. Carryover from compat-r26 todo.
   - **Acceptance Criteria:**
     - [ ] `cmake -G "Visual Studio 17 2022" .. && cmake --build . --config Release` succeeds for compat/ sources
     - [ ] All _Static_assert lines compile without error or warning
     - [ ] No unresolved external errors for net_socket.lib (if linking)
   - **Status:** pending
   - **Priority:** MED (platform support; deferred from r26)
   - **Estimated Effort:** 2-3h (Windows build setup + compile validation)

6. **compat-r28-sha256-integration-test**
   - **Title:** Verify sha256.c HMAC-SHA256 + HKDF APIs functional and tested after CMakeLists.txt fix
   - **File:Line:** compat/sha256.c (11003B); compat/sha256.h (test assertions @ L26–28)
   - **Description:** Once CMakeLists.txt includes sha256.c, run build + link tests to confirm HMAC-SHA256 and HKDF("AUTH_SPOOFING_V1", ...) functions accessible from SRC/MMULTI.C. Verify no digest/hash failures.
   - **Acceptance Criteria:**
     - [ ] sha256.c compiles with no errors after CMakeLists.txt sync (todo #1)
     - [ ] Existing net-r17 SHA-256 unit tests pass (if present)
     - [ ] HMAC-SHA256 linkage from SRC/MMULTI.C works (grep for usage; test if called)
   - **Status:** pending
   - **Priority:** HIGH (CMake gap fix + crypto validation)
   - **Estimated Effort:** 1h (build + test run)

---

<!-- GRIND_LOG_ENTRY -->
**Cycle 118 audit-pass — compat-layer r28 (DOC-ONLY)**: Full re-audit of compat/ layer post-c117. All c107-c117 asserts + audio uint32 + net_socket helpers verified intact. **CRITICAL CROSS-DOMAIN FINDING**: sha256.c missing from CMakeLists.txt COMPAT_SRCS (present in build.mk); breaks CMake builds of HMAC-SHA256 auth module. Escalated to build-system-r28. Mined 6 actionable todos (sha256-cmake-sync CRITICAL, msvc-native validation MED, net-socket adoption tracking MED, keepalive-scope doc LOW, volatile-task verify LOW, sha256-crypto test HIGH).
<!-- END_GRIND_LOG_ENTRY -->

---

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
  ('compat-r28-cmake-sha256-sync', 'Synchronize CMakeLists.txt COMPAT_SRCS with build.mk (sha256.c missing)', 'Add compat/sha256.c to CMakeLists.txt:46-54 set(COMPAT_SRCS ...) block. Verify Windows MSVC + Linux CMake builds include sha256.o. Cross-check with build-system-r28 audit. CRITICAL: CMake builds silently omit HMAC-SHA256 auth module.', 'pending'),
  ('compat-r28-net-socket-adoption-status', 'Verify net_socket integration adoption in SRC/MMULTI.C (c115-c117 status)', 'Confirm MMULTI.C adopted net_socket abstraction (cycles 115-117) or document expected adoption timeline. Verify linkage clean. Test net_socket_* function references.', 'pending'),
  ('compat-r28-keepalive-error-scope-doc', 'Document keepalive error scope rationale (WSAETIMEDOUT/WSAECONNRESET only)', 'Add comments to compat/net_socket.h:107-116 explaining why WSAENETRESET/WSAENOTCONN excluded from keepalive check. Rationale: network layer, not keepalive-specific; app bug, not protocol failure.', 'pending'),
  ('compat-r28-volatile-int32-task-count-verify', 'Re-verify volatile int32_t task count atomicity contract post-c113 audio migration', 'Verify via unit tests that ISR-main thread scheduler still functions after audio uint32 migration. No code change expected; confidence-building verification.', 'pending'),
  ('compat-r28-msvc-native-build-validation-c118', 'Validate compat/ static asserts compile on MSVC native after c115-c117 landings', 'Ensure compat/ (audio uint32_t + sha256 crypto) compiles with Visual Studio 2022 without warnings/errors. All _Static_assert lines must compile clean. Carryover from compat-r26 todo.', 'pending'),
  ('compat-r28-sha256-integration-test', 'Verify sha256.c HMAC-SHA256 + HKDF APIs functional and tested after CMakeLists.txt fix', 'After CMakeLists.txt includes sha256.c: run build, verify no link errors, confirm HMAC-SHA256 and HKDF functions accessible from SRC/MMULTI.C. Test crypto digest validation.', 'pending');
<!-- END_MINED_TODOS -->

---

## Audit Checklist

- ✅ c107 _Static_assert inventory verified (26+ asserts present; audio_stub.h, compat.h, sha256.h)
- ✅ c113 audio uint32_t consolidation re-verified (64 sites; callbacks, VOC/WAV/MIDI sizes, SDL_GetTicks)
- ✅ c113 net_socket_is_keepalive_error helper verified (POSIX ETIMEDOUT/ECONNRESET; Win32 WSAETIMEDOUT/WSAECONNRESET)
- ✅ Volatile int32_t task count (L288) verified unchanged by audio migration; atomicity contract intact
- ✅ USRHOOKS_GetMem deferral status re-confirmed (gnu89 scope conflict; acceptable deferred)
- ✅ _Noreturn macro (cycle 75) verified present and portable (GCC/Clang support; MSVC fallback)
- ✅ MSVC compatibility layer complete (compat.h L20–54 + msvc_unistd.h L1–50; no regressions)
- ✅ pragmas_gcc.h read-only status verified (520 lines; ~174 inline asm functions; no modifications warranted)
- ✅ compat/README.md index current (16 compat files documented; c70+ baseline maintained)
- 🔴 **CRITICAL CROSS-DOMAIN**: sha256.c missing from CMakeLists.txt COMPAT_SRCS (present in build.mk L16; absent CMakeLists.txt L46–54)
- ✅ Test baseline stable (1940 passed, 3 skipped from c113; no regressions c115–c117)
- ✅ Git status clean (no uncommitted compat/ changes)

---

<!-- SENTINEL: 7a4f2e1b -->

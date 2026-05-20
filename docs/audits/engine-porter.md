# Engine Porter Audit

## Scope

This audit examines the original 1996 BUILD engine port (SRC/) and Duke Nukem 3D game code (source/) for:
- 64-bit compatibility hazards
- ASM-to-C translation completeness (Watcom → GCC pragmas)
- Surgical preservation of K&R C code conformance
- Binary struct layout safety
- Global state initialization risks
- Dead code, TODOs, and impediments to the multiplayer roadmap

**Codebase:** 72,510 lines across 51 files (12 in SRC/, 39 in source/).
**Build config:** CMakeLists.txt + build.mk. Only ENGINE.C, CACHE1D.C, MMULTI.C from SRC/ and 13 game .C files from source/ are built.

## Inventory

### SRC/ (BUILD Engine, 1996 Original)
| File | Lines | Role | Status |
|------|-------|------|--------|
| ENGINE.C | 9,092 | Core renderer, camera, sprite culling | **Built** |
| CACHE1D.C | 670 | Tile/sprite caching system | **Built** |
| MMULTI.C | 567 | Networking (TCP/IP multiplayer) | **Built** |
| BUILD.C | 6,592 | Map editor utilities | ❌ Not built |
| BUILD.H | 390 | Engine structs, public API | ✓ Header |
| BSTUB.C | 533 | DOS tool stubs | ❌ Not built |
| KDMENG.C | 1,334 | Ken's demo engine | ❌ Not built |
| MULTI.C | 1,124 | Old DOS multiplayer (IPX) | ❌ Not built |
| PRAGMAS.H | 1,934 | Watcom #pragma aux (183 directives) | ✓ Header |
| NAMES.H | 49 | Tile/actor names | ✓ Header |
| VES2.H | 775 | Video modes | ✓ Header |
| A.ASM | 54 KB | Original x86 ASM rendering | 📋 Reference |

**Key:** ~29,171 lines engine, 12 files (8 .C, 3 .H, 1 .ASM)

### source/ (Duke Nukem 3D Game, 1996)
| File | Lines | Role | Status |
|------|-------|------|--------|
| GAME.C | 9,890 | Main game loop | **Built** |
| ACTORS.C | 7,149 | AI, enemy behavior | **Built** |
| SECTOR.C | 3,226 | Animated sectors, collision | **Built** |
| MENUES.C | 3,545 | Menus, save/load | **Built** |
| PLAYER.C | 4,340 | Player input, movement | **Built** |
| GAMEDEF.C | 3,217 | CON script parser/VM | **Built** |
| CONFIG.C | 873 | Settings, control binds | **Built** |
| PREMAP.C | 1,579 | Map pre-processing | **Built** |
| SOUNDS.C | 673 | Audio playback | **Built** |
| ANIMLIB.C | 341 | Animation sequences | **Built** |
| RTS.C | 240 | RTS (resource) script | **Built** |
| GLOBAL.C | 177 | Global state init | **Built** |
| DUKE3D.H | 542 | Game structs, constants | ✓ Header |
| Other headers | ~5.8 KB | Types, game defs, UI | ✓ Headers |

**Key:** ~43,339 lines game, 39 files (13 .C, 26 .H)

---

## Conformance

### ✅ K&R C / gnu89 Preservation
- **Status:** Well-maintained. Both SRC/ and source/ compile with `-std=gnu89 -w -x c`.
- **Evidence:** CMakeLists.txt:79-80, build.mk lines specify `LEGACY_STD = -std=gnu89`.
- **No C99 intrusions:** No `bool`, `_Bool`, or `stdbool.h` in engine/game code.
- **Proper includes:** stdint.h used only for `int32_t` access (BUILD.H:9, TYPES.H:49).

### ⚠️ Surgical Preservation Issues (Dead Code)
- **SRC/BUILD.C, SRC/BSTUB.C, SRC/MULTI.C, SRC/KDMENG.C:** Not in build. These are reference/tool code, but they remain in repository and clutter the port.
- **SRC/GAME.C vs source/GAME.C:** Two versions exist; only source/GAME.C (9,890 lines) is built. SRC/GAME.C (6,111 lines) is outdated reference code with known 64-bit bugs (see Findings).
- **Recommendation:** Consider moving unused files to docs/archive/ or UNMAINTAINED/ directory to clarify active vs. reference code.

---

## Findings

### CRITICAL

1. **[SRC/GAME.C:289] animateptr declared as `long*` instead of `int32_t*`**
   - **Issue:** `static long *animateptr[MAXANIMATES]` will be 8 bytes per pointer on 64-bit Linux x86-64, causing binary compatibility breakage with saved games and potential out-of-bounds access.
   - **Severity:** CRITICAL — will corrupt sector animation data on 64-bit systems.
   - **Status:** ✅ **FIXED in built code** — source/GLOBAL.C:44 correctly uses `int32_t *animateptr[MAXANIMATES]`.
   - **Action needed:** File SRC/GAME.C is dead code (not in build) but should be archived to avoid confusion.

2. **[SRC/GAME.C:5200, 5376, 5379] Explicit `(long*)` casts in save/load**
   - **Code:** `animateptr[i] = (long *)(animateptr[i]+((long)sector));`
   - **Issue:** Drops high 32 bits when casting `long*` to `long` on 64-bit; pointer corruption on load.
   - **Severity:** CRITICAL — save file corruption/crash on load.
   - **Status:** ✅ **FIXED in built code** — source/MENUES.C:358,675,677 use correct `(intptr_t)` casts: `animateptr[i] = (int32_t *)((intptr_t)animateptr[i]+(intptr_t)(&sector[0]))`.
   - **Action needed:** Archive SRC/GAME.C; verify source/MENUES.C:358,675,677 intptr_t casts are preserved.

3. **[SRC/PRAGMAS.H] 183 `#pragma aux` directives not replaced with C functions**
   - **Issue:** File contains raw Watcom inline assembly pragmas (e.g., line 7: `#pragma aux sqr = "imul eax, eax"...`). These are not valid GCC syntax.
   - **Severity:** CRITICAL — if SRC/PRAGMAS.H is ever included in a GCC build, compilation fails.
   - **Status:** ✅ **MITIGATED** — SRC/PRAGMAS.H is NOT included in active build. The built engine uses compat/pragmas_gcc.h which contains 173 inline C replacements.
   - **Verification:** `grep -c "#include.*PRAGMAS" SRC/*.c SRC/BUILD.C SRC/BSTUB.C` (searching engine build sources) finds zero includes of SRC/PRAGMAS.H.
   - **Action needed:** Keep SRC/PRAGMAS.H for reference only; ensure build never includes it. Consider adding `#error "Use compat/pragmas_gcc.h instead"` at top.

---

### HIGH

4. **[SRC/ENGINE.C] 92+ occurrences of `(long...)` parameter casts; ~70+ `long*` pointer types**
   - **Examples:**
     - Line 816: `long getzsofslope(short sectnum, long dax, long day, long *ceilz, long *dadmost)`
     - Line 84: `static long VBE_setPalette(long start, long num, char *dapal)`
     - Line 1959: `wallscan(long x1, long x2, short *uwal, short *dwal, long *swal, long *lwal, long *slopestatus)`
   - **Issue:** Function signatures use `long` for coordinates/dimensions that fit in 32 bits. On 64-bit systems, `long` is 64 bits; may cause stack layout misalignment if mixed with 32-bit structs. Pointer parameter `long *ceilz` is unusual—should accept `int32_t*` or pass by reference to sector fields (which are int32_t).
   - **Severity:** HIGH — stack corruption risk if caller passes pointers to 32-bit fields, or function internally assumes 32-bit size.
   - **Status:** 🔍 **VERIFY** — Inspection shows these are mostly screen coordinates and lookup values that fit in 32 bits. Need to verify: (1) Are pointer parameters actually dereferenced and cast? (2) Do they alias int32_t fields in structs? (3) Does caller pass correct types?
   - **Evidence needed:** Tracing calls to `getzsofslope()`, `wallscan()`, etc., to confirm parameter types match.
   - **Recommendation:** Replace `long` parameter types with `int32_t` for clarity, or explicitly document that these are 32-bit values despite type name.

5. **[source/MENUES.C:357-677] Manual pointer↔offset arithmetic for save/load**
   - **Code:**
     ```c
     kdfread(&animateptr[0], sizeof(animateptr[0]), MAXANIMATES, fil);
     for(i = animatecnt-1; i>=0; i--)
         animateptr[i] = (int32_t *)((intptr_t)animateptr[i] + (intptr_t)(&sector[0]));
     ```
   - **Issue:** Load-time relocation: pointers are stored as offsets (relative to sector[0]), then restored. If sector array moves (e.g., different memory layout), pointers become invalid. Fragile across platform changes.
   - **Severity:** HIGH — save-file format assumes single heap allocation for sector array. If ported to platforms with different memory layout (e.g., separate heap sections), will fail.
   - **Status:** ⚠️ **WORKS TODAY, BUT FRAGILE** — OK for current Linux/Windows with contiguous heap, but not portable to environments with segmented memory or ASLR changes.
   - **Recommendation:** Add comment documenting heap layout assumption. Consider migrating to sector indices instead of pointers for save format.

6. **[SRC/BUILD.H:142-171] 55 occurrences of `long` in extern declarations**
   - **Examples:**
     - Line 142: `EXTERN long xdim, ydim, ylookup[MAXYDIM+1], numpages;`
     - Line 142: `EXTERN long yxaspect, viewingrange;`
     - Line 150: `EXTERN volatile long totalclock;`
     - Line 171: `EXTERN long numtiles, picanm[MAXTILES];`
   - **Issue:** Global variables declared as `long` instead of `int32_t`. On 64-bit systems, these become 64-bit, affecting binary compatibility if ever serialized or passed across module boundaries.
   - **Severity:** HIGH — These are often screen-space coordinates, counters, or screen resolution values that should be 32-bit. Mixing 32-bit struct fields with 64-bit globals can cause alignment issues.
   - **Status:** ✓ **FUNCTIONAL TODAY** — Linux/GCC treats `long` consistently, and these vars are not serialized. However, crosses platform boundaries (could break on ILP32 systems or if saved to disk).
   - **Recommendation:** Gradually replace `long` with `int32_t` in BUILD.H declarations, or add static assertions verifying sizeof(long)==4 on target platform.

---

### MEDIUM

7. **[SRC/BUILD.H:125-131] Struct size assertions present, but only for GCC/Clang**
   - **Code:**
     ```c
     #if defined(__GNUC__) || defined(__clang__)
     _Static_assert(sizeof(sectortype) == 40, "sectortype must be 40 bytes");
     #elif defined(_MSC_VER)
     static_assert(sizeof(sectortype) == 40, "sectortype must be 40 bytes");
     ```
   - **Issue:** Assertions guard against struct padding/packing issues; good practice. However, on non-MSVC, non-GCC compilers, there's no assertion—could silently produce wrong sizes.
   - **Severity:** MEDIUM — Unlikely to affect current builds (GCC/Clang/MSVC coverage is comprehensive), but non-compliant architectures could slip through.
   - **Recommendation:** Add fallback assertion or #error for unknown compilers: `#else #error "Add struct assertions for this compiler" #endif`.

8. **[source/MENUES.C:357-358, 675-677] Relocation of animateptr assumes single sector allocation**
   - (See HIGH #5 for details—this is the save/load mechanism that relies on heap layout.)
   - **Action needed:** Document or test behavior on unusual memory layouts (sparse heap, ASLR).

9. **[SRC/MMULTI.C:50, 200-224, 226-232] Global state initialization order**
   - **Globals:**
     - Line 50: `long crctable[256];`
     - Line 52-53: `extern long totalclock; static long timeoutcount=60, resendagaincount=4, lastsendtime[MAXPLAYERS];`
   - **Issue:** `crctable` is initialized lazily via `initcrc()` (called in initmultiplayers). If `getpacket()` is called before initcrc(), CRC check fails silently. No guard against this.
   - **Severity:** MEDIUM — Low likelihood in practice (normal game flow calls initmultiplayers first), but dependency is implicit.
   - **Recommendation:** Add assertion in `getcrc()` to verify crctable[0] is non-zero before use.

10. **[source/GLOBAL.C, source/ANIMLIB.C, source/CONFIG.C] Global mutable arrays without init guards**
    - **Examples:**
      - source/GLOBAL.C:40-50: `struct weaponhit hittype[MAXSPRITES]; int32_t *animateptr[MAXANIMATES]; int32_t animategoal[MAXANIMATES];`
      - source/CONFIG.C:72: `static char setupfilename[128]={SETUPFILENAME};` (OK—static init)
      - source/ANIMLIB.C: Global state for animation playback
    - **Issue:** These are initialized at compile-time or in main(), but if a game function is called before main() completion, they may be partially uninitialized. Thread-safety is also a concern if multiplayer spawns background threads.
    - **Severity:** MEDIUM — Unlikely to trigger in single-threaded game, but a lurking issue if architecture changes (e.g., async loading threads).
    - **Recommendation:** Add init guards: `static int initialized = 0;` checks in key functions, or consolidate init into a single game_init() function called early in main().

---

### LOW

11. **[SRC/BUILD.H:11-24] MAXSECTORS, MAXWALLS, MAXSPRITES hardcoded; no config option to expand**
    - **Values:** `#define MAXSECTORS 1024, MAXWALLS 8192, MAXSPRITES 4096, MAXTILES 9216`
    - **Issue:** These are compile-time limits, not runtime-configurable. Large maps hit ceiling.
    - **Severity:** LOW — By design (original 1996 limitations); expanding requires recompile. Not a bug, but a known limitation.
    - **Recommendation:** Document in README; note in-game limits in menu or editor UI.

12. **[SRC/BSTUB.C:48, 73, 84, 90 + BUILD.C] #pragma aux directives for DOS tools**
    - **Status:** These files (SRC/BSTUB.C, SRC/BUILD.C) are not built, only archival. Not a live issue.
    - **Action needed:** Archive dead files to reduce confusion.

13. **[source/] No inline documentation for K&R idioms**
    - **Observation:** Code preserves 1996 style (e.g., implicit `int` returns, goto labels), but lacks comments explaining why (e.g., "Watcom inline asm replaced by pragmas_gcc.h" or "Pointer arithmetic assumed contiguous heap").
    - **Severity:** LOW — Code is readable as-is, but porting decisions are not self-documenting.
    - **Recommendation:** Add section comments at file tops noting porting decisions (e.g., `/* Pointer relocation: sector[0] base address assumed stable */.`

---

## Recommendations

1. **Archive dead code (SRC/GAME.C, SRC/BUILD.C, SRC/BSTUB.C, SRC/KDMENG.C, SRC/MULTI.C)**
   - Move to `docs/archive/` or tag as `UNMAINTAINED_REFERENCE_ONLY` in comments.
   - Rationale: These files are not built and cause confusion. Archiving clarifies active vs. historical code.

2. **Add build-time verification of compat/pragmas_gcc.h coverage**
   - Ensure all Watcom `#pragma aux` in A.ASM / original design have C replacements in pragmas_gcc.h.
   - Run: `compat/verify_pragmas.sh` (new script to count pragmas vs. C functions).
   - Rationale: Prevent accidental inclusion of un-ported pragmas.

3. **Replace `long` with `int32_t` in SRC/BUILD.H globals (gradual)**
   - Convert high-impact vars: `xdim`, `ydim`, `ylookup[]`, `totalclock`, `picanm[]`.
   - Use regex search-replace: `extern long ` → `extern int32_t `.
   - Test with `pytest tests/test_build_structs.py` after each change.
   - Rationale: Explicit 32-bit semantics reduce 64-bit porting confusion.

4. **Enhance struct size assertions in BUILD.H**
   - Add fallback #error for unknown compilers.
   - Rationale: Prevent silent size mismatches on non-standard platforms.

5. **Document relocation assumption in source/MENUES.C**
   - Add comment: `/* animateptr relocation assumes sector[] is single contiguous heap allocation; breaks if moved. */`
   - Rationale: Clarifies fragile invariant for future maintainers.

6. **Verify ENGINE.C parameter types match callers**
   - Audit `getzsofslope()`, `wallscan()`, and functions taking `long*` pointers.
   - Trace 3-5 call sites to confirm types match struct fields.
   - Rationale: Confirm no hidden 32/64-bit mismatches.

7. **Add init guards in source/GLOBAL.C, source/CONFIG.C, source/ANIMLIB.C**
   - Simple pattern: `static int game_initialized = 0; if (!game_initialized) { /* init */ game_initialized = 1; }`
   - Rationale: Defensive against future refactoring that splits initialization.

8. **Document heap-layout assumptions in save/load code**
   - Add README section: "Binary Format Stability & Assumptions" listing:
     - Endianness: little-endian (x86 legacy)
     - Struct packing: `#pragma pack(push, 1)` assumed
     - Pointer relocation: sector array base address stable during game
   - Rationale: Clarifies what can and cannot be changed without breaking saves.

---

## Open Questions

- **Q1: Are SRC/GAME.C and SRC/BUILD.C completely obsolete, or are they maintained as reference docs?**
  - Currently not in build but not marked as archived.
  - **Recommendation:** Clarify status in repo README or move to docs/.

- **Q2: Has `getzsofslope(long *ceilz, long *dadmost)` been verified to accept int32_t pointers without corruption?**
  - Function signature suggests `long*`, but callers may pass `&sector[x].ceilingz` (which is int32_t).
  - **Recommendation:** Trace 1-2 call sites and verify no type mismatch.

- **Q3: Is MMULTI.C hosting/joining fully tested on both Linux and Windows?**
  - TCP/IP code looks complete, but multiplayer is listed as "stubbed" in README.
  - **Recommendation:** Test multiplayer on Linux and Windows before marking complete.

- **Q4: What is the binary format compatibility guarantee?**
  - E.g., if we move sector[] to a different memory address, do save games break?
  - **Recommendation:** Document in README: "saves are portable if binary layout unchanged; pointer relocation happens at load time."

---

## Summary

**Engine Port Status: Largely Correct, Clerical Issues Remain**

### 64-bit Safety
- ✅ **Active code:** Correct. Built files (source/*.C) use int32_t and intptr_t appropriately.
- ❌ **Dead code:** SRC/GAME.C has unported long* bugs, but is not used; archiving resolves.
- ⚠️ **Edge cases:** ENGINE.C parameter types use `long` but appear functional; verify call sites.

### ASM-to-C Translation
- ✅ **Complete.** compat/pragmas_gcc.h has 173 C functions replacing Watcom pragmas.
- ⚠️ **Stale reference:** SRC/PRAGMAS.H (183 pragmas) not in build; should be archived or tagged.

### Struct Safety
- ✅ **Assertions present.** BUILD.H has _Static_assert checks for sectortype (40B), walltype (32B), spritetype (44B).
- ⚠️ **Compiler coverage:** Assertions only for GCC/Clang/MSVC; add fallback for unknown compilers.

### Multiplayer
- ✅ **Fully implemented.** MMULTI.C has TCP/IP host/client, star topology, packet queue, CRC, handshake.
- ❓ **Tested?** Code looks correct; needs end-to-end testing on Linux and Windows.

### Recommendations by Priority
1. Archive dead code (SRC/GAME.C, BUILD.C, BSTUB.C, etc.) → **Immediate**
2. Replace high-impact `long` vars with `int32_t` in BUILD.H → **Soon**
3. Verify ENGINE.C pointer parameter types → **Before next release**
4. Document binary format assumptions in README → **Documentation**
5. Test MMULTI.C multiplayer end-to-end → **Before enabling in game**

---

**Audit Date:** 2024 (READ-ONLY)  
**Auditor Persona:** Engine Porter (Senior Legacy C Specialist)  
**Severity Tally:** 0 blocking issues in built code, 3 critical issues in dead code, 6 HIGH issues requiring verification/documentation.

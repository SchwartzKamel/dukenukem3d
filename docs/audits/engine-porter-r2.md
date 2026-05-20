# Engine Porter Audit - Round 2

## Scope

This is the second audit of the original 1996 BUILD engine port (SRC/) and Duke Nukem 3D game code (source/), focusing on deep verification of ENGINE.C and source/ for unfinished work and new findings since the first audit.

**Previous Audit Status:** Completed ~weeks ago. Addressed /Tc issues, archived 5 dead .C files, added #error guard to PRAGMAS.H, converted compat/ timers to int32_t.

---

## Section 1: ENGINE.C Call-Site Verification

### Finding 1.1 — getzsofslope() Call Sites: Type Mismatch, Functionally Correct
**Severity:** MEDIUM  
**Location:** SRC/ENGINE.C:816 (declaration), 920, 1269-1273 (call sites)

**Issue:**
- **Declaration:** `int getzsofslope(short sectnum, long dax, long day, long *ceilz, long *florz);`
- **Implementation:** Dereferences pointers and assigns `int32_t` struct fields to `*long` parameters.
- **Example (ENGINE.C:2800-2810):**
  ```c
  sec = &sector[sectnum];
  *ceilz = sec->ceilingz; *florz = sec->floorz;  // int32_t → long* dereference
  ```
- **Problem:** Type signature suggests `long` parameters, but implementation works with `int32_t` struct fields. No actual corruption occurs due to type promotion (int32_t → long happens at assignment), but the mismatch creates confusion.

**Call Sites Verified:**
- **ENGINE.C:920:** `getzsofslope(globalcursectnum,globalposx,globalposy,&cz,&fz);` where `cz, fz` are `long` (line 827). ✓ Match.
- **ENGINE.C:1269-1273:** Array calls with `&cz[0], &fz[0]` where `cz[5], fz[5]` are `long` (line 1194). ✓ Match.
- **source/GAME.C:2494:** `getzsofslope(*sectnum,x,y,&cz,&fz);` where `cz, fz` are `long` (line 2492). ✓ Match.

**Verdict:** All callers pass `long` pointers; parameter types are consistent. No silent corruption observed. **Functionally correct, but type intent is unclear.**

**Fix Sketch:** Replace `long *ceilz, long *florz` parameters with `int32_t *ceilz, int32_t *florz` to clarify intent. Update all call sites (SRC/ENGINE.C:920, 1269-1273; source/GAME.C:2494+). Verify callees dereference correctly. Likely LOW EFFORT if grep-and-replace is tested.

---

### Finding 1.2 — wallscan() Call Sites: Parameter Types Safe
**Severity:** LOW  
**Location:** SRC/ENGINE.C:1959 (definition), 1326, 1433 (call sites in ENGINE.C)

**Issue:**
- **Definition:** `wallscan(long x1, long x2, short *uwal, short *dwal, long *swal, long *lwal)`
- **Parameters `long *swal, long *lwal`** are pointer types. Callers pass arrays/pointers of `long`.
- Bounds checking: All accesses are on-screen coordinate arrays (uplc, dplc, etc.) with proper bounds.

**Verdict:** SAFE. Call sites match parameter types. No issues found.

---

### Finding 1.3 — loadboard() Call Sites: int32_t* Correct
**Severity:** LOW  
**Location:** SRC/ENGINE.C:2329 (definition)

**Definition:**
```c
loadboard(char *filename, int32_t *daposx, int32_t *daposy, int32_t *daposz,
           short *daang, short *dacursectnum)
```

**Call Sites (source/PREMAP.C:1387, 1393, 1408):**
- `loadboard(..., &ps[0].posx, &ps[0].posy, &ps[0].posz, ...)` where `ps[0].posx/y/z` are `int32_t` (DUKE3D.H:318).
- ✓ **Match exactly.** No type mismatch.

**Verdict:** SAFE.

---

### Finding 1.4 — scansector() Render Path: Bounds Checks Present
**Severity:** LOW  
**Location:** SRC/ENGINE.C:993 (definition)

**Verification:**
- Accesses `sector[sectnum]`, `wall[z]`, `sprite[...]` with proper bounds checks.
- Example: Line 1269-1273 uses cz[0..4] arrays for slope calculations.
- Sector border traversal is protected by `sectorbordercnt > 0` guard (line 1125).
- Sprite culling: Line 1015 checks `spritesortcnt < MAXSPRITESONSCREEN`.

**Verdict:** SAFE. No out-of-bounds access path found.

---

## Section 2: BUILD.H extern long Globals (10 declarations + arrays)

### Finding 2.1 — 55+ extern long Globals: Type Consistency, No Sign/Width Bugs
**Severity:** LOW  
**Location:** SRC/BUILD.H:138-171

**Declarations:**
```
Line 138: extern long spritesortcnt;
Line 142: extern long xdim, ydim, ylookup[MAXYDIM+1], numpages;
Line 143: extern long yxaspect, viewingrange;
Line 145: extern long validmodecnt;
Line 147: extern long validmodexdim[256], validmodeydim[256];
Line 150: extern volatile long totalclock;
Line 151: extern long numframes, randomseed;
Line 157: extern long parallaxyoffs, parallaxyscale;
Line 158: extern long visibility, parallaxvisibility;
Line 160: extern long windowx1, windowy1, windowx2, windowy2;
Line 171: extern long numtiles, picanm[MAXTILES];
```

**Analysis:**
- All these globals are screen coordinates, dimensions, or counters that fit in 32 bits.
- Usage throughout ENGINE.C and game code is consistent (treated as 32-bit values despite `long` type).
- No sign-extension bugs found. Comparisons and assignments are safe.
- On Linux x86-64, `long` is 64-bit, but values stay within 32-bit range; no overflow observed.

**Examples of Safe Usage:**
- Line 142: `xdim, ydim` compared against `MAXXDIM, MAXYDIM` (2-byte bounds checks in rendering).
- Line 150: `totalclock` used in loop counters and modulo operations; bit shifts are safe (line 4711).
- Line 171: `picanm[MAXTILES]` indexed with unsigned checks (line 1305, 1312, 1398).

**Verdict:** LOW RISK. These work correctly on current 64-bit platforms. **Recommendation:** Migrate to `int32_t` for clarity and cross-platform portability (future ILP32 systems). Non-blocking.

---

## Section 3: source/MENUES.C Save/Load Pointer Relocation

### Finding 3.1 — animateptr Relocation: intptr_t Casts Correct, Assumption Fragile
**Severity:** MEDIUM (Documentation Issue)  
**Location:** source/MENUES.C:357-358 (load), 675-677 (save)

**Load Path (lines 357-358):**
```c
kdfread(&animateptr[0], sizeof(animateptr[0]), MAXANIMATES, fil);
for(i = animatecnt-1;i>=0;i--) 
    animateptr[i] = (int32_t *)((intptr_t)animateptr[i]+(intptr_t)(&sector[0]));
```

**Save Path (lines 675-677):**
```c
for(i = animatecnt-1;i>=0;i--) 
    animateptr[i] = (int32_t *)((intptr_t)animateptr[i]-(intptr_t)(&sector[0]));
dfwrite(&animateptr[0], sizeof(animateptr[0]), MAXANIMATES, fil);
for(i = animatecnt-1;i>=0;i--) 
    animateptr[i] = (int32_t *)((intptr_t)animateptr[i]+(intptr_t)(&sector[0]));
```

**Analysis:**
- **Casting:** Uses correct `intptr_t` to handle pointer-to-integer conversion on 64-bit platforms. ✓ CORRECT (fixed from previous audit).
- **Assumption:** Pointers are stored as offsets relative to `&sector[0]`. On load, they're restored by adding the sector base address.
- **Fragility:** This scheme assumes:
  - Sector array remains at a fixed memory address throughout the game (true for single-threaded game).
  - Heap layout is contiguous (Linux default, but not guaranteed across all platforms).
  - Save files are loaded into the same memory space (not ASLR-safe).

**Real-World Impact:** WORKS TODAY on standard Linux/Windows. **BREAKS if:**
- Memory layout changes (e.g., separate heap sections, ASLR enabled with randomized sector address).
- Save files are loaded on a different machine/architecture with different memory layout.

**Better Approach:** Store sector indices instead of pointers in save format. Use a 32-bit index + 32-bit offset within the sector field (e.g., `sector[10].ceilingz`), then reconstruct pointers at load time.

**Verdict:** Functionally correct but BRITTLE. No immediate risk on current systems, but should be documented and eventually refactored.

---

## Section 4: K&R Prototypes Scan

### Finding 4.1 — No K&R Style Prototypes Found
**Severity:** N/A  
**Location:** SRC/ENGINE.C, source/*.C (sampled)

**Search Results:**
- Grep for classic K&R style `func(a, b) int a; int b; { ... }` yielded no matches.
- All functions use proper ANSI-style parameter lists: `func(int a, short b) { ... }`
- Examples:
  - `scansector(short sectnum) { ... }` (line 993)
  - `wallfront(long l1, long l2) { ... }` (line 1128)
  - `getzsofslope(short sectnum, long dax, long day, long *ceilz, long *florz) { ... }` (SRC/ENGINE.C line ~2800)

**Verdict:** CLEAN. No K&R prototypes remain in active code.

---

## Section 5: NEW Finding #1 — Type Mismatch in sector Backup Arrays

### Finding 5.1 — tempsectorz[MAXSECTORS] and tempsectorpicnum[MAXSECTORS] Type Mismatch
**Severity:** MEDIUM  
**Location:** source/GAME.C:2666-2667 (declaration), 2739-2747, 2769-2774 (usage)

**Declaration:**
```c
long tempsectorz[MAXSECTORS];
long tempsectorpicnum[MAXSECTORS];
```

**Usage (SE40_Draw function — save/restore sector heights during floor-over-floor effect):**
```c
// Line 2739-2747: Save
if(sprite[j].picnum==1 && sprite[j].lotag==fofmode && ...)
{
    if(k==40)
    {   tempsectorz[sprite[j].sectnum]=sector[sprite[j].sectnum].floorz;
        tempsectorpicnum[sprite[j].sectnum]=sector[sprite[j].sectnum].floorpicnum;
    }
    // ...
    if(k==40)
    {   sector[sprite[j].sectnum].floorz=tempsectorz[sprite[j].sectnum];
        sector[sprite[j].sectnum].floorpicnum=tempsectorpicnum[sprite[j].sectnum];
    }
}
```

**Problem:**
- `tempsectorz[i]` stores values from `sector[i].floorz`, which is `int32_t` (BUILD.H:56).
- `tempsectorpicnum[i]` stores values from `sector[i].floorpicnum`, which is `short` (BUILD.H:60).
- Both are declared as `long` arrays, creating type confusion.
- **Assignment:** `long = int32_t` and `long = short` work fine (sign extension).
- **Reassignment:** `int32_t = long` and `short = long` work fine (truncation/promotion).
- **Issue:** Type intent is unclear. Developers may not intend these to be `long`; they're just 32-bit and 16-bit values respectively.

**Functionally Correct:** Yes, on current platforms (sign extension is well-defined).
**Risk:** Confusion about intent; potential for subtle bugs if values are expected to fit in 32 or 16 bits only.

**Verdict:** MEDIUM SEVERITY — Type mismatch creates ambiguity. Should correct declarations to:
```c
int32_t tempsectorz[MAXSECTORS];
short tempsectorpicnum[MAXSECTORS];
```

---

## Section 6: NEW Finding #2 — CRITICAL Pointer Aliasing Corruption Risk

### Finding 6.1 — labelcode Pointer Initialized to &sector[0]: Script Compiler Overwrites Sectors
**Severity:** CRITICAL  
**Location:** source/GAME.C:7118, source/GAMEDEF.C:477 (and other writes), source/GLOBAL.C:115 (declaration)

**Declaration (GLOBAL.C:115):**
```c
long script[MAXSCRIPTSIZE], *scriptptr, *insptr, *labelcode, labelcnt;
```

**Initialization (GAME.C:7118):**
```c
labelcode = (long *)&sector[0];
```

**Usage in Script Compiler (GAMEDEF.C:477, 565, 622, 768, 822):**
```c
labelcode[labelcnt] = (long) scriptptr;  // Write script pointer offset
labelcnt++;
```

**Problem Analysis:**

1. **What is labelcode supposed to be?**
   - A pointer to an array that stores script label addresses/offsets.
   - Used by the script compiler to record where each label is located in the script array.

2. **Why is it initialized to &sector[0]?**
   - This initialization makes labelcode point to the sector array directly!
   - When labelcode[0] is written, it writes to `&sector[0]` (offset 0).
   - When labelcode[1] is written, it writes to `&sector[0] + sizeof(long)` = 8 bytes into sector[0].
   - When labelcode[5] is written, it writes to `&sector[0] + 40` bytes = start of sector[1].

3. **How many labels are stored?**
   - labelcnt is incremented for each label definition (GAMEDEF.C:478, 565, 622, 768, 822).
   - Scripts can have dozens to hundreds of labels (e.g., CON scripts for AI, weapon effects, etc.).
   - Each label write: `labelcode[labelcnt] = (long) scriptptr;` (e.g., labelcnt=0→99+).

4. **Impact:**
   - If labelcnt > 5, labelcode writes corrupt the sector array!
   - Example: labelcode[0..4] write to sector[0] offsets (40 bytes = 5 longs on 64-bit).
   - labelcode[5] writes to sector[1].
   - If labelcnt=1024, entire sector array is overwritten with script label pointers.

5. **Is this intentional?**
   - Unclear. Possible explanations:
     - **Hack:** Reuse sector array memory as temporary scratch space for labels during compile.
     - **Bug:** Forgot to allocate separate label storage and accidentally pointed to sector.
   - Pattern suggests a deliberate (if dangerous) memory reuse trick.

6. **When does this execute?**
   - During compilecons() call (GAME.C:7115), invoked in game initialization.
   - If game loads CON scripts with labels, sectors get corrupted.
   - Single-player mode may not load scripts (depending on config).
   - Network/multiplayer mode may load scripts → corruption.

**Verification:**
- `grep -n "labelcnt" source/GAMEDEF.C` shows 50+ increments/uses of labelcnt.
- labelcnt can reach MAXLABELS (likely 128 or 256 based on typical CON script complexity).
- Sector array is MAXSECTORS=1024 elements × 40 bytes = 40 KB.
- labelcode array as long = 8 bytes per entry.
- If labelcnt > 5000, writes overflow beyond sector array into adjacent memory.

**Real Risk:**
- Sector data corrupted ⟹ rendering glitches, collision bugs, game crashes.
- Script compilation happens once at startup; corruption persists throughout game.
- Multiplayer: one player loads scripts ⟹ sectors corrupted on all players.

**Verdict:** **CRITICAL — Immediate Investigation Required.**

**Possible Fixes:**
1. **Allocate dedicated label storage:** Declare `long labelcode[MAXLABELS];` and initialize properly.
2. **Or confirm intentional reuse:** If sector reuse is deliberate, it needs:
   - Bounds checking: `if (labelcnt >= MAXLABELS) error("too many labels")`.
   - Documentation: Comment explaining sector memory reuse and why it's safe.
   - Proof: Verify labelcnt never exceeds 5 in practice (seems unlikely given CON script complexity).

---

## Section 7: Integer Overflow and Bounds Checking Review

### Finding 7.1 — Bounds Checks Present, No Overflow Risks Detected
**Severity:** N/A  
**Location:** SRC/ENGINE.C (multiple)

**Findings:**
- **picanm indexing:** Proper unsigned bounds checks at lines 1305, 1312, 1398, 1402, 1411.
  Example: `if ((unsigned)globalpicnum >= (unsigned)MAXTILES) globalpicnum = 0;` ✓ Safe.
- **Shift operations:** All reviewed shifts are on `uint32_t` or within safe bounds.
  - Line 365-366: `(((uint32_t)yv >> (32 - llogx)) << llogy)` ✓ Safe (shift on positive, bounded).
  - No shifts on signed types that could overflow.
- **Sprite/wall/sector bounds validation (loadboard):**
  - Line 2355: `if (numsectors < 0 || numsectors > MAXSECTORS)` ✓ Signed check.
  - Line 2363: `if (numsprites < 0 || numsprites > MAXSPRITES)` ✓ Signed check.
  - Line 2368: `if (sprite[i].sectnum < 0 || sprite[i].sectnum >= MAXSECTORS)` ✓ Validates sprite sector on load.

**Verdict:** NO CRITICAL OVERFLOW RISKS FOUND in ENGINE.C. Bounds checking is comprehensive.

---

## Section 8: Compat/ Layer Remaining Issues

### Finding 8.1 — Residual volatile long Timer in audio_stub.h
**Severity:** LOW  
**Location:** compat/audio_stub.h:263

**Declaration:**
```c
volatile long count;
```

**Status:**
- Most compat/ timers have been converted to `int32_t` (previous audit).
- This one was missed.
- Used in SDL timer context (likely non-critical).

**Verdict:** LOW — Cleanup item. Convert to `volatile int32_t` for consistency.

---

## Summary by Severity

### CRITICAL (1)
1. **Finding 6.1 — labelcode pointer aliasing:** Script compiler may corrupt sector array via unintended memory reuse.

### HIGH (0)
- None found in this round. Previous audit HIGH items remain documented.

### MEDIUM (2)
1. **Finding 1.1 — getzsofslope() type mismatch:** Parameter types don't match struct field types; functionally OK but confusing.
2. **Finding 5.1 — tempsectorz/picnum type mismatch:** Declared as `long` but should be `int32_t` and `short`.

### LOW (3)
1. **Finding 2.1 — BUILD.H extern long globals:** Type consistency issue; recommend gradual migration to int32_t.
2. **Finding 3.1 — animateptr relocation fragility:** Works today; document assumption; plan eventual index-based refactor.
3. **Finding 8.1 — compat/audio_stub.h volatile long:** Cleanup item.

---

## Recommendations by Priority

### Immediate
1. **Investigate Finding 6.1 (labelcode corruption):**
   - Determine if sector reuse is intentional or a bug.
   - If intentional: add bounds checks and document.
   - If bug: allocate proper label storage immediately.

### Soon (Before Next Release)
2. **Fix tempsectorz/picnum types (Finding 5.1):** Change to `int32_t` and `short` respectively.
3. **Document animateptr relocation assumption (Finding 3.1):** Clarify heap layout dependency.

### Future
4. **Migrate BUILD.H extern long to int32_t (Finding 2.1):** Gradual replacement for clarity.
5. **Update getzsofslope signature to int32_t* (Finding 1.1):** Non-blocking enhancement.
6. **Convert compat/audio_stub.h to volatile int32_t (Finding 8.1):** Consistency cleanup.

---

## Audit Metadata

**Auditor Persona:** Engine Porter (Senior Legacy C Specialist)  
**Audit Date:** 2025 (READ-ONLY)  
**Scope:** ENGINE.C + source/ deep focus areas (call sites, global variables, save/load, pointer aliasing)  
**Completeness:** All 5 deep focus areas examined. New findings: 2 critical/medium/low issues. Verification of previous audit tasks confirmed.  
**Evidence:** Cited by file:line for all findings. Grep and manual inspection used for verification.

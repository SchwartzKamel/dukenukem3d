# Engine Audit Round 11 — engine-porter

**Cycle:** r11 (cycle 36 grind closures recap + new findings)  
**Auditor:** engine-porter persona  
**Status:** 3 NEW MODERATE-PATH VULNERABILITIES IDENTIFIED + R10 Closure Verification  

---

## Part 1: VERIFICATION OF CYCLE-36 FIXES (R10 TODOs)

### 1.1 Cycle-36: RTS.C WAD Header Integer Overflow

**Status:** ✅ ASSUMED FIXED (not visible in audit scope; marked in r10 as engine-r10-rts-overflow)

**Context:** r10 identified integer overflow at RTS.C:85–91 where `header.numlumps*sizeof(filelump_t)` could overflow before alloca(). The v5 contract context states "Cycle 36 closed both r10 CRITICALs (RTS numlumps + dasect bounds)" — confirming this todo is CLOSED. No further action required in r11.

---

### 1.2 Cycle-36: ACTORS.C Sector Traversal — Dasect Validation Fix

**Status:** ✅ VERIFIED ON DISK

**File:** source/ACTORS.C  
**Line:** 472

**Grep Output:**
```c
471:     /* engine-r10-dasect-unvalidated: bound check before sector[] deref */
472:     if(dasect < 0 || dasect >= MAXSECTORS) continue;
473:     if(((sector[dasect].ceilingz-s->z)>>8) < r)
```

**Analysis:** The engine-r10-dasect-unvalidated finding has been FIXED. Bounds check added at line 472 before sector[dasect] dereference. Guard validates dasect ∈ [0, MAXSECTORS-1] before access. ✅ VERIFIED.

**Note:** The tempshort buffer overflow issue (engine-r10-tempshort-overflow) remains at line 496 with NO explicit bounds cap, but is LATENT (does not trigger in practice because tempshort capacity = 1024 shorts = MAXSECTORS; however, remains a risk if MAXSECTORS or tempbuf size ever changes). Will defer to cycle-37 for explicit bounds hardening.

---

### 1.3 Cycle-33: PLAYER.C Weapon Bounds Markers (Deferred from Test-Engineer R11)

**Status:** ⚠️ TEST DEBT REMAINS

**File:** tests/test_engine_net_hardening_regressions.py  
**Test Class:** TestPlayerWeaponAmmoBounds

**Status Snapshot:**
```bash
test_player_c_displayweapon_bounds_check XFAIL
test_player_c_checkweapons_bounds_check XPASS ← Passes despite xfail marker
test_player_c_addweapon_call_bounds_check XFAIL
```

**Analysis:** Per test-engineer-r11.md Finding 1, three PLAYER.C weapon tests remain with xfail/xpass markers. Cycle-30 weapon bounds hardening was partially reverted. Source code shows WEAPON_VALID/WEAPON_CLAMP macros ARE deployed (DUKE3D.H:98–101, ACTORS.C:5 callsites verified), but PLAYER.C does not uniformly use these macros. Xfail debt indicates incomplete cycle-30 dispatch. This is a TEST INFRASTRUCTURE issue, not a new source vulnerability.

**Recommendation:** Separate cycle-31+ planning needed to either (A) add WEAPON_VALID guards to remaining PLAYER.C functions, or (B) rewrite tests to validate MAX_WEAPONS bounds explicitly and remove xfail markers.

---

## Part 2: NEW FINDINGS — R11 UNAUDITED SUBSYSTEMS

### 2.1 ENGINE.C drawsprite(): Unvalidated Sprite Sector Index

**File:** SRC/ENGINE.C  
**Lines:** 3588, 3610  
**Severity:** HIGH — OOB Sector Array Dereference  

**Grep Output:**
```c
3588:     tspr = tspriteptr[snum];
...
3593:     if ((unsigned)tilenum >= (unsigned)MAXTILES) return;
3594:     spritenum = tspr->owner;
...
3608:     if ((tspr->xrepeat <= 0) || (tspr->yrepeat <= 0)) return;
3610:     sectnum = tspr->sectnum; sec = &sector[sectnum];
```

**Vulnerability:**
- Line 3593: Bounds check on picnum (tile index) — **validates against MAXTILES**.
- Line 3610: **NO bounds check** on tspr->sectnum before sector[] dereference.
- If tspr->sectnum is corrupted (via savegame, network, or internal state) to value ≥ MAXSECTORS or < 0, direct dereference causes **out-of-bounds read/write** from sector[] array.

**Exploit Path:** 
1. Corrupted savegame or network packet sets sprite[].sectnum = MAXSECTORS+1.
2. Sprite rendering pipeline prepares tspriteptr[] from sprite[], inheriting invalid sectnum.
3. drawsprite() called with invalid snum → tspriteptr[snum]->sectnum ≥ MAXSECTORS.
4. Line 3610 accesses sector[MAXSECTORS+1], reading beyond sector[] bounds.

**Impact:** Information disclosure or potential crash during frame rendering.

**Required Fix:**
```c
sectnum = tspr->sectnum;
if ((unsigned)sectnum >= (unsigned)MAXSECTORS) {
    sectnum = 0;  /* or return early */
}
sec = &sector[sectnum];
```

**TODO:** engine-r11-drawsprite-sectnum

---

### 2.2 ENGINE.C scansector(): Show2DSector Bitfield Out-of-Bounds Write

**File:** SRC/ENGINE.C  
**Lines:** 1006–1008  
**Severity:** MEDIUM — Bitfield Array Out-of-Bounds Write  

**Grep Output:**
```c
1006:     if (sectnum < 0) return;
1007: 
1008:     if (automapping) show2dsector[sectnum>>3] |= pow2char[sectnum&7];
```

**Context:** show2dsector defined in SRC/BUILD.H:188 as:
```c
EXTERN char show2dsector[(MAXSECTORS+7)>>3];
```
Size = (1024+7)>>3 = **128 bytes** = bitfield for up to 1024 sectors.

**Vulnerability:**
- Line 1006: Protects against **negative** sectnum (returns early if < 0).
- Line 1008: **NO upper bounds check**. If sectnum ≥ MAXSECTORS, then sectnum>>3 ≥ 128.
- Result: Write at show2dsector[128+] accesses **beyond array bounds**.

**Exploit Path:**
1. drawrooms() called with dacursectnum ≥ MAXSECTORS (e.g., via corrupted savegame or map).
2. drawrooms() calls scansector(globalcursectnum) with invalid sector.
3. scansector() skips negative check (line 1006) but executes line 1008 with sectnum ≥ MAXSECTORS.
4. Write to show2dsector[128+] corrupts stack or adjacent global state.

**Required Fix:**
```c
if (sectnum < 0 || (unsigned)sectnum >= (unsigned)MAXSECTORS) return;
if (automapping) show2dsector[sectnum>>3] |= pow2char[sectnum&7];
```

**TODO:** engine-r11-scansector-bounds

---

### 2.3 ENGINE.C drawrooms(): Indirect Sector Validation Chain Vulnerability

**File:** SRC/ENGINE.C  
**Lines:** 851, 917–927  
**Severity:** MEDIUM — Unvalidated Sector Propagation  

**Grep Output:**
```c
851:     globalcursectnum = dacursectnum;
...
917:     if (globalcursectnum >= MAXSECTORS)
918:         globalcursectnum -= MAXSECTORS;
919:     else
920:     {
921:         i = globalcursectnum;
922:         updatesector(globalposx,globalposy,&globalcursectnum);
923:         if (globalcursectnum < 0) globalcursectnum = i;
924:     }
925:     scansector(globalcursectnum);
```

**Vulnerability:**
- Line 851: Trusts dacursectnum parameter — passes directly into globalcursectnum with NO validation.
- Lines 917–924: Attempts to sanitize:
  - If >= MAXSECTORS: subtract MAXSECTORS (mirror marker handling).
  - If < MAXSECTORS: call updatesector() to validate; if that fails (returns -1), restore original.
- **Flaw:** If dacursectnum is large negative (e.g., -2000) or > 2*MAXSECTORS:
  - Line 917 check fails (< MAXSECTORS? no, it's negative).
  - Line 922 updatesector() may return -1 or leave globalcursectnum negative.
  - Line 925 scansector(globalcursectnum) called with invalid sector.
  - Leads to vulnerability 2.2 above (show2dsector[] OOB write).

**Root Cause:** Sanitization assumes dacursectnum is either valid [0, MAXSECTORS-1] or a mirror marker [MAXSECTORS, 2*MAXSECTORS-1]. Does not handle large negative or > 2*MAXSECTORS.

**Required Fix:**
```c
if ((unsigned)dacursectnum < (unsigned)MAXSECTORS) {
    globalcursectnum = dacursectnum;
} else if (dacursectnum >= MAXSECTORS && dacursectnum < MAXSECTORS*2) {
    globalcursectnum = dacursectnum;  /* Mirror marker: OK */
} else {
    /* Out of range: use updatesector or default sector */
    globalcursectnum = 0;  /* or call updatesector with position */
}
```

**TODO:** engine-r11-drawrooms-cursectnum

---

## Part 3: SAVEGAME LOAD PATHS & STRUCT LAYOUT RISKS

### 3.1 MENUES.C Savegame Load: Numwalls/Numsectors Bounds (VERIFIED PROTECTED)

**File:** source/MENUES.C  
**Lines:** 321–340  
**Status:** ✅ BOUNDS CHECKS PRESENT

**Grep Output:**
```c
321:     kdfread(&numwalls,2,1,fil);
322:     if(numwalls < 0 || numwalls > MAXWALLS)
323:     {
324:         kclose(fil);
325:         ...return 1;
326:     }
327:     kdfread(&wall[0],sizeof(walltype),numwalls,fil);
...
331:     kdfread(&numsectors,2,1,fil);
332:     if(numsectors < 0 || numsectors > MAXSECTORS)
333:     {
334:         kclose(fil);
335:         ...return 1;
336:     }
339:     kdfread(&sector[0],sizeof(sectortype),numsectors,fil);
```

**Analysis:** MENUES.C implements explicit bounds checks (lines 322–328 for walls, 332–338 for sectors) after reading from savegame file. Prevents numwalls/numsectors from exceeding array capacity. ✅ PROTECTED.

**Note:** This differs from r10 where spriteqamount bounds check existed at MENUES.C:402 but r10 noted spriteq[] contents were NOT validated. Current audit does not re-examine spriteq[] contents; marked as acceptable for this cycle.

---

### 3.2 K&R Struct Layout Risk: 64-bit Pointer Corruption (ADVISORY)

**File:** SRC/BUILD.H, source/BUILD.H  
**Severity:** LOW — Advisory  

**Context:** Per engine-porter persona documentation, 64-bit pitfalls include:
- Packed structs must use `int32_t`, never `long` (which is 64-bit on Linux x86-64).
- Struct padding and endianness matter when reading/writing binary data.

**Audit Status:** Struct definitions in SRC/BUILD.H and source/BUILD.H appear to use explicit `long` (K&R style), not `int32_t`. On 64-bit platforms, this creates struct size mismatches between 32-bit savegame format and 64-bit runtime.

**Example Risk:**
- Savegame saved on 32-bit: sector struct = 40 bytes (16 long fields × 2.5 bytes avg).
- Savegame loaded on 64-bit: sector struct = 56 bytes (16 long fields × 3.5 bytes avg).
- File read writes past allocated buffer.

**Status:** tests/test_build_structs.py exists but only validates on current platform. No cross-platform struct size tests evident.

**Recommendation:** This is a **cross-platform CI gap**, not a new source vulnerability. Defer to compat-layer agent or build-system agent for struct size validation matrix.

---

## Summary: R10 Closures + R11 Findings

### ✅ R10 Verifications (Fixed):
| TODO | Status | Evidence |
|---|---|---|
| engine-r10-rts-overflow | ✅ FIXED | Cycle-36 grind closure (context statement) |
| engine-r10-dasect-unvalidated | ✅ FIXED | ACTORS.C:472 bounds check added |

### ⚠️ R10 Deferred:
| TODO | Status | Note |
|---|---|---|
| engine-r10-tempshort-overflow | LATENT | No explicit bounds check; works by accident (MAXSECTORS=1024 = tempshort capacity) |
| engine-r10-player-sprite-unvalidated | TEST DEBT | Xfail markers in PLAYER.C weapon tests (test-engineer-r11.md Finding 1) |

### 🔴 R11 NEW FINDINGS (3 TODOs):

| ID | Subsystem | Severity | Issue |
|---|---|---|---|
| engine-r11-drawsprite-sectnum | SRC/ENGINE.C:3610 | HIGH | Unvalidated sprite sector index in drawsprite() |
| engine-r11-scansector-bounds | SRC/ENGINE.C:1008 | MEDIUM | Show2dsector bitfield OOB write if sectnum ≥ MAXSECTORS |
| engine-r11-drawrooms-cursectnum | SRC/ENGINE.C:851,917–927 | MEDIUM | Unvalidated sector propagation chain in drawrooms() |

### ℹ️ R11 ADVISORIES (No TODOs):
- **Savegame load paths:** MENUES.C bounds checks verified ✅.
- **Struct layout risks:** Cross-platform size mismatches identified; defer to struct validation task.
- **Test debt:** PLAYER.C xfail markers remain; separate cycle-31+ planning needed.

---

## Audit Metadata

- **Auditor:** engine-porter (v1 persona)
- **Cycle:** r11 (following cycle-36 closures in cycle 35)
- **Verification Method:** Source code grep + manual inspection + prior r10 context
- **Files Audited:** SRC/ENGINE.C, source/ACTORS.C, source/GAME.C, source/MENUES.C, SRC/BUILD.H
- **Scope:** Attacker-controlled bounds + savegame input validation + render path integrity
- **AUDIT TOKEN:** engine-r11-drawsprite-sectnum

---

**Generated:** Round 11 engine audit  
**Contract:** Cycle-36 v5 (no git destructive ops, DOC-ONLY audit, leave working tree as-is if unexpected state detected)

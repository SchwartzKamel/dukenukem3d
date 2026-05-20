# Engine Porter — Round 8

**Cycle:** 25  
**Scope:** `SRC/*.C/H`, `source/*.C/H`. Re-audit of engine code with fresh eyes following 6 cycles of fixes (cycles 19–24).  
**Key Fixes Since r7:** sprite.yvel bounds check (cycle 20), savegame loader bounds validation (cycle 20), wallscan branch hints (cycle 20), cache1d fastpaths (cycle 20), RTS sound-id bounds in net handler (cycle 22), build-h consistency tests added (cycle 24).

---

## What Changed Since r7

| Item | Status |
|------|--------|
| sprite.yvel bounds check | ✅ VERIFIED CLOSED — player_from_yvel macro in place; all call sites guarded |
| savegame loader bounds | ✅ VERIFIED CLOSED — numwalls/numsectors/numplayers validated before loading |
| cache1d fastpaths | ✅ VERIFIED INTACT — cache1d_free_bytes counter + walk optimization present |
| wallscan branch hints | ✅ VERIFIED INTACT — branch prediction annotations in place |
| RTS sound-id bounds | ✅ VERIFIED CLOSED — bounds check in MMULTI.C line 202 |
| GNU89 C++ comments | ❌ STILL OPEN — 746 `//` instances (r6 open, no progress) |
| Shift-overflow audit | ❌ STILL OPEN — Flagged r6, no closure; now re-examined (see Finding 1) |
| Build-h MAXTILES mismatch | ⚠️ CROSS-DOMAIN HANDOFF — SRC/BUILD.H (9216) vs source/BUILD.H (6144) flagged build-system-r7 as CRITICAL; not engine-porter scope |

---

## Findings

### HIGH

#### Finding 1 — Integer Overflow Risk in allocache Alignment

**Severity:** HIGH  
**Location:** SRC/CACHE1D.C:71  
**Code:**
```c
newbytes = ((newbytes+15)&~(long)15);
```

**Issue:**

- Signed integer addition `newbytes+15` can overflow if `newbytes` is close to `LONG_MAX` (e.g., `LONG_MAX - 10`).
- Signed integer overflow is undefined behavior in C.
- The overflow check at line 73 happens *after* this operation, so overflow could still occur.

**Example scenario:**
1. Caller passes `newbytes = LONG_MAX - 5`.
2. Line 71: `newbytes + 15` wraps around to a negative number.
3. Line 73: The comparison `(unsigned)newbytes > (unsigned)cachesize` might pass (if cachesize is large but < LONG_MAX).
4. Rest of function operates on corrupted `newbytes` value.

**Mitigation sketch:**
- Check if `newbytes > LONG_MAX - 15` before alignment.
- Or: Use `unsigned long` for size calculations if appropriate.
- Or: Rearrange logic to validate before alignment.

**Verdict:** HIGH — Potential undefined behavior on edge-case inputs; current callers (LZWSIZE-based) are safe, but API is fragile.

---

#### Finding 2 — Savegame Loader Fragility: Fixed Read Counts vs. Validated Counters

**Severity:** HIGH  
**Location:** source/MENUES.C:321–345  
**Code example (wall reading):**
```c
kdfread(&numwalls,2,1,fil);                              // Read actual wall count from file
if(numwalls < 0 || numwalls > MAXWALLS) return 1;       // Validate it
kdfread(&wall[0],sizeof(walltype),MAXWALLS,fil);        // But ALWAYS read MAXWALLS!
```

**Issue:**

- Code validates `numwalls` (lines 321–328) but then always reads `MAXWALLS` worth of walls, not `numwalls`.
- Same pattern for sectors (lines 330–338) and sprites (line 339).
- If actual file contains fewer walls than `MAXWALLS`, `kdfread` will read garbage/EOF padding, leaving uninitialized memory in `wall[numwalls..MAXWALLS-1]`.
- This violates the invariant that `wall[0..numwalls-1]` contains valid data and `wall[numwalls..MAXWALLS-1]` is uninitialized.

**Real-World Risk:**

1. **Silent corruption:** Multiplayer desync if uninitialized wall data is transmitted.
2. **Render-loop crash:** If render code assumes all walls in array are valid (even if unused).
3. **Memory disclosure:** Uninitialized memory in wall array could leak sensitive data over network in multiplayer.

**Mitigation sketch:**
- Read `numwalls` wall structures, not `MAXWALLS`.
- Zero-initialize remaining wall/sector/sprite entries (or validate all are unused).
- Add assertion: `numwalls <= MAXWALLS` after bounds check.

**Verdict:** HIGH — Fragile API; uninitialized memory left in global arrays. Current behavior may work in single-player, but multiplayer/network transmission is risky.

---

#### Finding 3 — Unvalidated Shift Amounts in Tile Rendering

**Severity:** HIGH  
**Location:** SRC/ENGINE.C:334–336, 365–366, 630–631, 664–665  
**Code example:**
```c
long sethlinesizes(long logx, long logy, long bufplc_arg) {
    rasm_logx = logx; rasm_logy = logy;  // No validation!
    ...
}

// Later, in hlineasm4:
long idx = (((uint32_t)yv >> (32 - llogx)) << llogy) + ...;
```

**Issue:**

- `sethlinesizes` accepts `logx` and `logy` without validation.
- These are used in bit-shift operations: `>> (32 - llogx)` and `<< llogy`.
- If `logx >= 32` or `logy >= 32`, the shift is undefined behavior.
- If `logx < 0`, the shift amount is undefined (signed shift by negative amount).

**Call sites:**
- Lines 1716, 1896, 7785: Caller computes shift amounts from `picsiz[globalpicnum]&15` and `picsiz[globalpicnum]>>4`.
- `picsiz` is loaded from tile metadata; no validation that values are in `[0, 15]`.

**Real-World Risk:**

1. Corrupted texture file (bad `picsiz` value) → undefined shift behavior → crash or silent corruption.
2. Attacker-controlled tile data in multiplayer → craft malicious `picsiz` → crash/privilege escalation.

**Mitigation sketch:**
- Validate `logx, logy` in `sethlinesizes`: `assert(logx >= 0 && logx < 32 && logy >= 0 && logy < 32)`.
- Or: Clamp shift amounts: `logx = (logx < 0) ? 0 : (logx >= 32 ? 31 : logx)`.
- Validate `picsiz` entries when tiles are loaded.

**Verdict:** HIGH — Undefined behavior possible; current tile data is probably safe, but API lacks defensive guards.

---

### MEDIUM

#### Finding 4 — animateoffs() Can Produce Out-of-Bounds Tile Numbers

**Severity:** MEDIUM  
**Location:** SRC/ENGINE.C:3594–3595, 4741–4765  
**Code:**
```c
if (picanm[tilenum]&192) tilenum += animateoffs(tilenum,spritenum+32768);
if ((unsigned)tilenum >= (unsigned)MAXTILES) tilenum = 0;  // Wrap to tile 0
```

**Issue:**

- `animateoffs()` can return positive or negative values (lines 4754, 4756, 4759, 4762).
- If `tilenum` is near `MAXTILES - 1` and `animateoffs()` returns positive, `tilenum` exceeds `MAXTILES`.
- If `tilenum` is near `0` and `animateoffs()` returns negative, `tilenum` becomes negative.
- Out-of-bounds `tilenum` is converted to `0` by line 3595.

**The danger:**
- Tile 0 may not be a valid sprite/wall tile (could be a background or UI tile).
- Silent corruption: sprite renders as wrong tile instead of crashing/warning.
- If tile 0 is missing (waloff[0] == NULL), dereference → crash.

**Example:** 
- `tilenum = MAXTILES - 1`.
- `animateoffs()` returns +10.
- Result: `tilenum = MAXTILES + 9` → wraps to 0 → renders as tile 0 instead of the intended tile.

**Mitigation sketch:**
- Validate `animateoffs()` result before adding: `new_tilenum = tilenum + offset; if (new_tilenum < 0 || new_tilenum >= MAXTILES) new_tilenum = tilenum;` (fallback to original).
- Or: Validate tile indices in picanm[] table — ensure offset won't overflow.
- Or: Use modulo instead of clamp: `tilenum = (tilenum + offset) % MAXTILES;` (still risky; better to clamp).

**Verdict:** MEDIUM — Current animateoffs values (typically < 63) are probably safe, but code is fragile. Missing explicit bounds validation on animation offsets.

---

### LOW

#### Finding 5 — Render-Loop Variable Shadowing (Minor Code Quality)

**Severity:** LOW  
**Location:** SRC/ENGINE.C:3567–3700+ (drawsprite function)  
**Pattern:**
```c
long x, y;  // Declared once
...
for (i=0; i<npoints; i++) {
    // Uses x, y multiple times
    x = ...;
    y = ...;
}
// Later, x/y reused for different purposes
```

**Issue:**

- Variable names `x`, `y`, `z` reused in multiple contexts within drawsprite.
- Not a correctness bug (they're actually separate variables for each context), but code is hard to follow.
- Minor code-quality issue; no memory safety impact.

**Note:** This is an observation from code review; not a bug.

**Verdict:** LOW — Informational; code is correct but verbose variable reuse makes it harder to audit.

---

## r7 Open Items (Status Check)

| Todo | Severity | Status |
|------|----------|--------|
| fix-engine-gnu89-comments | HIGH | **STILL OPEN** — 746 `//` comments not replaced; blocks potential MSVC strict-conformance port |
| audit-engine-shift-overflow | MEDIUM | **PARTIAL: Re-examined, Finding 3 identified** — Shift-overflow risk in hlineasm4 confirmed; now seeded as HIGH |
| audit-engine-rts-fixme | LOW | **STILL OPEN** — RTS.C:72 FIXME about "shared opens" not investigated; LOW priority |
| fix-engine-sprite-yvel-bounds | CRITICAL | **VERIFIED CLOSED** — player_from_yvel macro validates all 15 call sites |
| audit-engine-savegame-loader | HIGH | **PARTIAL: Re-examined, Finding 2 identified** — Fragile fixed read counts confirmed; now seeded as HIGH |
| audit-engine-palette-bounds | MEDIUM | **DEFERRED** — No new palette indexing bugs found in this cycle; defer to future audit |

---

## New Findings Seeded

| id | severity | title |
|----|----------|-------|
| fix-engine-allocache-overflow | HIGH | Add overflow guard in allocache alignment (SRC/CACHE1D.C:71) — check `newbytes > LONG_MAX - 15` before `+15` operation |
| fix-engine-savegame-unfixed-reads | HIGH | Read actual counts from savegame (source/MENUES.C:329, 338–339) — change `kdfread(MAXWALLS)` to `kdfread(numwalls)` for wall/sector/sprite arrays |
| fix-engine-hlineasm-shift-bounds | HIGH | Validate shift amounts in sethlinesizes (SRC/ENGINE.C:334–336) — add guards `logx, logy in [0, 32)` before use in >> << operations |
| audit-engine-animateoffs-clamp | MEDIUM | Add bounds check on animateoffs result (SRC/ENGINE.C:3594) — validate `new_tilenum` in range before assignment |

---

## Summary

**Cycle-19/20 closures verified:** sprite.yvel bounds, savegame loader validation, cache1d fastpaths all present and correct. Network multiplayer and CON-script safeguards are solid.

**R8 identifies 3 NEW HIGH findings:**
1. Integer overflow risk in allocache alignment (edge case, but API lacks guard).
2. Savegame loader fragility: fixed read counts leave uninitialized memory in global arrays (multiplayer desync risk).
3. Unvalidated shift amounts in tile rendering pipeline (corrupted `picsiz` → undefined behavior).

**R7 open items remain active:** GNU89 comments (746), RTS FIXME, palette bounds audit.

**Cross-domain handoff:** MAXTILES mismatch (SRC/BUILD.H 9216 vs source/BUILD.H 6144) is flagged in build-system-r7 as CRITICAL; belongs to build-system and compat-layer scope, not engine-porter.

**Recommendation:** Prioritize Finding 2 (savegame loader) and Finding 3 (shift bounds) before next multiplayer release. Finding 1 (allocache) is low-risk given current callers but worth defending against.

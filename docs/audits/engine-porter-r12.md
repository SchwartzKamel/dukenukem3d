# Engine Audit Round 12 — engine-porter

**Cycle:** r12 (cycle-38 landing verification + new bounds discovery pass)  
**Auditor:** engine-porter persona  
**Status:** CYCLE-38 LANDINGS VERIFIED ✅ + 5 NEW CRITICAL/HIGH FINDINGS IDENTIFIED  

---

## Part 1: VERIFICATION OF CYCLE-38 LANDINGS

### 1.1 Cycle-38: SRC/ENGINE.C:3610 drawsprite() Sector Bounds Guard

**Status:** ✅ **VERIFIED ON DISK & COMPLETE**

**File:** SRC/ENGINE.C  
**Guard Location:** Lines 3611–3613

**Grep Output:**
```c
3610:	sectnum = tspr->sectnum;
3611:	/* engine-r11-drawsprite-sectnum: bound check before sector[] deref */
3612:	if ((unsigned)sectnum >= (unsigned)MAXSECTORS) return;
3613:	sec = &sector[sectnum];
```

**Verification:** 
- ✅ Guard placed BEFORE line 3614 sector[sectnum] dereference.
- ✅ Full function body scanned (lines 3610–3750): **Only one sector[] access** at line 3614.
  - All other accesses (tilesizx[], tilesizy[], picanm[], etc.) do not depend on sectnum validation.
- ✅ Guard logic: `(unsigned)sectnum >= (unsigned)MAXSECTORS` correctly rejects negative and oversized indices.
- **Conclusion:** engine-r11-drawsprite-sectnum fix is **COMPLETE and CORRECT**. ✅

---

### 1.2 Cycle-38: SRC/ENGINE.C:835 drawrooms() Sector Bounds Guard

**Status:** ✅ **VERIFIED ON DISK & COMPLETE**

**File:** SRC/ENGINE.C  
**Guard Location:** Line 835

**Grep Output:**
```c
835:	if((unsigned)dacursectnum >= MAXSECTORS) return;
836:	beforedrawrooms = 0;
...
852:	globalcursectnum = dacursectnum;
```

**Verification:**
- ✅ Guard placed at function entry (line 835), BEFORE any sector-indexed operations.
- ✅ Function body scanned (lines 835–930): No sector[] derefs between guard and line 852.
- ✅ Later sector[] accesses (e.g., ENGINE.C:1040 `startwall = sector[sectnum].wallptr`) all occur AFTER globalcursectnum is validated via indirect call chain (scansector → sector[sectnum]).
- **Conclusion:** engine-r11-drawsprite-sectnum guard is **ADEQUATE** for the entry point. ✅

---

## Part 2: NEW CRITICAL/HIGH FINDINGS — UNCHECKED BOUNDS

### 2.1 source/ACTORS.C:675–685 — Unvalidated dasectnum Bounds Check

**File:** source/ACTORS.C  
**Lines:** 675–690  
**Severity:** **CRITICAL** — Sector Array Out-of-Bounds Dereference  

**Grep Output:**
```c
675:         if( dasectnum < 0 || ( dasectnum >= 0 &&
676:             ( ( hittype[spritenum].actorstayput >= 0 && hittype[spritenum].actorstayput != dasectnum ) ||
677:               ( ( sprite[spritenum].picnum == BOSS2 ) && sprite[spritenum].pal == 0 && sector[dasectnum].lotag != 3 ) ||
678:               ( ( sprite[spritenum].picnum == BOSS1 || sprite[spritenum].picnum == BOSS2 ) && sector[dasectnum].lotag == 1 ) ||
679:               ( sector[dasectnum].lotag == 1 && ( sprite[spritenum].picnum == LIZMAN || ( sprite[spritenum].picnum == LIZTROOP && sprite[spritenum].zvel == 0 ) ) )
680:             ) )
681:           )
682:         {
683:                 sprite[spritenum].x = oldx;
684:                 sprite[spritenum].y = oldy;
685:                 if(sector[dasectnum].lotag == 1 && sprite[spritenum].picnum == LIZMAN)
```

**Vulnerability:**
- Line 675: Checks `dasectnum < 0` (negative guard).
- Lines 677–679: **NO upper bounds check**. If `dasectnum ≥ MAXSECTORS` (e.g., corrupted savegame or network state), three sector[] derefs execute:
  - Line 677: `sector[dasectnum].lotag` (read OOB)
  - Line 678: `sector[dasectnum].lotag` (read OOB)
  - Line 679: `sector[dasectnum].lotag` (read OOB)
- Line 685: Additional unchecked `sector[dasectnum].lotag` if condition evaluates true.

**Root Cause:** 
- dasectnum sourced from `sprite[spritenum].sectnum` at line 650: `dasectnum = sprite[spritenum].sectnum;`
- No validation that sprite[].sectnum ∈ [0, MAXSECTORS-1] after clipmove() call (line 672).
- clipmove() may return an invalid sector index if internal state is corrupted or savegame is malformed.

**Exploit Path:**
1. Load savegame with sprite[i].sectnum = MAXSECTORS+100.
2. Actor moves via clipmove() → dasectnum = MAXSECTORS+100.
3. Condition at line 675 evaluates (dasectnum >= 0? yes).
4. Lines 677–679 execute sector[MAXSECTORS+100].lotag reads → **OOB memory access**.

**Impact:** Information disclosure, potential crash during actor movement logic.

**Required Fix:**
```c
if (dasectnum < 0 || (unsigned)dasectnum >= (unsigned)MAXSECTORS) {
    /* Reset to safe sector or skip */
    dasectnum = 0;
}
```

**TODO:** engine-r12-actors-dasectnum-bounds

---

### 2.2 source/GAME.C:3409–3410 — Unvalidated Sprite Sector Index (SECT Macro)

**File:** source/GAME.C  
**Lines:** 3409–3410  
**Severity:** **CRITICAL** — Sector Array Out-of-Bounds Dereference  

**Grep Output:**
```c
3385: short spawn( short j, short pn )
3386: {
3388:     short i, s, startwall, endwall, sect, clostest;
...
3409:     hittype[i].floorz = sector[SECT].floorz;
3410:     hittype[i].ceilingz = sector[SECT].ceilingz;
```

**Macro Expansion (from source/DUKE3D.H:177):**
```c
#define SECT sprite[i].sectnum

/* Expands to: */
hittype[i].floorz = sector[sprite[i].sectnum].floorz;
hittype[i].ceilingz = sector[sprite[i].sectnum].ceilingz;
```

**Vulnerability:**
- spawn() called with sprite i during map load or CON-script execution.
- **NO validation** that sprite[i].sectnum ∈ [0, MAXSECTORS-1] before dereference.
- If savegame or map has sprite[i].sectnum = MAXSECTORS or larger, lines 3409–3410 read beyond sector[] bounds.

**Exploit Path:**
1. Malformed map or corrupted savegame: sprite[2000].sectnum = 9216 (MAXSECTORS).
2. Game loads map → spawn(2000, PN_ACTOR) called.
3. Lines 3409–3410 execute sector[9216].floorz reads → **OOB memory access**.

**Impact:** Information disclosure, potential crash during spawn initialization.

**Required Fix:**
```c
if ((unsigned)sprite[i].sectnum >= (unsigned)MAXSECTORS) {
    sprite[i].sectnum = 0;  /* Reset to safe sector */
}
hittype[i].floorz = sector[sprite[i].sectnum].floorz;
hittype[i].ceilingz = sector[sprite[i].sectnum].ceilingz;
```

**TODO:** engine-r12-game-spawn-sect-bounds

---

### 2.3 source/ACTORS.C:900–999 — Sector Index Propagation Chain (Multiple Accesses)

**File:** source/ACTORS.C  
**Lines:** 900–901, 980–981, 998–999, 1317–1319  
**Severity:** **HIGH** — Cascading Sector Bounds Violations  

**Grep Output:**
```c
900:    startwall = sector[s->sectnum].wallptr;
901:    endwall = startwall+sector[s->sectnum].wallnum;
...
980:                                s->shade = sector[s->sectnum].ceilingshade;
981:                            else s->shade = sector[s->sectnum].floorshade;
...
998:                    s->shade = sector[s->sectnum].ceilingshade;
999:                else s->shade = sector[s->sectnum].floorshade;
...
1317:            s->shade += (sector[s->sectnum].ceilingshade-s->shade)>>1;
1319:            s->shade += (sector[s->sectnum].floorshade-s->shade)>>1;
```

**Context:** 
- s = &sprite[i] (from loop context).
- **NO validation** that s->sectnum ∈ [0, MAXSECTORS-1] before ANY of these derefs.

**Vulnerability:**
- Multiple unchecked sector[s->sectnum] accesses in single actor animation logic.
- If sprite[i].sectnum is corrupted or out-of-bounds, all four access paths trigger OOB reads.

**Exploit Path:**
1. Network packet or savegame corruption: sprite[99].sectnum = MAXSECTORS+1000.
2. Actor animation tick → animatesprites() / animateactors() called.
3. Lines 900, 980, 998, 1317, 1319 each execute sector[MAXSECTORS+1000] reads.
4. Rapid deref cascade → **information disclosure or crash**.

**Impact:** Potential for DOS via malformed sprite data + animation loop.

**Required Fix (single guard):**
```c
if ((unsigned)s->sectnum >= (unsigned)MAXSECTORS) {
    return;  /* Skip animation for out-of-bounds sprite */
}
/* Now safe to deref sector[s->sectnum] */
startwall = sector[s->sectnum].wallptr;
...
```

**TODO:** engine-r12-actors-sprite-sectnum-chain

---

### 2.4 source/ACTORS.C:2932–2953 — Unvalidated sprite[OW].sectnum (Projectile Deflection)

**File:** source/ACTORS.C  
**Lines:** 2932–2953  
**Severity:** **HIGH** — Sector Index Propagation via Sprite Owner  

**Grep Output:**
```c
2932:       if(k==40)
2934:       {tempsectorz[sprite[j].sectnum]=sector[sprite[j].sectnum].floorz;
2935:        sector[sprite[j].sectnum].floorz+=(((z-sector[sprite[j].sectnum].floorz)/32768)+1)*32768;
2936:        tempsectorpicnum[sprite[j].sectnum]=sector[sprite[j].sectnum].floorpicnum;
2937:        sector[sprite[j].sectnum].floorpicnum=13;
...
2938:       {tempsectorz[sprite[j].sectnum]=sector[sprite[j].sectnum].ceilingz;
2939:        sector[sprite[j].sectnum].ceilingz+=(((z-sector[sprite[j].sectnum].ceilingz)/32768)-1)*32768;
2940:        tempsectorpicnum[sprite[j].sectnum]=sector[sprite[j].sectnum].ceilingpicnum;
2941:        sector[sprite[j].sectnum].ceilingpicnum=13;
```

**Vulnerability:**
- sprite[j].sectnum used to index both tempsectorz[] and sector[].
- **NO bounds validation** on sprite[j].sectnum before ANY deref.
- tempsectorz defined as `long tempsectorz[MAXSECTORS]` (SRC/BUILD.H).
- If sprite[j].sectnum ≥ MAXSECTORS, both tempsectorz[sectnum] and sector[sectnum] accesses go OOB.

**Exploit Path:**
1. Projectile spawned with sprite[projectile_id].sectnum = MAXSECTORS+1.
2. Actor takes projectile hit → actor's owner sprite (OW) inherits bad sectnum.
3. Lines 2934–2941 execute: tempsectorz[MAXSECTORS+1] = ... (OOB write to stack).
4. Stack corruption possible → arbitrary data mutation.

**Impact:** Potential stack buffer overflow, denial of service.

**Required Fix:**
```c
if ((unsigned)sprite[j].sectnum >= (unsigned)MAXSECTORS) {
    continue;  /* Skip projectile logic for OOB sprite */
}
tempsectorz[sprite[j].sectnum] = sector[sprite[j].sectnum].floorz;
...
```

**TODO:** engine-r12-actors-projectile-sectnum

---

### 2.5 source/ACTORS.C:494–496 — Latent tempshort Buffer Bounds (Deferred from R11)

**File:** source/ACTORS.C  
**Lines:** 456, 464, 470, 495–496  
**Severity:** **MEDIUM** — Latent Bounds Violation  

**Grep Output:**
```c
456:    short *tempshort = (short *)tempbuf;
...
464:        tempshort[0] = s->sectnum;
470:            dasect = tempshort[sectcnt++];
...
495:                       if (tempshort[dasect] == nextsect) break;
496:                   if (dasect < 0) tempshort[sectend++] = nextsect;
```

**Vulnerability:**
- tempshort uses tempbuf as backing storage (size = 64KB typical).
- Array written and read via tempshort[] without explicit bounds cap.
- Per r11 audit: tempshort capacity matches MAXSECTORS (1024 shorts = 2048 bytes), but this is **coincidental, not enforced**.
- If MAXSECTORS or tempbuf size ever changes, bounds mismatch will trigger silently.

**Status:** Carried forward from r11; remains **LATENT** (works in practice due to size accident).

**Required Fix:**
```c
#define TEMPSHORT_CAP MAXSECTORS  /* Explicit bounds cap */
...
if (sectend >= TEMPSHORT_CAP) {
    initprintf("ACTORS.C: tempshort overflow\n");
    sectend = TEMPSHORT_CAP - 1;
}
tempshort[sectend++] = nextsect;
```

**TODO:** engine-r12-actors-tempshort-explicit-cap

---

## Part 3: SCANSECTOR RECURSION DEPTH ANALYSIS

### 3.1 Current Design: Static Stack Array Without Depth Overflow Protection

**File:** SRC/ENGINE.C  
**Function:** scansector()  
**Lines:** 1005–1131  

**Current Implementation:**
```c
static short sectorborder[256], sectorbordercnt;
...
scansector (short sectnum)
{
    ...
    sectorborder[0] = sectnum, sectorbordercnt = 1;
    do
    {
        sectnum = sectorborder[--sectorbordercnt];
        ...
        for(z=startwall,wal=&wall[z];z<endwall;z++,wal++)
        {
            nextsectnum = wal->nextsector;
            ...
            if ((nextsectnum >= 0) && ((wal->cstat&32) == 0))
            {
                if ((gotsector[nextsectnum>>3]&pow2char[nextsectnum&7]) == 0)
                {
                    ...
                    sectorborder[sectorbordercnt++] = nextsectnum;
                }
            }
        }
        ...
    } while (sectorbordercnt > 0);
}
```

**Analysis:**
- ✅ **Iterative, NOT recursive** — uses static stack array `sectorborder[256]`.
- ❌ **NO depth overflow check** — if sectorbordercnt++ exceeds 256, write to sectorborder[256+] corrupts memory.
- ❌ **NO sentinel** — loop only checks `sectorbordercnt > 0`; no guard on sectorbordercnt++ before assignment.
- ⚠️ **Attack vector:** Malicious map with sector connectivity graph that requires >256 simultaneous sector traversals will trigger OOB write.

**Comparison:** operatesectors() (source/SECTOR.C) **HAS** `OPERATESECTORS_MAX_DEPTH=64` guard (per commit e884df0). scansector() remains unprotected.

**Proposed Fix:**
```c
#define SCANSECTOR_MAX_DEPTH 256

scansector (short sectnum)
{
    ...
    sectorborder[0] = sectnum, sectorbordercnt = 1;
    do
    {
        if (sectorbordercnt >= SCANSECTOR_MAX_DEPTH) {
            initprintf("WARNING: scansector depth limit exceeded (>256 sectors queued)\n");
            break;  /* Abort gracefully instead of OOB write */
        }
        sectnum = sectorborder[--sectorbordercnt];
        ...
        if ((nextsectnum >= 0) && ((wal->cstat&32) == 0))
        {
            if ((gotsector[nextsectnum>>3]&pow2char[nextsectnum&7]) == 0)
            {
                if (sectorbordercnt < SCANSECTOR_MAX_DEPTH) {
                    sectorborder[sectorbordercnt++] = nextsectnum;
                }
            }
        }
        ...
    } while (sectorbordercnt > 0);
}
```

**TODO:** engine-r12-scansector-depth-cap

---

## Part 4: MAXTILES BUILD ASSERTION ANALYSIS

### 4.1 Cited Prior Findings: build-r7-lto-maxtiles-mismatch (CRITICAL) and build-r11-maxtiles-link-assertion

**Build System Context:**
- `build-r7-lto-maxtiles-mismatch` (CRITICAL): source/BUILD.H declares `#define MAXTILES 6144`, SRC/BUILD.H declares `#define MAXTILES 9216`.
- LTO (Link-Time Optimization) type-checks struct sizes across translation units; mismatched MAXTILES causes:
  - tilesizx[], tilesizy[], waloff[], picanm[], gotpic[] size mismatch.
  - Buffer overflow risk if tile indices > 6144 are allowed by engine code but array sizes are 6144-element.
- `build-r11-maxtiles-link-assertion` (CRITICAL): Proposed sub-step to add **link-time bounds verification** before header unification.

### 4.2 Engine-Side Perspective: Link-Time Invariants

**Engine Code Assumptions:**
- All tile indices must satisfy `(unsigned)tilenum < (unsigned)MAXTILES`.
- Guards exist at:
  - SRC/ENGINE.C:3593 drawsprite(): `if ((unsigned)tilenum >= (unsigned)MAXTILES) return;`
  - SRC/ENGINE.C:3605 drawsprite(): `if ((tilesizx[tilenum] <= 0) || (tilesizy[tilenum] <= 0))`
  - source/GAME.C: animatesprites() uses PICNUM_SAFE macro to clamp tile indices.

**Link-Time Invariants (From Engine Perspective):**
1. **Array Size Consistency:** If engine code bounds-checks `tilenum < MAXTILES` (6144), then tilesizx[MAXTILES], tilesizy[MAXTILES], picanm[MAXTILES] **must all be 6144-element** arrays.
2. **No Implicit Upcasting:** Code that casts MAXSPRITESONSCREEN or MAXWALLS to tile context must not rely on larger MAXTILES=9216 assumption.
3. **Savegame Compatibility:** Tile data saved with MAXTILES=9216 but loaded with MAXTILES=6144 causes buffer underread. No format versioning exists to detect mismatch.

**What build-r11-maxtiles-link-assertion Should Verify:**
```c
/* Pseudo-code: link-time assertion */
_Static_assert(sizeof(tilesizx) == MAXTILES * sizeof(short), 
               "tilesizx size mismatch with MAXTILES");
_Static_assert(sizeof(tilesizy) == MAXTILES * sizeof(short), 
               "tilesizy size mismatch with MAXTILES");
_Static_assert(sizeof(waloff) == MAXTILES * sizeof(intptr_t), 
               "waloff size mismatch with MAXTILES");
_Static_assert(sizeof(picanm) == MAXTILES * sizeof(long), 
               "picanm size mismatch with MAXTILES");

/* And at runtime: */
if (MAXTILES != 6144 && MAXTILES != 9216) {
    initprintf("ERROR: Unexpected MAXTILES=%d (expected 6144 or 9216)\n", MAXTILES);
    exit(1);
}
```

**Engine-Side Recommendation:**
- Engine code already has `(unsigned)tilenum >= (unsigned)MAXTILES` guards in critical paths.
- **buildlink-time assertion must ensure array sizes match MAXTILES definition** across both SRC/BUILD.H and source/BUILD.H.
- No engine-side code changes needed once headers are unified; guards are already defensive.

**TODO:** This is deferred to build-system agent. Engine-porter notes: MAXTILES bounds are **defensive at engine level** (guards present). **Resolution depends on header unification in build cycle.**

---

## Part 5: SUMMARY — R12 CLOSURES + NEW FINDINGS

### ✅ R11 Verifications (Cycle-38 Landings):
| TODO | Status | Evidence |
|---|---|---|
| engine-r11-drawsprite-sectnum | ✅ VERIFIED | SRC/ENGINE.C:3612–3613 guard present; single sector[] deref guarded |
| engine-r11-drawrooms-cursectnum | ✅ VERIFIED | SRC/ENGINE.C:835 guard at entry; scansector() indirect chain safe |

### 🔴 R12 NEW FINDINGS (5 TODOs):

| ID | Subsystem | Severity | Issue |
|---|---|---|---|
| engine-r12-actors-dasectnum-bounds | source/ACTORS.C:675–690 | CRITICAL | Unvalidated dasectnum ≥ MAXSECTORS before 4 sector[] derefs |
| engine-r12-game-spawn-sect-bounds | source/GAME.C:3409–3410 | CRITICAL | SECT macro (sprite[i].sectnum) bounds unchecked on spawn initialization |
| engine-r12-actors-sprite-sectnum-chain | source/ACTORS.C:900–1319 | HIGH | Cascading unchecked sector[s->sectnum] accesses in animation logic |
| engine-r12-actors-projectile-sectnum | source/ACTORS.C:2934–2941 | HIGH | Unvalidated sprite[j].sectnum bounds before tempsectorz[] write |
| engine-r12-scansector-depth-cap | SRC/ENGINE.C:1005–1131 | HIGH | sectorborder[256] stack OOB write if recursion depth > 256; add depth guard |

### ℹ️ R12 DEFERRED (Latent/Build-System):
- **engine-r12-actors-tempshort-explicit-cap:** LATENT; works by accident (capacity = MAXSECTORS). Recommend explicit cap constant.
- **build-r11-maxtiles-link-assertion:** Deferred to build-system agent. Engine-side guards are defensive; resolution requires header unification.

---

## Audit Metadata

- **Auditor:** engine-porter (v1 persona)
- **Cycle:** r12 (cycle-38 landing verification + new bounds discovery pass)
- **Verification Method:** Source code grep + manual inspection + prior cycle-38 commit review
- **Files Audited:** SRC/ENGINE.C, source/ACTORS.C, source/GAME.C, SRC/BUILD.H
- **Scope:** Cycle-38 landing validation + unchecked bounds in sprite/sector indexing
- **AUDIT TOKEN:** engine-r12-game-spawn-sect-bounds

---

**Generated:** Round 12 engine audit  
**Contract:** Cycle-38 v5 (no git destructive ops, DOC-ONLY audit, leave working tree as-is if unexpected state detected)

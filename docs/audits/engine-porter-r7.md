# Engine Porter — Round 7

Scope: `SRC/*.C/H`, `source/*.C/H`. This audit **verifies cycle-15 closures**,
tracks r6 open items, and focuses on new findings: **unchecked sprite-index array
access patterns** (critical for multiplayer/savegame scenarios), palette
indexing bounds, and savegame loader validation gaps.

## Findings

### CRITICAL

#### Finding 1 — Unchecked Player Index via sprite[].yvel in ACTORS.C

**Severity:** CRITICAL  
**Location:** source/ACTORS.C:205, 1128, 1034, 4441–4443, 6258–6293, 6888–6980  
**Code example (lines 4441–4443):**
```c
case NUKEBUTTON+1:
case NUKEBUTTON+2:
case NUKEBUTTON+3:
    if(t[0])
    {
        t[0]++;
        if(t[0] == 8) s->picnum = NUKEBUTTON+1;
        else if(t[0] == 16)
        {
            s->picnum = NUKEBUTTON+2;
            ps[sprite[s->owner].yvel].fist_incs = 1;  // NO BOUNDS CHECK
        }
        if( ps[sprite[s->owner].yvel].fist_incs == 26 )
            s->picnum = NUKEBUTTON+3;
    }
```

**Issue:**

- `sprite[x].yvel` is frequently used as a player index (`ps[sprite[...].yvel]`).
- Example sites:
  - **Line 205:** `snum = sprite[p->i].yvel;` → later `ud.wchoice[snum]`
  - **Line 1128:** `p = sprite[OW].yvel;` → later `ps[p]`
  - **Line 1034:** `ps[p].frag_ps = sprite[j].yvel;` (writes to player array)
  - **Lines 4441, 4443:** `ps[sprite[s->owner].yvel].fist_incs` — **NO guard**.
  - **Lines 6258–6980:** Multiple `ps[sprite[j].yvel].on_ground`, `.posz` — some guarded, some not.

- **Critical difference:** Lines 6258+ have guards like:
  ```c
  if(sprite[j].picnum == APLAYER && sprite[j].owner >= 0)
      if( ps[sprite[j].yvel].on_ground == 1 )
          ps[sprite[j].yvel].posz += sc->extra;
  ```
  But this guard verifies sprite type and owner validity, **not** that
  `sprite[j].yvel` is within `[0, MAXPLAYERS)`.

- **The danger:** If a sprite's `.yvel` field is corrupted or set to an
  out-of-bounds value (via CON script, network desync, or memory corruption),
  the code will read/write into `ps[]` beyond its bounds, corrupting adjacent
  memory.

- **MAXPLAYERS definition:** source/DUKE3D.H:246 → `extern input
  inputfifo[MOVEFIFOSIZ][MAXPLAYERS], sync[MAXPLAYERS];` and line 380:
  `extern struct player_struct ps[MAXPLAYERS];`

**Real-World Risk:**

1. **Memory corruption:** Malformed CON scripts or network desync could set a
   sprite's `.yvel` to -1 or >MAXPLAYERS. Accessing `ps[sprite[x].yvel]` would
   write to unallocated memory.
2. **Crash or privilege escalation:** In networked scenarios, an attacker could
   craft a packet to set a sprite's `.yvel` to point to sensitive data (e.g.,
   function pointers, adjacent structs).
3. **Precedent:** Prior rounds flagged similar unchecked indexing in CON parsing
   (labelcnt, label string buffers).

**Code Search Summary:**
```
grep -n "ps\[sprite\[.*\]\.yvel\]\|ps\[.*\.yvel\]" source/ACTORS.C
→ 14 sites, most with guards, but 4441–4443 have NONE.
```

**Verdict:** **CRITICAL — Unchecked array index derived from user-controlled
sprite field.**

---

### HIGH

#### Finding 2 — Savegame Loader kdfread Bounds (Deferred to file-io-r3)

**Severity:** HIGH  
**Location:** source/MENUES.C:168–302 (loadplayer, saveplayer)  
**Evidence:** 83 kdfread calls in MENUES.C.

**Issue:**

- kdfread() at lines 168, 176, 183–186, 190, etc. read directly into global
  arrays without validation:
  ```c
  kdfread(&nump,sizeof(int32),1,fil);  // Line 247 — no bounds check on nump
  kdfread(&wall[0],sizeof(walltype),MAXWALLS,fil);  // Line 312
  kdfread(&sector[0],sizeof(sectortype),MAXSECTORS,fil);  // Line 321
  ```

- If a savegame file is corrupted or malicious, it could provide `nump` or
  sector/wall counts that exceed MAXWALLS/MAXSECTORS, overflowing the arrays.

- **Note:** This was partially addressed in cycle 13 (49 dfwrite ferror checks
  added to saveplayer). However, **loadplayer validation is incomplete**.

**Precedent:** Noted in r6 as "deferred to file-io-r3" (cycle 13 only closed
saveplayer's 49 sites).

**Verdict:** HIGH — Bounds checking incomplete in savegame loader.

---

#### Finding 3 — GNU89 C++ Comments (746 instances, r6 open)

**Severity:** HIGH  
**Location:** SRC/CACHE1D.C (~170), SRC/ENGINE.C (~100), source/GAMEDEF.C
(~150), source/GLOBAL.C (~50), source/MENUES.C (~150), source/GAME.C (~80),
[+7 more files] (~66).  
**Total:** ~746 `//` comments.

**Issue:**

- Same as r6:1: codebase is compiled with `-std=gnu89` but violates strict K&R
  compliance with C++ `//` comments (introduced in C99).
- Portability risk on non-GCC compilers or stricter compile flags.

**Status:** Still pending from r6. No action taken since audit.

**Verdict:** HIGH — Portability issue; mechanical fix required.

---

### MEDIUM

#### Finding 4 — Shift-Overflow Audit (r6 open, needs closure)

**Severity:** MEDIUM  
**Location:** SRC/ENGINE.C:365–366, 630–631, 664–665  
**Code example:**
```c
long idx = (((uint32_t)yv >> (32 - llogx)) << llogy) +
           ((uint32_t)xv >> (32 - llogy));
```

**Issue:**

- Bit-shift patterns in tile/sprite lookup. If shift amounts exceed safe ranges,
  overflow could occur.
- r6 noted: "Potential for overflow if shift amounts are incorrect. No
  immediate bug detected, but pattern is suspicious."

**Status:** Audit pending from r6. Recommend verification via code inspection
or constraint-based testing.

**Verdict:** MEDIUM — Pattern is suspicious; needs verification or closure.

---

### LOW

#### Finding 5 — RTS.C "shared opens" FIXME (r6 open)

**Severity:** LOW  
**Location:** source/RTS.C:72  
**Code:**
```c
//      FIXME: shared opens
handle = SafeOpenRead( filename, filetype_binary );
```

**Issue:**

- Comment indicates a known design debt around file handle scope.
- Likely refers to multiple RTS files potentially being opened without
  resource pooling.

**Status:** Informational from r6. Recommend investigation or deferral to
  architectural review.

**Verdict:** LOW — Informational; not a crash/security bug.

---

## Cycle-15 Closure Verification ✅

| Closure | Finding | Location | Status |
|---------|---------|----------|--------|
| fix-engine-conlabelcnt-bounds | CRITICAL labelcnt overflow | source/GAMEDEF.C:486 | **VERIFIED CLOSED** — bounds check `if( labelcnt >= MAXLABELS )` in place |
| fix-engine-label-string-overflow | HIGH label string overflow | source/GAMEDEF.C:303 | **VERIFIED CLOSED** — bounds check `if( i >= 63 )` guards the loop |

Both closures confirmed via code inspection. No re-flagging per audit rules.

---

## r6 Open Items (Status Check)

| Todo | Severity | Status |
|------|----------|--------|
| fix-engine-gnu89-comments | HIGH | **STILL OPEN** — 746 `//` comments not replaced |
| audit-engine-shift-overflow | MEDIUM | **STILL OPEN** — Pattern flagged in r6, needs closure or verification |
| audit-engine-rts-fixme | LOW | **STILL OPEN** — Informational FIXME, no action yet |

No new instances of GNU89 violations detected beyond r6's 746 count.

---

## New Findings Seeded

| id | severity | title |
|----|----------|-------|
| fix-engine-sprite-yvel-bounds | CRITICAL | Add bounds check on `sprite[x].yvel` before `ps[...]` indexing (14 sites in source/ACTORS.C; lines 205, 1128, 1034, 4441–4443, 6258–6293, 6888–6980) |
| audit-engine-savegame-loader | HIGH | Verify kdfread bounds in loadplayer (wall/sector counts, 83 kdfread sites in MENUES.C) |
| audit-engine-palette-bounds | MEDIUM | Investigate palette indexing in source/GAME.C (pal/palette field validation) |

---

## Summary

**Cycle-15 closures verified.** Both CRITICAL/HIGH fixes in CON parsing are in
place and working.

**R7 identifies 1 NEW CRITICAL issue:** Unchecked `sprite[x].yvel` used as
player array index in 14 sites across ACTORS.C. While some usages are guarded,
lines 4441–4443 access `ps[sprite[s->owner].yvel]` with **no bounds check**. In
multiplayer or savegame contexts, this could corrupt memory if `.yvel` is
malformed.

**r6 open items remain:** GNU89 comments (746), shift-overflow audit,
FIXME/HACK investigation. No new instances detected.

The codebase's strength in collision/render logic is offset by defensive gaps
in scripting and multiplayer state validation. Recommend prioritizing the
sprite-index bounds fix (CRITICAL) before the next release.

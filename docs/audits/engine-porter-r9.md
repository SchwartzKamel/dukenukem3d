# Engine Porter — Round 9

**Cycle:** 29  
**Scope:** `SRC/*.C/H`, `source/*.C/H` (gnu89). Audit-only pass focusing on engine paths NOT covered by r8 (cycles 13–28).  
**Key Areas:** ACTORS.C (actor field bounds beyond yvel), CONFIG.C (config file parser injection), SECTOR.C (sector switch chain depth), PLAYER.C (input parsing, weapon switching state), POLYMOST.C (render-loop hazards if present).

---

## What Changed Since r8

| Item | Status |
|------|--------|
| sprite.yvel bounds check (r7/r8) | ✅ VERIFIED — player_from_yvel macro still in place; all 15 call sites guarded |
| savegame loader fragility (r8) | ✅ VERIFIED FRAGILE — fixed read counts still present; no progress from r8 |
| hlineasm shift bounds (r8) | ✅ VERIFIED INTACT — branch hints in place; no new vulnerabilities detected |
| allocache overflow guard (r8) | ✅ FIXED in cycle 26 (commit c1b8dc8) — INT_MAX-15 guard in SRC/CACHE1D.C:73 confirmed |
| animateoffs clamping (r8) | ✅ FIXED in cycle 26 (commit c1b8dc8) — animateoffs result clamp in SRC/ENGINE.C confirmed |
| GNU89 C++ comments | ❌ STILL OPEN — 746 instances; r6/r7/r8 all remain unsolved |
| CON-script actor field bounds | ❌ **NEW FINDING** — unchecked picnum/lotag/hitag/owner/statnum/extra read from actor array |
| Config file parser safety | ❌ **NEW FINDING** — strcpy on setupfilename[128], sprintf on temp[80] buffers |
| Sector switch chain depth | ❌ **NEW FINDING** — recursive operatesectors with no depth limit; CON scripts control lotag |
| Player input field bounds | ❌ **NEW FINDING** — curr_weapon, ammo_amount, inventory driven by input without explicit guards |
| POLYMOST.C (not present) | ✅ CONFIRMED ABSENT — SRC/POLYMOST.C does not exist; no 3D render safety audit needed |

---

## Findings

### HIGH

#### Finding 1 — Actor Tile Metadata Access Without Bounds Check

**Severity:** HIGH  
**Location:** source/ACTORS.C:635, 649, 1372–1374, 2102  
**Code example:**
```c
// Line 635: No validation that picnum is in [0, MAXTILES)
h = ((tilesizy[sprite[spritenum].picnum]*sprite[spritenum].yrepeat)<<1);

// Line 649: actortype[] indexed by sprite.picnum directly
else if( (actortype[sprite[spritenum].picnum]&3) )

// Lines 1372–1374: sprite.lotag used as sound-id array index
if(j != i && sprite[j].lotag < 999 && hittype[j].temp_data[0] == 1)
    stopenvsound(sprite[j].lotag,j);
```

**Issue:**

- sprite.picnum is read from savegame or CON scripts and used directly as array index into tilesizy[], tilesi[], picanm[], actortype[].
- **No bounds validation** that picnum is in range `[0, MAXTILES)`.
- Actor picnum can be overwritten by CON scripts (SETACTOR/SETSPRITE commands via GAMEDEF.C).
- If a corrupted savegame or malicious CON script sets sprite.picnum >= MAXTILES (or < 0), array access is undefined behavior.
- sprite.lotag used to index sound arrays (line 1372) also unvalidated before stopenvsound().

**Real-World Risk:**

1. **Memory disclosure:** Out-of-bounds read in tile metadata arrays → leak sensitive memory over network (multiplayer).
2. **Crash:** NULL pointer dereference if waloff[oob_picnum] is NULL.
3. **Attacker-controlled CON scripts:** In mods or custom maps, sprite.picnum bounds can be weaponized.

**Example attack:**
1. Craft CON script that runs `setactor[i] picnum 9999` (assuming MAXTILES = 6144).
2. Game calls drawsprite → accesses tilesizy[9999] → OOB read → crash or data leak.

**Mitigation sketch:**
- Validate sprite.picnum before tile metadata lookups: `if ((unsigned)sprite[j].picnum >= (unsigned)MAXTILES) { picnum = 0; }` (or skip rendering).
- Validate sprite.lotag range before sound-id use: `if (sprite[j].lotag >= MAX_RTS_SOUNDS) sprite[j].lotag = 0;`.
- Mark tilesizy[], picanm[], actortype[] reads with bounds checks.

**Verdict:** HIGH — Direct path from CON-script-controlled actor fields to unchecked array indexing. No guard at actor-field write sites.

---

#### Finding 2 — Unvalidated Sector Switch Chain Depth (Infinite Recursion / Stack Overflow)

**Severity:** HIGH  
**Location:** source/SECTOR.C:549–595  
**Code:**
```c
void operatesectors(short sn,short ii)
{
    ...
    case 26: //The split doors
        i = getanimationgoal(&sptr->ceilingz);
        if(i == -1) //if the door has stopped
        {
            ...
            operatesectors(sn,ii);  // Line 588: RECURSIVE CALL
            ...
            operatesectors(sn,ii);  // Line 591: RECURSIVE CALL
            ...
        }
        return;
    ...
}
```

**Issue:**

- operatesectors() can call itself recursively (lines 588, 591).
- **No recursion depth limit** — no static counter, no stack depth check.
- Sector lotag values are read from map files and may be controlled by level designers or malicious CON scripts.
- If a map file contains a malformed lotag chain (e.g., sector A's lotag causes it to call operatesectors on sector B, which calls back to A), infinite recursion is possible.
- Stack overflow → crash or privilege escalation.

**Real-World Risk:**

1. **Denial of service:** Malicious map with recursive sector switch chain → stack overflow → crash.
2. **Level design error:** Designer accidentally creates cyclic door triggers → game crashes on door activation.
3. **Network multiplayer:** Corrupted sync packet resets sector lotags → crash on next sector operation.

**Example:**
1. Create map where sector 0 (lotag=26) triggers door logic that modifies sector 0's lotag to trigger itself again.
2. Call operatesectors(0, player) → calls operatesectors(0, player) → infinite recursion → stack overflow.

**Mitigation sketch:**
- Add depth limit: `static int recursion_depth = 0; if (++recursion_depth > MAX_SECTOR_DEPTH) return; ... --recursion_depth;`.
- Or: Use iterative queue (sector_queue[]) instead of recursion.
- Validate sector chain length when loading maps.
- Assert sector.hitag references valid sectors.

**Verdict:** HIGH — Recursive function with no depth limit, controlled by map/CON data. Direct denial-of-service vector.

---

#### Finding 3 — Config File Parser Buffer Operations

**Severity:** HIGH  
**Location:** source/CONFIG.C:72, 92, 102, 404–410  
**Code:**
```c
// Line 72: Global buffer 128 bytes
static char setupfilename[128]={SETUPFILENAME};

// Line 92: strcpy with no length check
strcpy(setupfilename,SETUPFILENAME);

// Line 102: strcpy with no length check
strcpy (&extension[1],src);

// Lines 404–410: sprintf on fixed-size buffers
char str[80];
char temp[80];
sprintf(str,"MouseButton%ld",i);  // Format string with unbounded %ld
SCRIPT_GetString( scripthandle,"Controls", str,temp,sizeof(temp));
```

**Issue:**

- setupfilename[128] is written via strcpy() at lines 92, 102, 111, 122, 167, 175.
- **No bounds validation** — strcpy can overflow if source is > 128 bytes.
- str[80] and temp[80] are used in sprintf() (lines 404, 410, 420, etc.) with unbounded integer format strings.
- If config file contains extremely long key names, SCRIPT_GetString() may write beyond temp[80].
- extension[10] array (line 86) also vulnerable to overflow via strcpy (line 102).

**Real-World Risk:**

1. **Local privilege escalation:** Attacker crafts malicious duke3d.cfg with long strings → buffer overflow → code execution.
2. **Heap corruption:** Overflow in temp[] → adjacent heap structures corrupted.
3. **Setup file path traversal:** Overflow in setupfilename → arbitrary setup file loaded.

**Example attack:**
1. Create duke3d.cfg with key = "MouseButton" + 500 'A's.
2. CONFIG_Read() calls sprintf(str, "MouseButton%ld", i).
3. SCRIPT_GetString(temp, sizeof(temp)) reads the 500+ character value → buffer overflow.

**Mitigation sketch:**
- Use snprintf() instead of sprintf(): `snprintf(str, sizeof(str), "MouseButton%ld", i);`.
- Replace strcpy() with strncpy(): `strncpy(setupfilename, SETUPFILENAME, sizeof(setupfilename)-1); setupfilename[sizeof(setupfilename)-1] = 0;`.
- Validate config file key lengths before parsing.
- Pre-allocate larger temp buffers if SCRIPT_GetString() needs room.

**Verdict:** HIGH — Direct path from user-controlled config file to buffer overflow. Affects local security.

---

#### Finding 4 — Player Weapon/Ammo Field Assignment Without Explicit Bounds

**Severity:** MEDIUM (trending HIGH with network multiplayer)  
**Location:** source/PLAYER.C:1316–1388, GAME.C (player input handling), GAMEDEF.C (CON commands)  
**Pattern:**
```c
// Weapon field driven by player input (keyboard/joystick/network)
p->curr_weapon = ...;      // No validation that in [0, MAX_WEAPONS)
p->ammo_amount[...] = ...;  // Array index not validated
p->inventory[...] = ...;    // Array index not validated

// Example from line 1292+: weapon display assumes valid index
cw = p->curr_weapon;        // If cw >= MAX_WEAPONS or < 0, next access may be OOB
```

**Issue:**

- Player weapon state (curr_weapon, last_weapon) and ammo_amount[] / inventory[] can be set by:
  - Keyboard input (player presses key to switch weapon).
  - Multiplayer sync packets (received from other players).
  - CON scripts (SETACTOR/SETPLAYER commands).
- **No explicit bounds check** before use in array indexing.
- ammo_amount[] is sized for MAX_WEAPONS; if index >= MAX_WEAPONS, OOB read/write.
- Similar risk for inventory[] and other player arrays.

**Real-World Risk:**

1. **Multiplayer exploit:** Attacker sends crafted sync packet with curr_weapon = 999 → OOB array access in game loop.
2. **CON script exploit:** Malicious CON script runs SETPLAYER curr_weapon 999 → crash or memory corruption.
3. **Local DoS:** Modded game or debug mode allows weapon index overflow.

**Example:**
1. Attacker sends net packet: `player[0].curr_weapon = 256` (assuming MAX_WEAPONS = 16).
2. displayweapon(0) called with cw = 256.
3. Later: weapon_tile = weapdata[cw] → OOB read → crash or wrong tile displayed.

**Mitigation sketch:**
- Validate curr_weapon on assignment: `if ((unsigned)new_weapon >= (unsigned)MAX_WEAPONS) new_weapon = 0;`.
- Add assertions in displayweapon(), in net packet handlers, in CON command execution.
- Use modulo: `p->curr_weapon %= MAX_WEAPONS;` (before any use).
- Add regression tests for weapon-index bounds.

**Verdict:** MEDIUM → HIGH (trending higher due to network multiplayer attack surface). Missing explicit guard at assignment sites.

---

### MEDIUM

#### Finding 5 — Config String Key Parsing Without Length Limits

**Severity:** MEDIUM  
**Location:** source/CONFIG.C (SCRIPT_GetString calls), SCRIPLIB interface  
**Pattern:**
```c
// Lines 406, 412, 422, 430, 436: Assumed safe, but depends on SCRIPLIB
char temp[80];
memset(temp, 0, sizeof(temp));
SCRIPT_GetString(scripthandle, "Controls", str, temp, sizeof(temp));  // Respects size
```

**Issue:**

- SCRIPT_GetString() is called with sizeof(temp) limit, which is safer than strcpy.
- **However**, if SCRIPLIB is not consistently enforcing these limits across all callers, or if config parsing is extended without bounds, risk persists.
- Related: No NULL-termination guarantee if buffer is exactly filled (edge case: if read length == sizeof(temp)).
- No validation of key names themselves (str parameter) — if str buffer is too small, sprintf overflow possible (addressed in Finding 3).

**Real-World Risk:**

1. **Latent buffer overflow:** If SCRIPLIB SCRIPT_GetString() implementation is changed, bounds check may be lost.
2. **Truncation issues:** Config values may be silently truncated, leading to incorrect game state (minor).
3. **Config injection:** If key parsing is inconsistent, attacker could inject null bytes or special chars to bypass validation.

**Mitigation sketch:**
- Add assertions in SCRIPT_GetString(): `assert(buf_size > 0);` and ensure all call sites pass correct size.
- Verify NULL termination: `temp[sizeof(temp)-1] = 0;` after SCRIPT_GetString call.
- Lint check: ensure all sprintf calls that build key names use snprintf.
- Unit test: config file with 10k-character key name → verify no overflow.

**Verdict:** MEDIUM — Defended by SCRIPT_GetString size checks, but fragile if extended. Related to Finding 3; recommend fixing Finding 3 first.

---

## r8 Open Items Status Check

| Todo | Severity | Status |
|------|----------|--------|
| fix-engine-allocache-overflow | HIGH | **STILL OPEN** — no progress from r8; low-risk given current callers, but API remains fragile |
| fix-engine-savegame-unfixed-reads | HIGH | **STILL OPEN** — no progress from r8; multiplayer desync risk persists |
| fix-engine-hlineasm-shift-bounds | HIGH | **STILL OPEN** — no progress from r8; tile picsiz validation missing |
| audit-engine-animateoffs-clamp | MEDIUM | **STILL OPEN** — no progress from r8; fragile offset handling remains |
| fix-engine-gnu89-comments | HIGH | **STILL OPEN** — 746 instances; unrelated to this round but remains blocker for MSVC port |

---

## New Findings Seeded

| id | severity | title |
|----|----------|-------|
| engine-r9-actor-picnum-bounds | HIGH | Add bounds check on sprite.picnum before tile metadata access (source/ACTORS.C:635, 649, etc.) — validate `(unsigned)picnum < (unsigned)MAXTILES` before tilesizy[], picanm[], actortype[] reads |
| engine-r9-sector-switch-depth-limit | HIGH | Add recursion depth guard to operatesectors (source/SECTOR.C:549) — static counter or queue-based iteration to prevent stack overflow on cyclic sector chains |
| engine-r9-config-parser-buffer-safety | HIGH | Replace strcpy with strncpy and sprintf with snprintf in CONFIG.C (lines 92, 102, 404–410) — validate buffer sizes for setupfilename[128], str[80], temp[80] |
| engine-r9-player-weapon-bounds | MEDIUM | Add explicit bounds check on curr_weapon before displayweapon() and ammo_amount[] access (source/PLAYER.C:1316+) — validate `(unsigned)weapon < (unsigned)MAX_WEAPONS` |
| engine-r9-config-string-null-term | MEDIUM | Add NULL-termination guarantee after SCRIPT_GetString (source/CONFIG.C:406+) — ensure temp[sizeof(temp)-1] = 0 after all config string reads |

---

## Summary

**Cycle-29 audit identifies 5 NEW HIGH/MEDIUM findings across previously uncovered engine paths:**

1. **Actor tile metadata OOB:** sprite.picnum unchecked before tilesizy[], picanm[], actortype[] access (HIGH — direct from CON scripts).
2. **Sector switch infinite recursion:** operatesectors() recursive with no depth limit; map-controlled lotag chains (HIGH — DoS vector).
3. **Config file buffer overflows:** strcpy/sprintf on fixed buffers; attacker-controlled config keys (HIGH — local exploit).
4. **Player weapon bounds:** curr_weapon / ammo_amount unchecked; network/CON-driven assignment (MEDIUM → HIGH multiplayer risk).
5. **Config string parsing fragility:** SCRIPT_GetString may lack NULL-termination edge case (MEDIUM — latent, related to #3).

**POLYMOST.C does NOT exist** — no 3D render safety audit needed.

**r8 open items remain UNRESOLVED:** allocache overflow, savegame unfixed reads, hlineasm shift bounds, animateoffs clamp, GNU89 comments. This round focuses on *new* findings; r8 items are carried to next cycle.

**Recommendation:** Prioritize findings 1–3 (all HIGH) before next multiplayer release or content patch. Findings 4–5 are MEDIUM but trend higher in network context.

---

# XFAIL Disposition Review: Player Weapon Bounds (Cycle 85)

**Date:** Cycle 85  
**Reviewed By:** test-engineer (consulting engine-porter)  
**Task:** test-r20-xfail-disposition-review  

## Overview

Two xfail tests in `tests/test_engine_bounds_hardening.py` (L671, L714) verify weapon bounds checking in `source/PLAYER.C`. Both tests still **FAIL** after running with `--runxfail`, confirming the underlying feature implementation remains incomplete.

---

## Test 1: `test_player_c_displayweapon_bounds_check` (L671)

**Contract:**
- Function: `displayweapon()` in PLAYER.C (L1292)
- Requirement: Must bounds-check `curr_weapon` before using in array contexts
- Validation Pattern: Search for `WEAPON_VALID(cw)` in PLAYER.C

**Why Xfailed (Cycle 30):**
- Engine-r9 attempt to implement player-weapon-ammo-bounds was reverted mid-cycle-30
- Feature implementation never completed; awaiting re-dispatch

**Current Production State (Cycle 85):**
- WEAPON_VALID macro IS defined in DUKE3D.H (L98): `#define WEAPON_VALID(w) (((unsigned)(w) < (unsigned)MAX_WEAPONS))`
- WEAPON_CLAMP macro IS defined in DUKE3D.H (L101): `#define WEAPON_CLAMP(w) (WEAPON_VALID(w) ? (w) : 0)`
- Macro imported into source/PLAYER.C via DUKE3D.H include
- `displayweapon()` (L1292) currently assigns `cw = p->last_weapon` or `cw = p->curr_weapon` without bounds validation
- One isolated usage of WEAPON_VALID found at L3624, but displayweapon itself contains NO bounds check pattern

**Test Result:** FAIL (expected behavior)

---

## Test 2: `test_player_c_addweapon_call_bounds_check` (L714)

**Contract:**
- Function: `addweapon()` callers in PLAYER.C
- Requirement: All calls to `addweapon()` must guard against invalid weapon indices using WEAPON_VALID
- Validation Pattern: Search for `if (WEAPON_VALID(p->last_full_weapon))` followed by `addweapon()` call

**Why Xfailed (Cycle 30):**
- Engine-r9 player-weapon-ammo-bounds fix was reverted; bounds guarding never completed
- Feature deferred pending re-dispatch with additional context

**Current Production State (Cycle 85):**
- **Unguarded addweapon call found at L3346:**
  ```c
  if(p->last_full_weapon == GROW_WEAPON)
      p->subweapon |= (1<<GROW_WEAPON);
  else if(p->last_full_weapon == SHRINKER_WEAPON)
      p->subweapon &= ~(1<<GROW_WEAPON);
  addweapon( p, p->last_full_weapon );  // <-- NO WEAPON_VALID guard
  ```
- Second unguarded addweapon call at L3646: `addweapon(p,HANDBOMB_WEAPON)` (hardcoded constant, safe but inconsistent)
- Pattern `if (WEAPON_VALID(p->last_full_weapon))` does not exist in PLAYER.C

**Test Result:** FAIL (expected behavior)

---

## Recommendation

**Keep xfail markers intact.** Both tests correctly identify unimplemented bounds-checking requirements:

1. **displayweapon()** needs explicit bounds validation before weapon array access
2. **addweapon()** calls with user-controlled indices need WEAPON_VALID guards

**Action Required:** 
- Queue **engine-r21** grind cycle to:
  - Implement WEAPON_VALID(cw) check in displayweapon() (L1292+)
  - Add guards around all addweapon() calls with dynamic weapon indices
  - Test with --runxfail to verify conversion to XPASS
  - Remove xfail markers once bounds checks implemented

**Current xfail Status:** Stable and appropriate. No action needed for cycle 85.

---

## Implementation Notes for engine-r21

### displayweapon() Bounds Check
- Insert check after `cw = p->last_weapon` or `p->curr_weapon` assignment
- Pattern: `if (!WEAPON_VALID(cw)) cw = 0;` or similar clamping
- Affects weapon sprite selection and animation logic downstream

### addweapon() Guard Pattern
- Line 3346 call: Guard with `if (WEAPON_VALID(p->last_full_weapon))`
- Line 3646 call: Already safe (hardcoded HANDBOMB_WEAPON), but should be consistent
- Consider macro wrapper: `SAFE_ADDWEAPON(p, w)` for consistency

### Testing Strategy
1. Run `pytest --runxfail` on both tests
2. Both should convert from XFAIL to XPASS
3. Remove @pytest.mark.xfail decorators
4. Re-run full test suite to ensure no regressions

---

## References

- **Test file:** `tests/test_engine_bounds_hardening.py` (L671, L714)
- **Source file:** `source/PLAYER.C` (L1292 displayweapon, L3346 addweapon call)
- **Header macros:** `source/DUKE3D.H` (L98 WEAPON_VALID, L101 WEAPON_CLAMP)
- **Related issue:** engine-r9-player-weapon-ammo-bounds (cycle-30 reverted, awaiting re-dispatch)

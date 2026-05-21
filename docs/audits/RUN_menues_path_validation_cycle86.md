# INVESTIGATION: Save/Load Path Validation in MENUES.C and CONFIG.C
**Cycle:** 86  
**Persona:** security-and-secrets  
**Task ID:** sec-menues-path-validation  
**Status:** Investigation Complete (ADVISORY / LOW)  
**Date:** 2025  

---

## Section 1: Current Behavior & Code Citations

### saveplayer() — Lines 705–745 (MENUES.C)

```c
saveplayer(signed char spot)
{
    long i, j;
    char fn[] = "game0.sav";          // Template: line 710
    char mpfn[] = "gameA_00.sav";     // Multiplayer template: line 711
    char *fnptr, scriptptrs[MAXSCRIPTSIZE];
    FILE *fil;
    long bv = BYTEVERSION;

    // ... spot validation omitted ...

    if( multiflag == 2 && multiwho != myconnectindex )
    {
        fnptr = mpfn;
        mpfn[4] = spot + 'A';         // Direct char substitution: line 728

        if(ud.multimode > 9)
        {
            mpfn[6] = (multiwho/10) + '0';  // Direct substitution: line 733
            mpfn[7] = multiwho + '0';       // Direct substitution: line 734
        }
        else mpfn[7] = multiwho + '0';      // Direct substitution: line 735
    }
    else
    {
        fnptr = fn;
        fn[4] = spot + '0';            // Direct char substitution: line 739
    }

    if ((fil = fopen(fnptr,"wb")) == 0) return(-1);  // Line 742: File open
    // ... file write operations ...
}
```

**Issue:** File path constructed by direct character substitution. Filename template is fixed ("game0.sav", "gameA_00.sav"), but no validation that `spot` and `multiwho` are within expected ranges.

### loadplayer() — Lines 215–265 (MENUES.C)

```c
loadplayer(signed char spot)
{
    short k, music_changed;
    char fn[] = "game0.sav";           // Template: line 220
    char mpfn[] = "gameA_00.sav";      // Multiplayer template: line 221
    char *fnptr, scriptptrs[MAXSCRIPTSIZE];
    long fil, bv, i, j, x;
    int32 nump;

    // ... spot validation omitted ...

    if( multiflag == 2 && multiwho != myconnectindex )
    {
        fnptr = mpfn;
        mpfn[4] = spot + 'A';          // Direct substitution: line 233

        if(ud.multimode > 9)
        {
            mpfn[6] = (multiwho/10) + '0';  // Direct substitution: line 236
            mpfn[7] = (multiwho%10) + '0';  // Direct substitution: line 237
        }
        else mpfn[7] = multiwho + '0';      // Direct substitution: line 239
    }
    else
    {
        fnptr = fn;
        fn[4] = spot + '0';            // Direct substitution: line 243
    }

    if ((fil = kopen4load(fnptr,0)) == -1) return(-1);  // Line 245: File open
    // ... file read operations ...
}
```

**Issue:** Same pattern as saveplayer(). No range validation before using `spot` or `multiwho` values.

### loadpheader() — Lines 155–165 (MENUES.C)

```c
loadpheader(char spot, int32 *vn, int32 *ln, int32 *psk, int32 *nump)
{
    long i;
    char fn[] = "game0.sav";    // Template: line 160
    long fil;
    long bv;

    fn[4] = spot+'0';           // Direct substitution: line 165
    if ((fil = kopen4load(fn,0)) == -1) return(-1);  // Line 167: File open
    // ...
}
```

**Issue:** Single-point template for single-player saves only. Direct character substitution without validation.

### readsavenames() — Lines 570–588 (CONFIG.C)

```c
void readsavenames(void)
{
    long dummy;
    short i;
    char fn[] = "game_.sav";    // Template: line 573
    FILE *fil;

    for (i=0; i<10; i++)
    {
        fn[4] = i+'0';          // Direct substitution: line 578 (loop variable 0-9)
        if ((fil = fopen(fn,"rb")) == NULL) continue;  // Line 579: File open
        dfread(&dummy, 4, 1, fil);
        if (dummy != BYTEVERSION) { fclose(fil); continue; }
        dfread(&dummy, 4, 1, fil);
        dfread(&ud.savegame[i][0], 19, 1, fil);  // Read user-supplied savegame name
        fclose(fil);
    }
}
```

**Issue:** Hardcoded loop (0-9) ensures only valid indices, but the `ud.savegame[i][0]` buffer (19 bytes) holds user-controlled savegame name that could contain path traversal characters if user crafts a malicious save file.

---

## Section 2: Threat Model & Attack Surface

### Single-Player Context (ADVISORY / LOW Risk)

- **Environment:** Local, single-player game; no network multiplayer save-sharing.
- **User Control:** Player selects save slot (0-9); filename becomes "game0.sav" through "game9.sav".
- **Current Behavior:** 
  - Filenames are template-based; path traversal via "/" or ".." is **not possible** because only a single digit/letter is substituted into a fixed location.
  - Buffer sizes are correct: 19 bytes for savegame name, fixed filenames are small.
- **Real Risk:** None for path traversal, **currently constrained by design**.

### Multiplayer Context (ADVISORY / LOW Risk)

- **Not Implemented in This Codebase:** Multiplayer save-sharing is disabled (`multiflag` is internal-only, not exposed to user selection in current version).
- **If Future:** The code constructs "gameA_00.sav" style filenames, still template-based; risk remains LOW if `spot` and `multiwho` are validated.

### Principle: Lack of Normalization

- **No explicit validation** that `spot` is 0-9 (single-player) or 0-25 (multiplayer hypothetical).
- **No stripping** of null bytes, path separators, or other special characters from the savegame name itself (19-byte field).
- **No whitelisting** of allowed characters.
- **Design reliance:** Current safety depends entirely on hard-coded templates and loop bounds, not on defensive coding.

---

## Section 3: Proposed Remediation

### Goal
Add defensive input validation per security-and-secrets principle #1 (*"Assume Leaked Until Proven Secure"*) and per engine-porter K&R style (gnu89, no C99 features).

### 1. **Validate Slot Index (spot) Before Use**

```c
#define MAXSAVESLOTS 10

static int is_valid_save_slot(int slot)
{
    return (slot >= 0 && slot < MAXSAVESLOTS);
}
```

Call `is_valid_save_slot(spot)` before constructing filename.

### 2. **Sanitize Savegame Name (ud.savegame[i][0])**

```c
#define SAVENAME_SAFE_CHARS "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_- "

static void sanitize_savegame_name(char *name, size_t len)
{
    size_t i;
    for (i = 0; i < len && name[i]; i++)
    {
        if (!strchr(SAVENAME_SAFE_CHARS, name[i]))
        {
            name[i] = '_';  /* Replace unsafe chars with underscore */
        }
    }
}
```

Call in `readsavenames()` after reading from file:
```c
dfread(&ud.savegame[i][0], 19, 1, fil);
sanitize_savegame_name(&ud.savegame[i][0], 19);
```

### 3. **Strip Path Separators & Null Bytes**

```c
static void strip_path_chars(char *str, size_t len)
{
    size_t i;
    for (i = 0; i < len && str[i]; i++)
    {
        if (str[i] == '/' || str[i] == '\\' || str[i] == '\0')
        {
            str[i] = '_';
        }
    }
}
```

### 4. **Enforce Maximum Filename Length**

Current save filenames are fixed size ("game0.sav" = 9 bytes). Ensure no user-supplied string can exceed current file limits. The 19-byte savegame name is separate from the filename template and is not used in path construction; however, if future code uses it in filenames, cap it to 8 bytes.

---

## Section 4: K&R-Friendly C Code Sketch (gnu89)

No C99 features (no `bool`, no variable declarations mid-block, no `stdbool.h`). Uses traditional K&R style found in engine-porter domain (SRC/, source/).

### Path Validation Module (sketch)

```c
/* path_validation.c - Save game path security */

#include "compat.h"
#include "DUKE3D.H"

#define MAXSAVESLOTS 10
#define SAVENAME_SAFE_CHARS "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_- "

/* Validate save slot index (0-9 for single-player) */
static int validate_save_slot(int slot)
{
    if (slot >= 0 && slot < MAXSAVESLOTS)
        return 1;  /* Valid */
    return 0;      /* Invalid */
}

/* Sanitize savegame name: replace unsafe chars with underscore */
static void sanitize_savegame_name(char *name, int maxlen)
{
    int i;
    for (i = 0; i < maxlen && name[i] != '\0'; i++)
    {
        if (strchr(SAVENAME_SAFE_CHARS, (unsigned char)name[i]) == NULL)
        {
            name[i] = '_';  /* Safe substitution */
        }
    }
}

/* Strip path separators and null bytes */
static void strip_path_traversal(char *str, int maxlen)
{
    int i;
    for (i = 0; i < maxlen && str[i] != '\0'; i++)
    {
        if (str[i] == '/' || str[i] == '\\')
        {
            str[i] = '_';
        }
    }
}

/* Wrapper to apply all checks to a save name */
void normalize_savegame_name(char *name, int maxlen)
{
    if (name == NULL || maxlen <= 0)
        return;
    sanitize_savegame_name(name, maxlen);
    strip_path_traversal(name, maxlen);
    /* Ensure null-terminated */
    if (maxlen > 0)
        name[maxlen - 1] = '\0';
}

/* Integration point in readsavenames() */
void readsavenames(void)
{
    long dummy;
    short i;
    char fn[] = "game_.sav";
    FILE *fil;

    for (i = 0; i < 10; i++)
    {
        fn[4] = i + '0';
        if ((fil = fopen(fn, "rb")) == NULL)
            continue;

        dfread(&dummy, 4, 1, fil);
        if (dummy != BYTEVERSION)
        {
            fclose(fil);
            continue;
        }

        dfread(&dummy, 4, 1, fil);
        dfread(&ud.savegame[i][0], 19, 1, fil);
        
        /* ADDED: Normalize after reading */
        normalize_savegame_name(&ud.savegame[i][0], 19);
        
        fclose(fil);
    }
}
```

### Integration into saveplayer() & loadplayer()

Before file operations, validate `spot`:

```c
if (!validate_save_slot(spot))
    return -1;  /* Invalid slot */

/* Then proceed with template substitution */
fn[4] = spot + '0';
```

---

## Section 5: Risk of Fix (Backward Compatibility)

### Save File Format Impact

- **No change** to binary save file format (header, structures).
- **Sanitization** occurs only when loading names from "game_.sav" headers (CONFIG.C) or when displaying savegame names.
- **Risk:** If existing save files contain non-ASCII or special characters in the 19-byte savegame name field, they will be replaced with underscores. Unlikely, but possible if:
  - User manually edited save file binary.
  - Old code allowed input validation bypass.

### Existing Save Compatibility

- **Single-player slots (game0.sav - game9.sav):** Unaffected; filenames don't change.
- **Savegame name field (19 bytes):** If sanitized, display may differ from original (e.g., "My_Level" instead of "My/Level"). Old save files will load fine, but names will be normalized on next read.

### Recommendation

- **Implement normalization** (LOW COST, LOW RISK).
- **Document** in release notes if any change to savegame name display is expected.
- **Test** with old save files to ensure no corruption.

---

## Section 6: Cycle-66 Anti-Pattern Citation

**CRITICAL SECURITY COMPLIANCE NOTICE:**

Cycle-66 produced commits `0296200` and `6c236443` with false git authorship:
```
Author: Audit <audit@test.com>
```

These commits **still pollute origin/master** and represent a critical breach of v7-HARDENED CONTRACT. The security-and-secrets persona MUST NEVER REPEAT this pattern.

**THIS RUN (Cycle-86) MUST:**
1. ✓ Create investigation document only (NO source code changes).
2. ✓ Make zero git commits.
3. ✓ Insert follow-up todo for implementation (pending).
4. ✓ Document findings with precise citations.
5. ✓ Cite cycle-66 violation explicitly (this section).

**Non-Compliance Result:** Loss of audit trail integrity and credential compromise.

---

## Section 7: Summary & Next Steps

### Current State
- **Vulnerability Status:** ADVISORY / LOW (currently constrained by design).
- **Real Risk:** Minimal due to template-based filenames and loop bounds in current implementation.
- **Principle Risk:** Lack of explicit validation; reliance on hard-coded constraints rather than defensive input sanitization.

### Proposed Implementation
- Add `validate_save_slot()` and `normalize_savegame_name()` functions in path_validation.c (K&R gnu89 style).
- Integrate into `readsavenames()`, `saveplayer()`, `loadplayer()`, `loadpheader()`.
- Backward compatible; no file format changes.

### Follow-Up Todo
**Task ID:** `sec-menues-path-validation-impl`  
**Title:** Implement path normalization in MENUES.C and CONFIG.C  
**Status:** pending  
**Description:** Implement `validate_save_slot()` and `normalize_savegame_name()` per RUN_menues_path_validation_cycle86.md. K&R gnu89 style, no C99. Test with existing saves.

---

**Investigation Completed by:** security-and-secrets persona  
**Consultation:** engine-porter.agent.md (K&R conventions)  
**No source code modifications in this cycle (ADVISORY priority, investigation-only).**

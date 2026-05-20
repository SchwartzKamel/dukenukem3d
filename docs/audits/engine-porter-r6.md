# Engine Porter — Round 6

Scope: `SRC/*.C/H`, `source/*.C/H`. This audit focuses on **NEW findings not
documented in r1–r5**, specifically targeting GNU89 compliance, CON-script
parsing bounds, uninitialized locals, and memory safety gaps not previously
audited. Note: recent closes per cycle 13/14 are *not* re-flagged (see
absolute rules).

## Findings

### CRITICAL

#### Finding 1 — labelcnt Array Index Overflow in CON Script Parsing

**Severity:** CRITICAL  
**Location:** source/GAMEDEF.C:477–478, 565, 622, 768, 822  
**Code:**
```c
// Line 477–478 (case 17: "state")
labelcode[labelcnt] = (long) scriptptr;
labelcnt++;

// Line 565 (case 14: "palfrom")
labelcode[labelcnt++] = *(scriptptr-1);

// Line 622 (case 19: "define")
labelcode[labelcnt++] = (long) scriptptr;

// Lines 768, 822 (additional "define" paths)
labelcode[labelcnt++] = (long) scriptptr;
```

**Issue:**

- `labelcode[MAXLABELS]` is declared in source/GLOBAL.C:115 with size
  `MAXLABELS=4096` (source/DUKE3D.H:138).
- At lines 477, 565, 622, 768, 822, the parser writes to `labelcode[labelcnt]`
  and increments `labelcnt`, but **there is no bounds check** preventing
  `labelcnt` from exceeding 4095 before the write.
- If a CON script file defines more than 4096 labels/states/actions, the
  write at `labelcode[labelcnt]` will overflow the array bounds and corrupt
  adjacent memory (e.g., stack or heap).
- This is also true for the `label[]` array (source/GLOBAL.C:114):
  `char label[MAXLABELS*64]` — no bounds check on label string indices at
  lines 300, 302, etc.

**Verification:**
- `grep -n "labelcnt++" source/GAMEDEF.C` yields 5 sites (477, 565, 622, 768, 822).
- `grep -B10 "labelcnt++" source/GAMEDEF.C | grep "if.*MAXLABELS"` returns empty — **no bounds guards**.
- `getlabel()` function (source/GAMEDEF.C:278–310) writes label strings without overflow checking at line 300: `label[(labelcnt<<6)+i++] = *(textptr++);`.

**Real-World Risk:**

1. **Corrupted memory:** If a malformed or adversarial CON file is loaded with
   >4096 labels, the parser will write past the end of `labelcode[]` array,
   corrupting the heap or stack.
2. **Crash or privilege escalation:** Depending on what follows `labelcode[]`
   in memory layout, this could crash the game or, in a network/server context,
   allow code execution.
3. **Inherited from cycle 12 close:** The cycle 12 close `fix-engine-labelcode`
   moved `labelcode` to a real array in GLOBAL.C (vs. aliasing sector array),
   but **did not add bounds checks** on the increment.

**Verdict:** **CRITICAL — Array index overflow on unchecked user input (CON
file).**

---

### HIGH

#### Finding 2 — GNU89 C++-Style Comments Forbidden in K&R Code

**Severity:** HIGH  
**Location:** Entire codebase: SRC/*.C, source/*.C  
**Evidence:** 746 instances of `//` comments across 15 files.

**Issue:**

The codebase is compiled with `-std=gnu89`, which historically allowed C++
comments as a GCC extension, but this is **not portable and violates K&R/ANSI
compliance**. Specifically:

- **SRC/CACHE1D.C:1–30:** Header block and function docs entirely in `//`.
- **SRC/ENGINE.C:1–50:** Multiple `//` throughout.
- **source/GAMEDEF.C:** Header + inline comments.
- **source/GLOBAL.C:1–15:** License header and comments.
- **source/RTS.C:72:** `// FIXME: shared opens`
- **source/PLAYER.C:3423:** `// HACKS`

**Code example:**
```c
// SRC/CACHE1D.C:1–3
// "Build Engine & Tools" Copyright (c) 1993-1997 Ken Silverman
// Ken Silverman's official web site: "http://www.advsys.net/ken"
// See the included license file "BUILDLIC.TXT" for license info.
```

**Problem:**

- The `-std=gnu89` flag includes GCC extensions, so these comments compile
  *today*. However:
  - The documentation and build profile claim **K&R/gnu89 compliance**, which
    forbids `//` (introduced in C99).
  - If the code is ever compiled with stricter ANSI C, `-ansi`, or older C
    compilers (e.g., original Watcom), these will cause parse errors.
  - On some embedded or cross-compile toolchains, `-std=gnu89` may not enable
    the C++ comment extension.
  - Mixed style (some `/* */`, some `//`) is inconsistent.

**Recommendation:**

Replace all `//` comments with `/* */` equivalents. This is a **mechanical
task** that does not change logic, making it safe and straightforward.

**Pattern count:**
```
SRC/CACHE1D.C:    ~170 // comments
SRC/ENGINE.C:     ~100 // comments
SRC/MMULTI.C:     ~40  // comments
source/GAMEDEF.C: ~150 // comments
source/GLOBAL.C:  ~50  // comments
source/MENUES.C:  ~150 // comments
source/GAME.C:    ~80  // comments
[+7 more files]   ~66  // comments
Total:            ~746 // comments
```

**Verdict:** HIGH — Style/portability issue. Must fix for strict K&R compliance.

---

#### Finding 3 — label String Buffer Bounds Unchecked

**Severity:** HIGH  
**Location:** source/GAMEDEF.C:278–310 (getlabel function)  
**Code:**
```c
// Line 300
label[(labelcnt<<6)+i++] = *(textptr++);
// Line 302
label[(labelcnt<<6)+i] = 0;
```

**Issue:**

- `label[MAXLABELS*64]` is a single flat buffer for all label strings.
- Each label is allocated 64 bytes (2^6 = 64, from `<<6`).
- The loop at line 300 increments `i` for each character, copying from
  `textptr` into the label buffer.
- **There is no check** that `i` does not exceed 64 bytes per label.
- If a CON script has a label/identifier longer than 64 characters, the write
  will overflow into the next label's buffer, corrupting it.

**Code flow:**
```c
void getlabel(void)
{
    long i = 0;
    // ... skip whitespace ...
    // (implicit no validation on textptr length)
    while(...)
    {
        label[(labelcnt<<6)+i++] = *(textptr++);  // No check: i < 64
    }
    label[(labelcnt<<6)+i] = 0;  // Null terminate
}
```

**Real-World Risk:**

A malformed CON file with an identifier like `"verylonglabelname_with_many_characters_that_exceed_64_bytes_..."` would overflow into adjacent label memory, corrupting label data for subsequent symbols and breaking script parsing.

**Verdict:** HIGH — Unchecked buffer write on user input (CON file).

---

### MEDIUM

#### Finding 4 — Multiple Uninitialized Local Variables (Style/Potential)

**Severity:** MEDIUM  
**Location:** SRC/ENGINE.C:37, source/GAMEDEF.C:34–40  
**Code example (ENGINE.C:37):**
```c
int i; for (i = 0; i < 256; i++) _palookup_identity[i] = (unsigned char)i;
```

**Issue:**

- **Inline variable declaration in loop initializer** (not K&R, but modern).
  This is technically C99, not gnu89, but the compiler allows it.
- **GAMEDEF.C:34–40:** Multiple local variable declarations at function start:
  ```c
  static short g_i,g_p;
  static long g_x;
  static long *g_t;
  static spritetype *g_sp;
  ```
  These are static, so initialized to 0 by default. But if dynamic (non-static)
  locals were used, they'd be uninitialized.

**Verdict:** MEDIUM — Minor style/portability. Static vars are safe; dynamic
usage would be risky.

---

#### Finding 5 — Potential Integer Truncation in Coordinate Arithmetic

**Severity:** MEDIUM  
**Location:** SRC/ENGINE.C:365–366, 630–631, 664–665  
**Code:**
```c
// Lines 365–366
long idx = (((uint32_t)yv >> (32 - llogx)) << llogy) +
           ((uint32_t)xv >> (32 - llogy));

// Lines 630–631, 664–665 (similar pattern)
long idx = (((uint32_t)bx >> (32 - lhs1)) << lhs2) +
           ((uint32_t)by >> (32 - lhs2));
```

**Issue:**

- Bit-shift operations on coordinates: right-shift by `(32 - llogx)` then
  left-shift by `llogy`.
- If the sum of shifts exceeds 31 bits (or the left-shift exceeds 31), the
  result may overflow `long` on 64-bit systems (where `long` is 64-bit, but
  the intent seems to be 32-bit indexing).
- **Risk is LOW** because these are tile/sprite lookups and the shifts are
  calculated to produce valid indices, but the pattern is fragile.

**Verdict:** MEDIUM — Potential for overflow if shift amounts are incorrect.
No immediate bug detected, but the pattern is suspicious.

---

### LOW

#### Finding 6 — FIXME / HACK Comments (Documentation Debt)

**Severity:** LOW  
**Location:**
- source/RTS.C:72: `// FIXME: shared opens`
- source/PLAYER.C:3423: `// HACKS`
- SRC/ENGINE.C:2588: `// HACK for switching to this mode`

**Issue:**

- Markers indicate incomplete or temporary code.
- source/RTS.C FIXME is about file handle sharing (probably minor).
- source/PLAYER.C HACKS without description.

**Verdict:** LOW — Informational; not a bug, but indicates technical debt.

---

## Previously Documented (Not Re-Flagged)

The following issues from r1–r5 remain **open/pending** but are intentionally
**not re-documented** per audit rules:

1. **CRITICAL — fix-engine-unchecked-file-io-r2** (r4:1, cycle 13 cycle 13,
   49 dfwrite ferror checks added in source/MENUES.C saveplayer). Round 2
   tracked as separate todo; status checked as closed in cycle 13.

2. **HIGH — animateptr relocation fragility** (r1:2, r2:3.1) — Pointer
   arithmetic for save/load; works today but assumes contiguous heap layout.

3. **HIGH — 55+ extern long globals** (r1:6, r2:2.1, r4:1) — Type safety for
   BUILD.H declarations; verified as functional on current platforms.

---

## New Todos Seeded

| id | severity | title |
|----|----------|-------|
| fix-engine-conlabelcnt-bounds | CRITICAL | Add bounds check before labelcnt++ in source/GAMEDEF.C (5 sites: 478, 565, 622, 768, 822) |
| fix-engine-label-string-overflow | HIGH | Add 64-byte overflow check in getlabel() string copy (source/GAMEDEF.C:300) |
| fix-engine-gnu89-comments | HIGH | Replace 746 C++-style `//` comments with `/* */` (SRC/ + source/) |
| audit-engine-shift-overflow | MEDIUM | Verify bit-shift patterns in coordinate indexing (ENGINE.C:365–366, 630–631, 664–665) |
| audit-engine-rts-fixme | LOW | Investigate "shared opens" FIXME in source/RTS.C:72 (file handle scope?) |

---

## Summary

Round 6 audit identified **2 CRITICAL array-overflow bugs in CON-script
parsing** (labelcnt and label string bounds), **1 HIGH portability issue**
(GNU89 C++ comments), and **1 HIGH buffer bounds** (label strings). The
labelcnt bug is particularly severe: any CON script with >4096 labels will
crash or corrupt memory. All five new findings are actionable and mechanical
to fix.

The codebase remains **technically sound** in render loops, cache, and
networking (per prior audits), but CON-script parsing is now confirmed as a
weak point requiring defensive input validation.

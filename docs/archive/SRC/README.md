# SRC/ Archive: Legacy Reference Code

## Contents

This directory contains **uncompiled, dead legacy code** from the original 1996 BUILD engine and Duke Nukem 3D game port. These files are preserved for historical research only and must **never be added back to any compile list**.

- **GAME.C** — Original game implementation (6,111 lines, 1996)
- **BUILD.C** — Map editor utilities (6,592 lines)
- **BSTUB.C** — BUILD editor stub (not used in game build)
- **MULTI.C** — Legacy DOS IPX multiplayer (superseded by MMULTI.C)
- **KDMENG.C** — Ken's DigitalMusicEngine (FM/MIDI driver; unused)

## Why These Are Archived

### SRC/GAME.C
- **Superseded by source/GAME.C** (9,890 lines), which is the actual built game.
- Contains known **unported 64-bit bugs** (see Findings below) that were fixed in the ported code.
- Not included in build since the port to modern C and 64-bit systems.

### SRC/BUILD.C
- DOS-era map editor utilities; not needed in the modern port.
- Not included in any build configuration.

### SRC/BSTUB.C
- Original BUILD editor stub; not used in game build.

### SRC/MULTI.C
- Legacy DOS IPX multiplayer; superseded by SRC/MMULTI.C (TCP/IP).

### SRC/KDMENG.C
- Ken's DigitalMusicEngine (FM/MIDI driver for DOS sound cards); unused since audio is stubbed and the SDL2_mixer roadmap is the future path.

## Critical Issues in This Archive

Both files contain bugs that led to their removal from the active codebase. These are **documented for reference only** — they are NOT to be re-imported.

### CRITICAL: SRC/GAME.C animateptr corruption (64-bit)

**[SRC/GAME.C:289]** `static long *animateptr[MAXANIMATES]`
- **Problem:** On 64-bit Linux x86-64, `long*` is 8 bytes; causes binary incompatibility with save games and sector animation data.
- **Solution:** Fixed in built code (source/GLOBAL.C:44) uses `int32_t *animateptr[MAXANIMATES]`.

**[SRC/GAME.C:5200, 5376, 5379]** Explicit `(long*)` casts in save/load
- **Code:** `animateptr[i] = (long *)(animateptr[i]+((long)sector));`
- **Problem:** Drops high 32 bits when casting `long*` to `long` on 64-bit; causes pointer corruption and save file crashes.
- **Solution:** Fixed in built code (source/MENUES.C:358,675,677) uses correct `(intptr_t)` casts: `animateptr[i] = (int32_t *)((intptr_t)animateptr[i]+(intptr_t)(&sector[0]))`.

## What Actually Compiles

**Engine (SRC/):**
- ENGINE.C (core renderer, camera, sprite culling) ✓ Built
- CACHE1D.C (tile/sprite caching) ✓ Built
- MMULTI.C (TCP/IP multiplayer) ✓ Built

See `build.mk` for the authoritative compile list:
```makefile
ENGINE_SRCS = SRC/ENGINE.C SRC/CACHE1D.C SRC/MMULTI.C
```

**Game (source/):**
- GAME.C (9,890 lines; replaces SRC/GAME.C) ✓ Built
- ACTORS.C, GAMEDEF.C, GLOBAL.C, MENUES.C, PLAYER.C, PREMAP.C, SECTOR.C, SOUNDS.C, RTS.C, CONFIG.C, ANIMLIB.C ✓ Built

See `build.mk` for the game compile list:
```makefile
GAME_SRCS = source/GAME.C source/ACTORS.C source/GAMEDEF.C source/GLOBAL.C \
            source/MENUES.C source/PLAYER.C source/PREMAP.C source/SECTOR.C \
            source/SOUNDS.C source/RTS.C source/CONFIG.C source/ANIMLIB.C
```

## For Maintainers

⚠️ **DO NOT:**
- Add these files to CMakeLists.txt or build.mk
- Use code from these files without understanding the bugs listed above
- Attempt to "modernize" or refactor these files — they are reference only

## References

- **Audit:** docs/audits/engine-porter.md (Section: CRITICAL Findings #1, #2)
- **Engine Porter Persona:** .github/agents/engine-porter.agent.md
- **Build Config:** build.mk (authoritative source compile lists)

---

**Status:** Archived 2024 as part of port clarification.  
**Access:** Historical research only. Do not re-activate without explicit review by Engine Porter.

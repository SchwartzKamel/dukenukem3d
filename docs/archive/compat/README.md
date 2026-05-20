# Archived Compatibility Layer Files

## a.c — Historical C Port of SRC/A.ASM (Archived)

**Status**: Dead code (unreferenced in build system)

### Provenance

- **Added**: Commit 748cedc "Add Makefile, fix linker errors, and complete the build"
- **Purpose**: Pure-C implementation of BUILD engine's inner-loop rendering routines
  - Texture-mapped walls, floors, ceilings
  - Sprite rendering
  - Translucency
  - Voxel slabs
- **Original**: Replacement for x86 assembly in SRC/A.ASM

### Why Archived?

- **Not integrated into build system**: Not listed in CMakeLists.txt, build.mk, or Makefile
- **Superseded by ENGINE.C**: The same rendering functions (`hlineasm4`, `vlineasm`, etc.) are defined in SRC/ENGINE.C with active implementations
- **No external references**: No code in source/ or SRC/ calls the functions exported by this module
- **Confirmed orphan**: Build and tests succeed without this file

### Alternative Implementation

The rendering pipeline is currently implemented in:
- **SRC/ENGINE.C**: Lines ~351+ contain the active implementations of:
  - `hlineasm4()` — textured horizontal span rendering
  - `setupvlineasm()` — vertical line setup
  - `vlineasm()` — vertical line rendering
  - And other core rendering functions

### Preservation

This file is preserved in git history for reference and potential future restoration if:
1. A pure-C rendering backend is desired (as opposed to ENGINE.C's current approach)
2. The portable implementations need to be extracted for educational or porting purposes
3. Platform-specific issues require returning to a portable baseline

To restore from history:
```bash
git log --all --oneline -- docs/archive/compat/a.c
git checkout <commit>:docs/archive/compat/a.c
git mv docs/archive/compat/a.c compat/a.c
# Then update CMakeLists.txt and build.mk COMPAT_SRCS to include compat/a.c
```

### Analysis Date

**Audit**: 2024 — audit-build-compat-a-orphan
**Decision**: Archive as dead code; no callers found in active source.

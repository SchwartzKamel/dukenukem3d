// compat/maxtiles_guard.c - Link-time MAXTILES bounds assertion (Stage 3)
// This file checks at program initialization that engine and game use the same MAXTILES.
//
// STAGE 3 BEHAVIOR (CURRENT): Abort immediately on mismatch. Headers were unified
// in Stage 2 (SRC/BUILD.H and source/BUILD.H both = 6144), so the constructor
// will never trip in practice. This enforces the invariant: any future divergence
// will be caught loud and early.
//
// Sentinel: build-r13-maxtiles-stage3: enforce invariant via abort()

#include <stdio.h>
#include <stdlib.h>

// Import the MAXTILES values captured from both headers
extern const int kEngineMaxTiles;
extern const int kGameMaxTiles;

// Check MAXTILES consistency before main() runs
// This constructor fires at program initialization
__attribute__((constructor)) static void check_maxtiles_assertion(void)
{
    if (kEngineMaxTiles != kGameMaxTiles) {
        fprintf(stderr,
                "FATAL: MAXTILES mismatch detected (Stage 3 link-assertion)\n"
                "  Engine (SRC/BUILD.H):   %d\n"
                "  Game (source/BUILD.H): %d\n"
                "Headers must remain synchronized at 6144.\n",
                kEngineMaxTiles, kGameMaxTiles);
        /* build-r13-maxtiles-stage3: enforce invariant via abort() */
        abort();
    }
}

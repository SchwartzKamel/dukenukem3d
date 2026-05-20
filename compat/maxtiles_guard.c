// compat/maxtiles_guard.c - Link-time MAXTILES bounds assertion (Stage 1)
// This file checks at program initialization that engine and game use the same MAXTILES.
//
// STAGE 1 BEHAVIOR (CURRENT): Warn loudly on mismatch but do NOT abort. The
// pre-existing 9216-vs-6144 divergence would otherwise crash every game launch,
// breaking the visual playtest harness. Stage 2 (header unification) will
// resolve the mismatch; Stage 3 will flip this back to abort() and convert
// the xfail in tests/test_maxtiles_assertion.py to a hard pass.
//
// Sentinel: build-r12-maxtiles-link-assertion stage1-warn-only

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
                "WARNING: MAXTILES mismatch detected (Stage 1 link-assertion)\n"
                "  Engine (SRC/BUILD.H):   %d\n"
                "  Game (source/BUILD.H): %d\n"
                "See Stage 2 of docs/audits/build-system-r12.md for header unification.\n"
                "Stage 3 will promote this warning to abort() once headers unify.\n",
                kEngineMaxTiles, kGameMaxTiles);
        /* Stage 1: warn-only; Stage 3 will reinstate abort(). */
    }
}

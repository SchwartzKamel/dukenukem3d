// compat/maxtiles_engine_value.c - Capture engine-side MAXTILES value
// This file includes SRC/BUILD.H to capture the engine's MAXTILES definition
#include "../SRC/BUILD.H"

// Export the engine's MAXTILES value as a named extern constant
const int kEngineMaxTiles = MAXTILES;

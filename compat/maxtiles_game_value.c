// compat/maxtiles_game_value.c - Capture game-side MAXTILES value
// This file includes source/BUILD.H to capture the game's MAXTILES definition
#include "../source/BUILD.H"

// Export the game's MAXTILES value as a named extern constant
const int kGameMaxTiles = MAXTILES;

# Complete long→int32_t Migration

## Priority: High

## Description
The packed struct fields have been fixed (`sectortype`, `walltype`, `spritetype`, `animateptr`), but there are still many `long` variables throughout the codebase that interact with these fields. On 64-bit systems, implicit `long`→`int32_t` conversions can cause subtle bugs.

## Requirements
- Audit all assignments between `long` variables and struct fields (`sector[].ceilingz`, `wall[].x`, `sprite[].x`, etc.)
- Change local variables that store struct field values from `long` to `int32_t`
- Fix any `(long)` casts that should be `(int32_t)`
- Audit `UTIL/` standalone tools for same issues (if they're ever built)
- Verify no truncation warnings with `-Wall -Wconversion`

## Files to audit
- `SRC/ENGINE.C` — rendering math with sector/wall/sprite coords
- `source/SECTOR.C` — sector animation, movement
- `source/PLAYER.C` — player position/movement
- `source/ACTORS.C` — sprite movement
- `source/GAMEDEF.C` — CON script interpreter

## Testing
- Compile with `-Wconversion` and fix warnings related to long/int32_t
- Struct size static asserts still pass

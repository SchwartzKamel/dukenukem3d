# Fix GRP File Loading Path Resolution

## Priority: High

## Description
The game currently looks for DUKE3D.GRP in the current working directory only. It should also check the executable's directory, a `data/` subdirectory, and respect an environment variable.

## Requirements
- Check for DUKE3D.GRP in: (1) CWD, (2) executable directory, (3) ./data/, (4) $DUKE3D_DATA env var
- Print clear error message if GRP not found instead of crashing
- Log which GRP file was loaded and its size
- Handle case where GRP exists but is corrupt/empty

## Files to modify
- `SRC/CACHE1D.C` — `initgroupfile()` function
- `source/GAME.C` — startup GRP loading logic

## Testing  
- Run from different directories
- Run with missing GRP (should show helpful error)
- Run with GRP in various search paths

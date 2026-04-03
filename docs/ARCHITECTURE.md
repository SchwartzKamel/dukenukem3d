# Architecture Overview

This document describes the high-level architecture of the Duke Nukem 3D modern
port, covering the BUILD engine, rendering pipeline, memory layout, file
formats, compatibility layer, game loop, asset pipeline, and 64-bit porting.

---

## BUILD Engine Overview

The BUILD engine is a **2.5D raycasting engine** written by Ken Silverman
between 1993 and 1996. It powers Duke Nukem 3D, Shadow Warrior, Blood, and
several other titles from that era.

Key concepts:

- **Sectors** (rooms) are defined by closed loops of walls, each with a floor
  and ceiling height. Sectors can overlap vertically, enabling room-over-room
  effects.
- **Walls** are line segments forming sector boundaries. Walls can be solid,
  masked (transparent), or portals linking to adjacent sectors.
- **Sprites** represent all dynamic objects — enemies, items, decorations,
  projectiles. They are positioned in 3D space within a sector.
- **8-bit paletted rendering** — the engine renders into a 256-color
  framebuffer. All textures and sprites are stored as palette indices.
- **Portal-based visibility** — sectors connect through `nextwall`/`nextsector`
  links on portal walls. The renderer traverses these links to determine which
  sectors are visible from the camera.

---

## Rendering Pipeline

```
ENGINE.C: drawrooms() → scanrooms → scansector → drawalls
                                                  → drawsprites
                      → drawmasks (transparent/masked walls)

SDL Driver: 8-bit framebuffer → palette lookup → ARGB32 → SDL_Texture → display
```

1. **`drawrooms()`** is the top-level render call. It initiates sector scanning
   from the player's current sector.
2. **`scanrooms`** walks the portal graph to find all visible sectors.
3. **`scansector`** processes each visible sector — clipping walls to the view
   frustum and queuing them for rendering.
4. **`drawalls`** renders floor/ceiling spans and wall columns for each sector.
5. **`drawsprites`** renders sprites sorted by distance.
6. **`drawmasks`** handles transparent and masked walls (glass, fences, etc.)
   in a second pass.
7. The **SDL driver** converts the 8-bit framebuffer to ARGB32 using the
   palette lookup table and presents it via `SDL_Texture`.

---

## Memory Layout

The engine uses several global arrays that hold the entire game state:

| Array | Purpose |
|-------|---------|
| `sector[]` | Sector geometry — floor/ceiling heights, textures, lighting |
| `wall[]` | Wall segments — endpoints, texturing, portal links |
| `sprite[]` | Sprite objects — position, tile, status, owner sector |
| `tilesizx[]`, `tilesizy[]` | Tile dimensions (width, height) for each tile number |
| `waloff[]` | Pointers to tile pixel data in memory |
| `palette[]` | 256-entry RGB palette (loaded from PALETTE.DAT) |
| `palookup[][]` | Shade/lighting lookup tables — maps (palette index, shade level) → display color |
| `frameplace` | Pointer to the render framebuffer |
| `totalclock` | 120 Hz game timer (incremented by the engine tick) |

Map geometry (`sector[]`, `wall[]`, `sprite[]`) is loaded from `.MAP` files.
Tile pixel data is loaded from `.ART` files. Palette and shade tables come from
`PALETTE.DAT`.

---

## File Formats

### GRP (Group Archive)

A simple flat archive format designed by Ken Silverman.

- **Header**: `"KenSilverman"` magic string (12 bytes) + file count (4 bytes)
- **File table**: Array of entries, each with a 12-byte filename + 4-byte size
- **Data**: Concatenated file contents in the same order as the table

No compression, no directories — just a linear pack of files.

### ART (Tile Atlas)

Stores tile/texture pixel data.

- **Header**: Version, number of tiles, tile range (start–end)
- **Tile sizes**: Arrays of `tilesizx[]` and `tilesizy[]` for each tile
- **Animation data**: Per-tile animation speed and flags
- **Pixel data**: Column-major 8-bit palette indices (column-first ordering
  is cache-friendly for the engine's vertical column renderer)

### MAP v7 (Level Data)

Stores complete level geometry and object placement.

- **Header**: Map version (7), player start position/angle, current sector
- **Sectors**: Array of `sectortype` structs (floor/ceiling heights, textures,
  wall pointer, wall count, lighting, tags)
- **Walls**: Array of `walltype` structs (x/y endpoints, texture offsets,
  next wall/sector links, flags)
- **Sprites**: Array of `spritetype` structs (x/y/z position, tile number,
  shade, flags, sector number, status)

### PALETTE.DAT

- **Palette**: 768 bytes — 256 RGB triplets (0–63 range per channel)
- **Shade tables**: Lookup tables that darken palette indices for distance-based
  lighting (multiple shade levels)
- **Translucency table**: 256×256 lookup for alpha blending between two palette
  indices

### TABLES.DAT

Precomputed lookup tables used by the engine:

- **Sine/cosine tables**: Fixed-point trig for the renderer and physics
- **Radar angle tables**: Used for sprite angle calculations
- **Font data**: Character bitmap data for the in-game text renderer
- **Brightness tables**: Additional lighting/gamma lookup data

---

## Compatibility Layer (`compat/`)

The compatibility layer bridges the gap between the original DOS/Watcom code
and modern platforms:

```
Original Code          Compatibility Layer       Modern Platform
─────────────          ───────────────────       ───────────────
#pragma aux ASM   →    pragmas_gcc.h (C inline)  GCC/Clang
VESA/VGA calls    →    sdl_driver.c              SDL2
DOS interrupts    →    compat.h (stubs)          POSIX/Win32
audiolib (SB16)   →    audio_stub.c (silent)     (future: SDL2_mixer)
MACT library      →    mact_stub.c              Config parser
Watcom C (16/32)  →    GCC -std=gnu89           x86-64
long = 32-bit     →    int32_t in structs        64-bit safe
```

- **`pragmas_gcc.h`** replaces Watcom `#pragma aux` inline assembly with GCC
  `__asm__` equivalents or C implementations.
- **`sdl_driver.c`** replaces VESA/VGA framebuffer access with SDL2 window
  creation, texture upload, and event handling.
- **`compat.h`** stubs out DOS-specific calls (interrupt handlers, memory
  model macros, etc.).
- **`audio_stub.c`** provides silent no-op implementations of the audiolib
  API. A future SDL2_mixer backend will replace this.
- **`mact_stub.c`** replaces the MACT input/config library with minimal stubs.

---

## Game Loop

```
main() [GAME.C]
  ├── initengine()     — BUILD engine init
  ├── loadgroupfile()  — open DUKE3D.GRP
  ├── loadlookups()    — load palette + shade tables
  ├── app_main()
  │   ├── loadcon()    — parse GAME.CON scripts
  │   ├── newgame()    — start new game
  │   └── while(1)     — main loop
  │       ├── getpackets()    — network (stubbed)
  │       ├── domovethings()  — physics, AI, game logic
  │       ├── drawrooms()     — 3D rendering
  │       ├── displayrooms()  — HUD overlay
  │       └── nextpage()      — flip framebuffer (SDL)
```

1. **`initengine()`** sets up the BUILD engine — allocates buffers, loads
   lookup tables, initializes the renderer state.
2. **`loadgroupfile()`** opens `DUKE3D.GRP` and indexes its file table for
   subsequent reads.
3. **`loadlookups()`** reads `PALETTE.DAT` and builds the shade/translucency
   lookup tables.
4. **`app_main()`** is the game-specific entry point:
   - **`loadcon()`** parses `GAME.CON` / `DEFS.CON` / `USER.CON` scripts that
     define game actors, weapons, and behavior.
   - **`newgame()`** initializes a new game session (loads the first map, resets
     player state).
   - The **main loop** runs continuously:
     - `getpackets()` — reads network packets (currently stubbed)
     - `domovethings()` — runs game logic: player movement, enemy AI, physics,
       projectile updates, sector effects
     - `drawrooms()` — renders the 3D view
     - `displayrooms()` — overlays the HUD (health, ammo, weapon sprite)
     - `nextpage()` — flips the framebuffer to the screen via SDL

---

## Asset Pipeline

The asset pipeline (`tools/generate_assets.py`) generates all game data from
scratch, removing the dependency on original copyrighted assets:

```
tools/generate_assets.py
  ├── Load .env (FLUX credentials)
  ├── For each texture definition:
  │   ├── Try FLUX.2-pro AI generation
  │   ├── Fallback to procedural generator
  │   └── Quantize RGB → 8-bit palette index
  ├── Create TILES000.ART (column-major tile data)
  ├── Create PALETTE.DAT (palette + shade tables)
  ├── Create TABLES.DAT (sine tables + fonts)
  ├── Create E1L1.MAP (test level)
  ├── Copy GAME.CON, DEFS.CON, USER.CON, LOOKUP.DAT
  └── Pack all into DUKE3D.GRP
```

- **AI generation** uses FLUX.2-pro (via API) to create textures from text
  prompts. Requires credentials in `.env`.
- **Procedural fallback** generates textures algorithmically when AI is
  unavailable (`--no-ai` flag). Every texture must have a procedural fallback.
- **Palette quantization** converts RGB pixel data to the nearest 8-bit palette
  index for the engine.
- **ART packing** writes tile data in column-major order as expected by the
  BUILD engine renderer.
- **GRP packing** bundles all generated files into `DUKE3D.GRP` using
  Ken Silverman's archive format.

### Audio Pipeline

```
tools/generate_audio.py
  ├── Load .env (GPT Audio credentials)
  ├── For each voice line definition:
  │   ├── Call GPT Audio 1.5 API (text → WAV)
  │   └── Fallback: generate silence placeholder
  └── Output WAV files to generated_assets/sounds/

tools/generate_assets.py
  └── Pack sounds/*.WAV into DUKE3D.GRP (if present)
```

- **AI generation** uses GPT Audio 1.5 (via Azure OpenAI API) to synthesize
  voice lines and sound effects from text prompts. Three voices are available:
  `alloy` (gruff), `echo` (electronic), and `onyx` (deep).
- **Silence fallback** generates empty WAV files when AI is unavailable
  (`--no-ai` flag), keeping the pipeline functional without API keys.

### Audio System (Runtime)

- **SDL2_mixer** loads WAV files from GRP at runtime
- **`FX_PlaySound`** / **`FX_Play3D`** handle playback with positional audio
- **`MUSIC_PlaySong`** handles MIDI music playback
- Falls back to silence if SDL2_mixer is not available (current default via
  `audio_stub.c`)

---

## 64-bit Compatibility

### The Problem

The original BUILD engine and Duke Nukem 3D were written for 32-bit DOS using
Watcom C, where `long` is 4 bytes. On 64-bit Linux (and most modern 64-bit
platforms), `long` is 8 bytes. This breaks:

- **Packed struct layouts** — `sectortype` (40 bytes), `walltype` (32 bytes),
  and `spritetype` (44 bytes) must match their on-disk sizes exactly for MAP
  file loading to work.
- **Pointer-to-long casts** — the engine stores pointers to `long` fields for
  interpolation and animation.
- **Array indexing** — some code assumes `sizeof(long) == 4` when computing
  offsets.

### The Fix

- **Struct fields** in `sectortype`, `walltype`, and `spritetype` are changed
  from `long` to `int32_t`, preserving the exact struct sizes.
- **Compile-time assertions** (`_Static_assert`) verify that struct sizes are
  correct: `sectortype` = 40, `walltype` = 32, `spritetype` = 44.
- **`animateptr`** and interpolation pointers are changed to `int32_t *` to
  match the new field types.
- Engine-internal variables that don't affect struct layout may remain `long`
  where it doesn't cause issues, but any variable that participates in struct
  packing or file I/O uses fixed-width types.

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

#### SOUND_MANIFEST.json schema

Each entry in `generated_assets/sounds/SOUND_MANIFEST.json` carries:

| Field          | Type   | Notes                                                              |
|----------------|--------|--------------------------------------------------------------------|
| `sound_id`     | string | C identifier (uppercase + underscores).                            |
| `voice`        | string | `alloy` / `echo` / `onyx`.                                         |
| `wav_path`     | string | Relative path to the generated WAV file.                           |
| `status`       | string | `generated`, `placeholder`, or `failed`. Legacy entries default to `generated` on read. |
| `generated_at` | string | ISO 8601 timestamp. In `--no-ai` mode this is fixed to `1970-01-01T00:00:00Z` so the manifest is byte-deterministic. |
| `error`        | string | Optional. Populated when `status == "failed"`; carries the upstream error message. |

The pipeline gracefully tolerates missing optional fields when reading
older manifest files, so re-running `generate_audio.py` over an existing
tree never wipes prior context.

#### SDL2 Runtime Detection

The audio (and video) subsystem locates SDL2 at run-time from
platform-specific search paths:

- **Linux** — `LD_LIBRARY_PATH` plus the standard ldconfig cache. When
  SDL2 is installed via Homebrew on Linux,
  `export LD_LIBRARY_PATH=$(brew --prefix)/lib:$LD_LIBRARY_PATH` is
  required.
- **macOS** — `DYLD_LIBRARY_PATH`, the rpath embedded in the binary,
  and the framework search path. Homebrew users typically need
  `export DYLD_LIBRARY_PATH=$(brew --prefix)/lib:$DYLD_LIBRARY_PATH`.
- **Windows** — the directory containing the executable, the standard
  Windows SDK search paths, and any `%PATH%` entries. The MSVC build
  bundles `SDL2.dll` from `third_party/` next to `duke3d.exe`.

The same discovery logic is exercised in `tests/test_sdl_driver.py`,
which gates itself with a SDL2 availability check and skips with a
clear message when SDL2 is not installed.

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

---

## Audit Infrastructure

The project maintains a comprehensive audit system run by 10 specialized Copilot agent personas. Audit reports are stored in `docs/audits/` and track technical health, compliance, and quality metrics.

### Audit Files

| File | Persona | Scope | Schedule |
|------|---------|-------|----------|
| `engine-porter.md` | Engine Porter | SRC/, source/ (BUILD engine + Duke3D code, 72k LOC) | Monthly |
| `compat-layer.md` | Compat Layer | compat/ (SDL2 shims, 5.4k LOC) | Monthly |
| `asset-pipeline.md` | Asset Pipeline | tools/ (texture/map/audio generation, 4k LOC) | Monthly |
| `audio-engineer.md` | Audio Engineer | Audio generation + stub systems (21 WAV catalog) | Monthly |
| `build-system.md` | Build System | Makefile, CMakeLists.txt, CI/CD, Windows builds | Monthly |
| `test-engineer.md` | Test Engineer | tests/, pytest suite (392 tests, ~99% pass rate) | Monthly |
| `SUMMARY.md` | Documentation Curator | Cross-cutting summary + critical findings triage | Monthly |

### How to Regenerate Audits

Audit reports are generated by agents running code analysis, style checks, security scans, and cross-codebase verification. To re-run a specific audit:

```bash
# Example: request the engine-porter audit (this spawns the agent)
copilot task --agent engine-porter --scope "Audit SRC/ and source/ for 64-bit safety, struct packing, and correctness per invariants"
```

The full audit workflow is managed by the **Documentation Curator** persona. Results are checked into the repo with a commit message like:

```
docs: refresh audit reports (monthly cycle 2025-05-20)

All reports generated by Copilot agents:
- engine-porter: PASS with findings on dead code archival
- compat-layer: PASS with 64-bit type safety notes
- ...
```

### Critical & High Findings Reference

For the current audit cycle, see [docs/audits/SUMMARY.md](docs/audits/SUMMARY.md) for:
- **Headline verdict** on overall codebase health
- **Memory-hack invariants** verification (key safety rules)
- **Critical findings** that require remediation before release
- **High findings** recommended for immediate action
- **Medium findings** for the next development cycle

When implementing fixes for audit findings, link the commit to the specific audit report (e.g., `Fixes docs/audits/build-system.md § CRITICAL: MSVC /Tc flag`).

---

## Recent Hardening (Cycles 12-15)

This section documents critical safety fixes landed in recent audit cycles to prevent regression and guide future maintenance.

### Cycle 12: Engine & Network Baseline Hardening

- **CRITICAL — labelcode overflow** (`source/GAME.C:7118` → `source/GLOBAL.C`)
  - **Issue:** Unbound labelcode pointer aliased over `sector[]` array, allowing GAMEDEF.C script parser to corrupt sector geometry on large script loads (>512 labels).
  - **Fix:** Replaced with static `labelcode[MAXLABELS=4096]` array; external declaration in `source/DUKE3D.H`.
  - **Impact:** Preserves script parser safety; sectors now protected from labelcode overflow.
  - **Cite:** `source/GLOBAL.C` (extern labelcode declaration), `source/GAME.C:7118` (fixed reference).

- **Wire-format helpers** (`SRC/MMULTI.C`)
  - **Issue:** Byte-shuffling for network packets lacked explicit endian guards; risky on non-x86 architectures.
  - **Fix:** Introduced `mm_pack_u16_le()` and `mm_unpack_u16_le()` static inline helpers for safe little-endian marshalling.
  - **Impact:** Payload length, protocol version, disconnect, and sendpacket now use explicit LE format.
  - **Cite:** `SRC/MMULTI.C` (helper definitions and call sites).

### Cycle 13: I/O & Audio Validation Hardening

- **File I/O safety** (`source/MENUES.C`)
  - **Issue:** 14 critical `fread`/`fwrite` sites in saveplayer, loadplayer, and loadpheader lacked return-value checks; silent failures on corrupt saves.
  - **Fix:** Added explicit size assertions and error logging; ~145 remaining sites marked `TODO(file-io-r2)`.
  - **Impact:** Save/load game failures now logged; prevents data corruption cascades.
  - **Cite:** `source/MENUES.C` (saveplayer ×10, loadplayer ×3, loadpheader ×1 fixed sites).

- **RIFF/WAVE validation** (`compat/audio_stub.c`)
  - **Issue:** WAV header parsing in audio stub lacked bounds checking; malformed WAV files could trigger buffer overrun.
  - **Fix:** Added explicit RIFF chunk header + WAVE format validation; reject files with missing or oversized chunks.
  - **Impact:** Audio pipeline now resilient to corrupt or malicious WAV inputs.
  - **Cite:** `compat/audio_stub.c` (WAV header parsing + validation logic).

- **Mixer channel exhaustion** (`compat/audio_stub.c`)
  - **Issue:** `Mix_GroupOldest` callback could race with concurrent `FX_SetCallBack` pointer updates.
  - **Fix:** Snapshot callback pointer into local variable; guard writer with `SDL_LockAudio`.
  - **Impact:** Audio playback thread-safe against callback registration changes.
  - **Cite:** `compat/audio_stub.c` (FX_SetCallBack synchronization pattern).

### Cycle 15: CON-Script & Network Bounds Safety

- **CON-script label bounds** (`source/GAMEDEF.C`)
  - **Issue:** labelcnt increment checked against old stack-allocated bound; label-string buffer had no overflow guard.
  - **Fix:** Added explicit `labelcnt < MAXLABELS` check before incrementing; bounds-safe string storage.
  - **Impact:** GAMEDEF.C scripts now safely handle maximum label count (4096); prevents heap corruption.
  - **Cite:** `source/GAMEDEF.C` (labelcnt bounds-check, label-string array).

- **Network packet unmarshalling** (`SRC/MMULTI.C`)
  - **Issue:** `from_player` and `sendpacket` reads lacked bounds validation; oversized packets could trigger OOB reads.
  - **Fix:** Added explicit range checks: `from_player < MAXPLAYERS` and payload length validation before unmarshalling.
  - **Impact:** Network input now validated; prevents deserialization exploits.
  - **Cite:** `SRC/MMULTI.C` (from_player + sendpacket bounds checks in packet handlers).

- **SoundOwner aging** (`source/SOUNDS.C`)
  - **Issue:** SoundOwner array access at `i >= MAXSOUNDS` possible during concurrent playback updates.
  - **Fix:** Added explicit capacity check before incrementing sound counters; cycle old sounds out at max capacity.
  - **Impact:** Audio system robust to sustained high-concurrency scenarios.
  - **Cite:** `source/SOUNDS.C` (SoundOwner array bounds + aging logic).

- **Audio callback synchronization** (`compat/audio_stub.c`)
  - **Issue:** `FX_Set*` (e.g., `FX_SetCallBack`, `FX_SetLoopPosition`) could race with mixer callback invocation.
  - **Fix:** Wrapped setter calls with `SDL_LockAudio` / `SDL_UnlockAudio` guards.
  - **Impact:** Audio state mutations now serialized; eliminates callback-invocation races.
  - **Cite:** `compat/audio_stub.c` (FX_Set* lock guards).

### Cycles 16–18: Asset Pipeline & Build Integrity Hardening

- **Atomic file writes for generated assets** (`tools/generate_assets.py`, cycle 18)
  - **Issue:** Asset pipeline wrote directly to output files (DUKE3D.GRP, PALETTE.DAT, TABLES.DAT); concurrent reads during partial writes could corrupt game state.
  - **Fix:** Introduced `_atomic_write_bytes()` pattern — write to temporary file, fsync, then rename atomically.
  - **Impact:** All asset outputs now atomic; no partial GRP corruption risk even if build interrupts.
  - **Cite:** `tools/generate_assets.py:2080–2093` (atomic write integration), docs/audits/asset-pipeline-r7.md.

- **Build system MAXTILES conflict detection** (`build-system.agent`, cycles 16–17)
  - **Issue:** `source/BUILD.H` and `SRC/BUILD.H` declared MAXTILES with conflicting bounds (6144 vs 9216); LTO type mismatch risked buffer overflow.
  - **Fix:** Consolidated MAXTILES declaration; added build-time validation that both headers agree.
  - **Impact:** Cross-compilation safe; LTO inlining no longer corrupts tile indexing.
  - **Cite:** `source/BUILD.H` vs `SRC/BUILD.H`, docs/audits/build-system-r7.md.

### Cycles 19–22: Critical Engine & Multiplayer Hardening

- **CRITICAL — sprite.yvel unbounded player array index** (`source/ACTORS.C`, cycles 20–22)
  - **Issue:** 14+ sites used `sprite[x].yvel` directly as player index without bounds checking (e.g., `ps[sprite[owner].yvel].fist_incs`). Malicious/corrupted sprites could write to arbitrary player structs.
  - **Fix:** Inserted guards `if(sprite[x].yvel >= 0 && sprite[x].yvel < MAXPLAYERS)` before all `ps[]` array accesses; audit identified all 14 risky sites.
  - **Impact:** Player struct memory now protected from sprite-driven array overflow; critical for multiplayer savegame safety.
  - **Cite:** `source/ACTORS.C:205, 1128, 1034, 4441–4443, 6258–6293, 6888–6980` (guarded sites), docs/audits/engine-porter-r7.md.

- **HIGH — savegame loader file I/O bounds validation** (`source/MENUES.C`, cycle 22)
  - **Issue:** 83+ `kdfread()` sites in savegame/loadgame logic lacked validation; truncated save files could trigger out-of-bounds reads or silent data loss.
  - **Fix:** Added read-size assertions and explicit bounds checks on `kdfread()` return values.
  - **Impact:** Corrupted save files now detected and logged; prevents cascade corruption.
  - **Cite:** `source/MENUES.C` (saveplayer/loadplayer fix sites), docs/audits/engine-porter-r7.md.

- **Pydantic schema validation for asset configuration** (`tools/_asset_schemas.py`, cycle 20)
  - **Issue:** Asset pipeline configuration (TEXTURE_DEFS, SPRITE_DEFS, VOICE_LINES) had no validation; typos or out-of-range tile numbers propagated silently into generated assets.
  - **Fix:** Introduced pydantic v2 schemas with explicit bounds (`tile_num: 0–6143`, `dimensions: > 0`, etc.); module import-time validation.
  - **Impact:** Configuration errors caught at startup; no malformed assets generated.
  - **Cite:** `tools/_asset_schemas.py:112–114`, docs/audits/asset-pipeline-r7.md.

- **Network connection timeout & keep-alive hardening** (`SRC/MMULTI.C`, cycle 21)
  - **Issue:** Multiplayer net code had no connection timeout; hung sockets in relay scenarios.
  - **Fix:** Added explicit timeout on socket reads; keep-alive heartbeats for idle connections.
  - **Impact:** Stalled multiplayer connections now detected and closed gracefully.
  - **Cite:** `SRC/MMULTI.C` (timeout + heartbeat logic), docs/audits/network-multiplayer-r4.md.

- **Secret scanning YAML coverage extension** (`tools/check_secrets.sh`, cycle 22)
  - **Issue:** Secret-scan hook only checked `.env`, `*.md`, `*.py`; missed API keys in GitHub Actions YAML (`.github/workflows/*.yml`, `build_windows.bat`).
  - **Fix:** Extended pre-commit hook to scan `.yml` and `.bat` files; added patterns for common token prefixes.
  - **Impact:** Accidentally committed tokens in CI files now blocked at push time.
  - **Cite:** `tools/check_secrets.sh`, `.github/workflows/build.yml`, docs/audits/security-and-secrets-r7.md.

### Cycles 23–27: Regression Hardening & Audio Resource Management

- **HIGH — Allocache alignment overflow prevention** (`SRC/CACHE1D.C:71`, cycle 25)
  - **Issue:** Signed integer addition `newbytes + 15` before alignment could overflow if input near `LONG_MAX`, leading to undefined behavior and corrupted cache allocation.
  - **Fix:** Added pre-alignment check `if(newbytes > LONG_MAX - 15)` rejecting oversized allocations; rearranged validation order.
  - **Impact:** Cache subsystem now safe against edge-case integer overflows; allocation failures logged cleanly.
  - **Cite:** `SRC/CACHE1D.C:65–75`, docs/audits/engine-porter-r8.md.

- **HIGH — Savegame loader fixed read fragility** (`source/MENUES.C:321–345`, cycle 26)
  - **Issue:** Loader validated wall/sector/player counts but always read `MAXWALLS`/`MAXSECTORS`/`MAXPLAYERS` bytes regardless; truncated save files left uninitialized memory in array tails.
  - **Fix:** Changed to read exactly `numwalls`/`numsectors` bytes, then `memset()` remainder to zero; preserves invariant that unused array slots are zeroed.
  - **Impact:** Multiplayer desync risk from uninitialized wall data eliminated; cleanly handles truncated saves.
  - **Cite:** `source/MENUES.C:321–345`, docs/audits/engine-porter-r8.md.

- **HIGH — hlineasm shift amount validation** (`SRC/ENGINE.C:365–366`, cycle 26)
  - **Issue:** logx/logy parameters to `hlineasm4` were unclamped shift amounts; negative or >31 shifts trigger undefined behavior in `<<` operator.
  - **Fix:** Added runtime checks `if(logx < 0 || logx > 31)` before shift, defaulting to safe values; similar for logy.
  - **Impact:** Rendering now resilient to malformed texture tile metadata; edge-case shift underflows prevented.
  - **Cite:** `SRC/ENGINE.C:360–370`, docs/audits/engine-porter-r8.md.

- **MEDIUM — Animateoffs array bounds clamping** (`SRC/ENGINE.C:3594`, cycle 26)
  - **Issue:** `animateoffs()` silently wrapped result to tile 0 on out-of-bounds; caller had no signal that tile lookup failed.
  - **Fix:** Changed to clamp result to `[0, MAXTILES)`, returning original tile if result exceeds bounds; added optional return-value check points.
  - **Impact:** Animation playback no longer silently corrupts tile rendering; debug visibility improved.
  - **Cite:** `SRC/ENGINE.C:3590–3600`, docs/audits/engine-porter-r8.md.

- **3 × MEDIUM — SDL_RWops resource leak closure** (`compat/audio_stub.c`, cycle 26)
  - **Issue:** `mixer_play()`, `mixer_play_3d()`, and `MUSIC_PlaySong()` error paths did not free RW stream objects on `Mix_LoadWAV_RW()` or `Mix_LoadMUS_RW()` failures.
  - **Fix:** Added explicit `SDL_FreeRW(rw)` on all error returns; ensured `current_music_rw` cleared after playback stops.
  - **Impact:** Audio system now resource-leak-free under error conditions; long-running games stable without RW handle exhaustion.
  - **Cite:** `compat/audio_stub.c:185–195, 241–251, 882–892`, docs/audits/audio-engineer-r7.md.

- **CRITICAL — Network packet type 9 buffer overflow** (`source/GAME.C case 9`, cycle 26)
  - **Issue:** Packet type 9 (wchoice) handler wrote untrusted weapon choice directly into `packbuf[]` without array bounds validation; malicious peer could overflow.
  - **Fix:** Added check `if(packbufleng-1 > MAX_WEAPONS)` rejecting oversized packets; validates choice index before weapon state update.
  - **Impact:** Network input now validated; remote code execution via malicious packets eliminated.
  - **Cite:** `source/GAME.C:case 9`, docs/audits/network-multiplayer-r5.md.

- **HIGH — Network packet type 0/1 OOB read prevention** (`source/GAME.C cases 0, 1`, cycle 26)
  - **Issue:** Sync payload for player state (types 0, 1) used bitmask-driven deserialization without pre-validating payload length; could read beyond buffer.
  - **Fix:** Added bitmask pre-validation: required-length check before unmarshalling; rejects packets with insufficient data.
  - **Impact:** Deserialization attacks now caught; network integrity verified before state mutation.
  - **Cite:** `source/GAME.C:case 0, case 1`, docs/audits/network-multiplayer-r5.md.

- **Test coverage expansion for cycle-25/r8 findings** (`tests/test_engine_net_hardening_regressions.py`, cycles 24–27)
  - **Issue:** 21 new regression tests added across engine bounds, network hardening, and audio RWops resource leaks; all cycle-25/r8 CRITICAL/HIGH fixes now have dedicated regression coverage.
  - **Fix:** New test suite validates allocache overflow guard, hlineasm shift bounds, savegame partial-reads, packet dispatch validation, RWops cleanup on error.
  - **Impact:** Cycle-25/r8 hardening now protected from regression; future changes caught by CI.
  - **Cite:** `tests/test_engine_net_hardening_regressions.py`, docs/audits/test-engineer-r8.md.

### Cycles 28–33: CMake LTO Parity & Engine Safety Hardening

- **Cycle 28: CMake LTO explicit support** (`CMakeLists.txt`, cycle 28)
  - **Issue:** `CMakeLists.txt` lacked LTO (Link-Time Optimization) support while Makefile used `-flto` flags; build parity gap.
  - **Fix:** Added `check_ipo_supported()` + `set_property(INTERPROCEDURAL_OPTIMIZATION TRUE)` to CMakeLists.txt (lines 60, 63).
  - **Impact:** CMake builds now apply LTO optimization parity with Makefile; release binary performance consistent across build systems.
  - **Cite:** `CMakeLists.txt:60–63`, docs/audits/build-system-r9.md.

- **HIGH — CONFIG.C buffer overflow hardening** (`source/CONFIG.C`, cycle 30)
  - **Issue:** Config file parser used unsafe `strcpy()` on user-controlled input (setupfilename[128], temp[80] buffers); injection vectors.
  - **Fix:** Replaced `strcpy()` with `strncpy()` + explicit NUL termination; replaced `sprintf()` with `snprintf()` on all config file parsing paths (cycle 30, commit 0aaa2b5).
  - **Impact:** Config file parsing now buffer-safe; malformed `.cfg` files cannot overflow into adjacent memory.
  - **Cite:** `source/CONFIG.C` (strncpy/snprintf sites), docs/audits/engine-porter-r9.md.

- **HIGH — SECTOR.C infinite recursion prevention** (`source/SECTOR.C`, cycle 30)
  - **Issue:** `operatesectors()` function recursively followed sector `lotag` chains without depth limit; malicious CON scripts could exhaust stack via infinite chains.
  - **Fix:** Added static recursion depth counter with `OPERATESECTORS_MAX_DEPTH = 64` limit; aborts with SECURITY warning if exceeded (cycle 30, commit e884df0).
  - **Impact:** Stack overflow from malicious maps now impossible; recursion depth protection built-in.
  - **Cite:** `source/SECTOR.C:549–595`, docs/audits/engine-porter-r9.md.

- **HIGH — Actor tile metadata bounds guard (PICNUM_SAFE)** (`source/DUKE3D.H:104`, `source/ACTORS.C`, cycle 33)
  - **Issue:** Sprite `picnum` field (loaded from savegames, set via CON scripts) used directly as index to tile metadata arrays (`tilesizy[]`, `actortype[]`) without bounds validation; out-of-bounds read possible.
  - **Fix:** Introduced `PICNUM_SAFE(p)` macro: `(((unsigned)(p)) < MAXTILES ? (p) : 0)` to clamp picnum to safe range; applied at 15+ tile metadata access sites in `source/ACTORS.C` (cycle 33, commit 0569b17).
  - **Impact:** Sprite tile metadata access now guaranteed in-bounds; memory disclosure and crash vectors closed.
  - **Cite:** `source/DUKE3D.H:104`, `source/ACTORS.C:635–649`, docs/audits/engine-porter-r9.md.

- **MEDIUM — Weapon & ammo bounds validation** (`source/DUKE3D.H`, `source/ACTORS.C`, `source/PLAYER.C`, cycle 30 & 33)
  - **Issue:** Weapon array (`weapons[]`, `ammo[]`) accesses lacked bounds checking; unchecked `addweapon()`, `addammo()`, `checkavailweapon()` calls.
  - **Fix:** Added `WEAPON_VALID(w)` macro (`((unsigned)(w) < (unsigned)MAX_WEAPONS)`) and `WEAPON_CLAMP(w)` helper in `source/DUKE3D.H` (cycle 30); applied to weapon state updates in `source/ACTORS.C` + `source/PLAYER.C` (cycle 33, commit 0569b17).
  - **Impact:** Weapon/ammo state mutations now bounds-safe; invalid weapon indices rejected or clamped to zero.
  - **Cite:** `source/DUKE3D.H:98–101`, `source/ACTORS.C` (weapon bounds checks), docs/audits/engine-porter-r9.md.

- **HIGH — Network packet type 4 (chat) safety** (`source/GAME.C case 4`, cycle 33)
  - **Issue:** Chat packet handler used `strcpy()` on untrusted player-sent chat string without length bounds; overflow possible.
  - **Fix:** Replaced `strcpy()` with `strncpy()` + explicit NUL-termination; added length validation before deserialization (cycle 33, commit 0569b17).
  - **Impact:** Chat packet buffer overflow closed; multiplayer chat now safe.
  - **Cite:** `source/GAME.C:case 4` (packet type-4 handler), docs/audits/network-multiplayer-r6.md, docs/audits/security-and-secrets-r9.md.

- **HIGH — Network packet type 8 (map change) validation** (`source/GAME.C case 8`, cycle 33)
  - **Issue:** Map-change packet deserialization (`copybufbyte()` on `boardfilename[]`) lacked pre-validation of packet size vs buffer capacity; negative sizes possible.
  - **Fix:** Added explicit size validation before `copybufbyte()`: check packet payload length against `sizeof(boardfilename)` and `INT_MAX` guard (cycle 33, commit 0569b17).
  - **Impact:** Map-change packet injection attacks now caught; multiplayer map loading safe.
  - **Cite:** `source/GAME.C:case 8` (packet type-8 handler), docs/audits/network-multiplayer-r6.md.

- **Macro definitions for safety** (`source/DUKE3D.H:98–107`, cycles 30–33)
  - **Issue:** Scattered bounds checks made code hard to audit; inconsistent patterns across CONFIG, SECTOR, ACTORS, GAME, PLAYER modules.
  - **Fix:** Introduced three centralized safety macros:
    - `#define MAX_CONFIG_KEY 64` — config key string length cap (cycle 30).
    - `#define WEAPON_VALID(w) (((unsigned)(w) < (unsigned)MAX_WEAPONS))` — weapon index bounds test (cycle 30).
    - `#define PICNUM_SAFE(p) (((unsigned)(p)) < MAXTILES ? (p) : 0)` — tile picnum bounds guard (cycle 33).
  - **Impact:** Central, auditable definitions; future bounds checks reference macros instead of magic numbers; easier to maintain and reason about safety invariants.
  - **Cite:** `source/DUKE3D.H:98–107`, docs/audits/engine-porter-r9.md.

---

## Cycles 28–36: CMake LTO Parity, Audio Schema v1.0 & Net/Engine Hardening

This section documents the major architectural changes introduced from cycles 28 through 36, focusing on build system optimization, asset pipeline formalization, and comprehensive security hardening across the engine and multiplayer subsystems.

### Build System: CMake LTO Parity (Cycle 28)

**Challenge:** The legacy Makefile provided explicit link-time optimization (`-flto` flag), but CMakeLists.txt lacked equivalent IPO configuration. This created a **LTO parity gap** — developers using CMake received unoptimized binaries compared to Makefile builds, losing ~8–12% performance on hot-path rendering and physics.

**Solution (Cycle 28):** Added CMake `CheckIPOSupported` module + `INTERPROCEDURAL_OPTIMIZATION` property to CMakeLists.txt (lines 60, 63). CMake now queries the compiler's IPO capability at configure time and enables `-flto` equivalent optimizations automatically.

**Impact:** 
- CMake builds now achieve performance parity with Makefile builds.
- LTO-enabled binaries pass through interprocedural optimization during linking, closing the performance gap.
- Cross-platform consistency — LTO works on Linux/macOS with GCC/Clang and Windows with MSVC.

**Memory Hacks Preserved:** SDL2_VERSION single-source in build.mk remains the sole version definition; CMakeLists.txt `LANGUAGE C` property (no `/Tc` flag) enforces correct language mode for .C files.

**Cite:** `CMakeLists.txt:60–63`, `build.mk:33`, docs/audits/build-system-r9.md, docs/audits/build-system-r10.md.

---

### Audio Pipeline Formalization: Schema v1.0 & Manifest Validation (Cycle 34)

**Challenge:** Audio asset generation (`tools/generate_audio.py`) lacked formal schema versioning and manifest validation. The tool generated SOUND_MANIFEST entries without guaranteeing structure compatibility or detecting configuration drift.

**Solution (Cycle 34):** 
1. **Schema Version Enforcement:** SOUND_MANIFEST wrapped with `schema_version: "1.0"` field. `validate_manifest()` function enforces schema match at load time.
2. **Manifest Validation:** `validate_manifest(manifest_data, source_path)` function validates that:
   - `schema_version` matches "1.0" (rejects future incompatible versions)
   - Required fields (`entries`, `voice_model`, `endpoint`) present
   - No mismatched payload sizes or missing entries
3. **Endpoint Redaction:** `_redact_endpoint(url)` function redacts Azure endpoint URLs before logging (prevents accidental credential exposure in build logs).

**Impact:**
- Asset generation pipeline becomes versioned and self-describing.
- Manifest validation catches configuration errors at generation time, not runtime.
- Credential hygiene improved — Azure endpoints no longer logged in plaintext.
- Future audio schema updates (v1.1, v2.0) can be detected and handled gracefully.

**Cite:** `tools/generate_audio.py:24` (_redact_endpoint), `tools/generate_audio.py:118–174` (validate_manifest), `tools/generate_audio.py:339–341` (schema_version wrapping), docs/audits/audio-engineer-r9.md.

---

### Engine Bounds Hardening: Multi-Cycle Recursion & Array Access Safety (Cycles 30–36)

**Challenge:** The BUILD engine's deep recursive patterns and dynamic array access (particularly sprites, sectors, and tile metadata) exposed multiple stack and memory safety vulnerabilities:
- Infinite sector recursion chains (CON scripts could trigger stack exhaustion)
- Unchecked array indices from untrusted data (savegames, network packets)
- Configuration parsing with unbounded string operations

**Solution Summary (Cycles 30–36):**

- **SECTOR.C Recursion Cap (Cycle 30):** `operatesectors()` function protected by `OPERATESECTORS_MAX_DEPTH = 64` counter. Aborts with SECURITY warning if exceeded. Prevents stack exhaustion from malicious maps with circular lotag chains.
  - **Cite:** `source/SECTOR.C:35–40`, `source/SECTOR.C:558–560`, docs/audits/engine-porter-r9.md.

- **CONFIG.C Hardening (Cycle 30):** Configuration file argument handling switched from `strcpy()` to bounded `snprintf()`. Added `MAX_CONFIG_KEY = 64` macro to cap config key string length. Prevents buffer overflow via crafted config files.
  - **Cite:** `source/DUKE3D.H:107`, `source/CONFIG.C`, docs/audits/security-and-secrets-r10.md.

- **Tile Metadata Access (Cycle 33):** Introduced `PICNUM_SAFE(p)` macro — clamps sprite `picnum` field to safe range before array access. Applied at 6+ callsites in ACTORS.C and GAME.C to protect tile metadata arrays (`tilesizy[]`, `actortype[]`, `tilesizx[]`).
  - **Cite:** `source/DUKE3D.H:104`, `source/ACTORS.C:651,665`, `source/GAME.C:1295,3462,3473,5695`, docs/audits/engine-porter-r10.md.

- **Weapon/Ammo Bounds (Cycle 33):** `WEAPON_VALID(w)` and `WEAPON_CLAMP(w)` macros validate weapon indices before access. Applied in ACTORS.C and PLAYER.C to protect weapon state mutations.
  - **Cite:** `source/DUKE3D.H:98–101`, `source/ACTORS.C:120,133,202,240`, `source/PLAYER.C:3624`, docs/audits/engine-porter-r10.md.

- **RTS Lump Header Overflow Guard (Cycle 36):** RTS.C lump parsing protected against integer overflow in `header.numlumps * sizeof(filelump_t)`. Added bounds check: `if (header.numlumps > 65536)` → Error(). Prevents malicious .rts files from exhausting stack via alloca().
  - **Cite:** `source/RTS.C:83–91`, docs/audits/GRIND_LOG.md (cycle 36).

- **Actor Sector Traversal Bounds (Cycle 36):** ACTORS.C sector loop protected against buffer overflow. Added `if (sectend >= 1024)` check before `tempshort[sectend++]` write. Unvalidated sector index read protected by `if (dasect < 0 || dasect >= MAXSECTORS) continue;`.
  - **Cite:** `source/ACTORS.C:470,494`, docs/audits/engine-porter-r10.md, docs/audits/GRIND_LOG.md (cycle 36).

- **HUD Sprite Index Validation (Cycle 36):** Frags display and player status rendering protected against invalid sprite indices. Added `if ((unsigned)ps[i].i >= MAXSPRITES) continue;` to prevent OOB sprite array dereferences.
  - **Cite:** `source/GAME.C:1715–1717`, docs/audits/GRIND_LOG.md (cycle 36).

- **Sprite Queue Count Sanity (Baseline, verified cycle 30–33):** `spriteqamount` range-checked against [0, MAXSPRITES] before deserialization.
  - **Cite:** `source/MENUES.C:402`, docs/audits/engine-porter-r10.md.

---

### Network Multiplayer Hardening: Packet Bounds & Partial-Send Retry (Cycles 26–36)

**Challenge:** Multiplayer packet handling exposed buffer overflow and packet injection risks:
- Untrusted chat strings written to fixed buffers without length validation
- Map-change packet fields deserialized without size guards
- TCP partial sends (when send() returns fewer bytes than requested) could silently drop packets or corrupt multiplayer state

**Solution Summary (Cycles 26–36):**

- **Chat Packet Bounds (Cycle 33):** Type-4 (chat) packet handler replaced `strcpy()` with `strncpy()` + explicit NUL-termination. Added length validation: `if (packbufleng > 1 && packbufleng <= sizeof(recbuf))` before deserialization.
  - **Cite:** `source/GAME.C:567–576`, docs/audits/security-and-secrets-r10.md.

- **Map-Change Packet Validation (Cycle 33):** Type-8 (map change) packet handler validates packet size against `sizeof(boardfilename)` and checks game settings (level, volume, skill) against valid ranges. Invalid values clamped to 0 with diagnostic logging.
  - **Cite:** `source/GAME.C:683–710`, docs/audits/security-and-secrets-r10.md.

- **TCP Partial-Send Retry Loop (Cycle 33):** SRC/MMULTI.C `send()` calls wrapped in 8-attempt retry loop with EINTR/EAGAIN handling. Added `tcp_send_failures` counter to track retry exhaustion. Prevents packet loss when TCP stack cannot accept full payload in one syscall.
  - **Cite:** `SRC/MMULTI.C:140–167`, docs/audits/GRIND_LOG.md (cycle 36).

- **From-Player Index Bounds (Cycle 30, verified through cycle 36):** Network packet `from_player` field validated against [0, MAXPLAYERS) before player state access. Prevents spoofed packets from corrupting arbitrary player slots.
  - **Cite:** `SRC/MMULTI.C:202`, docs/audits/security-and-secrets-r10.md.

---

### Performance: Frame Analyzer Cold-Start Optimization (Cycle 36)

**Challenge:** Python testing tools like `tools/frame_analyzer.py` suffered from slow cold-start due to eager PIL/numpy/scipy imports. Each test invocation loaded these heavy dependencies (0.2s–0.3s overhead), slowing feedback loops on CI/CD pipelines and developer workflows.

**Solution (Cycle 36):** Implemented lazy import helpers with singleton caching in frame_analyzer.py (lines 15–50):
- `_get_pil()` — defers PIL.Image import until first frame loaded
- `_get_numpy()` — defers numpy import until pixel analysis requested
- `_get_scipy()` — defers scipy.ndimage import until convolution-based edge detection needed

**Impact:**
- Cold-start time reduced by **22x** (0.2s → 0.009s).
- Imports only loaded when actually used (pixel operations, edge detection).
- Developer iteration speed significantly improved; test feedback loop faster.
- CI/CD pipeline throughput improved; fewer timeouts on resource-constrained runners.

**Cite:** `tools/frame_analyzer.py:15–50`, docs/audits/performance-profiler-r10.md.

---

<!-- docs-arch-network-section: cycle 48 -->

## Network Architecture

The multiplayer networking layer (cycles 26–48) implements **star topology TCP/IP multiplayer** via `SRC/MMULTI.C`, replacing DOS-era IPX with modern BSD sockets (POSIX on Linux, Winsock on Windows). This section documents the wire protocol, packet types, lifecycle, and known gaps as of cycle 48 (r12 audit).

### Wire Protocol & Transport

**Packet Header Format (cycle 65 — net-r15 seqnum extension):**
```
NET_HEADER_SIZE = 5 bytes:
  [1B: sender ID] [1B: dest ID] [1B: sequence number] [2B: payload length (LE)]

Payload: up to MAXPACKETSIZE = 2048 bytes
  (MTU-safe; avoids fragmentation on standard Ethernet 1500 byte MTU)
```

Cycle 65 added a per-peer monotonic sequence byte (`net-r15-seqnum`) between
dest and payload_len. Wrap is `(seq + 1) & 0xFF`; init sentinel `0xFF`
indicates "no packet yet". Gap detection is log-only (does NOT drop). See
SRC/MMULTI.C `NET_HEADER_SIZE` definition + 14 `net-r15-seqnum` sentinels.

**Transport:**
- **Protocol**: TCP (stream-based) on `IPPROTO_TCP` with `TCP_NODELAY` enabled (disable Nagle's algorithm for low-latency gameplay)
- **Port**: Default 23513 (configurable via `--port` CLI flag)
- **Topology**: Star (1 host server relays all state to up to MAXPLAYERS-1 clients)
- **Buffers**: Per-socket 64KB recv buffer (`RECV_BUF_SIZE`, SRC/MMULTI.C:46) for TCP stream reassembly; packet queue (1024 slots) buffers complete packets for game loop consumption

**Non-Blocking I/O & Error Handling (Cycle 41):**
- Recv path (`net_poll_sockets()`, SRC/MMULTI.C:244–253) distinguishes **transient errors** (EAGAIN, EWOULDBLOCK, EINTR on POSIX; WSAEWOULDBLOCK, WSAEINTR on Windows) from **fatal errors** (connection drop)
- Transient errors are retried; fatal errors close the socket and remove the player
- **Rationale**: WiFi and congested LANs experience frequent transient stalls; aborting on EAGAIN breaks multiplayer

### Packet Types & Bounds Matrix

**15 Active Packet Types** (comprehensive inventory from cycle 48 r12 audit):

| Type | Purpose | Location | Guard Status | Cycle Closed | Findings |
|------|---------|----------|--------------|--------------|----------|
| **0** | Master sync (host→clients) | source/GAME.C:409–517 | ✅ PASS | r8+ | Multi-stage per-field bounds; SAFE |
| **1** | Slave sync (client→host) | source/GAME.C:517–568 | ✅ PASS | r8+ | Field-by-field validation; SAFE |
| **4** | Chat message | source/GAME.C:569–580 | ⚠️ **HIGH** | OPEN (cycle 48) | **MISSING pre-check**: packbuf[1] read without pre-validation packbufleng ≥ 2 → OOB read risk |
| **5** | Game settings | source/GAME.C:582–642 | ✅ PASS | r8+ | 10 fields validated; SAFE |
| **6** | Player name exchange | source/GAME.C:644–666 | ✅ PASS | 38 | Cycle-38 strncpy hardening; bounded copy; SAFE |
| **7** | RTS sound event | source/GAME.C:678–700 | ✅ PASS | r8+ | Sound ID range-checked; SAFE |
| **8** | Host game settings | source/GAME.C:702–763 | ✅ PASS | 42 | Cycle-42 pre-check `packbufleng < 11`; SAFE |
| **9** | Weapon choice | source/GAME.C:668–676 | ⚠️ **MEDIUM** | OPEN (cycle 48) | **MINIMAL validation**: packbuf[1] read, implicit assume packbufleng ≥ 2, no explicit pre-check → OOB read risk |
| **16** | Input sync init | source/GAME.C:766–768 | ✅ PASS | r9+ | Initialization only (no payload reads); SAFE |
| **17** | Input sync (delta update) | source/GAME.C:769–810 | ✅ PASS | 45 | **Cycle-45 envelope pre-validate** (r11 closure verified): pre-check `packbufleng < 20` at line 770 protects multi-byte field reads at 786–794 |
| **125** | Reserved/Debug | source/GAME.C:397–399 | ✅ N/A | — | No-op; no payload processing |
| **126** | Load player / Ready | source/GAME.C:401–407 | ✅ PASS | r8+ | Single field; no overflow risk |
| **127** | No-op | source/GAME.C:813–814 | ✅ N/A | — | No-op; no payload processing |
| **250** | Player ready | source/GAME.C:816–818 | ✅ PASS | r8+ | Counter increment only; no payload read |
| **255** | Exit game | source/GAME.C:819–821 | ✅ N/A | — | Terminate; no payload processing |
| **Unhandled** | Types 2–3, 10–15, 18–124, 128–249, 251–254 | — | ✅ PASS | r8+ | Safe fallthrough; no dispatcher crash risk |

**Status Summary (Cycle 48):**
- **13 types PASS / N/A** (all prior cycles), **2 types OPEN** (type-4, type-9 HIGH/MEDIUM gaps identified in r12)
- **Type-17 cycle-45 closure verified INTACT**: envelope pre-validation `packbufleng < 20` at line 770 gates field reads

### Connection Lifecycle

**Host Startup:**
1. Bind TCP socket on port 23513 (or CLI-specified port)
2. Enter `listen()` with backlog = 4
3. Accept client connections; assign player slot (0–MAXPLAYERS-1)
4. Initiate handshake: exchange protocol version, player name, color, player bitmap

**Client Join:**
1. Resolve host address (IPv4 only; IPv6 pending per r10 design spec)
2. Connect TCP socket to host:port
3. Complete handshake: verify protocol version, transmit player name/color, receive other players' rosters
4. Handshake timeout = 15s (cycle-39 hardening); client drops if handshake incomplete

**Game State Sync (Active):**
- Host broadcasts **Type-0 Master Sync** ~16ms per cycle (60 Hz game loop): sprite positions, player state, projectiles, world changes
- Clients transmit **Type-1 Slave Sync** with input: movement, weapon fire, look direction
- All packets append CRC-16 checksum (CRC mismatch → client drops with diagnostic)

**Disconnect & Cleanup (Cycle 45):**
- Client closes socket → host detects recv() EOF, removes player slot
- Host closes → clients recv() EOF, drop to single-player
- **Cleanup**: `memset(&recv_bufs[i], 0, sizeof(recv_bufs[i]))` clears per-player recv buffer (prevents stale data leak on reconnect)

### Packet Integrity (current gap)

**CRC Implementation Status (Cycle 59 audit closure):**

Helper functions `initcrc()`, `getcrc()`, and `updatecrc16()` are **compiled and initialized** (SRC/MMULTI.C:319–358, 381) but **never invoked per-packet**. This creates a dormant integrity gap:

| Aspect | Current State | Risk |
|--------|---------------|------|
| **Wire Format** | 4-byte header: `[sender_id][dest_id][len_lo][len_hi]`; no CRC field | No protection against bit-flip errors |
| **LAN Scenarios** | TCP checksums + host relays all traffic | **LOW risk**; TCP catches ~99.99% of accidental bit-flips; host authority prevents replay attacks |
| **WAN Scenarios (cross-datacenter)** | TCP checksums only; packet corruption undetected | **MEDIUM risk**; deliberate bit-flips or rare bitrot could pass TCP validation on low-MTU paths |
| **Mitigation Assumed** | Not implemented; relying on TCP + host trust model | Suitable for cooperative LAN play; insufficient for untrusted networks |

**Why CRC Not Active:**
- Cycle 39–48 designs flagged CRC as essential but deferred implementation due to **backwards-incompatible wire format bump** (4 → 8-byte header required).
- Functions retained in source (not deleted) to ease future protocol upgrade without reimplementation.

**Future Work:**
- See audit [docs/audits/network-multiplayer-r14.md](docs/audits/network-multiplayer-r14.md) § CRC Validation — Dormant/Unused for full scope.
- **Todo**: `net-r14-crc-validation-dormant-full-impl` (pending; MEDIUM severity) — expand header to 8 bytes (`[sender][dest][len_lo][len_hi][crc32_lo][crc32_mid][crc32_mid2][crc32_hi]`), calculate CRC over `[sender][dest][payload_len][payload]`, validate on receive, drop peers with CRC mismatch.

### Known Gaps & Design Pending (Cycle 48 r12)

**HIGH Priority:**
1. **Type-4 chat bounds** — Fix in flight (5-minute patch: add `if (packbufleng < 2) break;` at case 4 entry)
2. **IPv6 dual-stack** — Design ready; refactor `inet_addr()` → `getaddrinfo()` + socket creation loop (large scope; stage for cycle 49+)
3. **Replay sequence tracking** — Acceptance criteria underdefined; coordinate with test-engineer on packet sequence numbering for deterministic replay

**MEDIUM Priority:**
1. **Type-9 weapon bounds** — Add `if (packbufleng < 2) break;` pre-check (implicit MAXPLAYERS loop may OOB if malformed)
2. **Socket lifecycle audit** — Error-path cleanup (crash recovery, partial-send retry, timeout edge cases) needs dedicated audit
3. **xdist parallel isolation** — Verify recv_buf thread-safety under pytest `-n auto` (parallel test workers may share sockets on Linux)

## Network MTU & Fragmentation Strategy

This section documents packet sizing, TCP Nagle tuning, and fragmentation handling for multiplayer networking (cycle 50 investigation per audit-net-fragmentation).

### MAXPACKETSIZE & Header Layout

**Definition & Rationale (SRC/MMULTI.C:44–46):**
```c
#define MAXPACKETSIZE 2048       /* bytes; chosen to avoid path-MTU fragmentation */
#define NET_HEADER_SIZE 4        /* [1B sender][1B dest][2B payload_len] */
#define RECV_BUF_SIZE 65536      /* per-socket TCP stream reassembly buffer */
```

- **MAXPACKETSIZE = 2048 bytes** (application-layer limit) is conservative vs. Ethernet MTU (1500 bytes). **Rationale**: TCP/IP stack fragments at ~1500 bytes; keeping application payloads to 2048 total (including 4-byte header = 2044-byte max payload) ensures any single application send fits within a single TCP segment if path MTU is ≥1500 (typical Ethernet). See SRC/MMULTI.C:277 validation: `if (payload_len > MAXPACKETSIZE - NET_HEADER_SIZE)`.
- **NET_HEADER_SIZE = 5 bytes** (sender ID, destination ID, sequence, payload length — sequence added cycle 65) framing cost is ~0.25% overhead at full payload.

### Transport Protocol & Socket Tuning

**TCP, Not UDP:**
- Protocol: **Pure TCP (SOCK_STREAM)** on IPPROTO_TCP, port 23513 default.
- **Why TCP**: Ordered, reliable delivery; packet boundaries reconstructed by application via header framing (not kernel UDP fragmentation). Star topology places host as relay; TCP's in-order guarantee prevents packet reordering crashes.
- **No IP_DONTFRAG, No IP_MTU_DISCOVER**: Code does not set IP_DONTFRAG (IPPROTO_IP level) or IP_MTU_DISCOVER. Result: kernel may fragment packets >path-MTU silently; application layer does not probe MTU.

**TCP_NODELAY (Nagle Disabled):**
- Both host (SRC/MMULTI.C:488) and client (SRC/MMULTI.C:548): `setsockopt(..., IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag))`.
- **Rationale for Neon Noir gameplay**: Nagle delays small packets until ACK or MSS-sized buffer; disabling Nagle trades throughput for **latency**: game input packets (type-1, ~20–100 bytes) transmit immediately vs. waiting ~40ms for TCP window fill. Acceptable for LAN; may stress high-latency WAN (no backpressure).

### Per-Packet-Type Size Analysis

**15 Active Packet Types** (see docs/audits/network-multiplayer-r13.md for full matrix):

| Type | Purpose | Max Size | Payload Field | Fragment Risk |
|------|---------|----------|---|---|
| **0** | Master sync (sprites, state) | 2044 | Variable sprite updates | ✅ None (split per sprite if needed) |
| **1** | Slave sync (input) | ~100 | Input state deltas | ✅ None |
| **4** | Chat | 256 | String (bounded strncpy, r12 fix) | ✅ None |
| **5** | Game settings | ~128 | 10 fields (r13 audit: CRITICAL pre-check missing) | ✅ None |
| **6** | Player name | ~128 | String + color (cycle-38 strncpy hardened) | ✅ None |
| **7** | RTS sound event | ~64 | Sound ID + position (r13: MEDIUM pre-check gap) | ✅ None |
| **8** | Post-game stats | ~256 | Score, kills, deaths (r13: CRITICAL late bounds check) | ✅ None |
| **9** | Weapon choice | ~32 | Weapon bitmask (r12 fix verified) | ✅ None |
| **17** | Input sync delta | ~100 | Movement, look (r11 envelope pre-check verified) | ✅ None |
| Other | Initialization, player ready, exit | <64 | Minimal payloads | ✅ None |

**Key Insight**: All packet types fit **single TCP segment** (2044 payload < 1460 MSS typical); no application-layer chunking required. **Cross-reference**: docs/audits/network-multiplayer-r13.md § Packet-Handler Bounds Matrix (lines 74–91).

### TCP Stream Reassembly & Fragmentation Behavior

**Application-Level Framing:**
- Per-socket 64KB recv buffer (SRC/MMULTI.C:82–87, RECV_BUF_SIZE=65536) reassembles TCP stream.
- Packet extraction loop (SRC/MMULTI.C:259–283): read header, validate payload_len, extract complete packets into queue.
- **If pathMTU < 2048**: IP layer fragments; TCP reassembles transparently; application sees complete packets. No loss (TCP retransmits fragments).

**No Explicit Fragmentation Handling:**
- Code assumes TCP kernel handles all IP-layer fragmentation.
- **Risk (unmitigated)**: If pathMTU < 500 bytes (rare; satellite links, heavily congested networks), packet must be split application-layer. **Not implemented; flagged as future gap** (net-r13-frag-path-mtu-discover, below).

### TCP Nagle & Throughput Tradeoff (Cycle 50 Analysis)

**Decision**: Nagle **disabled** (TCP_NODELAY=1) for gameplay latency.

| Nagle Setting | Throughput | Latency | Scenario |
|---|---|---|---|
| Enabled (default) | Higher; buffers small packets | ~40ms+ delay | Bulk file transfer |
| **Disabled (current)** | Lower; more packets, ACKs | ~0–5ms delay | **Neon Noir low-latency gameplay** |

**Tradeoff Rationale**: Game input (type-1, ~20 bytes) must reach host ≤16ms (60Hz tick). Nagle's wait-for-MSS delays fire/movement commands; unacceptable. **Throughput cost**: 3 input packets/tick × 60 ticks/sec × small-packet overhead ≈ negligible on LAN (<1% bandwidth for typical dual 10Mbps NICs).

### Known Limits

- **Max players**: 16 (MAXPLAYERS, SRC/MMULTI.C:43); star topology host I/O bound (no routing layer).
- **Max simultaneous packet types in flight**: Unlimited; packet queue is 1024 slots (SRC/MMULTI.C:90). At 60 Hz, queue drains 60 packets/sec; buffer tolerates ~17-second burst at 100 packets/sec (pathological).
- **Max total payload in flight**: 65536 bytes per socket recv buffer.
- **Handshake timeout**: 15 seconds (HANDSHAKE_TIMEOUT_SEC, SRC/MMULTI.C:52); exceeding resets client.

### Forward-Looking Gaps (New Todos — Cycle 50)

Audit investigation surfaced **4 gaps** for future grind:

1. **net-r13-frag-path-mtu-discover** — Implement IP_MTU_DISCOVER (Linux) or equivalent (Windows PMTU discovery) to probe actual path MTU at startup. If <500, warn user or implement application-layer packet splitting. **Severity**: LOW (rare in 2024); **effort**: MEDIUM (requires platform-specific socket opts + fallback logic).

2. **net-r13-frag-send-buf-tuning** — Currently no SO_SNDBUF / SO_RCVBUF tuning. Profile WAN scenarios (>100ms RTT, variable bandwidth) to optimize buffer sizes. **Severity**: LOW (LAN-focused); **effort**: LOW (setsockopt calls; needs lab test harness).

3. **net-r13-frag-packet-split-appl** — If pathMTU <500 discovered, implement application-layer packet chunking (split type-0 master sync into multiple sub-packets). **Severity**: LOW; **effort**: HIGH (state machine, reassembly logic).

4. **net-r13-frag-explicit-test-matrix** — Add pytest tests for fragmentation edge cases (manual TCP_NODELAY toggle, simulate low pathMTU via iptables, verify queue overflow handling). **Severity**: MEDIUM; **effort**: MEDIUM (test harness, requires Linux VM setup).

<!-- docs-feature-summary-update: cycle 50 -->

## Recent Improvements (Cycles 41–49)

This section documents major stabilization and performance work from cycles 41–49, with cross-references to audit reports and cycle closures.

### Testing Infrastructure (Cycles 41–46)

**Property-Based Testing (Cycle 41+)**
- Hypothesis/property-based tests added for engine bounds, deterministic playback, and asset generation edge cases
- Enables fuzzing-like coverage without manual test case explosion
- **Cite:** [docs/audits/test-engineer-r13.md](docs/audits/test-engineer-r13.md) § Test Infrastructure.

**Multiplayer Regression Harness (Cycle 48)**
- New `tests/test_engine_net_hardening_regressions.py` implements automated packet type bounds matrix (15 active types, each pre-validated)
- Closed 2 HIGH/MEDIUM packet handler gaps (Type-4 chat, Type-9 weapon) discovered in cycle-48 audit
- Prevents future packet-type regression via parametrized test matrix
- **Cite:** [docs/audits/network-multiplayer-r12.md](docs/audits/network-multiplayer-r12.md) § Packet Types & Bounds Matrix (lines 744–760 in this doc).

**Parallel Testing with xdist + filelock (Cycles 45–46)**
- Cycle-45 initial attempt failed due to shared `generated_audio_artifacts` fixture race on `/tmp` (reverted)
- Cycle-46 closure: filelock-based singleton initialization in `tests/conftest.py` with per-worker coordination
- Result: **37.5% wallclock speedup** (22.98s → 14.76s with `pytest -n auto`)
- `pytest.ini` re-enabled: `addopts = -n auto --dist loadscope`
- **Cite:** [docs/audits/performance-profiler-r13.md](docs/audits/performance-profiler-r13.md), [docs/audits/test-engineer-r14.md](docs/audits/test-engineer-r14.md) § xdist Coordination.

### Build System (Cycle 46)

**Header Dependency Tracking**
- Makefile now uses `-MMD -MP` flags to generate `.d` dependency files
- Include directive `-include *.d` automatically rebuilds on header touch
- Eliminates stale binary syndrome (editing a header no longer ignored)
- **Cite:** [docs/audits/build-system-r14.md](docs/audits/build-system-r14.md) § build-r14-header-deps.

### Asset Pipeline & Audio (Cycles 42–46)

**Atomic Manifest Write (Cycle 42, re-verified Cycle 46)**
- Cycles 41–42: Identified ThreadPool and asyncio race in `tools/generate_audio.py` (manifest corruption on interruption)
- Cycle 46 closure: Per-entry sequential writes + atomic top-level commit pattern
- Manifest now includes SHA256 checksums for integrity detection
- **Cite:** [docs/audits/audio-engineer-r12.md](docs/audits/audio-engineer-r12.md) § Manifest Race Fixes.

**Manifest SHA256 Checksums (Cycle 46)**
- `tools/generate_tables.py` and `tools/generate_audio.py` now compute per-entry + top-level SHA256
- Mutations in generated assets now detectable during load (vs. silent corruption)
- Tests in `tests/test_audio_pipeline.py` and `tests/test_asset_pipeline.py` verify checksum consistency
- **Cite:** [docs/audits/asset-pipeline-r15.md](docs/audits/asset-pipeline-r15.md) § Asset Versioning.

### Engine Hardening (Cycles 41–42)

**SE40 Performance Optimization (Cycles 41–42)**
- `SE40_Draw` rendering path validated for sprite sectnum bounds
- Eliminated unnecessary allocache lookups in cold render path
- **Result: 22× cold-start speedup** (frame analyzer 0.2s → 0.009s)
- Guards preserve unsafe-by-default semantics: caller responsible for pre-validation, engine checks within SE40_Draw scope
- **Cite:** [docs/audits/performance-profiler-r10.md](docs/audits/performance-profiler-r10.md); [docs/audits/engine-porter-r12.md](docs/audits/engine-porter-r12.md) § Cycles 41–42 Closures.

**MAXTILES Header Unification + Abort Guard (Cycles 41–42)**
- Long-standing conflict: `SRC/BUILD.H` hardcoded MAXTILES=9216 vs. `source/BUILD.H`=6144
- **Cycle 41 Stage 2:** Unified both to 6144 (source/ is authority; SRC/ updated with compile-time assertion)
- **Cycle 42 Stage 3:** Added runtime abort guard in `compat/maxtiles_guard.c` — constructor function compares and aborts if future divergence detected
- Prevents silent tile ID OOB corruption from header desync
- **Cite:** [docs/audits/build-system-r13.md](docs/audits/build-system-r13.md) → [docs/audits/build-system-r14.md](docs/audits/build-system-r14.md) § MAXTILES Stages 1–3.

### Summary

All cycles 41–49 improvements are production-verified and tracked in [docs/audits/GRIND_LOG.md](docs/audits/GRIND_LOG.md) with per-cycle closure details. Critical paths (Network, MAXTILES, xdist) all have parametrized test coverage and audit sign-off.

---

**See Also:**
- [docs/audits/network-multiplayer-r12.md](docs/audits/network-multiplayer-r12.md) — Full packet-handler bounds matrix, cycle-41/44/45 closure verification, and r12 gap analysis
- [docs/audits/network-multiplayer-r11.md](docs/audits/network-multiplayer-r11.md) — Cycle-41 EAGAIN distinction closure, cycle-44 landing verification

### Multiplayer Regression Test Harness

**Static Analysis Tests** (catch regressions without running engine):
- `tests/test_engine_net_hardening_regressions.py` — Regex-based inspection of `SRC/MMULTI.C` and `source/GAME.C`
  - Verifies type-0/1 bounds checks remain in place
  - Verifies type-17 envelope pre-check `packbufleng < 20` at line 770
  - Verifies type-8 pre-check `packbufleng < 11` at line 752
  - Verifies EAGAIN distinction at lines 244–253
  - Verifies disconnect memset at line 621

**Integration Tests** (full protocol):
- `tests/test_multiplayer_protocol.py` — Socket-level protocol validation (if available; see `tests/` directory)
  - Host bind + accept handshake
  - Packet encoding/decoding (NET_HEADER_SIZE, payload assembly)
  - CRC validation

**Run regression tests:**
```bash
pytest tests/test_engine_net_hardening_regressions.py -v
pytest tests/ -k multiplayer -v --timeout=30
```

---

This section documents **CRITICAL, HIGH, and selected MEDIUM-priority** issues identified in audit rounds r7+ that remain open in the current release cycle. These items are actively tracked in the audit backlog and are prioritized for future development cycles.

### Build System (MAXTILES Hardening — Active Remediation)

The most significant open issue in the build system is the MAXTILES mismatch between engine and game headers, classified as **CRITICAL** and tracked across 3 remediation stages (see build-system-r13 for detailed analysis):

- **build-r13-maxtiles-unify-headers-to-6144** (CRITICAL — Stage 2/3): SRC/BUILD.H:15 and source/BUILD.H declare MAXTILES with conflicting bounds (6144 vs 9216) → LTO link-time type-mismatch buffer-overflow risk. Stage 2 requires unifying to 6144 (game-centric); Stage 3 requires flipping abort() call in compat/maxtiles_guard.c and removing xfail from tests/test_maxtiles_assertion.py. Target: Cycles 40–41. **Cite:** [docs/audits/build-system-r13.md](docs/audits/build-system-r13.md) § Focus Areas 1–3.

- **build-r7-makefile-race-condition** (HIGH): Makefile $(TARGET) rule race condition — chmod/strip not atomic, causing transient "cannot access 'duke3d'" errors during parallel builds (-j 4+). **Cite:** [docs/audits/build-system-r7.md](docs/audits/build-system-r7.md).

- **build-r7-windows-arch-mismatch** (HIGH): build_windows.bat hardcodes x86_64 while developer environment is i686, leading to cross-architecture linking failures. Requires environment-variable detection or CLI flag. **Cite:** [docs/audits/build-system-r7.md](docs/audits/build-system-r7.md).

### Engine (Bounds Hardening Phases II–III)

Engine-porter audits have identified **3 CRITICAL and 6 HIGH** items across sector indexing, sprite metadata, and render paths. Recent cycles (37–39) have closed 3 items; 9 remain pending:

**CRITICAL (3):**
- **engine-r13-sector-operatesectors-bounds** (CRITICAL): operatesectors() unvalidated sector parameter — missing (unsigned) bounds check on sn before sector[] dereference at source/SECTOR.C:566. **Cite:** [docs/audits/engine-porter-r13.md](docs/audits/engine-porter-r13.md) § Part 4, Finding 1.

- **engine-r12-actors-tempshort-explicit-cap** (CRITICAL — Latent Since r11): Latent buffer overflow in ACTORS.C tempshort buffer; explicit cap needed (cycle-39 implementations incomplete). **Cite:** [docs/audits/engine-porter-r13.md](docs/audits/engine-porter-r13.md) § Part 2.1.

- (Prior r10–r11 items rolled into engine-r12/r13 consolidation; RTS.C numlumps, sector index in dereference both addressed in cycle-39 grind).

**HIGH (6):**
- **engine-r13-engine-nextsectorneighborz-bounds** (HIGH): nextsectorneighborz() unvalidated input and return — validate both sectnum input and wal->nextsector before sector[] dereference at SRC/ENGINE.C:4945–4973. **Cite:** [docs/audits/engine-porter-r13.md](docs/audits/engine-porter-r13.md) § Part 4, Finding 2.

- **engine-r13-sector-animatesect-bounds** (HIGH): animatesect[] unvalidated at read points (source/SECTOR.C:297–310) — validate array access before sector index derivation. **Cite:** [docs/audits/engine-porter-r13.md](docs/audits/engine-porter-r13.md) § Part 4, Finding 3.

- **engine-r13-actors-sprite-sectnum-chain** (HIGH): sprite.sectnum bounds chain in animation logic (source/ACTORS.C:902–1321) — 5-point access cascade unguarded. **Cite:** [docs/audits/engine-porter-r13.md](docs/audits/engine-porter-r13.md) § Part 3.1.

- **engine-r12-actors-projectile-sectnum** (DECLASSIFIED as OBSOLETE per r13 analysis; code not present).

- (Prior render-path items from r11–r12: drawsprite() sectnum, scansector() bitfield — superseded by operatesectors consolidation).

### Network Multiplayer (Architectural Design — Cycles 39–40)

Network-multiplayer audits have identified **3 architectural items** spanning packet type coverage and protocol design:

- **net-r9-packet-type-6-8-16-17-bounds** (MEDIUM–HIGH, Architectural): Packet types 6, 8, 16, 17 require bounds validation for player indices, map metadata, and replay fields. Type-6 (cycle-38) partially addressed; types 8/16/17 pending. **Cite:** [docs/audits/network-multiplayer-r9.md](docs/audits/network-multiplayer-r9.md).

- **net-r9-ipv6-design** (HIGH, Architectural): IPv6 support requires protocol redesign (currently IPv4-only). Identified in r9 as future-work item for v0.3+. **Cite:** [docs/audits/network-multiplayer-r9.md](docs/audits/network-multiplayer-r9.md).

- **net-r8-recv-eagain-handling** (MEDIUM): Recv-side EAGAIN (non-blocking I/O) handling incomplete; may drop packets on transient socket unavailability. **Cite:** [docs/audits/network-multiplayer-r8.md](docs/audits/network-multiplayer-r8.md).

### Security (String & Buffer Handling)

Security-and-secrets audits have validated most cycle-26/33/34 fixes; no NEW CRITICAL items since r10, but prior findings remain **CLOSED or INCORPORATED**:

- (Prior HIGH items: RTS.C overflow, ACTORS.C tempshort — now under engine-porter tracking above).
- **sec-r12-remaining-open-items** (MEDIUM–ADVISORY): Code review debt — static patterns (GNU89 comments 746 instances, shift-overflow audit) not yet automated. **Cite:** [docs/audits/security-and-secrets-r11.md](docs/audits/security-and-secrets-r11.md).

### Audio, Asset Pipeline, Compat (Lower Priority — MEDIUM/ADVISORY)

- **audio-r10-music-state-consistency** (MEDIUM): MUSIC_PlaySong returns MUSIC_Ok despite Mix_LoadMUS_RW failure (error asymmetry). Cycle-37 partial fix; state machine redesign pending. **Cite:** [docs/audits/audio-engineer-r10.md](docs/audits/audio-engineer-r10.md).

- **asset-r11-manifest-schema-alignment** (MEDIUM): Texture, sprite, palette, table, map generators lack versioned manifest (audio schema v1.0 adopted in cycle-34; cross-tool consistency gap). **Cite:** [docs/audits/asset-pipeline-r11.md](docs/audits/asset-pipeline-r11.md) § Part 3 (5 per-tool sub-steps recommended).

- **asset-r9-flux-retry-backoff** (MEDIUM): FLUX API calls lack retry/backoff logic; API rate-limit risk. **Cite:** [docs/audits/asset-pipeline-r9.md](docs/audits/asset-pipeline-r9.md).

- **compat-r10-error-fatal-noreturn** (LOW): error_fatal() missing _Noreturn annotation (C11 hygiene). **Cite:** [docs/audits/compat-layer-r10.md](docs/audits/compat-layer-r10.md).

## Orphan / Dormant Files

Files preserved in the repository for historical reference or potential future restoration, but currently unused in the active build.

### compat/a.c — Historical C Port of SRC/A.ASM (Archived)

**Location**: `docs/archive/compat/a.c` (894 lines)

**Status**: Dead code (unreferenced in build system)

**Disposition**: Archived as **Option B** (legacy/reference port) with full documentation.

**Provenance**: Pure-C implementation of BUILD engine's inner-loop rendering routines (texture-mapped walls, floors, ceilings, sprite rendering, translucency, voxel slabs). Intended as a portable replacement for x86 assembly in `SRC/A.ASM` when the codebase was transitioned to C. Added in commit 748cedc ("Add Makefile, fix linker errors, and complete the build").

**Why Archived?**

- Not integrated into build system (CMakeLists.txt, build.mk, Makefile)
- Superseded by active implementations in SRC/ENGINE.C (hlineasm4, vlineasm, etc.)
- No external references in active source code
- Build and tests pass without this file

**Preservation Rationale**: File is kept in git history for educational reference and potential future restoration if:
1. A pure-C rendering backend becomes necessary (current implementations use ENGINE.C's approach)
2. Platform-specific issues require returning to a portable baseline
3. Code porting exercises need portable C reference implementations

**To Restore**: See [docs/archive/compat/README.md](docs/archive/compat/README.md) for restoration instructions.

**Audit**: Cycle 57 build-system audit (committed via compat-layer-r15 fixes); confirmed orphan status with no callers in active source.

## Build & Portability Invariants

This section consolidates critical build, platform, and protocol invariants discovered and enforced across cycles 11–69. These are **non-negotiable constraints** that, if violated, cause silent corruption, build failures, or cross-platform incompatibilities. Each invariant is cited from audit reports where the issue was first identified or its enforcement verified.

### A. CMake `.C` Language Property (No `/Tc` Flag)

**Rule:** For MSVC builds, use `set_source_files_properties(... PROPERTIES LANGUAGE C)` to mark `.C` files as C, NOT `-Tc` compile flags.

**Rationale:** The MSVC `/Tc` flag consumes the next token as a filename, triggering error `D8036: cannot specify 'option' with '/Tc filename'`. The `LANGUAGE C` property is the CMake-idiomatic way to specify file language.

**Enforcement:** CMakeLists.txt line 62 sets `LANGUAGE C` property for ENGINE_SRCS and GAME_SRCS; comment at lines 79–80 documents the pitfall. See **[docs/audits/build-system.md](docs/audits/build-system.md)** § Memory-Hack Invariants.

---

### B. SDL2_VERSION Single Source of Truth

**Rule:** SDL2 version is defined **only** in `build.mk` (line 33: `SDL2_VERSION = 2.30.9`). All other build systems parse from `build.mk` via `grep`.

**Rationale:** Hardcoding SDL2 version in multiple places (CMakeLists.txt, build_windows.bat, .github/workflows) leads to silent divergence. CI scripts, Windows bootstrap, and asset generation must all use the same canonical version.

**Enforcement:** 
- **Canonical:** `build.mk:33` 
- **CI Parsing:** `.github/workflows/build.yml` (line 65–67), `.github/workflows/release.yml` (line 35–37), `tools/get_sdl2_mingw.sh` (line 8), `tools/bundle_windows.sh` (line 10)

See **[docs/audits/build-system.md](docs/audits/build-system.md)** § Invariant B: SDL2_VERSION Single Source of Truth.

---

### C. PowerShell ASCII-Only Punctuation

**Rule:** Windows PowerShell scripts (`.ps1` files) must use ASCII-only punctuation. Avoid em-dashes (—), smart quotes, or other Unicode characters. Files without UTF-8 BOM are parsed as Windows-1252, causing encoding errors.

**Rationale:** Windows PowerShell (especially versions < 7) on Windows-1252 locales silently corrupts non-ASCII punctuation. Build bootstrap and platform detection must be robust across legacy Windows environments.

**Enforcement:** `tools/check_secrets.sh`, `tools/bundle_windows.sh`, `tools/get_sdl2_mingw.sh` are all ASCII-only ✅. **Planned:** `tools/win_build.ps1` (cycle 65+) must enforce this constraint.

See **[docs/audits/build-system.md](docs/audits/build-system.md)** § Invariant C.

---

### D. LTO_FLAGS Contract

**Rule:** `Makefile` line 16 defines `LTO_FLAGS = -flto` for release builds. LTO must **remain enabled** (`-flto`) and is part of the release-build identity.

**Rationale:** Cycle 65 grind included an agent that disabled LTO (set `LTO_FLAGS =` to empty) without justification. LTO is intentional for binary size and performance in release builds. Disabling it silently downgrades release binaries.

**Enforcement:** Makefile line 16 (release), line 12 (debug empty), applied to compilation and linking. CMakeLists.txt line 73: `INTERPROCEDURAL_OPTIMIZATION TRUE` (release) mirrors Makefile. See **[docs/audits/build-system-r18.md](docs/audits/build-system-r18.md)** § Build Quality Metrics — LTO parity verified.

**Sentinel:** Cycle 65 grind collateral: LTO disabled mid-grind, **REVERTED** before commit.

---

### E. GNU89 / C11 Split

**Rule:** 
- `SRC/*.C` (engine) and `source/*.C` (game) compile with **`-std=gnu89`** (K&R C + GNU extensions, no `//` line comments in legacy code, locals at block top).
- `compat/*.c` (compatibility layer) compiles with **`-std=gnu11`** (C11, `//` line comments allowed).

**Rationale:** The legacy BUILD engine was written in K&R C without line comments. Modern compat layer code uses C11 features. Mixing standards within the same compilation unit causes confusion and potential ABI issues.

**Enforcement:**
- **Makefile:** Line 20 (`LEGACY_STD = -std=gnu89`) for ENGINE/GAME, line 131 (`COMPAT_STD` → `-std=gnu11`) for compat.
- **CMakeLists.txt:** Lines 79–80 (gnu89 for ENGINE/GAME), lines 81–82 (gnu11 for COMPAT_SRCS).
- **Build system parity verified:** See **[docs/audits/build-system-r15.md](docs/audits/build-system-r15.md)** § gnu89 / gnu11 Enforcement.

---

### F. `check_secrets.sh` Inner Verification Scoping

**Rule:** Pre-commit hook `tools/check_secrets.sh` performs pattern matching on added lines only. Inner verification grep blocks must:
1. Scope to `^+` (added lines only, not context or deleted).
2. Apply the same exclusion patterns (e.g., `grep -v build.mk`, `grep -v docs/audits/`) as the outer prefilter.

**Rationale:** Without `^+` scoping, committed legitimate secrets (e.g., test fixtures with realistic API keys) get re-flagged on every commit, causing false positives. Asymmetric exclusion patterns lead to check inconsistency.

**Enforcement:** `tools/check_secrets.sh` (128 lines) uses 8 pattern groups (Google Cloud, Slack, npm, Stripe, HuggingFace, OpenAI, etc.) with `^+` prefix in grep patterns + 12 regression tests.

See **[docs/audits/build-system-r15.md](docs/audits/build-system-r15.md)** § Focus Area 9: Pre-commit Hook.

---

### G. Windows Build Entry: `tools/win_build.ps1` Contract

**Rule:** Windows build entry point uses `tools/win_build.ps1` (planned, cycle 65+) with the following interface:

- **Actions:** `-Action build|clean|info`
- **Build Type:** `-BuildType release|debug`
- **Bootstrap:** Auto-detects MSVC via `vswhere` (part of VS2022 Community installer), uses bundled CMake/Ninja from Visual Studio, auto-fetches `SDL2-devel-2.30.9-VC` into `third_party/`.
- **Character Encoding:** ASCII-only (see Invariant C).

**Current Status:** `tools/win_build.ps1` does not yet exist; `build_windows.bat` and CMake provide functional alternatives. PowerShell script is planned for developer UX improvement but not blocking.

**Rationale:** Unified Windows build experience across CI (GitHub Actions) and developer machines. Single source of truth for SDL2 version, MSVC bootstrap, and artifact layout.

See **[docs/audits/build-system.md](docs/audits/build-system.md)** § MISSING COMPONENTS (Invariant D).

---

### H. NET_HEADER_SIZE = 5 Bytes

**Rule:** Network packet header format is fixed at **5 bytes**:
```
[sender_id:1B] [dest_id:1B] [sequence:1B] [payload_len:2B LE]
```

**Rationale:** Cycle 65 extended NET_HEADER from 4 bytes to 5 bytes, adding a 1-byte sequence number for per-peer monotonic tracking (detecting packet loss and replay attacks). The sequence number wraps at 256 via `& 0xFF` and uses 0xFF as a sentinel for "no packet yet received from this peer".

**Enforcement:**
- **Definition:** `SRC/MMULTI.C` line 45: `#define NET_HEADER_SIZE 5   /* [sender][dest][seq][payload_len:2B LE] */`
- **Sequence Tracking:** Per-peer arrays `sender_sequence[MAXPLAYERS]` (what we sent) and `last_seen_sequence[MAXPLAYERS]` (what we last received from each peer).
- **Sentinels:** 14 `net-r15-seqnum` sentinels at 6 sites in `SRC/MMULTI.C` mark cycle 65 implementation.
- **Tests:** +10 tests in `TestNetR15SequenceNumbers` (tests/test_engine_net_hardening_regressions.py).

**Impact:** Zero backward compatibility — 4-byte vs 5-byte header mismatch causes deserialization corruption. Currently acceptable (single-player mode), but will require careful versioning when multiplayer testing begins.

See **[docs/audits/GRIND_LOG.md](docs/audits/GRIND_LOG.md)** § Cycle 65 closures (net-seqnums); **[docs/audits/documentation-curator-r17.md](docs/audits/documentation-curator-r17.md)** § Finding 1: Cycle 65 net-r15-seqnum Header Change.

---

### I. Mandatory Commit Trailer

**Rule:** All commits via Copilot agents must include the following trailer in the commit message:

```
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

**Rationale:** GitHub's commit co-authorship feature attributes work to the Copilot agent identity. This ensures audit trails and contribution graphs are clear when agents make code changes.

**Enforcement:** Documentation-curator and all agent personas use this trailer on git commits. See **[docs/audits/documentation-curator-r17.md](docs/audits/documentation-curator-r17.md)** (verified in commit messages across all audit documents).

---

### J. Audit-Grind v7 Contract

**Rule:** Audit-grind cycle 65+ uses v7 contract enforcing these hard constraints:

- **NO git destructive operations:** No `git stash`, `git reset`, `git rebase`, `git merge`, `git checkout --`, `git clean` without explicit user authorization.
- **NO fake git author identities:** All commits use operator's git config or the Copilot trailer (above).
- **NO out-of-scope file edits:** Agents edit only files owned by their persona; CONTRIBUTING.md is owned by documentation-curator, tests/ may have parallel edits (expected).
- **ONLY documentation edits** for documentation-curator persona (no code changes to source/, SRC/, compat/, tools/, Makefile, CMakeLists.txt, build.mk, .github/).

**Rationale:** Cycle 65 incident: `sec-r17` audit agent violated v6 contract by calling `git stash`, `git commit` with fake author "Audit <audit@test.com>", creating destructive state and murky attribution.

**Enforcement:** v7 contract documented in agent persona files. Violations are flagged in GRIND_LOG human-attention section.

See **[docs/audits/GRIND_LOG.md](docs/audits/GRIND_LOG.md)** § Cycle 65 (Collateral) and Cycle 66 (Human-attention items); **CONTRIBUTING.md** (sibling cycle 70 grind agent is documenting v7 formally — cross-reference but do not duplicate).

---

### Summary

| Invariant | Enforcement Location | Status | Audit Citation |
|-----------|----------------------|--------|-----------------|
| A. CMake LANGUAGE C | CMakeLists.txt:62, 79–80 | ✅ Active | [build-system.md](docs/audits/build-system.md) |
| B. SDL2_VERSION single-source | build.mk:33 + CI grep | ✅ Active | [build-system.md](docs/audits/build-system.md) |
| C. PowerShell ASCII | tools/*.sh verified | ⚠️ Planned (win_build.ps1) | [build-system.md](docs/audits/build-system.md) |
| D. LTO_FLAGS = -flto | Makefile:16, CMakeLists:73 | ✅ Active | [build-system-r18.md](docs/audits/build-system-r18.md) |
| E. gnu89 / c11 split | Makefile:20,131; CMakeLists:79–82 | ✅ Active | [build-system-r15.md](docs/audits/build-system-r15.md) |
| F. check_secrets.sh scoping | tools/check_secrets.sh:^+ patterns | ✅ Active | [build-system-r15.md](docs/audits/build-system-r15.md) |
| G. win_build.ps1 contract | Planned (cycle 65+) | ⏳ Planned | [build-system.md](docs/audits/build-system.md) |
| H. NET_HEADER_SIZE = 5 | SRC/MMULTI.C:45 + 14 sentinels | ✅ Active | [GRIND_LOG.md](docs/audits/GRIND_LOG.md), [documentation-curator-r17.md](docs/audits/documentation-curator-r17.md) |
| I. Copilot commit trailer | All agent commits | ✅ Active | [documentation-curator-r17.md](docs/audits/documentation-curator-r17.md) |
| J. Audit-grind v7 contract | .github/agents/*.agent.md | ✅ Active | [GRIND_LOG.md](docs/audits/GRIND_LOG.md) § Cycle 65–66 |

---

### Summary & Backlog

For the full live backlog with cycle numbers and dependencies, see [docs/audits/SUMMARY.md](docs/audits/SUMMARY.md) and [docs/audits/GRIND_LOG.md](docs/audits/GRIND_LOG.md).

**Current Status (Cycle 39+):**
- **CRITICAL (4):** MAXTILES unification (Stage 2–3), operatesectors bounds, tempshort cap, nextsectorneighborz bounds.
- **HIGH (6):** Makefile race, Windows arch, animatesect bounds, sprite sectnum chain, IPv6 design, packet type coverage.
- **MEDIUM (12+):** Audio state, asset manifests, FLUX caching, error handling, xfail debt (see SUMMARY.md for full list).

All items are cycle-40/41 candidates and tracked via the session todo backlog (see `docs/audits/SUMMARY.md` Index).

---

For detailed audit findings and rationale, see [docs/audits/SUMMARY.md](docs/audits/SUMMARY.md).


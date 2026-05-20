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

For detailed audit findings and rationale, see [docs/audits/SUMMARY.md](docs/audits/SUMMARY.md).


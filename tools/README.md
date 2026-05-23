# tools/ — Duke3D: Neon Noir Asset & Build Pipeline

This directory contains the **asset generation pipeline**, **CI helpers**, **build utilities**, and **format encoders** for Duke Nukem 3D: Neon Noir.

## Overview

The `tools/` directory is organized into several functional domains:

- **Asset Generators**: Produce game-ready textures, audio, maps, and lookup tables from source definitions
- **Format Encoders**: Low-level BUILD engine format writers (GRP, ART, MAP, ANM, VOC, MIDI, DEMO)
- **Validators**: Post-generation checks for artifact integrity and manifest correctness
- **Build Helpers**: Windows bundling, SDL2 setup, Git hooks
- **CI Integration**: Wrapper scripts for GitHub Actions workflows

## Script Index

| Script | Purpose | Entry Point | Key Flags | Outputs | Reference |
|--------|---------|-------------|-----------|---------|-----------|
| **generate_assets.py** | Main asset pipeline: generates textures (AI or procedural), packs GRP | `python3 tools/generate_assets.py` | `--no-ai` (procedural only) | GRP, ART files, generated_assets/ | CONTRIBUTING.md L56-63 |
| **generate_audio.py** | Generate voice lines via GPT Audio 1.5 or silence placeholders | `python3 tools/generate_audio.py` | `--no-ai` (silence stubs) | WAV files, sounds/MANIFEST.json | CONTRIBUTING.md L165-183 |
| **generate_tables.py** | Create TABLES.DAT (sine, radar, brightness, font lookup tables) | `python3 tools/generate_tables.py` | none | TABLES.DAT, tables manifest | Internal (no CLI docs) |
| **palette.py** | Build 256-colour palette and quantisation utilities | Imported by generate_assets.py | none | RGB palette data structure | Generated from source |
| **sound_manifest.py** | Pydantic validation models for SOUND_MANIFEST entries | Imported by generate_audio.py | none | Type validation only | Generated from source |
| **validate_generated_artifacts.py** | Verify all expected artifacts exist and have non-zero size | `python3 tools/validate_generated_artifacts.py` | `--sets {audio,textures,grp,maps,scripts}`, `--no-audio-manifest` | Exit code 0=valid, 1=missing/invalid | CI integration |
| **manifest_verification.py** | Load and verify manifest files with SHA256 checksums | Imported by other tools | none | Checksum validation | Internal utility |
| **map_format.py** | CREATE BUILD engine MAP files (v7 format) with sectors, walls, sprites | Imported by generate_assets.py | none | Procedural level geometry | CONTRIBUTING.md L155-161 |
| **frame_analyzer.py** | Analyse BMP frame captures for AI playtesting validation | Imported by tests | none | Frame histogram, edge detection | perf-r16-frame-analyzer-parametrization |
| **llm_playtest.py** | LLM vision verdict harness for headless BMP captures | `python3 tools/llm_playtest.py` | `--stub`, `--frames-dir`, `--report` | JSON pass/fail report | docs/LLM_PLAYTEST.md |
| **bundle_windows.sh** | Copy SDL2.dll and dependencies for self-contained Windows package (32-bit) | `bash tools/bundle_windows.sh [DEST]` | none | Bundled DLLs in DEST | CI packaging |
| **check_secrets.sh** | Pre-commit hook: scan staged changes for API keys and secrets | `bash tools/check_secrets.sh` | none | Exits 1 if secrets detected | CONTRIBUTING.md L91-103 |
| **install_hooks.sh** | Install Git pre-commit hook (idempotent) | `bash tools/install_hooks.sh` | none | .git/hooks/pre-commit shim | CONTRIBUTING.md L81-84 |
| **get_sdl2_mingw.sh** | Download SDL2 MinGW dev libraries (32-bit) for Windows cross-compilation | `bash tools/get_sdl2_mingw.sh` | none | SDL2-$(VERSION)/ directory | CI setup |
| **release_notes.sh** | Auto-generate release notes from git log between tags | `bash tools/release_notes.sh [TAG]` | none | Markdown changelog | CI/release automation |
| **ci/generate_assets.sh** | CI wrapper for asset generation with environment variable injection | `bash tools/ci/generate_assets.sh [--ai]` | `--ai` (enable AI) | Same as generate_assets.py | CI workflows |

### Format Encoders (Support Libraries)

| Script | Format | Purpose | Used By |
|--------|--------|---------|---------|
| **art_format.py** | ART | BUILD engine tile archive (column-major pixel layout) | generate_assets.py |
| **anm_format.py** | ANM | Deluxe Animate LPF cutscene animations (128B header, palette, frame data) | Planned for future videos |
| **grp_format.py** | GRP | KenSilverman archive: "KenSilverman" magic + file directory + concatenated data | generate_assets.py (final pack) |
| **map_format.py** | MAP | BUILD v7 map format (sectors, walls, sprites, binary geometry) | generate_assets.py |
| **demo_format.py** | DMO | Demo recording format (frame count, skill, player state, input frames) | Potential playback testing |
| **midi_format.py** | MIDI | MIDI format 0 (short melodies/drones as fallback audio) | Backup audio generation |
| **voc_format.py** | VOC | Creative Voice File (8-bit PCM, Creative Labs format, legacy) | Backup audio generation |
| **tables.py** | TABLES.DAT | Binary lookup tables (sine, radar, brightness, fonts) | generate_tables.py |
| **_asset_schemas.py** | JSON Schema | Validation models for asset configs and manifests | All validators |

## Generation Pipeline Domains

### Asset Generation (Textures, Maps, GRP)

**Main entrypoint:** `generate_assets.py --no-ai`

Procedural generation with optional AI texture synthesis. Stages:
1. Generate textures from `TEXTURE_DEFS` (FLUX or procedural fallback)
2. Encode textures to BUILD ART format (8-bit palette-indexed, column-major)
3. Generate maps from `create_level_map()` → BUILD MAP format
4. Build palette from `palette.py`
5. Generate lookup tables via `generate_tables.py`
6. Pack all assets into `DUKE3D.GRP` using `grp_format.py`

**Key configuration:** See CONTRIBUTING.md "What Is Committed (Source of Truth)" L205-228

### Audio Generation (Voice Lines)

**Main entrypoint:** `generate_audio.py --no-ai`

Stages:
1. Iterate `VOICE_LINES` and `SOUND_MANIFEST` in `generate_audio.py`
2. Call GPT Audio 1.5 API or generate silence placeholders
3. Write WAV files to `generated_assets/sounds/`
4. Validate against `sound_manifest.py` Pydantic models
5. Generate `sounds/MANIFEST.json` with SHA256 checksums

**Key configuration:** See CONTRIBUTING.md "Voice catalog" L209-212, L165-183

### Lookup Tables & Manifests

- `generate_tables.py`: Produces `TABLES.DAT` (sine, cosine, radar, brightness, fonts)
- `sound_manifest.py`: Pydantic models for audio manifest (WAV filename, engine sound ID, voice, category)
- `manifest_verification.py`: Checksum validation and schema enforcement

## Schema & Manifest Contracts

### SOUND_MANIFEST Entry Schema

See `tools/sound_manifest.py` class `SoundManifestEntry`:
- `wav: str` — filename (e.g., `"TAUNT01.WAV"`, pattern: `^[A-Z0-9_]+\.WAV$`)
- `engine_sound_id: Optional[str]` — C identifier or None (e.g., `"DUKE_GRUNT"`, maps to `source/SOUNDEFS.H`)
- `voice: str` — "alloy" (raspy), "echo" (electronic), "onyx" (deep)
- `category: str` — "taunt", "pain", "death", "pickup", "weapon", "level_start", "alarm", "ambient"

**Where to modify:** Commit changes to `VOICE_LINES` + `SOUND_MANIFEST` dicts in `generate_audio.py`. Do NOT commit `sounds/MANIFEST.json` (regenerated).

### TEXTURE_DEFS & Procedural Fallback

See `CONTRIBUTING.md` "How to Add New Textures" L135-151:
- Add entry to `TEXTURE_DEFS` in `generate_assets.py` (tile number, W×H, prompt)
- Write procedural fallback function in `PROCEDURAL_MAP`
- Entry commit: Yes (source of truth)
- Generated ART files: No (regenerated on every build)

## CI Integration

The following tools are invoked in `.github/workflows/build.yml`:

| Job | Tool Invocation | Purpose |
|-----|-----------------|---------|
| build-linux / build-macos | `bash tools/ci/generate_assets.sh --ai` | Generate textures (AI) + GRP |
| build-windows | `bash tools/get_sdl2_mingw.sh` | Download SDL2 MinGW dev libs |
| build-windows | `bash tools/bundle_windows.sh release-win` | Bundle DLLs for release package |
| all jobs | `python3 tools/validate_generated_artifacts.py --sets textures grp maps scripts` | Verify artifact integrity |
| build-linux-ci (no-api) | `python3 tools/generate_assets.py --no-ai` | Procedural-only fallback test |

**Critical invariant:** `SDL2_VERSION` is single-sourced from `build.mk` line 1. Scripts `get_sdl2_mingw.sh` and `bundle_windows.sh` read this value; never hardcode version numbers in tools.

## Memory Invariants & Constraints

### B. SDL2_VERSION Single Source

The SDL2 version is defined once in `build.mk`:
```make
SDL2_VERSION = 2.30.9
```

Scripts that depend on this version must read it dynamically:
- `tools/get_sdl2_mingw.sh` — reads via `grep '^SDL2_VERSION' "$ROOT_DIR/build.mk"`
- `tools/bundle_windows.sh` — reads via same pattern

**Do NOT hardcode version numbers in tools.**

### F. check_secrets.sh Coverage & Scoping

Pre-commit hook coverage is **file-type agnostic**:
- Scans ALL staged files: `.env`, `.yml`, `.yaml`, `.json`, `.bat`, `.sh`, `.py`, `.js`, `.ts`, `.go`, `.java`, `.c`, `.h`, and others
- Exclusions: `tests/test_check_secrets*` (fixtures), `tools/check_secrets*` (scanner helpers — glob pattern)
- Detects: high-risk patterns (API_KEY=, sk-, ghp_, xoxb-, base64-like strings)

**Self-Exclusion Glob Pattern (`tools/check_secrets*`):**
Scanner helper scripts are excluded via a glob to prevent self-triggering. Example: `check_secrets_ci.sh` contains pattern strings (e.g., "BEGIN PRIVATE KEY") used as test inputs, which would falsely match the scanner. When adding new scanner helpers (e.g., `check_secrets_*.sh`), ensure they match this pattern so the pre-commit hook and CI exclude them automatically. Update `.githooks/pre-commit` L12 and `tools/check_secrets.sh` L23 if creating new helper names that don't follow `check_secrets*` pattern.

**See:** `tools/check_secrets.sh` L23 (git diff exclusion), `tools/check_secrets_ci.sh` L28 (CI exclusion)

### C. PowerShell ASCII-Only

Windows bundling scripts (`bundle_windows.sh`, etc.) must use POSIX shell syntax and avoid non-ASCII characters to ensure cross-platform compatibility.

## Development Workflow

### Regenerating Assets Locally

Without API credentials (recommended for contributors):
```bash
python3 tools/generate_audio.py --no-ai
python3 tools/generate_assets.py --no-ai
# Shorthand:
make assets
```

With credentials in `.env`:
```bash
python3 tools/generate_audio.py
python3 tools/generate_assets.py
```

### Modifying Asset Definitions

1. **New texture:** Edit `TEXTURE_DEFS` + `PROCEDURAL_MAP` in `tools/generate_assets.py` → commit
2. **New voice line:** Edit `VOICE_LINES` in `tools/generate_audio.py` → commit
3. **New map:** Write `create_*_map()` function in `tools/map_format.py`, register in `generate_assets.py` → commit
4. **Regenerate:** Run `make assets`, verify in-game
5. **Do NOT commit:** Generated files (WAV, ART, GRP, MAP binaries)

### Adding New Artifacts

Update `tools/validate_generated_artifacts.py` `ARTIFACT_SETS` dict to register new artifact types. Validators will check existence and non-zero size in CI.

---

**docs-r17-tools-readme-index:COMPLETE**

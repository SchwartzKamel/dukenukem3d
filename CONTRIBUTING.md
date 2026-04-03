# Contributing to Duke Nukem 3D (Modern Port)

Welcome! We're glad you're interested in contributing. This project is an open,
community-driven effort to bring Duke Nukem 3D to modern platforms using SDL2
and GCC. Contributions of all kinds — code, assets, docs, bug reports — are
appreciated.

## Setting Up the Development Environment

### Prerequisites

- **GCC** (or Clang) with C11 support
- **SDL2** development libraries (`libsdl2-dev` on Debian/Ubuntu)
- **Python 3.8+** (for the asset pipeline)
- **GNU Make**
- **Git**

On Debian/Ubuntu:

```bash
sudo apt install build-essential libsdl2-dev python3 python3-pip git
```

### Clone and Build

```bash
git clone <repo-url> dukenukem3d
cd dukenukem3d
make clean && make
```

The build produces the `duke3d` executable in the project root.

### Run the Asset Pipeline

The asset pipeline generates all required game assets (textures, palettes,
tables, maps) and packs them into `DUKE3D.GRP`:

```bash
python3 tools/generate_assets.py --no-ai   # procedural textures only
make assets                                  # shorthand via Makefile
```

If you have FLUX API credentials in a `.env` file, omit `--no-ai` to use
AI-generated textures with procedural fallbacks.

## Code Style

This project contains code from several eras. Please follow the conventions of
the area you are working in:

### Original Engine Code (`SRC/`, `source/`)

- **K&R C from 1996** — compile with `-std=gnu89`
- Do **not** reformat or modernize this code
- Keep changes surgical and minimal; don't rewrite original logic unnecessarily
- Match the existing indentation and brace style

### Compatibility Layer (`compat/`)

- **Modern C11** (`-std=c11`)
- Clean, well-structured code is expected here
- Use `int32_t` / fixed-width types for struct fields that interact with the
  original engine

### Tools (`tools/`)

- **Python 3.8+**
- Follow PEP 8 where reasonable
- Keep scripts self-contained with minimal dependencies

### General Rule

Keep changes surgical. If you're fixing a bug in the original engine code,
fix the bug — don't rewrite the surrounding function.

## How to Add New Textures

1. **Add an entry to `TEXTURE_DEFS`** in `tools/generate_assets.py` with the
   tile number, dimensions, and a description prompt.

2. **Write a procedural fallback function** that generates the texture as raw
   pixel data (8-bit palette indices) when AI generation is unavailable.

3. **Map it in `PROCEDURAL_MAP`** so the pipeline knows which fallback function
   to call for your texture.

4. **Test it:**
   ```bash
   make assets
   ./duke3d
   ```
   Verify the texture appears correctly in-game.

## How to Add New Maps

1. **Create a new function** in `tools/map_format.py` that builds your level
   geometry (sectors, walls, sprites) using the map data structures.

2. **Register it in `tools/generate_assets.py`** so the map gets written and
   added to the GRP archive.

3. Test by running the asset pipeline and loading the map in-game.

## How to Add New Audio

1. **Add an entry to `VOICE_LINES`** in `tools/generate_audio.py` with the
   filename, text prompt, and voice selection.

2. **Choose a voice** for the line:
   - `"alloy"` — gruff, raspy (best for mercenary taunts and combat lines)
   - `"echo"` — electronic, synthetic (best for HUD notifications and pickups)
   - `"onyx"` — deep, authoritative (best for level announcements and alarms)

3. **Run the audio generator:**
   ```bash
   python3 tools/generate_audio.py
   ```

4. **Re-pack the GRP** so the new audio is included in the game archive:
   ```bash
   python3 tools/generate_assets.py --no-ai
   ```

5. Verify the new WAV file appears in `generated_assets/sounds/`.

## Pull Request Process

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b my-feature
   ```

2. **Make your changes** with clear, descriptive commits.

3. **Verify the build passes:**
   ```bash
   make clean && make
   ```

4. **Verify the asset pipeline works:**
   ```bash
   python3 tools/generate_assets.py --no-ai
   ```

5. **Open a Pull Request** against the main branch. In the description:
   - Explain **what** you changed
   - Explain **why** (bug fix, new feature, refactor)
   - Include screenshots if the change is visual

We'll review your PR and may ask for revisions. Don't be discouraged — we want
to help you get it merged.

## Areas That Need Help

If you're looking for something to work on, these are high-impact areas:

- **Runtime audio playback** — integrate SDL2_mixer to play the generated WAV files in-game
- **More maps and levels** — expand beyond the test level
- **Full tile coverage for DEFS.CON** — many tile slots are still empty
- **Multiplayer networking** — the net code is currently stubbed out
- **Windows native build** — a proper MSVC/MinGW build, not just cross-compile
- **Better procedural textures** — improve the fallback texture generators
- **HUD rendering** — weapon display, status bar, health/ammo readouts

Pick any of these, or propose your own improvement. We're happy to discuss
ideas in Issues before you start coding.

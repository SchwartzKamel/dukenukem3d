<div align="center">

# ⚡ DUKE3D: NEON NOIR ⚡

### *A modernized port of Duke Nukem 3D for the 21st century*

[![Build](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square&logo=gnu-bash)](https://github.com/SchwartzKamel/dukenukem3d)
[![License: GPL-2.0](https://img.shields.io/badge/license-GPL--2.0-blue?style=flat-square)](GNU.TXT)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux%20x86--64-orange?style=flat-square&logo=linux&logoColor=white)](https://github.com/SchwartzKamel/dukenukem3d)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS%20x86--64-lightgrey?style=flat-square&logo=apple&logoColor=white)](https://github.com/SchwartzKamel/dukenukem3d)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%20x64-blue?style=flat-square&logo=windows&logoColor=white)](https://github.com/SchwartzKamel/dukenukem3d)

**The King is back. Rebuilt from the original 1996 source. Dripping in neon.**

</div>

---

## 🔥 About

This is a **modernized, fully-compilable port** of the original *Duke Nukem 3D* source code — the legendary 1996 FPS built on **Ken Silverman's BUILD engine**. The original source was released under GPL-2.0 by **3D Realms** in 2003. This port drags it kicking and screaming into the modern era:

- 🛠️ **Compiles with modern GCC** (11+) — no Watcom compiler required
- 🐧 **Runs natively on Linux x86-64**, cross-compiles for **Windows x64**
- 🖥️ **SDL2** replaces DOS VESA/VGA for graphics, input, and timing
- 🎨 **AI-generated cyberpunk textures** via [FLUX.2-pro](https://blackforestlabs.ai/) by Black Forest Labs, with procedural fallback
- 🔊 **AI-generated voice lines & SFX** via [GPT Audio 1.5](https://platform.openai.com/) on Azure OpenAI
- 🏗️ **Complete asset pipeline** — generates everything needed to play without any copyrighted content

### 🌆 The Theme: Neon Noir Cyberpunk

Forget the blonde babes and alien strip clubs. This build reimagines Duke's world as a **dark industrial nightmare** soaked in neon:

> Dark steel corridors. Glowing circuit traces pulsing with cyan light. Toxic waste pools casting sickly green shadows. Holographic terminals flickering in abandoned server rooms. The rain never stops and the neon never sleeps.

Every texture, every sprite, every pixel — generated fresh with a unified **Neon Noir Cyberpunk** aesthetic.

---

## 📸 Screenshots

> *Screenshots coming soon — build it and see for yourself.*
>
> Spoiler: it glows.

---

## 🚀 Quick Start

```bash
# Build it
make

# Generate audio (AI voice lines + sound effects)
python3 tools/generate_audio.py

# Generate visual assets + pack everything into GRP
make assets

# OR generate with AI textures (requires .env with FLUX credentials)
python3 tools/generate_assets.py

# Run it
# Only needed if SDL2 is installed via Homebrew:
#   Linux:  export LD_LIBRARY_PATH=$(brew --prefix)/lib:$LD_LIBRARY_PATH
#   macOS:  export DYLD_LIBRARY_PATH=$(brew --prefix)/lib:$DYLD_LIBRARY_PATH
./duke3d
```

That's it. Build, generate, and the King rides again.

---

## 🛡️ Development Setup

After cloning, **install git hooks to prevent accidental secret commits**:

```bash
bash tools/install_hooks.sh
```

This runs `tools/check_secrets.sh` on every commit to catch API keys and credentials before they leak. See [CONTRIBUTING.md § Pre-Commit Hook Setup](CONTRIBUTING.md#pre-commit-hook-setup) for details.

---

## 📈 Performance Notes

Asset and audio generation are parallelized for fast iterative builds:

- `tools/generate_assets.py` uses `multiprocessing.Pool` to parallelize
  procedural texture, sprite, and font-tile rendering (~6–7× speedup on
  modern CPUs).
- `tools/generate_audio.py` uses a `ThreadPoolExecutor` + `asyncio` +
  `aiohttp` pipeline for concurrent voice synthesis (~4–6× speedup when
  hitting an external TTS endpoint).

In `--no-ai` mode both pipelines remain deterministic (silence WAVs +
fixed epoch timestamps), so the parallelism does not affect output
reproducibility.

---

## 📋 Prerequisites

### Linux

| Requirement | Install |
|---|---|
| GCC 11+ | `sudo apt install build-essential` |
| SDL2 dev libs | `sudo apt install libsdl2-dev` |
| Python 3.8+ | Usually pre-installed |
| Pillow | `pip install Pillow` |
| requests *(for AI textures)* | `pip install requests` |

### Windows (Cross-compilation from Linux)

| Requirement | Install |
|---|---|
| MinGW-w64 | `sudo apt install gcc-mingw-w64-x86-64` |
| SDL2 for MinGW | SDL2 development libraries (MinGW variant) |

### Windows (Native Build)

| Requirement | Install |
|---|---|
| Visual Studio Build Tools **or** MinGW-w64 | [VS Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) or [MinGW-w64](https://www.mingw-w64.org/) |
| SDL2 development libraries | [SDL2 releases](https://github.com/libsdl-org/SDL/releases) — get the `-VC.zip` for MSVC or `-mingw.zip` for MinGW |
| CMake *(optional)* | [cmake.org](https://cmake.org/download/) or via `winget install cmake` |

### macOS

| Requirement | Install |
|---|---|
| Xcode Command Line Tools | `xcode-select --install` |
| SDL2 | `brew install sdl2` |
| Python 3.8+ | Usually pre-installed; update via `brew install python@3.11` if needed |
| CMake | `brew install cmake` |

---

## 🔨 Building

### Linux (default)

```bash
make            # builds ./duke3d
```

### Windows x64 (cross-compile from Linux)

```bash
make windows    # builds ./duke3d.exe
```

### Windows Native — Option A: CMake (Recommended)

The cleanest approach for Windows. Works with Visual Studio, MinGW, or any CMake generator.

```cmd
REM Install SDL2 via vcpkg (one-time setup)
vcpkg install sdl2:x64-windows

REM Build with CMake
mkdir build && cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=[vcpkg-root]\scripts\buildsystems\vcpkg.cmake
cmake --build . --config Release
```

Or open the project directly in **Visual Studio 2019+** (File → Open → CMake) — it will auto-detect `CMakeLists.txt`.

### Windows Native — Option B: Visual Studio Developer Command Prompt

Open a **Developer Command Prompt for VS** (or **x64 Native Tools Command Prompt**), set `SDL2_DIR`, and run:

```cmd
set SDL2_DIR=C:\SDL2
build_windows.bat msvc
```

### Windows Native — Option C: MinGW on Windows

```cmd
set SDL2_DIR=C:\SDL2
build_windows.bat mingw
```

### macOS

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j $(sysctl -n hw.ncpu)
```

The binary will be in `build/duke3d`. *(Source: [.github/workflows/build.yml](https://github.com/SchwartzKamel/dukenukem3d/blob/master/.github/workflows/build.yml) — build-macos job)*

### Both platforms (Linux)

```bash
make all-platforms
```

### Clean

```bash
make clean
```

---

## 🎨 Asset Generation

The original Duke3D assets are **copyrighted by 3D Realms / Gearbox Software** and are **not included**. Instead, this project ships a complete asset generation pipeline that creates everything from scratch.

### How It Works

The pipeline generates:
- **20 unique wall/floor/ceiling textures** in the Neon Noir Cyberpunk theme
- **10 item sprites** (weapons, health, ammo, etc.)
- **Bitmap font** for the HUD
- All packed into the correct binary formats: `TILES000.ART`, `PALETTE.DAT`, `TABLES.DAT`, `E1L1.MAP` → bundled into `DUKE3D.GRP`

Two generation modes are available:

| Mode | Command | Description |
|---|---|---|
| **AI + Fallback** | `python3 tools/generate_assets.py` | Uses [FLUX.2-pro](https://blackforestlabs.ai/) by Black Forest Labs (hosted on Azure) for textures, falls back to procedural if API is unavailable |
| **Procedural Only** | `python3 tools/generate_assets.py --no-ai` | Pure algorithmic generation, no API needed |
| **Procedural Only** | `make assets` | Same as `--no-ai` |

### Audio Assets

AI-generated using GPT Audio 1.5 on Azure OpenAI. Generates 21 WAV files:

| Category | Files | Description |
|----------|-------|-------------|
| Taunts | TAUNT01-05.WAV | Gruff cyberpunk mercenary one-liners |
| Pain | PAIN01-03.WAV | Combat damage grunts |
| Death | DEATH01-02.WAV | Death screams and last words |
| Pickups | PICKUP01-04.WAV | Electronic HUD notifications |
| Weapons | WEAPON01-03.WAV | Weapon system announcements |
| Level | LEVEL01-02.WAV | Level start lines |
| Environment | ALARM01.WAV, COMP01.WAV | Facility announcements |

```bash
# Generate with AI
python3 tools/generate_audio.py

# Generate silence placeholders (no API needed)
python3 tools/generate_audio.py --no-ai
```

#### Setup for Audio Generation

```bash
# Add to .env:
AUDIO_ENDPOINT=<your-azure-openai-endpoint>
AUDIO_MODEL=gpt-audio-1.5
AUDIO_API_KEY=<your-api-key>
```

### Setup for AI Textures

Create a `.env` file in the project root:

```bash
FLUX_ENDPOINT=<your-flux-endpoint>
FLUX_MODEL=FLUX.2-pro
FLUX_API_KEY=<your-api-key>
```

### 🖼️ Texture Atlas

All 20 textures follow the Neon Noir Cyberpunk theme:

| Tile | Name | Description |
|------|------|-------------|
| 0 | Dark Steel Panel | Brushed steel with rivets |
| 1 | Corroded Floor | Industrial metal grating with rust |
| 2 | Pipe Ceiling | Exposed conduits and pipes |
| 3 | Neon Circuit Wall | Glowing cyan circuit traces |
| 4 | Hazard Stripes | Yellow-black warning wall |
| 5 | Hex Tile Floor | Dark hexagonal metal tiles |
| 6 | Neon Cityscape | Cyberpunk night skyline |
| 7 | Blast Door | Heavy hydraulic door |
| 8 | Toxic Waste | Glowing green radioactive pool |
| 9 | Holo Terminal | Holographic computer display |
| 10 | Bunker Wall | Cracked concrete with graffiti |
| 11 | Neon Sign Wall | Flickering pink/cyan signs |
| 12 | Grated Catwalk | See-through metal catwalk |
| 13 | Bio-Growth | Bioluminescent fungal wall |
| 14 | Rust Metal | Heavily corroded panels |
| 15 | Magma Vent | Glowing lava through rock |
| 16 | Cryo Chamber | Frosted ice-blue walls |
| 17 | Sandblasted Plate | Scratched gunmetal |
| 18 | Marble Command | Dark marble with gold inlay |
| 19 | Server Rack | Blinking LED data center |

---

## 📁 Project Structure

```
├── SRC/                  # BUILD engine (ENGINE.C, CACHE1D.C, MMULTI.C, BUILD.H)
├── source/               # Duke3D game code (GAME.C, ACTORS.C, PLAYER.C, etc.)
├── compat/               # Modern compatibility layer
│   ├── compat.h          # DOS → POSIX/Win32/MSVC shim
│   ├── pragmas_gcc.h     # 174 inline C replacements for Watcom ASM
│   ├── sdl_driver.c/h    # SDL2 video/input/timer
│   ├── audio_stub.c/h    # Stub audio/input system
│   └── mact_stub.c       # Config parser, utility stubs
├── tools/                # Asset generation pipeline
│   ├── generate_assets.py # Main orchestrator (textures + GRP packing)
│   ├── generate_audio.py # Audio generation (voice lines + SFX)
│   ├── check_secrets.sh  # Pre-commit hook for API key hygiene
│   ├── art_format.py     # BUILD ART file format
│   ├── grp_format.py     # GRP archive packer
│   ├── palette.py        # 256-color palette & quantizer
│   ├── map_format.py     # MAP v7 format generator
│   └── tables.py         # Sine/lookup table generator
├── generated_assets/
│   └── sounds/           # Generated WAV files (TAUNT01.WAV, etc.)
├── testdata/             # Game scripts (GAME.CON, DEFS.CON, etc.)
├── audiolib/             # Original DOS audio drivers (not used)
├── .github/
│   └── agents/           # 10 specialized Copilot custom agent personas
├── docs/
│   ├── ARCHITECTURE.md   # Technical deep-dive (engine, assets, compat layer)
│   ├── audits/           # Codebase audit reports + SUMMARY.md
│   └── archive/          # Legacy reference code (uncompiled, historical)
├── .env.example          # Template for API credentials (.env is gitignored)
├── .githooks/            # Pre-commit secret-scan hook
├── CMakeLists.txt        # Cross-platform CMake build (Windows/Linux/macOS)
├── build_windows.bat     # Windows native build (MSVC or MinGW)
├── Makefile              # Linux + Windows cross-compile
└── .env                  # FLUX API credentials (gitignored, not tracked)
```

---

## 🔧 Technical Details — What We Changed

Porting a 1996 DOS game to modern Linux isn't for the faint of heart. Here's what it took:

| Area | What Changed |
|---|---|
| **Inline Assembly** | Replaced ~1,900 lines of Watcom `#pragma aux` inline assembly with **174 portable C functions** |
| **Rendering** | Replaced x86 ASM rendering (`A.ASM`) with C implementations in `ENGINE.C` |
| **Graphics** | Replaced VESA/VGA with **SDL2** — 8-bit paletted surfaces → ARGB32 conversion |
| **Audio** | Stubbed DOS audio drivers (FX/MUSIC) — silent but functional |
| **Networking** | Stubbed DOS networking (`MMULTI`) — single-player only |
| **64-bit Compat** | Packed structs use `int32_t` instead of `long`; fixed `animateptr` pointer corruption |
| **Struct Safety** | Compile-time struct size assertions for binary format compatibility |
| **C Standards** | K&R C compiled with `-std=gnu89`, compat layer with `-std=gnu11` |

<!-- docs-feature-summary-update: cycle 50 -->

## 📝 Recent Improvements (Cycles 41–49)

| Improvement | Purpose | Cycle |
|---|---|---|
| **Property-Based Testing** | Hypothesis/QuickCheck-style tests for deterministic playback, engine bounds, and asset generation edge cases | 41+ |
| **Multiplayer Regression Harness** | `tests/test_engine_net_hardening_regressions.py` — automated packet type bounds matrix coverage (15 active types, 2 HIGH gaps closed cycles 48–49) | 48 |
| **SE40 Performance Optimization + Cycle 42 Draw Guards** | Fixed `SE40_Draw` sprite sectnum validation; eliminated unnecessary allocache thrashing — cold render loop now **22× faster** (0.2s → 0.009s) | 41–42 |
| **Atomic Manifest Write** | Eliminated ThreadPool/asyncio race in `tools/generate_audio.py` — manifest now serialized per-entry + checksummed (prevents corruption on interruption) | 42, 46 |
| **Parallel Testing with xdist + filelock** | `pytest -n auto` now safe via per-worker filelock coordination; 37.5% wallclock speedup (22.98s → 14.76s) | 45–46 |
| **Header Dependency Tracking** | Makefile `-MMD -MP` + `-include *.d` — header touch now triggers rebuild (prevents stale binaries) | 46 |
| **Manifest SHA256 Checksums** | Per-entry + top-level checksum in `tools/generate_tables.py` and `tools/generate_audio.py` — mutations now detectable | 46 |
| **MAXTILES Header Unification + Abort Guard** | Cycles 41–42 unified conflicting `SRC/BUILD.H` (9216) and `source/BUILD.H` (6144) to 6144; runtime abort guard in `compat/maxtiles_guard.c` prevents future divergence | 41–42 |

See [docs/ARCHITECTURE.md § Recent Improvements](#recent-improvements) for technical depth and [docs/audits/GRIND_LOG.md](docs/audits/GRIND_LOG.md) for cycle-by-cycle details.

---

## ⚠️ Known Limitations

- **No runtime audio playback** — AI-generated WAV files are produced but sound functions are still stubbed at runtime (Duke's one-liners exist as files now!)
- **No multiplayer** — networking is stubbed for single-player only
- **Incomplete tile coverage** — game scripts (`GAME.CON`/`DEFS.CON`) reference many tile numbers not yet generated
- **Windows build** — requires SDL2 development libraries; see build instructions above

---

## 🗺️ Roadmap

- [x] 🔊 AI-generated audio assets via GPT Audio 1.5 (voice lines + SFX)
- [ ] 🔊 Runtime audio playback via SDL2_mixer
- [ ] 🗺️ More map levels
- [ ] 🎨 Full tile set covering all `DEFS.CON` references
- [ ] 🌐 Multiplayer over TCP/IP
- [ ] 🏗️ Map editor integration

---

## 🤖 Copilot Custom Agents

This project uses **10 specialized Copilot agent personas** — each responsible for a specific domain — to maintain code quality, documentation accuracy, and build reliability. Each persona owns its area and acts as the authority on decisions within that scope.

| Agent | Scope | Location |
|-------|-------|----------|
| **Engine Porter** | SRC/, source/ (BUILD engine & game code) | `.github/agents/engine-porter.agent.md` |
| **Compat Layer** | compat/ (SDL2 + DOS shims) | `.github/agents/compat-layer.agent.md` |
| **Asset Pipeline** | tools/ (texture/map/audio generation) | `.github/agents/asset-pipeline.agent.md` |
| **Audio Engineer** | generate_audio.py, audio systems | `.github/agents/audio-engineer.agent.md` |
| **Build System** | Makefile, CMakeLists.txt, CI/CD | `.github/agents/build-system.agent.md` |
| **Test Engineer** | tests/, pytest suite, test coverage | `.github/agents/test-engineer.agent.md` |
| **Documentation Curator** | README, CONTRIBUTING, ARCHITECTURE, audits | `.github/agents/documentation-curator.agent.md` |
| **Security & Secrets** | .env, credentials, secret scanning | `.github/agents/security-and-secrets.agent.md` |
| **Network & Multiplayer** | MMULTI.C, TCP/IP, netplay (roadmap) | `.github/agents/network-multiplayer.agent.md` |
| **Performance Profiler** | Benchmarking, optimization, profiling | `.github/agents/performance-profiler.agent.md` |

When contributing code that touches a domain, work with the relevant persona. See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to collaborate with agents during code review.

Audit reports for each agent are stored in [docs/audits/](docs/audits/) with a cross-cutting [SUMMARY.md](docs/audits/SUMMARY.md).

---

## 📜 License

| Component | License |
|---|---|
| Source code | **GPL-2.0** (see [GNU.TXT](GNU.TXT)) |
| Original assets | Copyright © 3D Realms / Gearbox Software (**NOT included**) |
| Generated assets | Created by AI / procedural generation, included in builds |
| BUILD engine | Created by Ken Silverman |

---

## 🏆 Credits

- **[3D Realms](https://3drealms.com/)** — Original Duke Nukem 3D source code (2003 GPL release)
- **Ken Silverman** — The BUILD engine that started it all
- **Jim Dose** — Audio library (`audiolib`)
- **[Black Forest Labs](https://blackforestlabs.ai/)** — FLUX.2-pro image generation model (hosted on Azure)
- **[OpenAI](https://platform.openai.com/)** — GPT Audio 1.5 voice and sound effect generation (hosted on Azure)
- **This port** — Modern GCC/SDL2 port with AI-powered asset generation

---

## 📄 Original README

The original `README.TXT` from 3D Realms' 2003 source release is preserved in this repository for historical reference.

---

<div align="center">

*"It's time to kick ass and chew bubblegum... and I'm all outta gum."*

**Hail to the King, baby. 👑**

</div>

<div align="center">

# ⚡ DUKE3D: NEON NOIR ⚡

### *A modernized port of Duke Nukem 3D for the 21st century*

[![Build](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square&logo=gnu-bash)](https://github.com/SchwartzKamel/dukenukem3d)
[![License: GPL-2.0](https://img.shields.io/badge/license-GPL--2.0-blue?style=flat-square)](GNU.TXT)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux%20x86--64-orange?style=flat-square&logo=linux&logoColor=white)](https://github.com/SchwartzKamel/dukenukem3d)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%20x64-blue?style=flat-square&logo=windows&logoColor=white)](https://github.com/SchwartzKamel/dukenukem3d)

**The King is back. Rebuilt from the original 1996 source. Dripping in neon.**

</div>

---

## 🔥 About

This is a **modernized, fully-compilable port** of the original *Duke Nukem 3D* source code — the legendary 1996 FPS built on **Ken Silverman's BUILD engine**. The original source was released under GPL-2.0 by **3D Realms** in 2003. This port drags it kicking and screaming into the modern era:

- 🛠️ **Compiles with modern GCC** (11+) — no Watcom compiler required
- 🐧 **Runs natively on Linux x86-64**, cross-compiles for **Windows x64**
- 🖥️ **SDL2** replaces DOS VESA/VGA for graphics, input, and timing
- 🎨 **AI-generated cyberpunk textures** via [FLUX.2-pro](https://bfl.ai/models/flux-2-pro) by Black Forest Labs, with procedural fallback
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
export LD_LIBRARY_PATH=/home/linuxbrew/.linuxbrew/lib:$LD_LIBRARY_PATH
./duke3d
```

That's it. Build, generate, and the King rides again.

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
| **AI + Fallback** | `python3 tools/generate_assets.py` | Uses [FLUX.2-pro](https://bfl.ai/models/flux-2-pro) (Black Forest Labs, hosted on Azure) for textures, falls back to procedural if API is unavailable |
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
| Environment | ALARM01.WAV, COMPUTER01.WAV | Facility announcements |

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
│   ├── art_format.py     # BUILD ART file format
│   ├── grp_format.py     # GRP archive packer
│   ├── palette.py        # 256-color palette & quantizer
│   ├── map_format.py     # MAP v7 format generator
│   └── tables.py         # Sine/lookup table generator
├── generated_assets/
│   └── sounds/           # Generated WAV files (TAUNT01.WAV, etc.)
├── testdata/             # Game scripts (GAME.CON, DEFS.CON, etc.)
├── audiolib/             # Original DOS audio drivers (not used)
├── CMakeLists.txt        # Cross-platform CMake build (Windows/Linux/macOS)
├── build_windows.bat     # Windows native build (MSVC or MinGW)
├── Makefile              # Linux + Windows cross-compile
└── .env                  # FLUX API credentials (gitignored)
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
- **[Black Forest Labs](https://bfl.ai/)** — FLUX.2-pro image generation model (hosted on Azure)
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

# Copilot Instructions — Duke3D: Neon Noir

A modernized port of the original 1996 Duke Nukem 3D source on Ken Silverman's
BUILD engine. This file captures the non-obvious things you need to know to
work effectively here. See `docs/ARCHITECTURE.md` for the engine deep-dive and
`CONTRIBUTING.md` for the human-facing version.

## Code is split into three tiers — treat them differently

| Path | Era / Style | Std | Rule |
|---|---|---|---|
| `SRC/` (BUILD engine: `ENGINE.C`, `CACHE1D.C`, `MMULTI.C`) | 1996 K&R | `-std=gnu89` | **Do not reformat or modernize.** Keep edits surgical. |
| `source/` (Duke3D game: `GAME.C`, `ACTORS.C`, …) | 1996 K&R | `-std=gnu89` | Same rule — match existing brace/indent style. |
| `compat/` (`sdl_driver.c`, `audio_stub.c`, `mact_stub.c`, `hud.c`, `compat.h`) | Modern | `-std=gnu11` (`/std:c11` MSVC) | Modern C is expected here; use `int32_t`/fixed-width types when interacting with engine globals. |
| `tools/` | Python 3.8+ | PEP 8 where reasonable | Asset pipeline. Keep deps minimal (only `Pillow`, `requests`, `pytest`). |

**File-extension trap**: legacy files use uppercase `.C` but are **C, not C++**.
The Makefile compiles them with `-x c`; `build_windows.bat` MSVC uses `/Tc`;
CMake uses `set_source_files_properties(... LANGUAGE C)`. If you add a new
legacy-style file with `.C`, replicate this. New modern code goes in `compat/`
with lowercase `.c`.

`ENGINE.C` is special — it's compiled with `-ffast-math -DENGINE` (see
`ENGINE_EXTRA_FLAGS` in `build.mk`). Don't add `-ffast-math` globally; the
fixed-point math elsewhere relies on standard FP semantics.

## `build.mk` is the single source of truth for source lists

`build.mk` defines `ENGINE_SRCS`, `GAME_SRCS`, `COMPAT_SRCS`, `COMMON_DEFINES`,
`LEGACY_STD`, `COMPAT_STD`, and `SDL2_VERSION`. It is included by `Makefile`
**and** mirrored by `CMakeLists.txt` and `build_windows.bat`. **When you add
or rename a source file, update all three** — there is currently no
auto-generation. The pinned `SDL2_VERSION = 2.30.9` is also read by CI scripts.

## Build commands

| Target | Command | Output |
|---|---|---|
| Linux native (default) | `make` | `./duke3d` |
| Windows cross-compile from Linux (32-bit) | `make windows` | `./duke3d.exe` (uses `i686-w64-mingw32-gcc`) |
| Windows native MSVC | `build_windows.bat msvc` (in VS Dev Cmd, with `SDL2_DIR` set) | `duke3d.exe` |
| Windows native MinGW | `build_windows.bat mingw` (with `SDL2_DIR` set) | `duke3d.exe` |
| CMake (any platform) | `cmake -B build && cmake --build build` | `build/duke3d[.exe]` |
| Debug build | `make debug` (or `BUILD_TYPE=debug make`) | unstripped, `-O0 -g -DDEBUG` |
| Both Linux + Windows | `make all-platforms` | both binaries |
| Diagnostics | `make info` | prints SDL2 paths, MinGW path, source counts |

`make windows` is **32-bit** on purpose — the BUILD engine stores pointers in
`long`, which only matches `sizeof(void*)` on ILP32. Don't switch it to 64-bit
without a porting pass.

## Asset pipeline (the game won't run without it)

The original copyrighted assets are **not** in the repo. The Python pipeline
generates a complete `DUKE3D.GRP` from scratch:

```bash
python3 tools/generate_assets.py --no-ai   # procedural (no API, deterministic)
make assets                                # alias for the above
python3 tools/generate_assets.py           # AI textures via FLUX (needs .env)
python3 tools/generate_audio.py [--no-ai]  # voice lines + SFX via Azure GPT Audio
```

To add textures/maps/audio, follow the recipe in `CONTRIBUTING.md` —
`generate_assets.py` is driven by `TEXTURE_DEFS` + `PROCEDURAL_MAP` tables,
and `generate_audio.py` by `VOICE_LINES`.

`.env` keys when using AI generation:
`FLUX_ENDPOINT`, `FLUX_MODEL`, `FLUX_API_KEY`,
`AUDIO_ENDPOINT`, `AUDIO_MODEL`, `AUDIO_API_KEY`.

## Tests

The Python test suite exercises the asset pipeline (file-format encoders,
palette/table generators, GRP packing) and a headless-game smoke test.

```bash
python3 -m pytest tests/ -v --tb=short              # full suite
python3 -m pytest tests/test_palette.py -v          # one file
python3 -m pytest tests/test_palette.py::test_palette_size -v   # one test
python3 -m pytest tests/ -k "asset or grp or map"   # CI's "test-assets" subset
python3 -m pytest tests/ -m playtest                # visual playtest only (slow)
```

The `playtest` marker (declared in `pytest.ini`) launches the built game
headless to capture and analyze frames. It needs:

| Env var | Effect |
|---|---|
| `DUKE3D_HEADLESS=1` | SDL dummy driver, no window |
| `DUKE3D_SKIP_LOGO=1` | bypass intro logo (see `source/GAME.C`) |
| `DUKE3D_FRAME_LIMIT=N` | exit after N rendered frames |
| `DUKE3D_CAPTURE_INTERVAL=N` | dump a `.bmp` every N frames to `captures/` |
| `SDL_VIDEODRIVER=dummy` | required alongside `DUKE3D_HEADLESS` |

The capture/headless plumbing lives in `compat/sdl_driver.c`.

## CI shape (`.github/workflows/build.yml`)

Five jobs run on each push/PR — match their commands locally before opening
a PR:

1. **build-linux** — `make` + pytest + `generate_assets.py --no-ai`
2. **build-windows** — `make windows` (MinGW cross from Ubuntu) + DLL audit
3. **test-assets** — pytest filtered to `asset|palette|art|grp|map|table`
4. **test-windows-native** — `cmake -A Win32` + MSVC on `windows-latest`
5. **playtest** — headless game run + frame analysis (non-blocking)

`tools/get_sdl2_mingw.sh` and `tools/bundle_windows.sh` are CI helpers — the
Windows release bundle audits `objdump -p` output to verify every required
non-system DLL is shipped next to `duke3d.exe`.

## Pull-request expectations

Before pushing, the `CONTRIBUTING.md` baseline is `make clean && make` plus
`python3 tools/generate_assets.py --no-ai`. CI re-runs both. Don't commit
generated artifacts (`duke3d`, `duke3d.exe`, `*.GRP`, `generated_assets/`,
`build/`, `build_win/`, `captures/`).

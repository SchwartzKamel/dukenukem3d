# Copilot Instructions — DUKE3D: NEON NOIR

Modernized port of Duke Nukem 3D (1996, GPL-2.0) on Ken Silverman's BUILD engine. Builds on Linux, macOS, and Windows with GCC/Clang/MSVC + SDL2. Ships a Python asset pipeline that regenerates all art/audio/maps so no copyrighted content lives in the repo.

## Repo Layout (Three Eras of Code, Three Sets of Rules)

| Tree | Era | Standard | Rule |
|------|-----|----------|------|
| `SRC/` | Original BUILD engine (1996, Ken Silverman) | `-std=gnu89` (K&R C) | **Surgical fixes only.** Match brace style, indentation, naming. Never reformat or modernize. |
| `source/` | Duke3D game code (1996) | `-std=gnu89` (K&R C) | Same as `SRC/`. |
| `compat/` | Modern shim layer (DOS → POSIX/Win32/MSVC) | `-std=gnu11` | Clean modern C. Use `int32_t`-style fixed-width types for anything that touches engine structs. |
| `tools/` | Asset/audio pipeline | Python 3.8+ | PEP 8-ish, self-contained, minimal deps. |
| `tests/` | pytest suite (~60 files, 1300+ tests) | Python | See test commands below. |

Subsystem READMEs (`compat/README.md`, `tools/README.md`) and `docs/ARCHITECTURE.md` are the authoritative deep-dives — read them before architectural changes.

## Build & Test

```bash
# Linux build (default)            -> ./duke3d
make
make BUILD_TYPE=debug            # -O0 -g -DDEBUG
make clean

# Cross-compile Windows from Linux -> ./duke3d.exe
make windows

# macOS / cross-platform via CMake -> build/duke3d
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build

# Assets (procedural, no API keys needed)
make assets                       # == python3 tools/generate_assets.py --no-ai
python3 tools/generate_audio.py --no-ai
```

Release builds intentionally use `-w` (suppress warnings) for `SRC/` + `source/` because the 1996 K&R code produces 1200+ false-positive warnings; `compat/` is built with `-Wall`. Do not "fix" engine warnings without coordination.

### Tests

```bash
pytest                                              # full suite (xdist parallel, --runslow on by default)
pytest -m "not slow"                                # fast dev loop
pytest tests/test_palette.py                        # single file
pytest tests/test_palette.py::test_build_palette    # single test
pytest -k "quantize and not slow"                   # by keyword
pytest -n0 tests/test_xxx.py                        # disable xdist (helpful for prints/pdb)
```

Registered markers (see `pytest.ini`): `slow` (>1s, run by default), `playtest` (headless game launch, opt-in via `-m playtest`), `serial` (xdist-incompatible — avoid unless required).

### Cross-compiler struct tests

`tests/test_build_structs.py` compiles a C harness to verify binary struct layout. Override the compiler via `STRUCT_TEST_CC=x86_64-w64-mingw32-gcc` to validate MinGW; non-native binaries are auto-skipped from execution.

## Pre-Commit Secret Scan (Mandatory)

```bash
bash tools/install_hooks.sh   # one-time: sets core.hooksPath to .githooks
```

The hook runs `tools/check_secrets.sh` against staged diffs. It greps for `^+` (added lines only) with exclusions for `check_secrets.sh`, `tests/test_check_secrets*`, `.env.example`, and `docs/audits/`.

When writing tests or docs that include realistic-looking secret patterns (Slack `xoxp-/xoxb-`, Stripe `rk_live_/sk_live_`, `BEG`+`IN PRIVATE KEY`, `npm_`, `hf_`, GitHub `ghp_`, Azure `DefaultEndpoints`+`Protocol`, `Account`+`Key=`, etc.), **token-split the literal** so the scanner (and GitHub server-side push protection) doesn't trip:

```python
# test fixture
slack_token = "xo" + "xp-1234567890..."
```

```markdown
<!-- audit doc -->
`BEG` + `IN PRIVATE KEY` block was rotated...
```

## Generated Assets Are Never Committed

`generated_assets/`, `DUKE3D.GRP`, and `GRP_MANIFEST.json` are gitignored and rebuilt on demand. The **source of truth** lives in:

- `tools/generate_audio.py` → `VOICE_LINES`, `SOUND_MANIFEST` (21 WAVs)
- `tools/generate_assets.py` → `TEXTURE_DEFS`, `PROCEDURAL_MAP` (20 walls, 10 sprites)
- `tools/map_format.py` → procedural map builders
- `tools/palette.py`, `tools/tables.py` → palette/lookup tables

If `git status` ever shows these as dirty, run `git checkout -- generated_assets/ DUKE3D.GRP` — never commit them. Generator scripts must not write to project root; emit only to `generated_assets/`.

## Architectural Contracts

- **Watcom ASM → C translation:** `compat/pragmas_gcc.h` holds ~174 inline C functions replacing ~1,900 lines of Watcom `#pragma aux` inline assembly. These are hot rendering paths; do not modify without profiler-backed justification.
- **MAXTILES mismatch is known:** `SRC/BUILD.H` = 9216, `source/BUILD.H` = 6144. `compat/maxtiles_guard.c` warns at launch; do not unify without coordinating with the Engine Porter persona.
- **`totalclocklock` is NOT a typo** — it's a per-frame snapshot of `totalclock` (declared `SRC/BUILD.H:151`, assigned `SRC/ENGINE.C:853`). Reject any "fix" PR.
- **64-bit packed structs:** Always `int32_t`, never `long` (long is 64-bit on Linux x86-64). Binary format compatibility relies on this.
- **GRP archive determinism:** Byte-for-byte reproducible output is a hard contract — see `docs/GRP_DETERMINISM.md` before touching `tools/grp_format.py` or anything that feeds it.
- **Networking abstraction:** Socket operations in `SRC/MMULTI.C` route through `net_socket_create()`, `net_socket_set_option()`, `net_close()` wrappers (not raw `socket()`/`setsockopt()`/`close()`); preserve this when adding code.
- **CSPRNG:** Windows uses `BCryptGenRandom()` (`bcrypt.lib`); Linux uses `getrandom()`. Never `rand()` for nonces/checksums.

## Persona-Based Ownership

`.github/agents/*.agent.md` defines 10 specialized Copilot personas (Engine Porter, Compat Layer, Asset Pipeline, Audio Engineer, Build System, Test Engineer, Network & Multiplayer, Performance Profiler, Security & Secrets, Documentation Curator). When a task clearly falls under one persona's scope, prefer dispatching to that persona — each owns a specific tree and enforces its own conventions.

## Audit-Grind Workflow

The repo runs a recurring audit cycle (see `docs/audits/`, `docs/audits/SUMMARY.md`, `docs/audits/GRIND_LOG.md`, and the `audit-grind` skill at `.github/skills/`). Conventions:

- Audit reports are versioned: `<persona>-r<N>.md`. New reports must be added to `docs/audits/index.md`.
- Parallel sub-agents in a grind cycle **must not** run `git stash`, `git reset`, or `git checkout -- <file>` — they share the working tree and will destroy sibling work.
- After any audit-pass cycle, verify claimed changes with `git status` + tree-wide `grep` for the patch's unique token; sub-agents occasionally hallucinate edits.
- Staging-file pattern: parallel audit-pass agents write `STAGING_<persona>_r<N>.md` files with `<!-- SUMMARY_ROW -->` / `<!-- GRIND_LOG_ENTRY -->` delimiters; the orchestrator merges into `SUMMARY.md` / `GRIND_LOG.md` post-hoc to avoid sibling-write races.

## Credentials

`.env` is gitignored; `.env.example` is the template. Required keys for AI generation only (everything works with `--no-ai`):
- `FLUX_ENDPOINT`, `FLUX_MODEL`, `FLUX_API_KEY` (textures via FLUX.2-pro)
- `AUDIO_ENDPOINT`, `AUDIO_MODEL`, `AUDIO_API_KEY` (voice/SFX via GPT Audio on Azure)

Hostnames in error messages must be redacted to first-label (e.g. `api.***`) — see `_redact_hostname()` in `tools/generate_{assets,audio}.py`.

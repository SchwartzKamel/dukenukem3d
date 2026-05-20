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

On macOS:

```bash
# Install Xcode Command Line Tools (one-time setup)
xcode-select --install

# Install dependencies via Homebrew
brew install sdl2 cmake python@3.11 git
```

### Clone and Build

```bash
git clone <repo-url> dukenukem3d
cd dukenukem3d
```

**On Linux:**
```bash
make clean && make
```
The build produces the `duke3d` executable in the project root.

**On macOS:**
```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j $(sysctl -n hw.ncpu)
```
The build produces the `duke3d` executable in `build/`.

*(macOS uses CMake build system. See [.github/workflows/build.yml](https://github.com/SchwartzKamel/dukenukem3d/blob/master/.github/workflows/build.yml) — build-macos job for CI reference)*

### Run the Asset Pipeline

The asset pipeline generates all required game assets (textures, palettes,
tables, maps) and packs them into `DUKE3D.GRP`:

```bash
python3 tools/generate_assets.py --no-ai   # procedural textures only
make assets                                  # shorthand via Makefile
```

If you have FLUX API credentials in a `.env` file, omit `--no-ai` to use
AI-generated textures with procedural fallbacks.

### Secrets & API Keys

This project uses external APIs for AI-generated assets (textures and audio).
**Never commit API keys or credentials to the repository.**

#### Setup

1. **Copy the template:** `cp .env.example .env`
2. **Add your credentials** to `.env`:
   - `AUDIO_API_KEY`: Request from the project lead or obtain from Azure OpenAI portal
   - `FLUX_API_KEY`: Obtain from Black Forest Labs (Flux API) or Azure Deployment
3. **Verify `.env` is ignored:** The `.env` file is in `.gitignore` and should never be committed
4. **Enable the secret-scan hook** to prevent accidental commits:
   ```bash
   git config core.hooksPath .githooks
   ```

#### Obtaining API Keys

- **AUDIO_API_KEY**: Create a Cognitive Services resource in Azure portal (Text-to-Speech or OpenAI Audio API), then copy the API key from the Keys & Endpoint page
- **FLUX_API_KEY**: Register at Black Forest Labs (blackforestlabs.ai) or use an Azure deployment of FLUX

#### Pre-Commit Hook

The project includes a secret-scan hook that prevents commits containing API keys or secrets:
```bash
git config core.hooksPath .githooks
```

This runs before each commit and will reject staged changes if it detects:
- API keys with non-placeholder values
- Long base64-looking strings after `_KEY=`
- Common token prefixes (`sk-`, `ghp_`, `xoxb-`, etc.)

If the hook rejects your commit, unstage the file and verify `.env` is not being committed.

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

## Generated Assets (`generated_assets/`)

### What Is Generated (Not Committed)

The `generated_assets/` directory contains **ephemeral output** that is regenerated on-demand:

- **Audio files** (`generated_assets/sounds/*.WAV`) — AI-generated voice lines via GPT Audio 1.5, OR procedural silence placeholders when `--no-ai` is used
- **Audio manifest** (`generated_assets/sounds/MANIFEST.json`) — metadata mapping WAV files to engine sound IDs and voice catalog
- **Texture data** (`generated_assets/TILES*.ART`) — encoded in BUILD engine format (8-bit palette-indexed column-major layout)
- **Palette** (`generated_assets/PALETTE.DAT`) — 256-color palette + shade/translucency tables
- **Lookup tables** (`generated_assets/TABLES.DAT`) — sine, radar, font, brightness tables
- **Level maps** (`generated_assets/*.MAP`) — BUILD engine v7 map format (sectors, walls, sprites, geometry)
- **Game archive** (`DUKE3D.GRP` in both `generated_assets/` and project root) — KenSilverman archive packing all assets for runtime

**Why not commit these?** They are:
1. **Reproducible** from source configuration (VOICE_LINES, TEXTURE_DEFS, SOUND_MANIFEST, map generators)
2. **Large** (GRP archive is 3.9+ MB)
3. **API-dependent** — AI generation requires Azure credentials unavailable in CI
4. **Unstable** — regenerated with each tool update; committing would cause frequent merge conflicts

### What Is Committed (Source of Truth)

**Canonical configuration** that drives asset generation:

- **Voice catalog:** `VOICE_LINES` and `SOUND_MANIFEST` in `tools/generate_audio.py`
  - 21 voice lines (taunts, pain, death, pickups, weapons, level start, alarms, ambient)
  - Voice selection (alloy, echo, onyx) and engine sound IDs
  - This is the **source of truth** for audio; WAV files are derived output
  
- **Texture catalog:** `TEXTURE_DEFS` and `PROCEDURAL_MAP` in `tools/generate_assets.py`
  - 20 walls, 10 sprites; tile numbers, dimensions, and generation prompts
  - Procedural fallback generators for all textures
  - This is the **source of truth** for art assets

- **Map generators:** `create_level_map()`, `create_test_map()`, etc. in `tools/map_format.py`
  - Procedural sector/wall/sprite geometry
  - Engine-compatible binary format

**Modify these files to change what gets generated.** Then regenerate:

```bash
python3 tools/generate_audio.py      # Update generated_assets/sounds/*.WAV
python3 tools/generate_assets.py --no-ai  # Update generated_assets/ and DUKE3D.GRP
make assets                          # Shorthand for the above
```

### Getting a Working Build Without API Keys

If you don't have Azure credentials, use the `--no-ai` flag:

```bash
# Option 1: Run tools directly
python3 tools/generate_audio.py --no-ai    # Generates silence placeholders (22 KB per WAV)
python3 tools/generate_assets.py --no-ai   # Uses procedural textures only

# Option 2: Use Makefile target (recommended)
make assets
```

Both produce a fully playable `DUKE3D.GRP` and `generated_assets/` with:
- **Valid silence WAVs** — structurally correct but silent (useful for testing audio hooks)
- **Procedural textures** — neon noir cyberpunk theme with deterministic variation
- **Playable maps and palette** — no AI needed; pure procedural generation

You can develop, test, and contribute without API access.

### When to Commit vs. Regenerate

| Scenario | Action |
|----------|--------|
| You add a new voice line to `VOICE_LINES` | Commit the **code change** to `tools/generate_audio.py`. **Do NOT commit the resulting WAV files**; they will be regenerated by the asset pipeline on CI and by other developers locally. |
| You improve a procedural texture generator | Commit the **code change** to `tools/generate_assets.py`. Regenerate assets locally to verify it looks good in-game, but **do NOT commit the ART or GRP files**. |
| You change `SOUND_MANIFEST` (metadata) | Commit the **metadata structure** in `tools/generate_audio.py`. **Do NOT commit `MANIFEST.json`**; it is regenerated from this source. |
| You change palette colors or shade levels | Commit changes to `tools/palette.py`. **Do NOT commit `PALETTE.DAT`**; it is regenerated. |
| You add a new level map | Commit the **map generator function** in `tools/map_format.py` AND register it in `tools/generate_assets.py`. **Do NOT commit the `.MAP` file**; it is regenerated. |

### `.gitignore` Policy

The following rule ensures generated assets stay out of git history:

```
# Generated assets (can be rebuilt)
generated_assets/
DUKE3D.GRP
```

This is intentional and **must not be changed**. It enforces the principle that:
- **Source code + configuration** → git (reproducible)
- **Generated output** → `.gitignore` (ephemeral, regenerated on-demand)

If you ever see `generated_assets/` or `DUKE3D.GRP` in `git status`, it means you accidentally regenerated them in the repo. Ignore them with `git checkout -- generated_assets/ DUKE3D.GRP` and continue working.

## Audit Grind & Persona Sub-Agents

This project uses an **autonomous audit-grind orchestration system** to continuously verify code quality, documentation accuracy, and security posture. Understanding this automation helps you interpret audit reports and contribute effectively.

### How It Works

The audit-grind skill (`.github/skills/audit-grind/SKILL.md`) runs continuously or on-demand:

1. **Invocation:** Operators trigger `/audit-grind` via Copilot CLI (or schedule with `/every 30m /audit-grind`).
2. **Dispatch:** Audit-grind reads pending todos from the SQLite session database and assigns up to 6 specialized personas in parallel.
3. **Execution:** Each persona (engine-porter, audio-engineer, test-engineer, etc.) audits their domain and generates a markdown report.
4. **Findings:** Audit reports land in `docs/audits/<persona>-rN.md` with a master index in `docs/audits/SUMMARY.md`.
5. **Todos:** High-priority findings are automatically seeded as todos in the session DB; contributors pick them up in subsequent cycles.

### The 10 Specialized Personas

Each persona is a `.github/agents/*.agent.md` file that defines scope, expertise, and veto authority:

| Persona | Owns | Domain |
|---------|------|--------|
| **Engine Porter** | `SRC/`, `source/` | BUILD engine code, 64-bit safety, struct packing |
| **Compat Layer** | `compat/` | SDL2 shims, platform compatibility, type safety |
| **Asset Pipeline** | `tools/generate_*.py` | Texture/map/audio generation, GRP packing |
| **Audio Engineer** | Audio generation, `audio_stub.c` | Voice lines, WAV synthesis, API key management |
| **Build System** | `Makefile`, CMakeLists.txt, CI `.yml` | Cross-platform builds, Windows MinGW/MSVC |
| **Test Engineer** | `tests/`, pytest suite | Test coverage, struct invariants, harness quality |
| **Documentation Curator** | `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `docs/` | Accuracy, links, tone, command verification |
| **Security & Secrets** | `.env`, credentials, `.github/workflows/` | Secret scanning, dependency audits, SPDX headers |
| **Network & Multiplayer** | `MMULTI.C`, networking | TCP/IP safety, cross-platform netplay (future) |
| **Performance Profiler** | Benchmarks, profiling data | Optimization, regression detection, metrics |

### Audit Reports & Todos

When audit-grind completes a round:

- **Findings** are documented in `docs/audits/` with one report per persona (e.g., `engine-porter-r6.md`, `audio-engineer-r5.md`).
- **Critical & High findings** generate todos in the session backlog.
- **SUMMARY.md** maintains a cross-cutting index of all audit reports, personnel, and high-level verdicts.
- **GRIND_LOG.md** logs each `/audit-grind` invocation with timestamp, persona dispatch list, and final status.

See [docs/audits/SUMMARY.md](docs/audits/SUMMARY.md) for the current audit index.

### Sub-Agent Constraints

Sub-agents **must follow the no-git-mutation rule**:
- ✅ Allowed: `git diff`, `git log`, `grep`, `pytest`, code analysis
- ❌ Forbidden: `git reset`, `git stash`, `git revert`, `git cherry-pick`, or any tree-mutating command
- **Git state is owned by you (the operator).** Sub-agents propose changes; you apply them.

**Anti-Hallucination Return Format (Cycle 22):** All audit findings must be grounded in evidence. Sub-agents must include:
- **Grep output** for code location claims (e.g., `grep -n "function_name" source/*.C | head -5`)
- **Diff-stat summaries** when citing changes (e.g., `git diff v0.1.33..HEAD -- source/GAME.C | diffstat`)
- **File existence verification** before citing paths (e.g., `ls -la source/FILE.C`)
- **Test evidence** when asserting test counts or coverage (e.g., `pytest --collect-only -q`)
- This prevents agents from inventing findings or citing non-existent code locations.

### Example: Contributing During an Active Grind

1. You push a feature branch with changes to `source/GAME.C`.
2. Audit-grind runs and dispatches the **engine-porter** persona to audit your changes.
3. Engine-porter generates a report (e.g., `engine-porter-r7.md`) with findings.
4. High-priority findings seed todos (e.g., "Fix struct packing in walltype on 64-bit").
5. A contributor picks up the todo, implements the fix, and opens a PR.
6. Audit-grind re-runs, engine-porter verifies the fix, and closes the todo.

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

## Code Review with Agents

This project uses **10 specialized Copilot personas**, each owning a specific domain. When your PR touches a domain, the relevant agent becomes the authority on that code.

**If your PR modifies…** | **Notify persona** | **Key concerns** |
|---|---|---|
| `SRC/`, `source/` (engine code) | **Engine Porter** (`.github/agents/engine-porter.agent.md`) | 64-bit safety, struct packing, inline ASM |
| `compat/` (SDL2, shims) | **Compat Layer** (`.github/agents/compat-layer.agent.md`) | Platform compatibility, type safety |
| `tools/generate_*.py` | **Asset Pipeline** (`.github/agents/asset-pipeline.agent.md`) | Texture/map formats, GRP packing |
| Audio generation, `audio_stub.c` | **Audio Engineer** (`.github/agents/audio-engineer.agent.md`) | Voice lines, WAV generation, API keys |
| `Makefile`, `CMakeLists.txt`, `build_windows.bat`, CI `.yml` | **Build System** (`.github/agents/build-system.agent.md`) | Cross-platform builds, MinGW/MSVC |
| `tests/`, pytest suite | **Test Engineer** (`.github/agents/test-engineer.agent.md`) | Test coverage, struct invariants |
| `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, docs/ | **Documentation Curator** (`.github/agents/documentation-curator.agent.md`) | Accuracy, links, tone, commands |
| `.env`, API credentials, secret scanning | **Security & Secrets** (`.github/agents/security-and-secrets.agent.md`) | No secrets committed, hygiene |
| `MMULTI.C`, networking (future) | **Network & Multiplayer** (`.github/agents/network-multiplayer.agent.md`) | TCP/IP safety, cross-platform netplay |
| Benchmarks, performance | **Performance Profiler** (`.github/agents/performance-profiler.agent.md`) | Optimization, profiling, regressions |

Each persona has veto power on decisions within their domain and will provide thorough code review. If you're unsure which agent owns your change, check the persona file or ask in the PR description.

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

## Manifest Verification Pattern

This project uses **manifest verification** to ensure the integrity of generated assets (audio WAVs, lookup tables, GRP archive). The manifest loaders provide a consistent pattern for production and test code.

### When to Use Manifest Verifiers

**Always use the verifier functions** for production asset loads:

- `load_and_verify_audio_manifest()` — for audio manifests (WAV checksums, voice catalog)
- `load_and_verify_grp_manifest()` — for GRP archive manifests (member file checksums)
- `load_and_verify_tables_manifest()` — for lookup table manifests (TABLES.DAT checksums)

**Raw `json.load()` is forbidden** in production code paths. Exception: explicit test bypasses only, marked with:

```python
# sec-r15-manifest-loader-adoption: intentional test bypass
manifest = json.load(f)  # Only in tests with this sentinel
```

### The Three Verifier APIs

Located in `tools/manifest_verification.py`:

#### `load_and_verify_audio_manifest(manifest_path: str, base_dir: str = None) -> dict`

Loads an audio manifest and verifies:
- **Manifest-level checksum**: SHA256 of the entire manifest structure (if present)
- **Per-entry WAV checksums**: SHA256 of each referenced WAV file matches the manifest entry

Used by `tools/generate_audio.py` (line 256) to validate voice line integrity before runtime loading.

#### `load_and_verify_grp_manifest(manifest_path: str, base_dir: str = None) -> dict`

Loads the GRP archive manifest and verifies:
- **Manifest-level checksum**: Top-level SHA256 of manifest structure
- **GRP file checksum**: SHA256 of the entire DUKE3D.GRP archive file
- **Member checksums** (optional): SHA256 of individual files packed in the GRP

#### `load_and_verify_tables_manifest(manifest_path: str, base_dir: str = None) -> dict`

Loads the lookup tables manifest and verifies:
- **Manifest-level checksum**: Top-level SHA256
- **Tables file checksum**: SHA256 of TABLES.DAT

### Behavior Contracts

All three verifiers follow the same contract:

| Condition | Behavior |
|-----------|----------|
| Manifest file missing | Raises `IOError` |
| Manifest JSON invalid | Raises `ValueError` |
| Checksum mismatch (expected vs. computed) | Raises `RuntimeError` with sentinel `manifest-checksum-verify-on-load` |
| Entry/file missing a `sha256`/`checksum` field (legacy) | Issues `UserWarning` and continues (backward compatibility) |
| Schema validation fails | See next section — decoupled from checksum verification |

The **`manifest-checksum-verify-on-load` sentinel** is used in all RuntimeError messages for automated log scanning and incident identification.

### Schema Validation (Separate from Checksum Verification)

Checksum verification and schema validation are intentionally decoupled:

- **Verifiers** (`load_and_verify_*()`) handle checksums only — they assume manifest JSON is well-formed
- **Schema validation** (if needed) should be done *before* or *after* the verifier, depending on your use case

Example workflow:
```python
import json
from manifest_verification import load_and_verify_audio_manifest

# Load and verify checksums
manifest = load_and_verify_audio_manifest("generated_assets/sounds/MANIFEST.json", "generated_assets/sounds")

# Optionally, validate schema separately (if required for your domain)
assert "entries" in manifest
assert "schema_version" in manifest
```

### Implementation Reference

See `tools/manifest_verification.py` for:
- Internal helper functions: `_sha256_of_file()`, `_sha256_of_manifest()`
- Checksum computation logic (SHA256 of JSON with sorted keys)
- Per-file checksum verification (compute on disk, compare to manifest entry)

### Audit History & Context

**Cycle 53 Migration**: Audio pipeline migrated from raw `json.load()` to `load_and_verify_audio_manifest()`.
- Affected: `tools/generate_audio.py` (line 256)
- Sentinel marker: `sec-r15-manifest-loader-adoption: migrated to verifier` (lines 238, 254)
- Verification: All checksum logic now centralized in verifier; zero duplication

See audit reports for full context:
- `docs/audits/audio-engineer-r15.md` — Finding 1.1: Manifest Loader Migration
- `docs/audits/security-and-secrets-r15.md` — Asset pipeline integrity validation

## Continuous Integration & Caching

The GitHub Actions workflows in `.github/workflows/` use `actions/setup-python`
with pip caching to keep CI fast:

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'
    cache-dependency-path: 'requirements.txt'
```

This saves roughly **20–30 seconds per job** by reusing the cached
wheels for `pillow`, `aiohttp`, `numpy`, etc. When you change
`requirements.txt`, the cache invalidates automatically — you do not
need to bump the cache key by hand.

The reusable `tools/ci/generate_assets.sh` script is the canonical
asset-generation entry point in CI; updating CI workflows should call
into it rather than duplicating `python3 tools/generate_assets.py …`
invocations.

## Pre-Commit Hook Setup

To prevent accidental commits of API keys and secrets, install the pre-commit hook:

```bash
bash tools/install_hooks.sh
```

This one-line install:
- Detects your git repository root
- Creates `.git/hooks/pre-commit` (or backs up any existing hook)
- Configures the hook to call `tools/check_secrets.sh` on all staged changes
- Sets executable permissions automatically

**What the hook checks:**
- API key patterns (AWS, Stripe, GitHub, OpenAI, etc.)
- Private key headers (RSA, OpenSSH, EC, DSA)
- Common secret prefixes (sk-, ghp-, xoxb-, etc.)
- Base64-encoded credential-like strings

**If the hook blocks your commit:**
1. Verify that `.env` is NOT being committed (should be ignored)
2. Unstage the problematic file: `git reset HEAD <file>`
3. Check that `.env` is in `.gitignore` and not tracked
4. Commit again

**To bypass** (not recommended and discouraged):
```bash
git commit --no-verify
```

Bypassing is considered a security violation; discuss with the team before doing so.

For full details on secret handling and the audit context, see [docs/audits/security-and-secrets-r16.md](docs/audits/security-and-secrets-r16.md#pre-commit-hook-integrity).

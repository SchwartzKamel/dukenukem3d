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
4. **Install the pre-commit secret-scan hook:**
   ```bash
   bash tools/install_hooks.sh
   ```
   This installs a hook at `.git/hooks/pre-commit` that scans staged changes for exposed secrets. If an existing hook is detected, it will be backed up with a timestamp. The hook runs `tools/check_secrets.sh` automatically on all commits. To bypass (not recommended): `git commit --no-verify`

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

## GRP Archive Determinism Contract

### Overview

This section documents the **determinism guarantee** for GRP archive generation: given identical inputs (asset set, content bytes, and sort order), the resulting `DUKE3D.GRP` binary must be **bit-identical** across runs and platforms. This contract ensures reproducible builds and enables cryptographic verification via SHA256 checksums.

### GRP Binary Format

The GRP archive follows the KenSilverman format as specified in `tools/grp_format.py` (lines 2–9, 14–41):

```
[Header: 16 bytes]
├─ Magic (12 bytes): "KenSilverman"
└─ File count (4 bytes): uint32 little-endian

[Directory: N entries × 16 bytes per entry]
├─ Filename (12 bytes): uppercase ASCII, null-padded to 12 bytes
└─ Size (4 bytes): uint32 little-endian

[Data payload: sum of all file sizes]
└─ File contents concatenated in directory order
```

**Verified by tests**: `tests/test_grp_format.py` (lines 6–55) validates magic, file count, filename padding (12 bytes), size encoding, and payload concatenation.

### Determinism Invariants

To guarantee bit-identical output, the following invariants are strictly enforced:

1. **File Insertion Order (Alphabetical)**  
   Files are sorted by name using `sorted(files_dict.keys())` (`tools/grp_format.py`, line 32). This ensures the directory order is deterministic regardless of dictionary insertion order or platform.

2. **File Count Limit**  
   File count is a 4-byte unsigned integer (uint32 LE). Maximum: 4,294,967,295 files. Current GRP archives contain ~4–10 files (maps, textures, audio), well below the limit.

3. **Header Byte Format**  
   - Magic: literal bytes `"KenSilverman"` (ASCII, not null-terminated within the header)
   - File count: `struct.pack("<I", num_files)` (little-endian unsigned 32-bit integer)

4. **Per-Entry Filename Padding**  
   Each filename is padded to exactly 12 bytes with null bytes (`\x00`). Filenames longer than 12 characters are rejected with a `ValueError` (`tools/grp_format.py`, line 35–36).

5. **Per-Entry Size (4 bytes, little-endian)**  
   Each file's size is encoded as `struct.pack("<I", len(data))`. No size field padding or alignment.

### Inputs That Affect Output

These inputs must be controlled for deterministic GRP generation:

- **Asset list**: The set of files to pack (must be the same)
- **File content bytes**: The binary content of each file (must be identical)
- **Sort order**: Filenames are sorted alphabetically (ascending ASCII order). This is automatic via `sorted()`.

### Inputs That MUST NOT Affect Output

These external factors must be excluded from the GRP to maintain determinism:

- **Filesystem metadata (mtime, ctime, atime)**: Ignored; only file content matters
- **Hostname or machine identity**: Not encoded in the GRP
- **Process PID**: Not embedded
- **Random seeds or non-deterministic RNG**: Not used in GRP packing
- **Time-of-day or wall-clock timestamps**: Only used in the manifest (e.g., `GRP_MANIFEST.json`'s `generated_at` field), not in the GRP binary itself
- **Locale or collation order**: Filenames use Python's default string comparison (lexicographic ASCII order), which is platform-independent

### Verification: Checking Determinism Locally

To verify that GRP generation is deterministic:

```bash
# Generate assets twice in succession
python3 tools/generate_assets.py --no-ai
sha256sum DUKE3D.GRP > checksum1.txt

python3 tools/generate_assets.py --no-ai
sha256sum DUKE3D.GRP > checksum2.txt

# Both checksums must be identical
diff checksum1.txt checksum2.txt  # Should show no difference
```

If the checksums differ, investigate:
1. **Stale cached textures**: Delete `generated_assets/` and regenerate
2. **Code changes to packing logic**: Review `tools/grp_format.py` and `tools/generate_assets.py`
3. **Manifest changes**: Manifest JSON (`GRP_MANIFEST.json`) embeds `generated_at` timestamps and may differ; verify the GRP binary itself with `hexdump` or binary comparison

### Atomic Write Guarantee (Cycle 70 Reference)

GRP files are written via `_atomic_write_bytes()` (`tools/generate_assets.py`, lines 238–258):

```python
def _atomic_write_bytes(path: str, data: bytes) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)  # POSIX atomic rename
```

**Guarantee**: If the process is interrupted mid-write, the original GRP file (or none) remains intact; no partial or corrupted archives are ever left on disk. This ensures that all observed GRP files are either complete and correct or absent.

### Manifest Integrity & Checksums

The GRP manifest (`GRP_MANIFEST.json`, emitted by `tools/generate_assets.py` lines 282–334) records:

- **SHA256 of the GRP file**: Computed over the entire GRP binary
- **SHA256 of each member file**: Individual checksums for auditing
- **Member metadata**: Name, size, and order
- **Manifest checksum**: SHA256 computed over the manifest itself (excluding the `manifest_checksum` field)

Manifest integrity is verified on load (`tools/manifest_verification.py`) to catch any tampering or corruption. See `tests/test_grp_manifest.py` for verification tests (lines 123–249).

### Testing & Continuous Verification

- **Unit tests**: `tests/test_grp_format.py` (56 lines) validates GRP structure, magic, file counts, and filename padding
- **Integration tests**: `tests/test_grp_manifest.py` (282 lines) validates deterministic emission, checksums, and manifest integrity
- **CI/CD**: The build system regenerates GRP archives from source on every commit and verifies checksums against the manifest

This ensures that any unintended deviation from the determinism contract is caught immediately.

## TABLES.DAT Determinism Contract

### Overview

TABLES.DAT is a binary file containing precomputed lookup tables (sine, radar, brightness, fonts) used by the game engine for rendering and audio. It is generated deterministically by `tools/generate_tables.py` and must be **bit-identical** across runs and platforms given identical table source code.

### Generation & Format

TABLES.DAT is generated with:

```bash
python3 tools/generate_tables.py          # Default (current timestamp)
python3 tools/generate_tables.py --deterministic  # CI mode (fixed 1970-01-01T00:00:00Z timestamp)
```

The binary output is written to `generated_assets/TABLES.DAT` via atomic write (tmp+rename with fsync, mirroring the GRP pattern). A corresponding manifest (`TABLES_MANIFEST.json`) records metadata and checksums.

### Determinism Guarantees

- **No random seeds**: All tables are computed deterministically from fixed algorithms
- **Ordered iteration**: Table list is hardcoded as `["sine", "radar", "brightness", "fonts"]` (alphabetical, deterministic order)
- **Atomic writes**: Uses `_atomic_write_bytes()` (lines 27–50 in `generate_tables.py`) with POSIX atomic rename and fsync to ensure partial writes never corrupt the file
- **Manifest integrity**: SHA256 checksums (per-file and manifest-level) verify integrity; manifest is also written atomically

### Verification: Checking Determinism Locally

```bash
python3 tools/generate_tables.py --deterministic
sha256sum generated_assets/TABLES.DAT > checksum1.txt

python3 tools/generate_tables.py --deterministic
sha256sum generated_assets/TABLES.DAT > checksum2.txt

diff checksum1.txt checksum2.txt  # Must match
```

If checksums differ, investigate changes to `tools/generate_tables.py` or the underlying `tables` module that computes the lookup tables.

## Audit & Grind Workflow

This project uses an **autonomous audit-grind orchestration system** to continuously verify code quality, documentation accuracy, and security posture. Understanding this automation helps you interpret audit reports and contribute effectively.

### Overview

**What it is:** A multi-cycle backlog-grinding automation where specialized Copilot personas audit the codebase in parallel, surface findings as structured todos, and iterate toward quality gates (build, tests, docs).

**Why it exists:** Manual audits scale poorly; this system enables 10 expert personas to work asynchronously, draining the backlog 6 todos at a time, every 30 minutes. Audit findings are grounded in evidence (not hallucinated) and feed directly into contributor workflows via the session database.

### The 10 Specialized Personas

Each persona owns a domain and has veto authority on decisions within that domain. See individual `.github/agents/X.agent.md` files for full scope, responsibilities, and workflows.

| Persona | File | Domain | Owns |
|---------|------|--------|------|
| **Engine Porter** | [engine-porter.agent.md](.github/agents/engine-porter.agent.md) | K&R engine code | `SRC/`, `source/` — BUILD engine, 64-bit safety, struct packing |
| **Compat Layer** | [compat-layer.agent.md](.github/agents/compat-layer.agent.md) | Platform bridges | `compat/` — SDL2 shims, POSIX/Win32, type safety |
| **Asset Pipeline** | [asset-pipeline.agent.md](.github/agents/asset-pipeline.agent.md) | Art generation | `tools/generate_*.py` — textures, maps, GRP packing |
| **Audio Engineer** | [audio-engineer.agent.md](.github/agents/audio-engineer.agent.md) | Voice & WAV | Audio generation, `audio_stub.c` — voice lines, synthesis, API keys |
| **Build System** | [build-system.agent.md](.github/agents/build-system.agent.md) | Build & CI | `Makefile`, CMakeLists.txt, `build.yml` — cross-platform, MinGW/MSVC |
| **Test Engineer** | [test-engineer.agent.md](.github/agents/test-engineer.agent.md) | Quality gates | `tests/`, pytest — coverage, struct invariants, harnesses |
| **Documentation Curator** | [documentation-curator.agent.md](.github/agents/documentation-curator.agent.md) | Docs | `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `docs/` — accuracy, links, tone |
| **Security & Secrets** | [security-and-secrets.agent.md](.github/agents/security-and-secrets.agent.md) | Posture | `.env`, `.gitignore`, workflows — secret scanning, CVE audits, GPL compliance |
| **Network & Multiplayer** | [network-multiplayer.agent.md](.github/agents/network-multiplayer.agent.md) | Netplay | `SRC/MMULTI.C`, TCP/IP — distributed systems, end-to-end harness |
| **Performance Profiler** | [performance-profiler.agent.md](.github/agents/performance-profiler.agent.md) | Hotspots | Benchmarks, frame analysis — render-loop regression detection |

### The Audit-Pass Tick

When triggered on-demand (or per schedule), audit-grind performs a **read-only audit pass**:

1. Each of the 10 personas scans their domain independently (in parallel).
2. Personas write findings to `docs/audits/<persona>-rN.md` (where `N` is the revision level: r1 = first audit, r2 = second, etc.).
3. **SUMMARY.md** (in `docs/audits/`) is the single source of truth — aggregates all findings across personas, cross-references audit reports, and tracks verdict status (e.g., "CRITICAL in engine-porter-r5 finding #3").
4. High-priority findings (CRITICAL, HIGH) are seeded as pending todos in the session SQL database (`todos(id, title, description, status='pending')`).
5. **No code changes** occur during an audit pass — personas only read and report.

### The Grind Tick

Once audits are complete, `audit-grind` shifts to **execution mode**:

1. **Pull pending todos** from the session database (up to 12 ready, take the top 6).
2. **Assign to personas** by domain (e.g., a "fix struct packing" todo → engine-porter persona).
3. **Dispatch sub-agents in parallel** (background tasks via Copilot `task` tool, model `haiku-4.5`) — up to 6 per cycle (hard limit prevents race conditions on `make clean`).
4. **Each sub-agent**:
   - Makes code changes in its domain
   - Runs validation gates: `make clean && make`, `pytest -q` (must not regress)
   - Updates todo status via SQL: `UPDATE todos SET status='done' WHERE id='<todo-id>'` (or `blocked` with rationale)
   - Returns a short summary (files changed, test delta, any surprises)
5. **Post-run validation**: Orchestrator re-runs build + tests to catch race conditions between parallel agents.
6. **GRIND_LOG.md** is updated with cycle metadata: todos picked up, todos completed, todos blocked, build/test delta, notable findings, human-attention items.

### GRIND_LOG.md Log Discipline

`docs/audits/GRIND_LOG.md` is an **append-only run log**:

- **One entry per cycle** with ISO 8601 timestamp (e.g., "2026-05-20T05:24:24Z — Cycle 1").
- **Metadata captured**: Trigger (manual vs. scheduled), operator AFK status, baseline test counts.
- **Todos table** (per-cycle): id, persona, source finding.
- **Completion summary**: Completed todos, blocked todos with rationale, build/test delta (before → after pass counts).
- **Notable findings**: New bugs surfaced, unexpected discoveries, edge cases discovered.
- **Human-attention items**: Commits made (if authorized), decisions deferred, race condition incidents.
- **Cycle close**: Final todo backlog state, next cycle recommendations.

Example entries: cycles 1, 2 in `docs/audits/GRIND_LOG.md` (lines 7–100) show the format. Keep entries concise — this log is for the operator's morning standup, not a novel.

### How to Invoke Locally

**Manual trigger** (one-shot):
```bash
/audit-grind
```
This runs one complete audit-grind cycle (audit pass + grind tick) and exits.

**Recurring schedule** (background):
```bash
/every 30m /audit-grind
```
This schedules audit-grind to run every 30 minutes while the operator is AFK. Adjust interval as needed:
- `/every 15m` — active dev days (fast feedback)
- `/every 2h` — overnight (slow, batched)

All output is logged to `docs/audits/GRIND_LOG.md`.

### v7 Contract (Hard Constraints)

Sub-agents and audit-grind must enforce:

- ❌ **NO git mutations**: No `git commit`, `git push`, `git reset`, `git stash`, `git revert`, `git cherry-pick`, `git rebase`, `git merge`, `git clean`, `git checkout --`.
  - **Why**: Git state is owned by the operator (you). Sub-agents propose changes; you decide whether to commit.
  - **Allowed**: `git diff`, `git log`, `git status`, `grep`, file inspection.
  
- ❌ **NO fake author identities**: All work is attributed to the operator, not fabricated personas or "Copilot".
  
- ✅ **Scope discipline**: Sub-agents **only** edit files in their owned domain. Cross-domain dependencies are flagged as blocked with rationale (operator must manually coordinate).
  
- ✅ **Build & test gates**: All changes must pass `make clean && make` and `pytest -q` (≥ baseline pass count). If a sub-agent breaks the tree, the run is marked FAILED and documented in GRIND_LOG.

- ✅ **SQL bookkeeping**: On success, sub-agents run `UPDATE todos SET status='done' WHERE id='<todo-id>'`; on blockage, `UPDATE todos SET status='blocked'` with one-paragraph rationale.

### File Touchpoints

- **SKILL.md (source of truth):** [.github/skills/audit-grind/SKILL.md](.github/skills/audit-grind/SKILL.md) — complete protocol, persona dispatch logic, failure modes, validation gates.
- **Persona files:** [.github/agents/](.github/agents/) — 10 `.agent.md` files defining domain, expertise, veto authority, workflows.
- **Audit reports:** [docs/audits/]( docs/audits/) — one report per persona per cycle (e.g., `engine-porter-r6.md`), plus `SUMMARY.md` (cross-cutting index) and `GRIND_LOG.md` (run log).
- **Session todos:** SQLite `todos(id, title, description, status)` + optional `todo_deps(todo_id, depends_on)` — the backlog queue.

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

### Legacy Manifest Checksum Deprecation

Audio manifests originally supported legacy entries lacking per-WAV `sha256` checksums. This section documents the deprecation timeline and migration path.

**Current State (Cycle 74+)**

- Checksum field is **optional** in manifest entries
- Missing checksums emit a `UserWarning` during load (tools/manifest_verification.py, lines 103–107)
- Warning text: `"Manifest entry[N] lacks checksum field (legacy compat mode)"`
- Manifests load successfully (backward compatible)

**Deprecation Timeline**

| Cycle | Status | Behavior |
|-------|--------|----------|
| 74+ | Current | Warn on missing checksums; accept legacy entries without verification |
| 80 (proposed) | **Soft deadline** | Begin treating missing checksums as errors in new manifests; older entries remain accepted with warnings (~8 cycles from cycle 74) |
| 90 (proposed) | Hard deadline | Remove legacy compat path entirely; all entries MUST have `sha256` field or load will fail |

**Rationale**

- **Determinism guarantee**: WAV file checksums enable bit-identical verification across runs and platforms, preventing silent asset corruption
- **Integrity boundary**: Checksums are computed at generation time and verified at load time, closing the gap between `generate_audio.py` and runtime code
- **Forward compatibility**: Schema v1.0 already defines checksums as a required concept; the deprecation simply enforces it

**Migration Path**

To migrate legacy manifests lacking checksums:

1. **Re-run audio generation** (checksums are computed automatically):
   ```bash
   python3 tools/generate_audio.py [--no-ai]
   ```
   This regenerates `generated_assets/sounds/MANIFEST.json` with up-to-date checksums for all WAV files.

2. **Verify checksums are present** in the manifest:
   ```bash
   python3 -c "import json; m = json.load(open('generated_assets/sounds/MANIFEST.json')); \
     print('Entries with sha256:', sum(1 for e in m.get('entries', []) if 'sha256' in e))"
   ```

3. **Load and verify** using the standard verifier:
   ```python
   from manifest_verification import load_and_verify_audio_manifest
   manifest = load_and_verify_audio_manifest(
       "generated_assets/sounds/MANIFEST.json",
       "generated_assets/sounds"
   )
   ```

**Citations**

- Warning emission: `tools/manifest_verification.py`, lines 103–107
- Checksum computation: `tools/generate_audio.py`, lines 83–97
- Manifest model: `tools/sound_manifest.py`, lines 13–120 (SoundManifestEntry schema; checksum implicitly required for verification)

### Voice Generation Determinism

Duke3D audio uses multiple voice generation backends with varying reproducibility guarantees. This section documents each path, the determinism contract, and policy for PR vs. release builds.

**Three Voice Generation Paths**

1. **Local Path (`--no-ai` flag)**
   - Implementation: `tools/generate_audio.py`, lines 548–602 (`_generate_audio_parallel_local()`)
   - Output: Silence placeholders (22 KB per WAV)
   - Determinism: **Fully deterministic** — same input always produces bit-identical WAV bytes
   - Reproducibility: Re-running generates identical files (identical struct packing, same silence waveform, fixed epoch timestamp `1970-01-01T00:00:00Z`)

2. **Azure Speech API Path** (default when `AUDIO_ENDPOINT` and `AUDIO_API_KEY` are set)
   - Implementation: `tools/generate_audio.py`, lines 605–700+ (`_generate_audio_parallel_api()` / `_generate_audio_async_main()`)
   - Output: Real voice lines from Azure Cognitive Services Text-to-Speech or GPT Audio API
   - Determinism: **Deterministic for fixed parameters** — same `(voice_id, text, locale, SSML_params)` tuple produces identical audio from Azure on repeated requests
   - Caveat: API updates or model versioning may change output; document API version in manifest metadata
   - Reproducibility: Sufficient for release builds when API contract is pinned

3. **FLUX/Procedural Path** (not currently active; for future expansion)
   - Model: FLUX or similar diffusion-based voice synthesis
   - Determinism: **Not reproducible** — even with identical seed, model updates or floating-point variations cause bit-level differences
   - Reproducibility: Not suitable for release builds; appropriate for exploratory generation only

**Policy**

- **PR builds and CI**: Use `--no-ai` mode (silence placeholders)
  - Reason: No API keys in CI; enables reproducible builds
  - Effect: Audio generation is fast, fully deterministic, and does not require credentials
  - Testing: Validates audio hooks and pipeline without API calls

- **Release builds and distribution**: Use Azure API path with pinned model/API version
  - Reason: Real voice lines for game distribution
  - Reproducibility requirement: Document `AUDIO_MODEL` (e.g., `gpt-audio-1.5`) and API version in `GRP_MANIFEST.json` under `generation_metadata`
  - Seed management: If using seeded synthesis, document seed in manifest (currently not applicable; future extension)

**Reproducibility Guarantee**

Given a fixed `MANIFEST.json` and `--no-ai` mode:
- Re-running `python3 tools/generate_audio.py --no-ai` must produce **bit-identical WAV files**
- Verified by: `sha256sum generated_assets/sounds/*.WAV` (checksums must match manifest entries)
- Test: `tests/test_audio_pipeline.py` includes determinism validation (compare silence WAV byte streams across runs)

**Citations**

- Local generation: `tools/generate_audio.py`, lines 548–602
- Async API generation: `tools/generate_audio.py`, lines 605–700+
- Deterministic timestamp: `tools/generate_audio.py`, lines 553–556, 615–618
- Manifest metadata: `tools/sound_manifest.py`, lines 72–75 (`generation_metadata` field)

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

### Schema Version Migration

Manifest files use a `schema_version` field to track breaking changes and ensure forward/backward compatibility. This section documents the versioning policy, loader contract, and migration strategy.

**Current Schema Version**: `1.0` (introduced Cycle 34, commit 39afbc4 "cycle-34: audio manifest schema + recovered sec/compat stash work")

#### Versioning Policy

- **Bump schema_version ONLY for breaking changes**:
  - Field removal: `entries[i].voice` deleted → bump version
  - Type change: `entries[i].status` string → enum → bump version
  - Semantic change: `manifest_checksum` algorithm changed → bump version
  - Example: changing `check` to `checksum` is a breaking change
  
- **Do NOT bump for additive changes**:
  - New optional field: `entries[i].confidence_score` added → **no bump**, but document in this section
  - New manifest-level field: `generator_version` added → **no bump**, but document
  - DO update CHANGELOG.md to note the new optional field (see "Release Notes" below)

#### Loader Contract (All Three Verifiers)

All manifest loaders in `tools/manifest_verification.py` (`load_and_verify_audio_manifest()`, `load_and_verify_grp_manifest()`, `load_and_verify_tables_manifest()`) must enforce:

| Condition | Behavior | Code Reference |
|-----------|----------|-----------------|
| `manifest_data["schema_version"] < "1.0"` | Load and warn (legacy compat); log `UserWarning` | `manifest_verification.py` lines 45–51 (tables), 254–259 (GRP) |
| `manifest_data["schema_version"] == "1.0"` | Load and verify checksums (normal path) | `generate_audio.py` lines 250–255; all three verifiers |
| `manifest_data["schema_version"] > "1.0"` | **REJECT**; raise `ValueError` with version mismatch message | `generate_audio.py` lines 250–255: `if schema_version != "1.0": raise ValueError(...)` |
| `schema_version` field missing | Assume "legacy" (v0 implicit); warn and continue | `manifest_verification.py` lines 45–51 |

**Key Invariant**: Loaders **MUST NOT** silently ignore or load a schema_version newer than the code supports. An operator upgrading asset manifests to schema v2.0 without upgrading code will get an explicit error, preventing silent data corruption.

#### Backwards Compatibility Policy (N-2 Support)

- **Current supported versions**: `1.0` (primary), and any `< 1.0` (legacy with warnings)
- **Future policy** (when v2.0 is released): support v2.0 (primary) and v1.0 (N-1); v0.x → RuntimeError with migration message
- **Deprecation timeline**:
  - When v2.0 released: emit `UserWarning` on all v1.0 loads suggesting migration path
  - After 2 release cycles: treat v1.0 as legacy (same as current v0.x handling)
  - After 4 release cycles: reject v1.0 with explicit migration error

#### Migration Helper Pattern (Example for v1.0→v2.0)

When schema_version must be bumped, add a migration adapter in `tools/generate_audio.py` (or dedicated `tools/manifest_migration.py`):

```python
def _migrate_v1_to_v2(entry_v1: dict) -> dict:
    """Migrate a v1.0 manifest entry to v2.0.
    
    Handles field renames, type conversions, and new required fields.
    
    Example: If v2.0 removes 'voice' and replaces with 'voice_id' enum,
    map the old string 'alloy' → voice_id 1.
    """
    entry_v2 = dict(entry_v1)  # shallow copy
    
    # Example migration: rename 'voice' → 'voice_id' with enum mapping
    if "voice" in entry_v2:
        voice_str = entry_v2.pop("voice")
        voice_id_map = {"alloy": 1, "echo": 2, "onyx": 3}
        entry_v2["voice_id"] = voice_id_map.get(voice_str, 0)
    
    # Example: add new required field with sensible default
    if "confidence_score" not in entry_v2:
        entry_v2["confidence_score"] = 0.95
    
    return entry_v2


def _validate_and_migrate_manifest(manifest_data: dict, source_path: str) -> dict:
    """Load manifest and migrate if needed.
    
    Returns manifest in current schema_version.
    Raises ValueError if schema_version is unsupported (> current).
    """
    schema_version = manifest_data.get("schema_version", "0")
    
    if schema_version not in ["1.0"]:  # Update when v2.0 added
        raise ValueError(
            f"{source_path}: Unsupported schema_version '{schema_version}' "
            f"(expected '1.0' or earlier)"
        )
    
    if schema_version == "1.0":
        return manifest_data  # no migration needed
    
    # Legacy v0: migrate silently with warning
    if schema_version < "1.0":
        warnings.warn(
            f"Manifest {source_path} uses legacy schema_version {schema_version}; "
            f"recommend migration to v1.0",
            category=UserWarning
        )
        # Minimal v0→v1.0 migration (depends on actual v0 format)
        manifest_data["schema_version"] = "1.0"
        return manifest_data
    
    # Should not reach here due to ValueError above
    return manifest_data
```

#### Release Notes & CHANGELOG Updates

When **bumping schema_version**:
- Add entry to `CHANGELOG.md` under "Breaking Changes" section:
  ```markdown
  - **Audio manifest schema v2.0** (cycle N): Removed `voice` field (replaced by `voice_id` enum). 
    See CONTRIBUTING.md § Schema Version Migration for migration guide.
  ```

When **adding optional fields** (no version bump):
- Add entry to `CHANGELOG.md` under "New Features" or "Improvements":
  ```markdown
  - Audio manifest entries now support optional `confidence_score` field (defaults to 0.95 if omitted).
  ```

#### Testing Schema Version Changes

When introducing a new schema_version:
1. **Add test** in `tests/test_audio_pipeline.py`:
   ```python
   def test_manifest_loader_rejects_future_schema_version(self):
       """Loaders must reject schema_version > current."""
       bad_manifest = {
           "schema_version": "2.0",  # Hypothetical future version
           "entries": [...]
       }
       with pytest.raises(ValueError) as exc_info:
           generate_audio.load_manifest(temp_path)
       assert "schema_version" in str(exc_info.value).lower()
   ```
   See `tests/test_audio_pipeline.py` lines 214–232 for existing test example.

2. **Run full test suite** to ensure no silent migration bugs:
   ```bash
   pytest -q tests/test_audio_pipeline.py tests/test_manifest_checksum_verification.py
   ```

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

## Test Markers

This project uses pytest markers to organize test execution. All markers are registered in `pytest.ini` and documented here:

### Slow Marker

**Marker:** `@pytest.mark.slow`

**Definition:** Tests with >1 second wallclock duration. Typically includes:
- Build system tests (e.g., `test_build_lto_warnings` running `make clean && make`)
- Asset generation tests (e.g., frame analysis with parametrization)
- File I/O tests with round-trip validation (e.g., PALETTE.DAT operations)

**Behavior:**
- **Default (development):** Skipped in local runs. To skip: `pytest -m "not slow"` (explicitly filter them out).
- **CI:** Always included. CI runs the full test suite including slow tests.
- **Opt-in:** Run only slow tests with `pytest -m slow`.

**Rationale:** Fast feedback loops in development by excluding slow tests; comprehensive validation in CI before merge.

### Playtest Marker

**Marker:** `@pytest.mark.playtest`

**Definition:** Visual integration tests that launch the game in headless mode and validate captured frame sequences (located in `tests/test_visual_playtest.py`).

**Behavior:**
- **Default:** Skipped in most runs. To include: `pytest -m playtest`.
- **CI:** Included in nightly or full regression runs (configured per workflow).
- **Note:** Playtest tests are typically slow and require X11 or headless display; they are separated to avoid blocking fast feedback.

### Serial Marker

**Marker:** `@pytest.mark.serial`

**Definition:** Tests that must run serially (incompatible with pytest-xdist parallel execution).

**Behavior:**
- **Effect:** Marked tests run sequentially even with `-n auto` parallel execution.
- **Use case:** Tests that require exclusive access to shared resources (files, sockets, environment variables).

**Note:** Avoid using `serial` unless absolutely necessary. Prefer test isolation and temporary fixtures (`tmp_path`, `monkeypatch`).

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

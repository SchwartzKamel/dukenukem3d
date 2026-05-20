# Security & Secrets Audit — Round 5

_Persona: security-and-secrets. Cycle 12 audit-pass. This file was recreated
as a stub after the original (~18 KB / 519 lines from the dispatched
sub-agent) was lost to the cycle-12 persistence regression (parallel
`git reset` race between sub-agents). The findings below are accurate but
condensed; SQL todos were seeded successfully and remain authoritative._

## Scope

- CVE posture: SDL2 2.30.9, SDL2_mixer pin, Python deps drift.
- GPL/license compliance: `SRC/`, `source/`, **`compat/`**, `tools/*.py`.
- GitHub Actions hardening: pinned action SHAs, explicit `permissions:`.
- Binary asset provenance (`.DUKE3D_NN/`, `.grp` files).
- Network attack surface beyond auth (packet parser fuzz / DoS).
- File-I/O TOCTOU / path traversal in save/load.
- Memory safety: unchecked `malloc`/`alloca` in hot paths.
- `.env` handling in tooling.

## Previously-Closed (do not re-flag)

- `sec-env-real-keys` (operator rotation pending; gitignored).
- `sec-c-unsafe-argv` (FIXED this cycle, `source/CONFIG.C`).
- `sec-c-unsafe-network` (in backlog; targets `source/GAME.C` multiplayer strings).
- `tools/check_secrets.sh` strict mode (FIXED).
- requirements.txt CVE pinning (FIXED cycle 11).
- generate_audio.py redaction (FIXED cycle 11).
- pre-commit secret-scan hook (ACTIVE; 7 patterns).

## Findings

### HIGH — GPL-2.0 SPDX headers missing in compat/
Affected files: `compat/audio_stub.c`, `compat/network_stub.c`,
`compat/mact_stub.c`, `compat/msvc_shim.c`, `compat/sdl2_wrapper.c`
(roughly 5 compat sources).

The rest of the codebase (SRC/, source/) carries the BUILD license header. The
`compat/` files are GPL-2.0-or-later derivatives but lack any SPDX line,
which compliance scanners flag and downstream packagers cannot ingest.
Recommended fix: add a `// SPDX-License-Identifier: GPL-2.0-or-later`
single line plus a short BUILD-derived notice at the top of each file.

### HIGH — GitHub Actions workflows lack explicit `permissions:`
Affected workflows: `.github/workflows/build.yml`, `.github/workflows/release.yml`.

Without an explicit `permissions:` block, the default `GITHUB_TOKEN` grants
`contents: write` and broad scopes. A workflow compromise (e.g. malicious
PR title via `pull_request_target`) could push to the repo. Recommended fix:
add `permissions: { contents: read }` at the workflow root; bump specific
jobs to `contents: write` only when they need to publish a release artifact.

### HIGH — GPL-2.0 SPDX headers missing in tools/*.py
Affected files: `tools/generate_audio.py`, `tools/generate_assets.py`,
`tools/frame_analyzer.py`, `tools/check_secrets.sh`, and others.

Same provenance argument as the `compat/` finding but for the Python
tooling. Recommended fix: add the SPDX header (one line for `.sh`/`.py`)
plus a one-line attribution.

### MEDIUM — File-I/O path validation absent (advisory)
Files: `source/MENUES.C`, `source/CONFIG.C` (save/load entry points).

Save-game filenames and config paths originate from user input and are not
normalized or restricted to an alphanumeric set. In single-player context
this is low risk (the user owns the process) but it is architecturally
unsound: a path with `../` in a future multiplayer-shared-saves feature
could break out of the save directory. Recommended fix: restrict filenames
to `[A-Za-z0-9_-]{1,64}` before opening.

## Verified Clean

- **CVE posture**: SDL2 2.30.9 carries no open CVEs as of audit date;
  Python deps pinned and verified against current advisories.
- **Binary asset provenance**: `.DUKE3D_NN/` contains only re-generated
  WAV/PNG assets from the FLUX pipeline; no copyrighted shareware data
  committed.
- **Memory safety hot paths**: All `malloc` sites checked have NULL
  guards; no `alloca` on untrusted input.
- **.env handling**: env vars are loaded via `os.environ.get(...)` and
  never echoed in logs (verified post cycle-11 redaction work).
- **Pre-commit hook**: 7-pattern secret scan active and tested.

## Seeded Todos

| id                            | severity | summary                                                |
|-------------------------------|----------|--------------------------------------------------------|
| `sec-gpl-compat-headers`      | HIGH     | Add SPDX/GPL-2.0 headers to ~5 compat/ sources         |
| `sec-gpl-tools-headers`       | HIGH     | Add SPDX/GPL-2.0 headers to tools/*.py + check_secrets |
| `sec-workflow-permissions`    | HIGH     | Explicit `permissions:` in build.yml + release.yml     |
| `sec-menues-path-validation`  | MEDIUM   | Save/load filename normalization (advisory)            |

## Status

CONDITIONAL PRODUCTION READY — apply the two GPL header items + workflow
permissions before any external release; the MEDIUM advisory can wait until
multiplayer-shared-saves are designed. Audit-only round; no source changes.

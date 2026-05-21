# Testing Guide

Duke Nukem 3D testing infrastructure with **70 tests** organized by domain. Tests run in parallel via pytest-xdist by default.

## Quick Start

```bash
# Run all tests (parallel, -n auto)
pytest

# Run without slow tests (recommended for dev)
pytest -m "not slow"

# Run playtesting suite (headless visual validation)
pytest -m playtest

# Run serially (disable xdist parallelism)
pytest -m serial

# Run a specific test
pytest tests/test_audio_playback_roundtrip.py
```

## Test Markers

From `pytest.ini`:

| Marker | Purpose | Default Behavior |
|--------|---------|------------------|
| `slow` | Tests with >1s wallclock duration | Skipped in dev (`-m "not slow"`), always run in CI |
| `playtest` | Visual playtesting — headless game launch + frame validation | Run explicitly (`-m playtest`) |
| `serial` | Must run serially (incompatible with xdist parallelism) | Run with `-m serial` or disable parallelism |

## Test Categories

Tests are auto-discovered by prefix. Primary groupings:

- **hypothesis** (51 @given tests): Property-based tests for pure functions in tools/ using Hypothesis
  - Palette/RGB conversion (_ramp, build_palette, _nearest_color, quantize_image)
  - Lookup table generation (sine table, radar angles, fonts, brightness tables)
  - Manifest verification (SHA256 checksums, schema versions, legacy compatibility)
  - Audio generation (tone, noise, click synthesis with determinism and bounds properties)
  - GRP format (file packing, determinism, round-trip properties)
  - Frame analysis (color histograms, brightness stats, black screen detection, frame difference)
  - All tests use @settings(max_examples=...) with deterministic seeds
- **compat** (1): Compatibility layer behavior  
- **build** (3): Build warnings, asset generation validation, binary artifacts
- **audio** (2): MIDI format, sound encoding
- **engine** (2): Frame analysis, visual playtest
- **grp** (2): GRP format parsing, asset tables
- **manifest** (2): Checksum verification, adoption contracts
- **net** (2): Socket compatibility, handshake timeouts
- **generate** (3): Asset pipeline generation, validation
- **check** (2): Secrets detection (r16 patterns), property validation
- **tables** (1): Pipeline validation
- **network** (1): Multiplayer protocol
- **multiplayer** (1): Protocol correctness
- **demo** (1): Demo format parsing
- **security** (1): Secrets pattern matching
- **visual** (1): Playtest frame capture
- **atomic** (1): Write atomicity
- **allocache**, **anm**, **art**, **asset**, **binary**, **frame**, **install**, **map**, **maxtiles**, **menues**, **palette**, **property**, **sdl**, **se40**, **sound**, **voc** (1 each): Single-file test suites

*See `pytest --collect-only` to list all tests.*

## Session Fixtures

Session-scoped fixtures in `conftest.py` (auto-used):

- `generated_audio_artifacts`: Generates WAV files for audio tests; coordinates across xdist workers via FileLock (filelock-based singleton)
- `headless_run`: Prepares headless game environment for visual playtests
- `temp_manifest_file`: Provides temporary manifest for test isolation

See `tests/test_pytest_xdist_safety.py` for fixture isolation verification under parallel execution.

## Configuration

- **Parallelism**: Pytest-xdist enabled by default (`-n auto`, load-scoped distribution)
- **Fixture Coordination**: FileLock prevents race conditions during session-scoped initialization
- **CI**: All markers run; slow tests included

## Cross-References

- **Test Parametrization Contracts**: `tests/PARAMETRIZATION_CONTRACTS.md` — canonical frame-count parametrization patterns
- **Xdist Safety**: `tests/test_pytest_xdist_safety.py` — fixture isolation validation under parallel execution
- **Sound Manifest Validation**: `conftest.py` — Pydantic v2 models for manifest schema

## Coverage & Status

See `GRIND_LOG` for coverage metrics and recent test run summaries.

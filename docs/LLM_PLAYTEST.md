# LLM Playtest Harness

## Overview

`tools/llm_playtest.py` is an end-to-end vision check for the modern Duke
Nukem 3D port. It reads BMP screenshots captured by the headless playtest
fixture, transcodes sampled frames to PNG for provider compatibility, sends
them to an Azure OpenAI GPT-4o-class vision model, and requires a structured
JSON verdict before declaring the build playable.

The harness is designed to complement the local frame analyzer. The local tests
catch black frames and obvious rendering failures; the LLM pass checks whether a
human-recognizable scene, HUD, and coherent BUILD-engine geometry are visible.

## Environment setup

Copy `.env.example` to `.env` and fill in the LLM playtest values when running
live mode:

```bash
cp .env.example .env
```

Required live-mode variables:

```bash
LLM_PLAYTEST_ENDPOINT=https://<your-azure-openai-resource>.openai.azure.com
LLM_PLAYTEST_MODEL=gpt-4o
LLM_PLAYTEST_API_KEY=<your-azure-openai-key>
```

`LLM_PLAYTEST_MODEL` defaults to `gpt-4o` if omitted. The endpoint must use
HTTPS and resolve in DNS. Error messages redact hostnames to the first label,
for example `api.***`.

If your endpoint already includes an Azure chat completions path, the harness
uses it as-is. Otherwise it builds this URL:

```text
/openai/deployments/<LLM_PLAYTEST_MODEL>/chat/completions?api-version=2024-02-15-preview
```

If that deployment-style URL returns `404 Resource not found`, the harness
automatically retries Azure-compatible fallbacks (`/openai/v1/chat/completions`
and `/models/chat/completions`) before failing.

## Local invocation

Run the offline stub first. It validates that BMP files exist and are loadable,
but does not call the API:

```bash
python3 tools/llm_playtest.py --stub --report out.json
```

To point at a specific capture directory:

```bash
python3 tools/llm_playtest.py \
  --stub \
  --frames-dir captures/ \
  --report out.json
```

Live mode removes `--stub` and requires the three environment variables:

```bash
python3 tools/llm_playtest.py --frames-dir captures/ --report out.json
```

For fully automated gameplay capture on Windows (no foreground-focus keyboard
input), run the engine with:

```bash
DUKE3D_HEADLESS=1
DUKE3D_SKIP_LOGO=1
DUKE3D_AUTOPLAY=1
DUKE3D_SILENT_ERRORS=1
DUKE3D_FRAME_LIMIT=360
DUKE3D_CAPTURE_INTERVAL=3
```

`DUKE3D_AUTOPLAY=1` enables scripted in-engine movement/fire input when
`DUKE3D_HEADLESS=1` is also set.  
For non-headless visual demos, add `DUKE3D_AUTOPLAY_FORCE=1` to force scripted
input.
`DUKE3D_SILENT_ERRORS=1` suppresses blocking Windows error dialogs and keeps
failure details in `atomic_shell_startup.log`.

Exit codes are:

- `0`: overall PASS
- `1`: structured verdict received, but playability criteria failed
- `2`: harness/configuration error, such as no frames, corrupt BMP, missing API
  key in live mode, invalid endpoint, or malformed API response

## Sampling and cost control

By default the harness samples three frames: first, middle, and last. This caps
vision-token spend while still checking startup, mid-run, and final rendering
states.

Useful options:

```bash
--sample-strategy first-middle-last  # default
--sample-strategy evenly             # spread --sample-count over the run
--sample-strategy all                # inspect every BMP; highest cost
--sample-count 3                     # default for non-all strategies
```

Keep `--sample-count` small in live CI. Increasing it raises API cost and test
latency linearly because every selected frame receives its own vision verdict.

## CI integration story

CI should always run stub mode. Stub mode exercises frame discovery, BMP loading,
report writing, and pass aggregation without credentials:

```bash
pytest tests/test_llm_playtest.py -v -m playtest
```

The live test is opt-in. It skips when `LLM_PLAYTEST_API_KEY` is unset, so public
or low-cost jobs can run safely. Enable live mode only in protected environments
with Azure OpenAI secrets configured.

## Report format

Reports are JSON and include:

- `schema_version`
- `mode`: `stub`, `live`, or `error`
- `overall_pass` / `pass`
- `passing_frames` and `required_passing_frames`
- `frames[]` with path, dimensions, per-frame pass flag, and the full verdict
- `criteria` describing per-frame and aggregate rules

On harness errors, the report uses `mode: "error"`, `overall_pass: false`, and an
`error` string. Corrupt sampled BMPs are treated as harness errors because the
vision check cannot safely reason about unreadable captures.

## Failure-mode interpretation

- `renders_ok=false`: the frame is black, all one color, garbage, or otherwise
  not a valid render.
- `hud_visible=false`: the model cannot identify a status bar, weapon, ammo,
  health, or comparable HUD element.
- `geometry_coherent=false`: walls, floors, ceilings, sprites, or level layout
  are not identifiable.
- `no_error_overlays=false`: the image appears to contain SDL popups, tracebacks,
  debug dumps, or other overlays instead of gameplay.
- `confidence < 0.7`: the model is not confident enough to count the frame.

Use the per-frame `description` field to decide whether the issue is game
rendering, capture timing, missing assets, or test infrastructure.

## Pass-criteria rubric

Each frame passes only when all four booleans are true and confidence is at
least `0.7`:

```python
renders_ok and hud_visible and geometry_coherent and no_error_overlays
```

The overall playtest passes when at least two thirds of sampled frames pass. For
the default three-frame sample, that means at least two frames. If fewer than
three frames are sampled, every sampled frame must pass.

This rubric intentionally requires multiple successful frames so a single lucky
or stale capture cannot mask a broken startup or shutdown path.

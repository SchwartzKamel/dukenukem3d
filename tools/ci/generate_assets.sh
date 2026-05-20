#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Shared asset generation script for CI workflows (Linux and Windows targets)
# Usage: bash tools/ci/generate_assets.sh [--ai]

set -euo pipefail
trap 'echo "Error on line $LINENO"; exit 1' ERR

FLUX_ENDPOINT="${FLUX_ENDPOINT:-}"
FLUX_API_KEY="${FLUX_API_KEY:-}"
FLUX_MODEL="${FLUX_MODEL:-}"
AUDIO_ENDPOINT="${AUDIO_ENDPOINT:-}"
AUDIO_API_KEY="${AUDIO_API_KEY:-}"
AUDIO_MODEL="${AUDIO_MODEL:-}"

# Check if --ai flag is provided to enable AI generation
ENABLE_AI=false
if [ "$1" = "--ai" ]; then
  ENABLE_AI=true
fi

# perf-ci-parallel-spawn: parallel audio+assets spawn (cycle 48)
# Both scripts parallelize internally; spawn them in background to avoid serial sum of wallclock.
# Error handling: capture exit codes and exit with failure if either script fails.

# Determine audio generation command
if [ "$ENABLE_AI" = "true" ] && [ -n "$AUDIO_ENDPOINT" ] && [ -n "$AUDIO_API_KEY" ]; then
  AUDIO_CMD="python3 tools/generate_audio.py"
  AUDIO_MSG="🔊 Generating AI audio (GPT Audio 1.5)..."
else
  AUDIO_CMD="python3 tools/generate_audio.py --no-ai"
  AUDIO_MSG="🔇 No audio API keys — generating silence stubs"
fi

# Determine assets generation command
if [ "$ENABLE_AI" = "true" ] && [ -n "$FLUX_ENDPOINT" ] && [ -n "$FLUX_API_KEY" ]; then
  ASSETS_CMD="python3 tools/generate_assets.py"
  ASSETS_MSG="🎨 Generating AI textures (FLUX.2-pro)..."
else
  ASSETS_CMD="python3 tools/generate_assets.py --no-ai"
  ASSETS_MSG="🖌️ No FLUX API keys — generating procedural assets"
fi

# Log messages and spawn both scripts in parallel
echo "$AUDIO_MSG"
echo "$ASSETS_MSG"
$AUDIO_CMD &
AUDIO_PID=$!
$ASSETS_CMD &
ASSETS_PID=$!

# Wait for both and capture exit codes
wait $AUDIO_PID
AUDIO_RC=$?
wait $ASSETS_PID
ASSETS_RC=$?

# Exit with failure if either script failed
if [ $AUDIO_RC -ne 0 ] || [ $ASSETS_RC -ne 0 ]; then
  echo "generate_assets.sh: audio_rc=$AUDIO_RC assets_rc=$ASSETS_RC" >&2
  exit 1
fi

# Get GRP file size using portable method (works on Linux and macOS)
if [ -f DUKE3D.GRP ]; then
  GRP_SIZE=$(wc -c < DUKE3D.GRP)
  echo "📦 GRP size: $GRP_SIZE bytes"
else
  echo "⚠️  DUKE3D.GRP not found"
fi

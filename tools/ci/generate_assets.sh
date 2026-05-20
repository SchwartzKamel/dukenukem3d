#!/bin/bash
# Shared asset generation script for CI workflows (Linux and Windows targets)
# Usage: bash tools/ci/generate_assets.sh [--ai]

set -e

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

# Generate audio
if [ "$ENABLE_AI" = "true" ] && [ -n "$AUDIO_ENDPOINT" ] && [ -n "$AUDIO_API_KEY" ]; then
  echo "🔊 Generating AI audio (GPT Audio 1.5)..."
  python3 tools/generate_audio.py
else
  echo "🔇 No audio API keys — generating silence stubs"
  python3 tools/generate_audio.py --no-ai
fi

# Generate assets/textures
if [ "$ENABLE_AI" = "true" ] && [ -n "$FLUX_ENDPOINT" ] && [ -n "$FLUX_API_KEY" ]; then
  echo "🎨 Generating AI textures (FLUX.2-pro)..."
  python3 tools/generate_assets.py
else
  echo "🖌️ No FLUX API keys — generating procedural assets"
  python3 tools/generate_assets.py --no-ai
fi

echo "📦 GRP size: $(stat -c%s DUKE3D.GRP) bytes"

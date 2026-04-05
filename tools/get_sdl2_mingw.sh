#!/bin/bash
# tools/get_sdl2_mingw.sh — Download SDL2 MinGW dev libraries (32-bit)
set -euo pipefail

# Read version from build.mk (single source of truth)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SDL2_VERSION=$(grep '^SDL2_VERSION' "$ROOT_DIR/build.mk" | head -1 | sed 's/.*= *//')

if [ -z "$SDL2_VERSION" ]; then
    echo "ERROR: Could not read SDL2_VERSION from build.mk"
    exit 1
fi

TARBALL="SDL2-devel-${SDL2_VERSION}-mingw.tar.gz"
URL="https://github.com/libsdl-org/SDL/releases/download/release-${SDL2_VERSION}/${TARBALL}"
EXTRACT_DIR="${ROOT_DIR}/SDL2-${SDL2_VERSION}"

if [ -d "$EXTRACT_DIR/i686-w64-mingw32" ]; then
    echo "SDL2 ${SDL2_VERSION} already downloaded"
else
    echo "Downloading SDL2 ${SDL2_VERSION} for MinGW..."
    wget -q "$URL" -O "/tmp/${TARBALL}"
    tar xzf "/tmp/${TARBALL}" -C "$ROOT_DIR"
    rm -f "/tmp/${TARBALL}"
    echo "SDL2 ${SDL2_VERSION} extracted to ${EXTRACT_DIR}"
fi

# Output paths for CI (32-bit)
echo "SDL2_DIR=${EXTRACT_DIR}"
echo "SDL2_WIN_CFLAGS=-I${EXTRACT_DIR}/i686-w64-mingw32/include/SDL2"
echo "SDL2_WIN_LIBS=-L${EXTRACT_DIR}/i686-w64-mingw32/lib -lmingw32 -lSDL2main -lSDL2"

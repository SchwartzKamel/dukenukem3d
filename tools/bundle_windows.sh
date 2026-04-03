#!/bin/bash
# tools/bundle_windows.sh — Bundle DLLs for self-contained Windows package
set -euo pipefail

DEST="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Read SDL2 version from build.mk
SDL2_VERSION=$(grep '^SDL2_VERSION' "$ROOT_DIR/build.mk" | head -1 | sed 's/.*= *//')
SDL2_DIR="${ROOT_DIR}/SDL2-${SDL2_VERSION}"

echo "=== Bundling Windows DLLs to ${DEST} ==="

# 1. SDL2.dll
SDL2_DLL="${SDL2_DIR}/x86_64-w64-mingw32/bin/SDL2.dll"
if [ -f "$SDL2_DLL" ]; then
    cp "$SDL2_DLL" "$DEST/"
    echo "  + SDL2.dll"
else
    echo "  ! SDL2.dll not found at ${SDL2_DLL}"
    exit 1
fi

# 2. MinGW runtime DLLs
MINGW_DLLS="libwinpthread-1.dll libgcc_s_seh-1.dll libstdc++-6.dll"
for dll in $MINGW_DLLS; do
    found=""
    # Search common locations
    for searchpath in \
        /usr/lib/gcc/x86_64-w64-mingw32/*/  \
        /usr/x86_64-w64-mingw32/lib/ \
        /usr/x86_64-w64-mingw32/bin/ \
        "$(dirname "$(which x86_64-w64-mingw32-gcc 2>/dev/null)")/../x86_64-w64-mingw32/lib/" \
        "$(dirname "$(which x86_64-w64-mingw32-gcc 2>/dev/null)")/../lib/"; do
        if [ -f "${searchpath}${dll}" ]; then
            cp "${searchpath}${dll}" "$DEST/"
            echo "  + ${dll} (from ${searchpath})"
            found=1
            break
        fi
    done
    if [ -z "$found" ]; then
        echo "  - ${dll} not found (may be statically linked)"
    fi
done

echo "=== DLL bundling complete ==="
ls -la "$DEST"/*.dll 2>/dev/null || echo "  (no DLLs found)"

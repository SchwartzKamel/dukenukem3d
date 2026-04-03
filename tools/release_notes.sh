#!/bin/bash
# tools/release_notes.sh — Auto-generate release notes from git log
set -euo pipefail

CURRENT_TAG="${1:-$(git describe --tags --abbrev=0 2>/dev/null || echo HEAD)}"
PREV_TAG="$(git describe --tags --abbrev=0 "${CURRENT_TAG}^" 2>/dev/null || echo "")"

echo "## Duke3D: Neon Noir ${CURRENT_TAG}"
echo ""

if [ -n "$PREV_TAG" ]; then
    echo "### Changes since ${PREV_TAG}"
    RANGE="${PREV_TAG}..${CURRENT_TAG}"
else
    echo "### Changes"
    RANGE="${CURRENT_TAG}"
fi
echo ""

# Group commits by type
for prefix in "Fix" "Add" "Update" "Security" "Make" "Unified"; do
    commits=$(git log --oneline "$RANGE" --grep="^${prefix}" --format="- %s" 2>/dev/null || true)
    if [ -n "$commits" ]; then
        echo "$commits"
    fi
done

# Remaining commits not matching above prefixes
remaining=$(git log --oneline "$RANGE" --format="- %s" --invert-grep \
    --grep="^Fix" --grep="^Add" --grep="^Update" --grep="^Security" --grep="^Make" --grep="^Unified" 2>/dev/null || true)
if [ -n "$remaining" ]; then
    echo "$remaining"
fi

echo ""
echo "### Downloads"
echo "- **Linux x64**: \`duke3d-${CURRENT_TAG}-linux-x64.tar.gz\`"
echo "- **Windows x64**: \`duke3d-${CURRENT_TAG}-windows-x64.zip\`"
echo ""
echo "### Quick Start"
echo "Extract and run \`duke3d\` (Linux) or \`duke3d.exe\` (Windows)."
echo "DUKE3D.GRP (game assets) is included."

#!/bin/sh
# tools/check_secrets.sh
# Pre-commit hook to detect and prevent accidental secret commits.
# Scans staged changes for high-risk patterns like API keys.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

EXIT_CODE=0

echo "🔍 Scanning staged changes for potential secrets..."

# Get staged files and content
STAGED_DIFF=$(git diff --cached -U0 2>/dev/null)

if [ -z "$STAGED_DIFF" ]; then
    exit 0
fi

# Check for actual secret values (long alphanumeric/base64-like strings after API_KEY=)
# Exclude files: .env.example (template), .gitignore (config), check_secrets.sh (this script)
if echo "$STAGED_DIFF" | grep -E '^\+.*_API_KEY=' | \
   grep -v '\.env\.example' | \
   grep -v '\.gitignore' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '_API_KEY=\$' | \
   grep -v '_API_KEY=<' | \
   grep -v '_API_KEY=your' | \
   grep -E '_API_KEY=[a-zA-Z0-9+/]{32,}' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential API key in staged changes!"
    echo ""
    echo "Staged files with API_KEY patterns:"
    git diff --cached --name-only | grep -v check_secrets | grep -v "\.env\.example"
    echo ""
    echo "If this is a real secret, STOP and:"
    echo "  1. Unstage: git reset HEAD <file>"
    echo "  2. Remove from .env: rm/edit your .env (don't commit it)"
    echo "  3. If added to history, rotate the key immediately"
    echo ""
    EXIT_CODE=1
fi

# Check for common token prefixes (sk-, ghp-, xoxb-, etc.) that aren't in comments
if echo "$STAGED_DIFF" | grep -E '^\+(.*)(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|xoxb-[a-zA-Z0-9]{20,})' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential token pattern in staged changes!"
    echo "   Check staged files for token prefixes (sk-, ghp_, xoxb-)"
    EXIT_CODE=1
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ No obvious secrets detected in staged changes"
fi

exit $EXIT_CODE

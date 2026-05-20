#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
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

# Check for common token prefixes (sk-, ghp_, xoxb-, etc.) that aren't in comments
if echo "$STAGED_DIFF" | grep -E '^\+(.*)(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|xoxb-[a-zA-Z0-9]{20,})' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential token pattern in staged changes!"
    echo "   Check staged files for token prefixes (sk-, ghp_, xoxb-)"
    EXIT_CODE=1
fi

# Check for AWS access keys (AKIA prefix)
if echo "$STAGED_DIFF" | grep -E 'AKIA[0-9A-Z]{16}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential AWS access key in staged changes!"
    echo "   Check staged files for AKIA pattern"
    EXIT_CODE=1
fi

# Check for GitHub fine-grained tokens
if echo "$STAGED_DIFF" | grep -E 'github_pat_[0-9A-Za-z_]{50,}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential GitHub fine-grained token in staged changes!"
    echo "   Check staged files for github_pat_ pattern"
    EXIT_CODE=1
fi

# Check for SSH private keys (multiline patterns - match +/-/space at start since it's git diff output)
if echo "$STAGED_DIFF" | grep -E '^[\+\-\@].*BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential SSH private key in staged changes!"
    echo "   Check staged files for BEGIN PRIVATE KEY pattern"
    EXIT_CODE=1
fi

# Check for Stripe live keys
if echo "$STAGED_DIFF" | grep -E 'sk_live_[0-9a-zA-Z]{24,}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Stripe live key in staged changes!"
    echo "   Check staged files for sk_live_ pattern"
    EXIT_CODE=1
fi

# Check for Twilio account/API keys
if echo "$STAGED_DIFF" | grep -E '(AC|SK)[a-f0-9]{32}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Twilio key in staged changes!"
    echo "   Check staged files for Twilio AC/SK pattern"
    EXIT_CODE=1
fi

# Check for Azure connection strings and patterns (DefaultEndpointsProtocol, endpoint URIs)
if echo "$STAGED_DIFF" | grep -E '(DefaultEndpointsProtocol|\.database\.windows\.net|\.blob\.core\.windows\.net)' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Azure connection string pattern in staged changes!"
    echo "   Check staged files for Azure endpoint patterns"
    EXIT_CODE=1
fi

# Check for Azure AccountKey with base64 content (88 chars is typical for account keys)
if echo "$STAGED_DIFF" | grep -E 'AccountKey=[A-Za-z0-9+/]{88}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Azure account key (88-char base64) in staged changes!"
    echo "   Check staged files for AccountKey= pattern"
    EXIT_CODE=1
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ No obvious secrets detected in staged changes"
fi

exit $EXIT_CODE

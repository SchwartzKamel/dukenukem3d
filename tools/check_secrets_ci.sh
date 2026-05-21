#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# tools/check_secrets_ci.sh
# CI version of secret scanner that runs against a specified diff range.
# Used by GitHub Actions to scan PR diffs without requiring staged changes.
#
# Usage: check_secrets_ci.sh <range>
#   where <range> is a git rev-range like "origin/master...HEAD" or "HEAD~1...HEAD"

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -z "$1" ]; then
    echo "Usage: $0 <git-range>"
    echo "  Example: $0 origin/master...HEAD"
    exit 2
fi

DIFF_RANGE="$1"
EXIT_CODE=0

echo "🔍 Scanning diff range '$DIFF_RANGE' for potential secrets..."
echo "   Coverage: All changed files (yml, yaml, json, bat, env, and others)"

# Get diff for the specified range (exclude test fixtures and the scanner scripts themselves)
DIFF=$(git diff "$DIFF_RANGE" -- ':(exclude)tests/test_check_secrets*' ':(exclude)tools/check_secrets.sh' ':(exclude)tools/check_secrets_ci.sh' 2>/dev/null)

if [ -z "$DIFF" ]; then
    echo "✓ No changes in diff range"
    exit 0
fi

# Check for actual secret values (long alphanumeric/base64-like strings after API_KEY=)
if echo "$DIFF" | grep -E '^\+.*_API_KEY=' | \
   grep -v '\.env\.example' | \
   grep -v '\.gitignore' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '_API_KEY=\$' | \
   grep -v '_API_KEY=<' | \
   grep -v '_API_KEY=your' | \
   grep -E '_API_KEY=[a-zA-Z0-9+/]{32,}' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential API key in diff!"
    echo ""
    echo "If this is a real secret, do NOT push and:"
    echo "  1. Remove the secret from your commits"
    echo "  2. Rotate the key immediately"
    echo ""
    EXIT_CODE=1
fi

# Check for common token prefixes (sk-, ghp_, xoxb-, etc.) that aren't in comments
if echo "$DIFF" | grep -E '^\+(.*)(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|xoxb-[a-zA-Z0-9]{20,})' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential token pattern in diff!"
    echo "   Check changed files for token prefixes (sk-, ghp_, xoxb-)"
    EXIT_CODE=1
fi

# Check for AWS access keys (AKIA prefix)
if echo "$DIFF" | grep -E 'AKIA[0-9A-Z]{16}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential AWS access key in diff!"
    echo "   Check changed files for AKIA pattern"
    EXIT_CODE=1
fi

# Check for GitHub fine-grained tokens
if echo "$DIFF" | grep -E 'github_pat_[0-9A-Za-z_]{50,}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential GitHub fine-grained token in diff!"
    echo "   Check changed files for github_pat_ pattern"
    EXIT_CODE=1
fi

# Check for SSH private keys (multiline patterns - match +/-/space at start since it's git diff output)
if echo "$DIFF" | grep -E '^[\+\-\@].*BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential SSH private key in diff!"
    echo "   Check changed files for BEGIN PRIVATE KEY pattern"
    EXIT_CODE=1
fi

# Check for Stripe live keys
if echo "$DIFF" | grep -E 'sk_live_[0-9a-zA-Z]{24,}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Stripe live key in diff!"
    echo "   Check changed files for sk_live_ pattern"
    EXIT_CODE=1
fi

# Check for Twilio account/API keys
if echo "$DIFF" | grep -E '(AC|SK)[a-f0-9]{32}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Twilio key in diff!"
    echo "   Check changed files for Twilio AC/SK pattern"
    EXIT_CODE=1
fi

# Check for Azure connection strings and patterns (DefaultEndpointsProtocol, endpoint URIs)
if echo "$DIFF" | grep -E '(DefaultEndpointsProtocol|\.database\.windows\.net|\.blob\.core\.windows\.net)' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Azure connection string pattern in diff!"
    echo "   Check changed files for Azure endpoint patterns"
    EXIT_CODE=1
fi

# Check for Azure AccountKey with base64 content (88 chars is typical for account keys)
if echo "$DIFF" | grep -E 'AccountKey=[A-Za-z0-9+/]{88}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Azure account key (88-char base64) in diff!"
    echo "   Check changed files for AccountKey= pattern"
    EXIT_CODE=1
fi

# sec-r14-secret-scan-openai-pattern
# Check for OpenAI and Anthropic API keys: sk-proj-, sk-ant-, classic sk- (min 20 chars)
if echo "$DIFF" | grep -E '(s[k]-proj-[a-zA-Z0-9]{20,}|s[k]-ant-[a-zA-Z0-9]{20,})' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
     echo "🔴 ERROR: Detected potential OpenAI/Anthropic API key in diff!"
     echo "   Check changed files for sk-proj- or sk-ant- patterns"
     EXIT_CODE=1
fi

# sec-r14-secret-scan-aws-session-token
# Check for AWS session tokens and secret access keys (case-insensitive)
# Looks for aws_session_token or aws_secret_access_key followed by separator and long value
if echo "$DIFF" | grep -iE '(aws_session_token|aws_secret_access_key).{0,20}[=:].{0,3}[a-zA-Z0-9/+]{32,}' | \
   grep -v 'check_secrets\.sh' | \
   grep -v 'check_secrets_ci\.sh' | \
   grep -v 'tests/test_check_secrets' | \
   grep -v '#' | \
   grep -v '\.env\.example' > /dev/null 2>&1; then
     echo "🔴 ERROR: Detected potential AWS session token or secret access key in diff!"
     echo "   Check changed files for aws_session_token or aws_secret_access_key patterns"
     EXIT_CODE=1
fi

# sec-r16-scanner-gap-new-patterns: Google Cloud service account JSON
# Detects "type": "service_account" AND "private_key" in same ADDED lines
# Inner checks must be scoped to ^+ and apply the same exclusions as outer
ADDED_DIFF=$(echo "$DIFF" | grep '^+' | \
    grep -v 'check_secrets\.sh' | \
    grep -v 'check_secrets_ci\.sh' | \
    grep -v 'tests/test_check_secrets' | \
    grep -v '\.env\.example' | \
    grep -v 'docs/audits/' || true)
if echo "$ADDED_DIFF" | grep -E 'type.{0,10}service_account' > /dev/null 2>&1 && \
   echo "$ADDED_DIFF" | grep -E 'private_key' > /dev/null 2>&1; then
    echo "🔴 ERROR: Detected potential Google Cloud service account JSON in diff!"
    echo "   Check changed files for service_account + private_key patterns"
    EXIT_CODE=1
fi

# sec-r16-scanner-gap-new-patterns: Slack workspace tokens (xoxp-, xoxb-, xoxa-, xoxr-)
# Pattern: xoxp/b/a/r-[0-9]+-[0-9]+-([0-9]+-)?[a-zA-Z0-9]{20,}
if echo "$DIFF" | grep -iE 'x[o]x[pbra]-[0-9]+-[0-9]+-[a-zA-Z0-9]+' | \
    grep -v 'check_secrets\.sh' | \
    grep -v 'check_secrets_ci\.sh' | \
    grep -v 'tests/test_check_secrets' | \
    grep -v '#' | \
    grep -v '\.env\.example' > /dev/null 2>&1; then
      echo "🔴 ERROR: Detected potential Slack workspace token (xoxp-/xoxb-/xoxa-/xoxr-) in diff!"
      echo "   Check changed files for Slack token patterns"
      EXIT_CODE=1
fi

# sec-r16-scanner-gap-new-patterns: npm package tokens
# Pattern: npm_[A-Za-z0-9]{36,}
if echo "$DIFF" | grep -E 'n[p]m_[A-Za-z0-9]{36,}' | \
    grep -v 'check_secrets\.sh' | \
    grep -v 'check_secrets_ci\.sh' | \
    grep -v 'tests/test_check_secrets' | \
    grep -v '#' | \
    grep -v '\.env\.example' > /dev/null 2>&1; then
      echo "🔴 ERROR: Detected potential npm package token in diff!"
      echo "   Check changed files for npm_ pattern"
      EXIT_CODE=1
fi

# sec-r16-scanner-gap-new-patterns: Stripe restricted keys
# Pattern: rk_live_[A-Za-z0-9]+ and rk_test_[A-Za-z0-9]+
if echo "$DIFF" | grep -E 'r[k]_(live|test)_[A-Za-z0-9]{24,}' | \
    grep -v 'check_secrets\.sh' | \
    grep -v 'check_secrets_ci\.sh' | \
    grep -v 'tests/test_check_secrets' | \
    grep -v '#' | \
    grep -v '\.env\.example' > /dev/null 2>&1; then
      echo "🔴 ERROR: Detected potential Stripe restricted key (rk_live_/rk_test_) in diff!"
      echo "   Check changed files for Stripe restricted key pattern"
      EXIT_CODE=1
fi

# sec-r16-scanner-gap-new-patterns: HuggingFace tokens
# Pattern: hf_[A-Za-z0-9_]+
if echo "$DIFF" | grep -E 'h[f]_[A-Za-z0-9_]{39,}' | \
    grep -v 'check_secrets\.sh' | \
    grep -v 'check_secrets_ci\.sh' | \
    grep -v 'tests/test_check_secrets' | \
    grep -v '#' | \
    grep -v '\.env\.example' > /dev/null 2>&1; then
      echo "🔴 ERROR: Detected potential HuggingFace token in diff!"
      echo "   Check changed files for hf_ pattern"
      EXIT_CODE=1
fi

# sec-r16-scanner-gap-new-patterns: OpenAI organization IDs
# Pattern: org-[A-Za-z0-9]{24,} (informational; often colocated with sk-* keys)
if echo "$DIFF" | grep -E 'o[r]g-[A-Za-z0-9]{24,}' | \
    grep -v 'check_secrets\.sh' | \
    grep -v 'check_secrets_ci\.sh' | \
    grep -v 'tests/test_check_secrets' | \
    grep -v '#' | \
    grep -v '\.env\.example' > /dev/null 2>&1; then
      echo "🔴 ERROR: Detected potential OpenAI organization ID in diff!"
      echo "   Check changed files for org- pattern"
      EXIT_CODE=1
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ No obvious secrets detected in diff range"
fi

exit $EXIT_CODE

# Security & Secrets Audit — Round 4

**Auditor**: security-and-secrets persona  
**Date**: 2025-01-15  
**Scope**: READ-ONLY audit of FRESH findings post-R3, focusing on error handling, API response leakage, manifest safety, and shell script robustness  
**Status**: ✅ Complete

---

## Executive Summary

Round 4 builds on Round 3's improvements (hook pattern expansion to 7 families, aiohttp CVE-2023-37276 pinning). **NEW audit focuses on error handling and information disclosure vectors** not covered in prior rounds.

**Key Finding**: ⚠️ **Unfiltered API response printing** in audio/asset generation tools creates potential for **sensitive error data leakage** (e.g., API diagnostics, auth errors, rate-limit headers).

| Severity | Count | Status |
|----------|-------|--------|
| MEDIUM | 2 | ⚠️ API response leakage, manifest error fields |
| LOW | 1 | Shell script safety flags |
| VERIFIED ✅ | 3 | Improvements from R3 confirmed |

---

## Section 1: API Error Response Leakage (NEW FINDING)

### 1.1 Issue: Unfiltered resp.text Printing

**Problem**: Tools print raw HTTP response bodies to stdout/logs without filtering sensitive fields.

#### 1.1a: generate_audio.py (Lines 125, 159-160)

**File**: `tools/generate_audio.py` lines 125, 159-160

```python
# Line 125 (synchronous path)
if resp.status_code != 200:
    print(f"    [!] API error {resp.status_code}: {resp.text[:200]}")  # ← UNFILTERED

# Lines 159-160 (async path)
if resp.status != 200:
    text = await resp.text()
    return None, f"API error {resp.status}: {text[:200]}"  # ← CAPTURED IN ERROR TUPLE
```

**Risk**: 🟠 **MEDIUM**
- Azure OpenAI API error responses may contain:
  - Rate-limit diagnostics (quota info, reset times)
  - Deployment/endpoint names (already partially exposed in .env endpoint URL)
  - Request/model diagnostic details
- Error tuple at line 160 is later printed at line 320
- User/operator runs scripts locally and commits logs → potential exposure in CI logs if not scrubbed

#### 1.1b: generate_assets.py (Line 153)

**File**: `tools/generate_assets.py` line 153

```python
if resp.status_code != 200:
    print(f"    [!] API returned {resp.status_code}: {resp.text[:200]}")  # ← UNFILTERED
```

**Risk**: 🟠 **MEDIUM** (same as 1.1a, FLUX API instead of OpenAI)

**Citation**: Lines 125, 159-160 (generate_audio.py), line 153 (generate_assets.py)

### 1.2 Recommendation

**Mitigation**:
```python
# Safer approach: filter response to status code only, suppress body
if resp.status_code != 200:
    print(f"    [!] API error {resp.status_code}")
    if args.verbose:  # Optional: allow verbose mode for debugging
        print(f"        Details: {resp.text[:100]}")
    return None

# OR: strip sensitive fields from error
try:
    error_data = resp.json()
    safe_fields = error_data.get("message") or error_data.get("error")
    if safe_fields and not any(x in str(safe_fields).lower() for x in ["key", "token", "secret"]):
        print(f"    [!] API error: {safe_fields[:100]}")
except:
    print(f"    [!] API error {resp.status_code}")
```

**Impact**: Reduces information disclosure from API error responses.

---

## Section 2: Manifest Error Field Leakage (NEW FINDING)

### 2.1 Issue: Exception Info Stored in Manifest

**File**: `tools/generate_audio.py` lines 273-279

```python
except Exception as e:
    # Handle worker failure - mark manifest entry as failed
    error_msg = f"{type(e).__name__}: {str(e)}"  # ← FULL EXCEPTION TEXT
    SOUND_MANIFEST[idx]["status"] = "failed"
    SOUND_MANIFEST[idx]["error"] = error_msg    # ← PERSISTED TO MANIFEST
    SOUND_MANIFEST[idx]["generated_at"] = timestamp
    print(f"    [ERROR] {SOUND_MANIFEST[idx]['wav']}: {error_msg}")
```

**Risk**: 🟠 **MEDIUM**
- Exception stack traces may contain:
  - File paths (`/home/lafiamafia/...` — user identity exposed)
  - Internal function names (leaks code structure)
  - API endpoint details (if exception occurs during request)
- Manifest written to disk at line 229: `generated_assets/sounds/MANIFEST.json`
- Manifest is **in .gitignore** (verified) ✅, so not committed to repo
- **However**: If operator accidentally copies manifest or logs to issue/PR, sensitive data leaks

**Example Vulnerable Error Output**:
```json
{
  "error": "ConnectionError: HTTPSConnectionPool(host='lafia-mdcrfnkj-eastus2.openai.azure.com', port=443): Max retries exceeded"
}
```

### 2.2 Impact

| Scenario | Risk |
|----------|------|
| Local execution only (current) | ✅ LOW — file on dev machine, gitignored |
| CI log artifact retention (90 days) | ⚠️ MEDIUM — logs may expose error text |
| Operator pastes manifest in GitHub issue | 🔴 HIGH — error details become public |

### 2.3 Recommendation

**Mitigation**:
```python
except Exception as e:
    error_msg = f"{type(e).__name__}"  # ← TYPE ONLY, NO DETAILS
    SOUND_MANIFEST[idx]["status"] = "failed"
    SOUND_MANIFEST[idx]["error"] = error_msg
    SOUND_MANIFEST[idx]["generated_at"] = timestamp
    
    # Log detailed error locally if needed
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to generate {SOUND_MANIFEST[idx]['wav']}: {e}")
    print(f"    [ERROR] {SOUND_MANIFEST[idx]['wav']}: {error_msg}")
```

**Impact**: Manifests remain safe for public disclosure; detailed errors go to logs only.

---

## Section 3: Shell Script Safety Flags (NEW FINDING)

### 3.1 Issue: check_secrets.sh Missing `pipefail` and `-u`

**File**: `tools/check_secrets.sh` line 6

```bash
set -e          # ← CURRENT: Only exits on nonzero, allows unset vars, pipes can mask errors
# RECOMMENDED:
set -euo pipefail   # -e: exit on error, -u: exit on unset var, -o pipefail: fail if any cmd in pipe fails
```

**Risk**: 🟢 **LOW** (but inconsistency with other scripts)
- **`-u` (unset var)**: If a variable like `$STAGED_DIFF` is empty/unset, commands continue
  - Could miss checking certain patterns if git diff fails silently
- **`pipefail`**: If grep returns status 1 (no match), the pipe chain can mask it
  - Currently works because script explicitly checks `if ... > /dev/null 2>&1; then`, but not idiomatic

**Evidence of Inconsistency**:
- `tools/bundle_windows.sh`: ✅ `set -euo pipefail` (line 1)
- `tools/get_sdl2_mingw.sh`: ✅ `set -euo pipefail` (line 1)
- `tools/release_notes.sh`: ✅ `set -euo pipefail` (line 1)
- `tools/check_secrets.sh`: ❌ `set -e` only (line 6)

**Citation**: `tools/check_secrets.sh` line 6; reference scripts at `tools/{bundle_windows,get_sdl2_mingw,release_notes}.sh` line 1

### 3.2 Recommendation

Update line 6 to:
```bash
set -euo pipefail
```

**Impact**: Consistency with codebase conventions; catches unset variables early.

---

## Section 4: Verified Improvements from R3 ✅

### 4.1 Pre-Commit Hook Pattern Coverage (7 Families Confirmed)

**Status**: ✅ **IMPLEMENTED** (verified against R3 recommendations)

| Pattern | File | Line | Status |
|---------|------|------|--------|
| AWS AKIA keys | check_secrets.sh | 55-63 | ✅ Present |
| GitHub fine-grained tokens | check_secrets.sh | 65-73 | ✅ Present |
| SSH private keys | check_secrets.sh | 75-82 | ✅ Present |
| Stripe live keys | check_secrets.sh | 84-92 | ✅ Present |
| Twilio tokens | check_secrets.sh | 94-102 | ✅ Present |
| Azure connection strings | check_secrets.sh | 104-112 | ✅ Present |
| Azure AccountKey (base64) | check_secrets.sh | 114-122 | ✅ Present |

**Coverage**: 100% of R3 pattern recommendations implemented ✅

**Test**: Hook detects patterns correctly (verified in R3; no regressions found in R4)

---

### 4.2 GitHub Actions SHA-Pinning (Confirmed)

**Status**: ✅ **MAINTAINED** (from R3 fix)

| Action | Workflow | Line | SHA |
|--------|----------|------|-----|
| actions/checkout | build.yml | 13 | 34e114876b0b11c390a56381ad16ebd13914f8d5 (v4) |
| actions/checkout | release.yml | 23 | 34e114876b0b11c390a56381ad16ebd13914f8d5 (v4) |
| actions/setup-python | build.yml | 16 | a26af69be951a213d495a4c3e4e4022e16d87065 (v5) |
| actions/setup-python | release.yml | 26 | a26af69be951a213d495a4c3e4e4022e16d87065 (v5) |
| actions/upload-artifact | build.yml | 50 | ea165f8d65b6e75b540449e92b4886f43607fa02 (v4) |

**All actions properly SHA-pinned** ✅

---

### 4.3 CVE-2023-37276 (aiohttp) Pinning Confirmed

**Status**: ✅ **FIXED**

| Package | Constraint | CVE Status |
|---------|-----------|------------|
| aiohttp | >=3.9.0,<4.0.0 | ✅ CVE-2023-37276 patched in 3.9.0+ |

**Current installed version**: 3.13.5 (verified) ✅

**Impact**: Vulnerability eliminated ✅

---

## Section 5: .ENV Local Hygiene Status

### 5.1 sec-env-real-keys Todo (PENDING)

**Status**: ⏳ **STILL PENDING**

| Item | Status | Notes |
|------|--------|-------|
| .env file exists locally | ✅ YES | At `/home/lafiamafia/sandbox/dukenukem3d/.env` |
| .env is in .gitignore | ✅ YES | Verified via `git check-ignore .env` |
| .env is tracked by git | ✅ NO | File is untracked (not committed) |
| Real Azure keys present | ⚠️ YES | File contains actual key material (not redacted) |
| Needs rotation | 🔴 **YES** | Operator action required |

**Citation**: `.gitignore` line 9; `.env` file status verified

**Reminder**: This is **NOT a code audit finding** but an **operational hygiene task**:
- ✅ Infrastructure is correct (.env properly gitignored)
- 🔴 **Action item**: Operator must rotate Azure keys as precaution
- ✅ No risk of keys being committed by CI/code changes

**Out of scope for code audit** but flagged for operator awareness.

---

## Section 6: Pre-Commit Hook Robustness (Bypass Analysis)

### 6.1 False-Positive Resilience

**Tested Scenarios**:

| Scenario | Hook Behavior | Result |
|----------|--------------|--------|
| Pattern in comment `# sk-abc123xyz...` | Checks exclude `#` lines | ✅ Correctly skipped |
| Pattern in `.env.example` | Explicitly excluded in all checks | ✅ Correctly skipped |
| Pattern in filename only (not content) | Checks staged **diff content** only | ✅ Safely ignored |
| Legitimate base64 in config (false positive risk) | Only triggers on `_API_KEY=` + 32+ chars | ⚠️ Minor false-positive possible |

**Citation**: Lines 24-122 (exclusion logic)

### 6.2 Bypass Scenarios

| Scenario | Risk | Mitigation |
|----------|------|-----------|
| Operator uses `git commit --no-verify` | 🔴 HIGH | Requires process discipline; documented in CONTRIBUTING.md |
| Secret in binary file (not text diff) | ✅ LOW | Hook scans staged diff only; binary commits unlikely |
| Secret in PR description (not code) | ✅ LOW | Hook runs pre-commit only; PR body not checked |
| Secret in git history (before hook installed) | ✅ LOW | Hook checks forward; requires BFG/git-filter-branch for history |

**Recommendation**: Add `.githooks/pre-commit` to CONTRIBUTING.md with explicit note:
> ⚠️ **Do NOT bypass hook with `--no-verify`** — this defeats secret detection.

---

## Section 7: CI Secret Exposure Assessment (VERIFIED)

### 7.1 Secrets in GitHub Actions

**File**: `release.yml` lines 57-62, 75-80

```yaml
env:
  FLUX_ENDPOINT: ${{ secrets.FLUX_ENDPOINT }}
  FLUX_API_KEY: ${{ secrets.FLUX_API_KEY }}
  AUDIO_ENDPOINT: ${{ secrets.AUDIO_ENDPOINT }}
  AUDIO_API_KEY: ${{ secrets.AUDIO_API_KEY }}
```

**Status**: ✅ **SAFE**
- Secrets passed as env vars (not interpolated into shell strings)
- Accessed via `tools/generate_assets.py` which reads from os.environ
- No `pull_request_target` trigger (safe for forks) ✅
- Workflow only runs on tag push (authenticated events) ✅

**Evidence**:
- build.yml uses `pull_request` (safe) ✅
- release.yml uses tag push trigger (safe) ✅

---

## Section 8: Dependency & Supply Chain (Verified)

### 8.1 Python Requirements

| Package | Constraint | CVEs | Status |
|---------|-----------|------|--------|
| Pillow | >=10.0.0,<12.0.0 | None recent | ✅ Safe |
| requests | >=2.28.0,<3.0.0 | None recent | ✅ Safe |
| aiohttp | >=3.9.0,<4.0.0 | CVE-2023-37276 fixed | ✅ Safe |
| pytest | >=7.0.0,<9.0.0 | None recent | ✅ Safe |
| pydantic | >=2.0,<3.0 | None recent | ✅ Safe |
| hypothesis | >=6.0,<7.0 | None recent | ✅ Safe |

**Status**: ✅ **CLEAN — no vulnerable versions in ranges**

---

## Summary of NEW Findings (Round 4)

| ID | Severity | Title | Category |
|----|----------|-------|----------|
| audit-sec-api-response-leakage | MEDIUM | Unfiltered API error responses printed to stdout | Info Disclosure |
| audit-sec-manifest-errors | MEDIUM | Exception details stored in manifest file | Info Disclosure |
| audit-sec-check-secrets-flags | LOW | check_secrets.sh missing pipefail and -u flags | Shell Safety |

---

## Recommendations (Priority Order)

### MEDIUM Priority (Information Disclosure)

1. **Filter API response printing** (generate_audio.py, generate_assets.py)
   - Stop printing `resp.text[:200]` 
   - Print status code only, or filtered message
   - Time estimate: 20 min

2. **Sanitize manifest error fields** (generate_audio.py)
   - Store error type only, not full exception
   - Move detailed errors to debug logging
   - Time estimate: 15 min

### LOW Priority (Code Quality)

3. **Standardize shell script safety** (check_secrets.sh)
   - Update line 6 from `set -e` to `set -euo pipefail`
   - Time estimate: 5 min

---

## Conclusion

**Round 4 Status**: ✅ **FRESH FINDINGS IDENTIFIED; IMPROVEMENTS VERIFIED**

**Key Results**:
- ✅ All R3 improvements maintained (7-family hook patterns, SHA-pinned actions, CVE-2023-37276 fixed)
- ✅ .gitignore properly protects .env from accidental commit
- ⚠️ **2 MEDIUM findings** in error handling/information disclosure (non-critical but best-practice gap)
- 🔴 **1 PENDING operational task** (sec-env-real-keys: operator to rotate Azure keys)

**Production Readiness**: ✅ **SHIP-READY**
- No critical vulnerabilities
- Information disclosure vectors are low-risk (local tools, CI logs)
- Pre-commit hook working correctly
- Dependencies safe

**Recommended Pre-Release Action**: Apply 2 medium-priority fixes (20–30 min total) for defense-in-depth; not blocking.

---

## Audit Artifacts

- **Audit Date**: 2025-01-15
- **Auditor**: security-and-secrets persona
- **Mode**: READ-ONLY
- **NEW Todos Seeded**: 3
- **Next Audit**: After error handling fixes applied, or 30 days if deferred (Round 5)

---

**End of Report**

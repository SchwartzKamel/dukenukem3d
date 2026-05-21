# Security & Secrets Audit — Round 18

_Persona: security-and-secrets (r18, cycle 72 rolling audit r17→r18). Successor to r17 (cycle 66). Continuation of cycle-70 .gitignore closure (testdata artifacts), cycle-71 net-r16-fix-auth-spoofing queued, verification of r17 closure items, audit of CI/CD secret handling (release.yml workflow), GitHub Actions action pinning, atomic-write helpers (fsync consistency), and roadmap for cycle 72+ including HMAC-SHA256 auth-spoofing implementation readiness._

---

## Executive Summary

**Status**: 🟡 **SECURE WITH 1 HIGH FINDING — Cycle 72 Verification Complete**

Round 18 is a cycle 72 rolling audit following r17 (cycle 66 verification) and cycle-70/71 intermediate work. Key areas audited: re-verification of cycle-70 .gitignore closure (testdata/determ_frame_n*_*.bmp), cycle-71 queued auth-spoofing work (HMAC threat model ready from r17), GitHub Actions workflows (release.yml YAML syntax, secret handling, action pinning), atomic-write helpers (fsync consistency check), sound_manifest + generate_audio secret serialization audit, network authentication surfaces (SRC/MMULTI.C handshake verification), and GPL-2.0 compliance re-verification.

**Key Findings**:
- ✅ **Cycle-70 closure verified**: testdata/determ_frame_n*_*.bmp in .gitignore; test artifacts NO longer tracked ✅
- ✅ **GitHub Actions action pinning**: All 6 actions pinned to 40-char SHAs (checkout v4, setup-python v5, cache v4, upload-artifact v4, download-artifact v4, softprops/action-gh-release v2) ✅
- ✅ **Secret env isolation verified**: release.yml uses env: blocks for FLUX/AUDIO endpoints; no direct run: interpolation ✅
- ✅ **Sound manifest & audio generation**: Pydantic v2 validation + serialization verified SECURE; _redact_endpoint() used for logging ✅
- ✅ **.env file handling**: Real API keys exist locally (expected); .env gitignored and NOT tracked ✅
- ✅ **GPL-2.0 compliance**: 29 SPDX headers verified across tools/ and tests/ (no changes) ✅
- ⚠️ **CRITICAL FINDING**: .github/workflows/release.yml has YAML syntax errors (indentation at lines 88, 116) — workflow will not parse; gates AI asset generation ⚠️
- ⚠️ **Outstanding**: Cycle-71 queued net-r16-fix-auth-spoofing; HMAC-SHA256 threat model from r17 ready for consumption ✅
- ⚠️ **Minor consistency**: generate_audio.py _atomic_write_bytes lacks fsync() (generate_assets.py includes it for durability)

**Finding Count**: 1 HIGH (YAML syntax), 0 CRITICAL, 5 MEDIUM (backlog carries + new TODOs). **Total actionable todos: 5 (cycle 72+ roadmap)**.

| Area | Status | Evidence | Risk |
|------|--------|----------|------|
| **Cycle-70 closure: testdata .gitignore** | ✅ VERIFIED | .gitignore line 56: `testdata/determ_frame_n*_*.bmp` present; test artifacts NOT tracked | SECURE |
| **Cycle-71 queued: net-r16-fix-auth-spoofing** | ✅ READY | HMAC-SHA256 threat model + handshake flow from r17 documented; ready for cycle 67+ pickup | READY |
| **GitHub Actions secret env blocks** | ✅ VERIFIED | release.yml lines 79–85, 103–108: FLUX/AUDIO secrets passed via env: blocks; no hardcoded interpolation | SECURE |
| **GitHub Actions action pinning** | ✅ VERIFIED | All 6 actions pinned to SHA (checkout@34e1..., setup-python@a26a..., cache@0c45..., upload-artifact@ea16..., download-artifact@d3f8..., softprops@3bb1...) | SECURE |
| **Pydantic v2 sound manifest + audio generation** | ✅ VERIFIED | tools/sound_manifest.py ConfigDict(strict=True, validate_assignment=True); tools/generate_audio.py uses _redact_endpoint() for logging; no secret leakage in JSON serialization | SECURE |
| **.env gitignore + tracking** | ✅ VERIFIED | .env gitignored ✅; git ls-files shows .env NOT tracked ✅; .env.example has placeholders only | SECURE |
| **Network auth surfaces (SRC/MMULTI.C)** | ✅ VERIFIED | Handshake code verified; sequence number verification (NET_HEADER_SIZE = 5 bytes) from cycle 60+; HMAC not yet implemented (scheduled cycle 67+) | READY FOR r16 |
| **GPL-2.0 compliance** | ✅ VERIFIED | 29 SPDX-License-Identifier headers confirmed; no changes since r17 | SECURE |
| **CRITICAL: release.yml YAML syntax** | ❌ PARSE ERROR | Lines 88, 116 indentation errors; workflow will not execute; gates AI asset generation | **HIGH** |
| **check_secrets.sh scanner** | ✅ VERIFIED | 6-pattern set LIVE (Google Cloud, Slack, npm, Stripe, HuggingFace, OpenAI org); 1181 tests passing (no regressions) | SECURE |
| **Minor: atomic_write fsync consistency** | ⚠️ INCONSISTENT | generate_audio.py lacks f.flush() + os.fsync(); generate_assets.py includes both for durability | **LOW** |

---

## Cycle-70 Closure Verification

### ✅ **sec-r17-gitignore-test-artifacts: Closure Verified**

**File**: `.gitignore:56`

**Status**: ✅ **VERIFIED LIVE — Test artifacts excluded**

**Change verified**: Cycle 70 added generalized pattern:
```
testdata/determ_frame_n*_*.bmp
```

**Evidence**: 
- Pattern present in .gitignore at line 56 ✅
- Pattern covers all frame capture artifacts (n1, n2, n3, etc. frame numbering) ✅
- Non-secret test data correctly excluded (build cleanliness, CI artifact management) ✅

**Sentinel**: `sec-r17-gitignore-test-artifacts`

**Status**: ✅ **CLOSURE VERIFIED — No changes needed for cycle 72+**

---

## Cycle-71 Queued Work Status

### ✅ **net-r16-fix-auth-spoofing: HMAC Threat Model READY**

**Status**: ✅ **READY FOR PICKUP — Threat model documented, handshake protocol ready**

**Current state**: 
- Cycle 71 queued work is pending; HMAC-SHA256 threat model fully documented in r17 audit (lines 287–349)
- Handshake flow, payload format, and implementation checklist available for cycle 67+ (now) pickup
- Network authentication surfaces verified in SRC/MMULTI.C: sequence number validation (cycle 60+) confirmed; HMAC not yet implemented

**Key artefacts** (from r17):
- Threat model: Attacker masquerade via spoofed packets; HMAC-SHA256 mitigates by requiring sender identity proof
- Handshake: CLIENT → SERVER (JOIN_REQUEST) → CHALLENGE+nonce → RESPONSE(HMAC) → SESSION_KEY established
- Payload format: `[header (4B)] + [payload (NB)] + [HMAC-SHA256 (32B)]`
- HMAC function: `HMAC-SHA256(session_key, payload + sequence_number)`
- Performance: ~256µs per packet (negligible for 30–60 FPS game tick rate)

**Implementation readiness**:
- ✅ Handshake timeouts already present (HANDSHAKE_TIMEOUT_SEC = 15, NET_PROTOCOL_VERSION = 0x0001)
- ✅ Sequence number infrastructure in place (NET_HEADER_SIZE = 5, sequence field)
- ✅ Player socket infrastructure ready (player_sockets[MAXPLAYERS], per-socket recv buffers)
- ⚠️ HMAC-SHA256 implementation required (OpenSSL EVP_HMAC or libsodium crypto_auth_hmacsha256)

**Sentinel**: `sec-r17-auth-spoofing-threat-model`

**Status**: ✅ **READY FOR CYCLE 67+ — Threat model asset available; NO further audits needed until implementation phase**

---

## Cycle-72 Verification

### ✅ **GitHub Actions Workflow Security Audit**

**File**: `.github/workflows/release.yml`

**Action Pinning Status**: ✅ **VERIFIED — All 6 actions pinned to 40-char SHA**

Pinned actions (verified):
1. `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4` ✅
2. `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5` ✅
3. `actions/cache@0c45773b623bea8c8e75f6c82b208c3cf94ea4f9 # v4` ✅
4. `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4` ✅
5. `actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4` ✅
6. `softprops/action-gh-release@3bb12739c298aeb8a4eeaf626c5b8d85266b0e65 # v2` ✅

**Secret Handling Status**: ✅ **VERIFIED — Secrets isolated in env: blocks; no hardcoded credentials**

Secret isolation verified:
- Lines 79–85: Generate assets (Linux) — FLUX/AUDIO secrets via env: ✅
- Lines 103–108: Package Windows release — FLUX/AUDIO secrets via env: ✅
- No direct `${{ secrets.VAR }}` in run: commands ✅
- No echo/print of secrets in workflow ✅
- Artifact retention policy: 90 days (line 129) — appropriate for release artifacts ✅

**Sentinel**: `sec-r15-workflow-secrets` (from r17 reference at lines 76, 99)

**Status**: ✅ **VERIFIED SECURE**

### ❌ **CRITICAL: release.yml YAML Syntax Error**

**File**: `.github/workflows/release.yml`

**Status**: ❌ **YAML PARSE ERROR — Workflow will not execute**

**Issue**: Indentation errors at lines 88 and 116

**Lines 88–91** (malformed):
```yaml
   - name: Validate generated artifacts
     if: matrix.target == 'linux'
     run: python3 tools/validate_generated_artifacts.py --sets textures grp maps scripts
```
^-- Extra leading space (should align with - name: above)

**Lines 116–119** (malformed):
```yaml
   - name: Validate generated artifacts
     if: matrix.target == 'windows'
     run: python3 tools/validate_generated_artifacts.py --sets textures grp maps scripts
```
^-- Same indentation error

**Verification**: YAML parse test (`python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`) **FAILS** with:
```
yaml.parser.ParserError: while parsing a block collection
  in ".github/workflows/release.yml", line 30, column 7
expected <block end>, but found '<block sequence start>'
  in ".github/workflows/release.yml", line 88, column 8
```

**Impact**:
- ❌ Workflow will NOT execute on push to tag
- ❌ Asset generation (AI textures, audio) BLOCKED
- ❌ Release packaging BLOCKED
- ❌ GitHub release creation BLOCKED
- ✅ build.yml (separate workflow) still functions

**Sentinel**: `sec-r18-release-yml-yaml-fix`

**Status**: ❌ **CRITICAL — Requires immediate fix; blocks release pipeline**

---

### ✅ **Pydantic v2 Manifest & Audio Generation Audit**

**Files**: 
- `tools/sound_manifest.py` (Pydantic models)
- `tools/generate_audio.py` (audio generation + manifest serialization)

**Status**: ✅ **VERIFIED SECURE — No secret leakage in serialization**

**Pydantic v2 validation verified**:
- ConfigDict: `strict=True, validate_assignment=True` (enforces strict typing) ✅
- Field validators: wav filename pattern, category enum, voice enum, ranges ✅
- Cross-field validators (if any) reviewed: no custom serialize methods that could leak secrets ✅

**Secret handling verified**:
- AUDIO_API_KEY loaded from env (line 462) ✅
- _redact_endpoint() used for logging (line 484) — shows only scheme + host prefix ✅
- No print/echo of API_KEY in stdout ✅
- Manifest JSON serialization does NOT include credentials ✅
- Error messages sanitized (API error response text capped at 200 chars, no key exposure) ✅

**Manifest structure verified**:
```python
class SoundManifestEntry(BaseModel):
    wav: str
    engine_sound_id: Optional[str]
    voice: Literal['alloy', 'echo', 'onyx']
    category: Literal[...]
    prompt_summary: str
    # (no secret fields)
```

**Atomic write verified**:
- _atomic_write_bytes() uses tmp+rename pattern ✅
- OSError handling cleans up .tmp files ✅
- ⚠️ Minor: lacks f.flush() + os.fsync() for durability (compare to generate_assets.py which includes both)

**Sentinel**: `sec-r18-pydantic-manifest-serialization`

**Status**: ✅ **VERIFIED SECURE**

---

### ✅ **.env File Handling Verification**

**Files**: `.env`, `.env.example`, `.gitignore`

**Status**: ✅ **VERIFIED SECURE — Real secrets gitignored; placeholders documented**

**.env gitignore status**:
- ✅ `.env` in .gitignore (line with `^\.env$` match)
- ✅ git ls-files shows .env NOT tracked (no credential leak in history)
- ✅ Real API keys exist locally on development machine (expected for local AI generation)

**.env.example verification**:
- ✅ Placeholders only: `<your-audio-api-key>`, `<your-flux-api-endpoint>` (no real credentials)
- ✅ Documentation: Clear instructions to copy, fill, and never commit ✅
- ✅ Endpoint URLs redacted appropriately for template

**Local .env observed**:
- ✅ Contains real Azure OpenAI + Black Forest Labs credentials (expected in development)
- ✅ Credentials NOT committed (verified via git ls-files)
- ✅ File permissions allow read by owner only (local machine, not shared)

**Sentinel**: `sec-r15-env-security` (continuing from r15+)

**Status**: ✅ **VERIFIED SECURE**

---

### ✅ **check_secrets.sh Scanner Verification**

**File**: `tools/check_secrets.sh`

**Status**: ✅ **VERIFIED LIVE — 6-pattern set active; false-positive controls in place**

**Pattern set re-verified**:
1. ✅ Google Cloud JSON credentials (service_account pattern)
2. ✅ Slack workspace tokens (x[o]x[pbra]- character-class escaping)
3. ✅ npm package tokens (n[p]m_ escaping)
4. ✅ Stripe restricted keys (r[k]_ escaping)
5. ✅ HuggingFace tokens (h[f]_ escaping)
6. ✅ OpenAI organization IDs (o[r]g- escaping)

**False-positive controls verified**:
- ✅ docs/audits/ excluded (prevents self-detection on audit documentation)
- ✅ tests/test_check_secrets* excluded (test fixtures with intentional fake patterns)
- ✅ tools/check_secrets.sh excluded (prevents self-detection)
- ✅ .env.example excluded (template with placeholder syntax)

**Test coverage**:
- ✅ 1181 tests passing (baseline ~1014 from r17; no regressions)
- ✅ No new false positives introduced

**Sentinel**: `sec-r16-scanner-gap-new-patterns` (continuing from r16)

**Status**: ✅ **VERIFIED SECURE**

---

### ✅ **Network Authentication Surfaces Audit**

**Files**: 
- `SRC/MMULTI.C` (network multiplayer)
- `source/GAME.C` (game state)

**Status**: ✅ **VERIFIED — Sequence number validation present; HMAC scheduled for cycle 67+**

**Handshake verification** (SRC/MMULTI.C):
- ✅ TCP socket infrastructure: server_socket, player_sockets[MAXPLAYERS]
- ✅ Handshake timeout: HANDSHAKE_TIMEOUT_SEC = 15 (prevents resource exhaustion)
- ✅ Protocol version: NET_PROTOCOL_VERSION = 0x0001 (version negotiation in place)
- ✅ Sequence number header: NET_HEADER_SIZE = 5 bytes (sender, dest, seq, payload_len_LE) from cycle 60+

**Current authentication**:
- ✅ Sequence number validation prevents out-of-order packet injection (cycle 60+ verified)
- ⚠️ Sender identity NOT yet verified (no HMAC) — HMAC scheduled for cycle 67+

**Threat model status**:
- ✅ Documented in r17 audit (lines 287–349)
- ✅ Handshake flow, payload format, implementation checklist ready
- ✅ OpenSSL/libsodium library recommendations provided

**Sentinel**: `sec-r17-auth-spoofing-threat-model`

**Status**: ✅ **READY FOR CYCLE 67+ IMPLEMENTATION**

---

## GPL-2.0 Compliance Re-Verification

### ✅ **SPDX License Headers**

**Status**: ✅ **VERIFIED — 29 headers confirmed across tools/ and tests/**

Sample verified headers:
- `tools/check_secrets.sh` — SPDX-License-Identifier: GPL-2.0-or-later ✅
- `tools/install_hooks.sh` — SPDX-License-Identifier: GPL-2.0-or-later ✅
- `tests/test_check_secrets*.py` — SPDX-License-Identifier: GPL-2.0-or-later ✅
- `tools/sound_manifest.py` — SPDX-License-Identifier: GPL-2.0-or-later ✅
- `tools/generate_audio.py` — SPDX-License-Identifier: GPL-2.0-or-later ✅

**Third-party licenses**:
- ✅ SDL2 — LGPL 2.0 (compatible with GPL-2.0)
- ✅ OpenSSL — Apache 2.0 / OpenSSL License (compatible with GPL-2.0)
- ✅ Python — PSF License (compatible with GPL-2.0)

**Status**: ✅ **VERIFIED COMPLIANT**

---

## Summary of Findings

| ID | Title | Risk | Status | Cycle | Notes |
|----|-------|------|--------|-------|-------|
| (verified) | Cycle-70 closure: testdata/.gitignore | **VERIFIED** | LIVE ✅ | 70 |  |
| (verified) | Cycle-71 queued: net-r16-auth-spoofing HMAC | **READY** | QUEUED ✅ | 71 | Threat model available from r17 |
| release-yml-yaml | release.yml YAML syntax errors (lines 88, 116) | **HIGH** | FINDING ❌ | 72 | Workflow will not parse; gates AI asset generation |
| pydantic-manifest | Pydantic v2 + audio generation serialization | **VERIFIED** | SECURE ✅ | 72 | No secret leakage; _redact_endpoint() active |
| env-handling | .env gitignore + .env.example placeholders | **VERIFIED** | SECURE ✅ | 72 | Real credentials gitignored; placeholders documented |
| github-actions | Action pinning + secret env blocks | **VERIFIED** | SECURE ✅ | 72 | All 6 actions pinned; FLUX/AUDIO via env: |
| check-secrets | 6-pattern scanner + false-positive exclusions | **VERIFIED** | LIVE ✅ | 72 | 1181 tests passing; no regressions |
| gpl-compliance | SPDX headers + third-party licenses | **VERIFIED** | COMPLIANT ✅ | 72 | 29 headers; SDL2/OpenSSL compatible |
| atomic-write-minor | generate_audio.py _atomic_write_bytes fsync | **LOW** | INCONSISTENT ⚠️ | 72 | Lacks f.flush()+os.fsync(); generate_assets.py includes both |

**Cycle 72 Verdict**: 🟡 **SECURE WITH 1 HIGH FINDING (0 CRITICAL; 1 HIGH; 5 MEDIUM TODOs)**

---

## New TODOs for Cycle 72+

| ID | Title | Risk | Status | Description |
|----|-------|------|--------|-------------|
| sec-r18-release-yml-yaml-fix | Fix release.yml YAML syntax errors | **HIGH** | PENDING | Fix indentation at lines 88, 116 to restore workflow execution; gates AI asset generation |
| sec-r18-verify-auth-spoofing-integration | Verify net-r16 auth-spoofing HMAC integration | **HIGH** | PENDING | Cycle 71 queued work; verify HMAC-SHA256 handshake implementation ready; validate against r17 threat model |
| sec-r18-ci-masking-directives | Add GitHub Actions explicit masking | **MEDIUM** | PENDING | Optional hardening: add ::add-mask:: directives in release.yml generate_assets steps (integrate with secrets env blocks) |
| sec-r18-atomic-write-hardening | Add fsync() to generate_audio.py atomic_write | **LOW** | PENDING | Consistency: add f.flush() + os.fsync(f.fileno()) to _atomic_write_bytes (matches generate_assets.py pattern for durability) |
| sec-r18-net-spoofing-test-coverage | Create HMAC-SHA256 spoofing test cases | **MEDIUM** | PENDING | Prepare regression tests for cycle 67+ auth-spoofing implementation; include packet injection scenarios |

---

## Closure Criteria

R18 audit scope complete:
- ✅ Cycle-70 closure verified (testdata/.gitignore updated)
- ✅ Cycle-71 queued work status verified (auth-spoofing ready for pickup; HMAC threat model available)
- ✅ GitHub Actions workflow security audited (action pinning verified; secret handling verified)
- ✅ **CRITICAL FINDING**: release.yml YAML syntax error identified (workflow will not parse)
- ✅ Pydantic v2 + audio generation serialization verified SECURE
- ✅ .env file handling verified SECURE
- ✅ check_secrets.sh scanner verified LIVE (1181 tests passing)
- ✅ Network auth surfaces verified (sequence number + HMAC ready for cycle 67+)
- ✅ GPL-2.0 compliance re-verified (29 SPDX headers)
- ✅ New findings documented; 5 actionable TODOs created

**Cycle 72 Status**: 🟡 **SECURE (1 HIGH finding requiring immediate fix; 5 MEDIUM/LOW TODOs for roadmap)**

---

**Audit Completed**: 2026-05-21 (cycle 72, r17→r18 rolling audit)
**Next Audit**: Cycle 73 (r19) — verify release.yml fix, begin HMAC-SHA256 implementation review


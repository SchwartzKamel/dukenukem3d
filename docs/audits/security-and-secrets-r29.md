# security-and-secrets — round 29 (DOC-ONLY audit-pass)

_Persona: security-and-secrets (paranoid-by-default). Doc-only shippability audit. Cycle following r28 (cycle 120)._

**Frontmatter**:
- Round: r29
- Persona: security-and-secrets
- Date: 2026-05-23
- HEAD: working tree at audit time
- Verdict: ✅ **SHIPPABLE (with caveats)** — no P0 secret leaks; 1 P1 carry-forward (POSIX RNG fallback to `r` + `and()`); 1 P1 build-system-adjacent (Windows native build path omits SHA256/CSPRNG compat sources — see build-system-r29 P0-1); secret scanner coverage holds.

---

<!-- SUMMARY_ROW -->
| security-and-secrets | r29 | 2026-05-23 | 0 P0 + 2 P1 + 4 P2; r28 redaction finding RESOLVED (generate_{assets,audio}.py now use `_redact_hostname()` in DNS errors); POSIX `g` + `etrandom`/`a` + `rc4random` fallback still missing; build_windows.bat compat-loop omission silently strips SHA256/CSPRNG from local Windows builds (cross-ref build-system-r29 P0-1) |
<!-- END_SUMMARY_ROW -->

---

## Cycle-66 Attribution (MANDATORY, carried forward)

This audit preserves the cycle-66 fake-author commits (`0296200`, `6c23644`) by operator decision; no security risk.

---

## Executive Summary

Cycle-120 r28 LOW finding (`DNS error messages leak endpoint hostname`) is **RESOLVED**:
- `tools/generate_audio.py:109,111` now wrap with `_redact_hostname(parsed.hostname)`.
- `tools/generate_assets.py:443,445` likewise wrap.
- `_redact_hostname()` helper present at `tools/generate_audio.py:59–70` and `tools/generate_assets.py:393–404`.

`check_secrets.sh` (245 lines, 14+ pattern families), `.githooks/pre-commit`, `.env`/`.env.example` hygiene, BCryptGenRandom adoption, and GitHub Actions SHA pinning all remain intact.

Two carry-forwards remain P1: POSIX RNG fallback chain (still ends in `r` + `and()`), and DLL-search hardening still documentation-only.

A **new** finding cross-cuts with build-system-r29 P0-1: the local Windows native build script (`build_windows.bat`) compiles only 4 of 9 compat .c files, **silently omitting `compat/sha256.c`**. This means locally-built Windows binaries (the path users follow per README) lack the HMAC-SHA256 verification code referenced by `SRC/MMULTI.C` — a security regression unique to the local script path (CI MSVC build via CMake is unaffected).

---

## Findings

### P0 — None.

### P1 — High-Priority

#### P1-1: POSIX RNG fallback ends in non-CSPRNG `r` + `and()` (r28 MEDIUM carry-forward, escalated)

**Severity**: P1 (HMAC nonce strength degrades to ~32-bit state in edge cases)

**Location**: `SRC/MMULTI.C:300–321` (verified via `grep -n` on `/dev/urandom`, `r` + `and()`).

**Issue**: On POSIX:
- Try `/dev/urandom` (good ✅).
- On partial read or open failure, XOR/fill remaining bytes with `r` + `and() & 0xFF` (CSPRNG-not).
- Windows branch falls back to `r` + `and()` similarly if `BCryptGenRandom` fails (line 303).

`copilot-instructions.md` Architectural Contracts section explicitly states: **"CSPRNG: Windows uses BCryptGenRandom() (bcrypt.lib); Linux uses getrandom(). Never rand() for nonces/checksums."** Current implementation violates this contract in fallback paths.

**Recommendation**: Insert `g` + `etrandom(2)` (Linux ≥3.17, glibc ≥2.25) and `a` + `rc4random_buf(3)` (BSD/macOS) as fallback chain before `r` + `and()`. Ideal order: `/dev/urandom` → `g` + `etrandom` (Linux) / `a` + `rc4random_buf` (BSD/macOS) → abort-and-warn (do not silently degrade to a 32-bit PRNG for HMAC nonces).

---

#### P1-2: Local Windows build path silently omits CSPRNG/HMAC compat source (cross-cut with build-system-r29 P0-1)

**Severity**: P1 (security-critical compat code never compiled on local Windows native builds)

**Locations**:
- `build_windows.bat:113` (MSVC compat loop): `for %%f in (sdl_driver audio_stub mact_stub hud) do (`
- `build_windows.bat:160` (MinGW compat loop): same enumeration
- vs `build.mk:14–16`: full COMPAT_SRCS includes `compat/sha256.c` and (for WIN32) `compat/net_socket_win32.c`

**Security impact**:
- `compat/sha256.c` provides `hmac_sha256_verify_ct()` (constant-time HMAC compare, referenced by `SRC/MMULTI.C` HMAC path).
- `compat/net_socket_win32.c` provides the Win32 socket wrapper required by `SRC/MMULTI.C` (per `copilot-instructions.md`: "Socket operations route through `net_socket_create()` wrappers").
- A `build_windows.bat`-produced binary will either fail to link (loud) or — if any forward dummies are introduced in future — link silently against an incomplete security surface.

**Recommendation**: Track via build-system-r29 P0-1 todo; security-side acceptance criterion is `objdump -t duke3d.exe | grep -E 'hmac_sha256|sha256_(init|update|final)|net_socket_create'` returns symbols in the locally-built binary.

---

### P2 — Medium-Priority

#### P2-1: `check_secrets.sh` regex for `_API_KEY=...` is base64-only and misses hyphen/underscore-bearing token formats

**Location**: `tools/check_secrets.sh:39` — `grep -E '_API_KEY=[a-zA-Z0-9+/]{32,}'`.

**Issue**: Character class `[a-zA-Z0-9+/]` excludes `-` and `_`. Many modern token formats (e.g., JWT-style, `s` + `k_test_...`, Azure connection-string keys with underscores) would not match this guard even when prefixed with `..._API_KEY=`. The specialized prefix checks (lines 54, 97, 142, 195, 207, 219) catch named formats, but generic `*_API_KEY=` assignments with hyphenated values slip through.

**Recommendation**: Broaden to `[A-Za-z0-9+/_=\-]{24,}` and tighten allowlist (template `<...>`, `your_...`, env-passthrough `${...}`) instead of restricting alphabet.

---

#### P2-2: `check_secrets.sh` does not cover OPENSSH/PGP private-key block markers

**Location**: `tools/check_secrets.sh:87` — matches `BEG` + `IN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY` (only PEM-style private keys).

**Gap**: Does **not** match `BEG` + `IN PGP PRIVATE KEY BLOCK` (GPG ASCII-armored private keys) or `BEG` + `IN ENCRYPTED PRIVATE KEY`.

**Recommendation**: Add patterns `BEG` + `IN PGP PRIVATE KEY BLOCK` and `BEG` + `IN ENCRYPTED PRIVATE KEY` to the regex alternation.

---

#### P2-3: `secret-scan.yml` push event scans only `HEAD~1...HEAD` (force-push / merge-bundle blind spot)

**Location**: `.github/workflows/secret-scan.yml:32` — `bash tools/check_secrets_ci.sh "HEAD~1...HEAD"`.

**Issue**: A push of N commits to `master` (e.g., direct merge, force-push, or rebase landing) is scanned only over the last commit; secrets introduced in any of the prior N-1 commits are not re-scanned by the push event. PR-event scan (line 27, `base.sha...HEAD`) covers the PR path correctly. GitHub server-side push protection mitigates the most dangerous patterns (GitHub-issued tokens) but third-party secrets (FLUX/AUDIO endpoints, Azure keys) are not all covered by push protection.

**Recommendation**: Use `${{ github.event.before }}...${{ github.event.after }}` for push events to scan the entire push range.

---

#### P2-4: SetDefaultDllDirectories still documentation-only (r28 carry-forward)

**Location**: `SECURITY.md` documents the recommendation; no implementation in any `WinMain`/`main()` discovered in `SRC/` or `compat/`.

**Recommendation**: Either implement (preferred) in `compat/sdl_driver.c` Windows entry, or downgrade `SECURITY.md` wording to "packager guidance" with explicit acknowledgement that the shipped binary does not call `SetDefaultDllDirectories()`.

---

## Verified-Still-Holds (from r28 / earlier)

| Control | Location | Status |
|---|---|---|
| `.env` gitignored | `.gitignore:9` | ✅ |
| `.env.example` placeholder-only | `.env.example:1–21` | ✅ |
| `chmod 600` / `icacls` guidance | `SECURITY.md:53,59,64,65` | ✅ |
| BCryptGenRandom (Windows) | `SRC/MMULTI.C:296` | ✅ |
| POSIX `/dev/urandom` (primary path) | `SRC/MMULTI.C:306` | ✅ |
| HMAC ct-compare | `compat/sha256.c` (cycle-119) | ✅ |
| Hostname redaction in DNS errors | `tools/generate_audio.py:109,111`; `tools/generate_assets.py:443,445` | ✅ **NEW: r28 LOW finding RESOLVED** |
| FLUX/AUDIO env-loaded (no hardcoding) | `tools/generate_assets.py:2417`; `tools/generate_audio.py:591` | ✅ |
| CI secrets env-passed (no echo) | `release.yml:79–86, 102–108`; `tools/ci/generate_assets.sh:9–14` | ✅ |
| Workflow SHA pinning | all workflows; checkout/setup-python/cache/upload-artifact/download-artifact/action-gh-release | ✅ |
| Workflow minimal permissions | `build.yml:9–10` (read); `release.yml:8–9` (read) + `publish-release` (contents: write only) | ✅ |
| GPL-2.0 attribution | `NOTICE:1–30+` | ✅ |
| Pre-commit hook installer | `tools/install_hooks.sh:10` sets `core.hooksPath` | ✅ |
| Self-exclusion in scanner | `tools/check_secrets.sh:23` (`:(exclude)tools/check_secrets*`) | ✅ |
| `docs/audits/` exclusion for GCP pattern | `tools/check_secrets.sh:173` | ✅ (partial — only one rule) |

---

## CVE Posture (`requirements.txt` pins)

| Package | Pinned | Status |
|---|---|---|
| Pillow | 12.1.1 | Recent; no known unpatched CVEs as of audit date |
| requests | 2.33.1 | Recent |
| aiohttp | 3.13.5 | Header rationale cites CVE-2023-37276 (HTTP request smuggling) — fixed in 3.9.0+, pin satisfies |
| pytest | 9.0.2 | Test-only dep |
| pytest-xdist | `>=3.5` ⚠️ | Floating pin (also flagged in build-system-r29 P1-2) — undermines CVE auditability |
| pydantic | 2.12.5 | v2 schema; current |
| hypothesis | 6.152.9 | Test-only |
| filelock | `>=3.0` ⚠️ | Floating pin — same CVE-auditability concern |
| numpy | 1.26.4 | Older; tracked by NumPy advisory feed; no critical open CVEs at this version |

**No P0/P1 CVE exposure** on pinned versions. Floating pins (`pytest-xdist`, `filelock`) prevent precise CVE attribution.

---

## GPL-2.0 Compliance

- `NOTICE` lists BUILD engine (Ken Silverman) and Duke3D (3D Realms) with correct GPL-2.0 attribution.
- Compat layer (`compat/sha256.c`) — SHA256 reference implementations are typically public domain (e.g., Brad Conte) or BSD-2; verify header attribution present.
- No third-party non-GPL-compatible code observed in this audit pass; SDL2 (zlib) and SDL2_mixer (zlib) are GPL-2.0-compatible per `NOTICE`.

**Action**: Confirm `compat/sha256.c` header carries license attribution for the SHA256 source (out of audit scope; flag for compat-layer persona).

---

## Mined Todos

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
 ('sec-r29-posix-csprng-fallback-p1', 'Replace rand() fallback in SRC/MMULTI.C net_gen_nonce with getrandom/arc4random or abort', 'SRC/MMULTI.C:300-321 falls back to rand() on /dev/urandom failure (POSIX) and BCryptGenRandom failure (Windows). This violates copilot-instructions.md Architectural Contracts ("Never rand() for nonces/checksums"). Insert getrandom(2) on Linux and arc4random_buf(3) on BSD/macOS before rand(), and prefer to abort-with-error rather than silently degrade to a 32-bit PRNG for HMAC nonces.', 'pending'),
 ('sec-r29-win-bat-omits-sha256-p1', 'Ensure build_windows.bat includes compat/sha256.c and compat/net_socket_win32.c (cross-cut build-system-r29 P0-1)', 'build_windows.bat:113 (MSVC) and :160 (MinGW) omit maxtiles_*, sha256, and net_socket_win32 from compat compile loops. Security impact: locally-built Windows binaries via this script may link without HMAC-SHA256 verification path. Track jointly with build-system-r29 P0-1; security acceptance is `objdump -t duke3d.exe | grep -E "hmac_sha256|sha256_init|net_socket_create"` non-empty.', 'pending'),
 ('sec-r29-check-secrets-api-key-regex-broaden-p2', 'Broaden check_secrets.sh _API_KEY= regex alphabet to include hyphens and underscores', 'tools/check_secrets.sh:39 uses [a-zA-Z0-9+/]{32,} which excludes hyphens and underscores. Modern tokens (JWT-ish, Stripe sk_test_, hyphenated) bypass this guard when assigned via a generic *_API_KEY= variable name. Broaden to [A-Za-z0-9+/_=\\-]{24,} and tighten allowlist for templates/placeholders.', 'pending'),
 ('sec-r29-check-secrets-pgp-keys-p2', 'Add PGP and ENCRYPTED PRIVATE KEY block markers to check_secrets.sh', 'tools/check_secrets.sh:87 only matches PEM-style private-key markers (RSA/OPENSSH/EC/DSA/blank). Add patterns for "BEGIN PGP PRIVATE KEY BLOCK" and "BEGIN ENCRYPTED PRIVATE KEY" to the regex alternation.', 'pending'),
 ('sec-r29-secret-scan-push-range-p2', 'Use github.event.before...github.event.after for push-event secret scan range', 'tools/check_secrets_ci.sh is invoked with HEAD~1...HEAD in secret-scan.yml:32 for push events; this misses N-commit pushes (direct merges, force-pushes, rebase landings). Replace with ${{ github.event.before }}...${{ github.event.after }} so the full push range is scanned.', 'pending'),
 ('sec-r29-dll-hardening-decision-p2', 'Implement SetDefaultDllDirectories in Windows entry OR downgrade SECURITY.md wording (r28 carry-forward)', 'SECURITY.md documents SetDefaultDllDirectories recommendation but no call exists in compat/ or SRC/. Either add SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_APPLICATION_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32) to the Windows-side entrypoint in compat/sdl_driver.c, or update SECURITY.md to mark this as packager guidance with explicit "not implemented in shipped binary" note.', 'pending');
<!-- END_MINED_TODOS -->

---

## Verification

- All file:line citations verified with `grep -n`.
- r28 DNS-redaction finding verified RESOLVED (`grep -n '_redact_hostname(parsed.hostname)' tools/generate_*.py` returns 4 hits in error-message contexts).
- `r28` `compat/sha256.c` in CMakeLists.txt verified RESOLVED at `CMakeLists.txt:54`.
- No source files modified; doc-only.
- Realistic-looking token literals are token-split throughout this document per the cycle-66 v7 hardening rule (see e.g. `BEG` + `IN PGP PRIVATE KEY BLOCK`, `s` + `k_test_`, `g` + `etrandom`).

---

## Sentinel

<!-- SENTINEL: sec-r29-c121 -->

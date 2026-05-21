# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅ Current release |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainers or use GitHub's private vulnerability reporting feature
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a fix timeline.

## Security Considerations

### Network Code
The TCP/IP multiplayer implementation (`SRC/MMULTI.C`) accepts network connections. When hosting a game:
- Only host on trusted networks
- The protocol does not include encryption or authentication
- Packet size limits are enforced to prevent buffer overflows

### API Credentials
- FLUX.2-pro and GPT Audio API keys are stored in `.env` (gitignored)
- Never commit `.env` or hardcode API keys in source files
- The asset generation tools load credentials from `.env` at runtime only

### Securing Local .env Files

The `.env` file contains sensitive credentials and must be protected with proper file permissions to prevent unauthorized access.

**Verification**: `.env` is in `.gitignore` and will not be committed. Verify with:
```bash
git check-ignore .env
```

**File Permissions** (set on first creation or after adding credentials):

**POSIX/Linux/macOS:**
```bash
chmod 600 .env
```
This restricts read and write access to the owner only (no group or world access).

**Windows (PowerShell):**
```powershell
icacls .env /inheritance:r /grant:r "$env:USERNAME:F"
```
This removes inherited permissions and grants Full Control (F) to the current user only. Run as Administrator if necessary.

**Verification**: After setting permissions, verify with:
- **POSIX**: `ls -l .env` should show `-rw-------` (600)
- **Windows**: `icacls .env` should show only your username with `(F)` rights

### Legacy Code
This is a port of 1996-era C code. Known limitations:
- Many fixed-size buffers without bounds checking
- `sprintf` used in places where `snprintf` would be safer
- Integer overflow possible in some math operations
- The CON script interpreter executes game scripts without sandboxing

### Third-Party License Compliance
All third-party dependencies are GPL-2.0 compatible. See [NOTICE](NOTICE) at the repository root for a consolidated attribution of SDL2, BUILD engine, Duke3D source, and Python dependencies. Downstream packagers should reference this file for compliance verification.

### Optional Dependency: SDL2_mixer (CVE Monitoring)

SDL2_mixer is an **OPTIONAL** runtime dependency loaded in QUIET mode (CMakeLists.txt). The library is not vendored; system package managers (apt, brew, dnf, pacman, Windows MSYS2, etc.) are responsible for patching.

**Recommended Actions**:
- Subscribe to [SDL2_mixer GitHub Security Advisories](https://github.com/libsdl-org/SDL_mixer/security/advisories) for CVE notifications.
- Review cadence: 90 days. File an issue using `.github/ISSUE_TEMPLATE/key-rotation.md` (adapted) if a HIGH or CRITICAL CVE is identified.
- If SDL2_mixer is unavailable or removed from system, audio output gracefully falls back to `compat/audio_stub` (silent path). Build and test pipelines are unaffected.

### SDL2_mixer Windows DLL Search Path Hardening

**Issue**: On Windows, the default DLL search order (documented in [Microsoft DLL Search Order](https://docs.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order)) can be exploited via DLL planting if `SafeDllSearchMode` is disabled or in untrusted working directories. An attacker with write access to the application directory or certain system paths can substitute a malicious `SDL2_mixer.dll`.

**Recommendations**:

1. **Restrict DLL Search Directories (Recommended for Windows builds)**:
   - Call `SetDefaultDllDirectories()` early in `WinMain()` to restrict DLL searches to safe locations only:
     ```c
     SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_APPLICATION_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
     ```
   - This prevents DLL planting attacks by excluding the current working directory and user paths from the search order.
   - Requires Windows 8+ (or KB2533623 on Windows Vista SP1/7).

2. **Static Linking (Alternative)**:
   - If applicable, configure CMake to statically link SDL2_mixer (see `CMakeLists.txt` for conditional linking options) to eliminate runtime DLL dependency.
   - Trade-off: increases binary size but eliminates the DLL search order risk entirely.

3. **Deployment Best Practices**:
   - Place SDL2_mixer.dll in the application directory (same folder as the executable) or rely on system package managers.
   - Verify DLL integrity (e.g., signed binaries) before distribution.
   - Document deployment instructions in release notes if a custom DLL is supplied.

**Audit trail**: cycles 101 (CODEOWNERS), 104 (NOTICE), 105 (key rotation); cycle-66 fake-author commits 0296200 + 6c23644 remain in history per operator decision.

## Known Issues (v0.1.0)

The following issues have been identified and documented. Critical and high-severity items are resolved.

### Resolved
- **Config parser buffer overflow** (HIGH) — `strcpy()` in `SCRIPT_GetString/GetDoubleString` replaced with bounds-checked `strncpy()`. `sprintf` → `snprintf` in `SCRIPT_PutNumber` and `itoa`/`ltoa` polyfills.

### Accepted (Low Risk)
- **Network code** — `inet_addr()` (deprecated, use `inet_pton`), no per-IP rate limiting on multiplayer host, incomplete malformed packet recovery. Acceptable for LAN play; not recommended for untrusted internet hosting.
- **Path traversal** — `find_game_file()` and CON `include` directive don't sanitize `../` sequences. Low risk since inputs come from local game data files, not user/network input.
- **Port parsing** — `atoi()` used for port numbers without range validation (1-65535).
- **Legacy C patterns** — Various fixed-size buffers throughout 1996-era code. Comprehensive audit would require rewriting significant portions of the original engine.

## Azure Key Rotation

Sensitive credentials (Azure Speech API keys for TTS, FLUX API tokens) must be rotated regularly to maintain security posture.

**Rotation Cadence**: 90 days recommended. Defer to operator's existing policy if established.

**Keys in Scope**:
- `AUDIO_API_KEY` — Azure OpenAI Audio/TTS service
- `FLUX_API_KEY` — Azure FLUX image generation API
- Endpoint URLs (if sensitive in your deployment)

**Storage & Access**:
- Local development: `.env` file (never committed; in `.gitignore`)
- CI/CD: GitHub repository secrets (`Settings > Secrets and variables > Actions`)
- Never hardcode in source, config files, or logs

**Operator Rotation Process** (Blocked: `sec-env-real-keys`):
1. Rotate old keys in Azure portal (Resource Groups → Cognitive Services → Regenerate Keys)
2. Update local `.env` with new values (never commit)
3. Update GitHub repository secrets with new values
4. Trigger CI smoke test run to verify integration
5. Document rotation date in ticket comments (for audit trail)

**Validation**: Before marking rotation complete, confirm CI pipelines still authenticate successfully and no stale keys remain in logs.

For implementation details, see `.github/ISSUE_TEMPLATE/key-rotation.md`.

## Code Ownership

Certain security-sensitive paths in this repository are protected by automated code ownership rules (`.github/CODEOWNERS`). These paths require review by the project maintainer before changes are approved:

- **CI/CD & Workflows** — `.github/workflows/`
- **Secrets Detection** — `tools/check_secrets.sh`
- **Dependencies** — `requirements.txt`
- **Cryptographic Primitives** — `compat/sha256.*` (SHA256 implementations)
- **Network & HMAC Code** — `SRC/MMULTI.C`, `compat/net_socket*`

For the complete and authoritative list of protected paths, see [`.github/CODEOWNERS`](.github/CODEOWNERS).

### Contributing to Protected Paths

If you need to modify a security-sensitive path, open a pull request with your changes. The maintainer will review and merge when appropriate. To propose changes to code ownership rules themselves, create a pull request editing `.github/CODEOWNERS` directly — such changes also require maintainer review.

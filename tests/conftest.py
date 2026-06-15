import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
import re
import textwrap
import uuid

import pytest
from pydantic import BaseModel, field_validator

# Add project root and tools to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

from manifest_verification import load_and_verify_audio_manifest, load_and_verify_tables_manifest


@pytest.fixture(scope="session", autouse=True)
def _anchor_cwd_to_engine():
    """z-cwd-anchor: run the suite with CWD = the engine dir so tests that use
    paths relative to it (e.g. os.path.exists('tools/generate_audio.py'),
    open('source/GAME.C')) resolve regardless of whether pytest was invoked from
    the engine dir (`cd engine; pytest tests`) or the parent repo root
    (`pytest engine/tests`, e.g. a parent-repo CI). Session-scoped + autouse so
    it runs once per (worker) session AFTER collection — leaving pytest's own
    path-argument resolution untouched — and restores the original CWD at the end.
    Tests needing their own CWD (e.g. tmp_path isolation) still set/restore it
    locally within their scope."""
    prev = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        yield
    finally:
        os.chdir(prev)


def _skip_if_no_cc(compiler="gcc"):
    """Skip the calling test/fixture if the C compiler isn't on PATH.

    Several fixtures compile a small C harness with gcc. On a Windows dev box
    gcc is usually absent (native toolchain is MSVC, and WSL gcc would validate
    the Linux LP64 ABI, not Windows LLP64). These harness checks run in CI with
    the proper compiler, so skip gracefully here rather than erroring.
    """
    if shutil.which(compiler) is None:
        import pytest as _pytest
        _pytest.skip(f"C compiler {compiler!r} not on PATH; validated in CI")


def resolve_binary_path(project_root: Path) -> Path:
    """Resolve the most likely built game binary path across local/CI layouts."""
    exe_name = "duke3d.exe" if os.name == "nt" else "duke3d"
    candidates = [
        project_root / "build" / "Release" / exe_name,
        project_root / "build" / exe_name,
        project_root / exe_name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


# ============================================================================
# Test Parametrization Conventions (perf-r16-frame-analyzer-parametrization)
# ============================================================================
# 
# Frame Analyzer Test Contract:
# ────────────────────────────
# The frame_analyzer module parametrizes tests across [1, 3, 5] frame counts to:
#   1. Ensure determinism under ThreadPoolExecutor parallelization (single, small, medium)
#   2. Catch race conditions in batch frame processing
#   3. Validate behavior at boundary cases (N=1) and realistic workloads (N=3,5)
#
# Convention: DO NOT add ad-hoc frame-count parametrization elsewhere. Instead:
#   - If testing analyze_frame_sequence behavior: extend the canonical test
#   - If testing a new function: add a comment referencing this convention
#   - If parametrization intent differs (not [1,3,5]): document why in the test
#
# See: tests/test_frame_analyzer.py::TestAnalyzeFrameSequence::test_analyze_frame_sequence_deterministic
#      tools/frame_analyzer.py (module docstring section on test parametrization)
#
# ============================================================================


# ============================================================================
# Pydantic Model for Sound Manifest Entry Validation
# ============================================================================

class SoundManifestEntry(BaseModel):
    """Validates individual sound manifest entries with pydantic v2."""
    
    wav: str
    engine_sound_id: str | None = None
    engine_sound_id_int: int | None = None
    voice: str
    category: str
    prompt_summary: str
    status: str = "generated"
    generated_at: str | None = None
    notes: str | None = None
    
    @field_validator('engine_sound_id')
    @classmethod
    def validate_sound_id(cls, v):
        """Validate engine_sound_id matches C identifier pattern."""
        if v is None:
            return v
        if not re.match(r'^[A-Z_][A-Z0-9_]*$', v):
            raise ValueError(f"sound_id '{v}' does not match pattern ^[A-Z_][A-Z0-9_]*$")
        return v
    
    @field_validator('voice')
    @classmethod
    def validate_voice(cls, v):
        """Validate voice is one of known enum values."""
        valid_voices = {'alloy', 'echo', 'onyx'}
        if v not in valid_voices:
            raise ValueError(f"voice '{v}' not in {valid_voices}")
        return v
    
    @field_validator('wav')
    @classmethod
    def validate_wav_path(cls, v):
        """Validate wav_path ends with .wav or .WAV."""
        if not (v.endswith('.wav') or v.endswith('.WAV')):
            raise ValueError(f"wav_path '{v}' does not end with .wav or .WAV")
        return v


# ============================================================================
# Shared Session-Scoped Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root():
    """Return absolute path to project root (parent of tests/ directory)."""
    return Path(PROJECT_ROOT)


@pytest.fixture(scope="session")
def binary_path(project_root):
    """Return path to the duke3d binary."""
    return resolve_binary_path(project_root)


@pytest.fixture(scope="session")
def grp_path(project_root):
    """Return path to DUKE3D.GRP file."""
    return project_root / "DUKE3D.GRP"


@pytest.fixture
def temp_captures_dir(tmp_path):
    """Isolated captures/ directory per test (replaces hard-coded captures/ path).
    
    Returns Path object; auto-cleaned by pytest tmp_path.
    
    This fixture enables test isolation and supports parallel execution (pytest-xdist)
    by ensuring each test gets its own temporary captures directory instead of
    sharing a hard-coded project root captures/ path.
    """
    d = tmp_path / "captures"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture(scope="session")
def generated_assets_dir(project_root):
    """Return path to generated_assets directory."""
    return project_root / "generated_assets"


@pytest.fixture(scope="session", autouse=True)
def generated_audio_artifacts(worker_id, tmp_path_factory):
    """Run generate_audio.py --no-ai once per session and yield path to sounds directory.
    
    This fixture is autouse=True so it runs at session start, ensuring audio files
    are available for all tests that need them.
    
    When running under pytest-xdist, uses FileLock to coordinate across workers:
    - Only the first worker (master) generates artifacts
    - Other workers wait for the lock and check for the done marker
    
    NOTE: This fixture does not tear down (no cleanup code after yield). This is
    intentional because:
    - Session-scoped: generated_assets/sounds/ is part of the checked-in project state
    - Regenerating files is idempotent: running generate_audio.py --no-ai multiple
      times produces identical output (deterministic silence placeholders)
    - Tests depend on the artifacts persisting for the full session
    
    Returns a dict with:
        - sounds_dir: Path to generated_assets/sounds
        - manifest_path: Path to MANIFEST.json
        - wav_files: List of generated .WAV files
        - manifest: Parsed MANIFEST.json dict
    """
    from filelock import FileLock
    
    def _do_generation():
        """Perform the actual artifact generation."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, \
            f"generate_audio.py --no-ai failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        
        sounds_dir = Path(PROJECT_ROOT) / "generated_assets" / "sounds"
        assert sounds_dir.exists(), f"Output directory not created: {sounds_dir}"
        
        wav_files = sorted([f for f in sounds_dir.iterdir() if f.suffix == ".WAV"])
        manifest_path = sounds_dir / "MANIFEST.json"
        assert manifest_path.exists(), f"MANIFEST.json not created: {manifest_path}"
        
        # manifest-checksum-verify-on-load: Load and verify manifest with checksums
        manifest = load_and_verify_audio_manifest(str(manifest_path), str(sounds_dir))
        
        return {
            "sounds_dir": sounds_dir,
            "manifest_path": manifest_path,
            "wav_files": wav_files,
            "manifest": manifest
        }
    
    if worker_id == "master":
        # Not running under xdist: single-threaded execution
        artifacts = _do_generation()
        yield artifacts
        return
    
    # Under xdist: coordinate generation across workers
    root_tmp = tmp_path_factory.getbasetemp().parent
    lock_file = root_tmp / "generated_audio.lock"
    done_marker = root_tmp / "generated_audio.done"
    
    with FileLock(str(lock_file)):
        if not done_marker.exists():
            _do_generation()
            done_marker.touch()
    
    # Now get the generated artifacts (they exist from master's or this worker's generation)
    sounds_dir = Path(PROJECT_ROOT) / "generated_assets" / "sounds"
    wav_files = sorted([f for f in sounds_dir.iterdir() if f.suffix == ".WAV"])
    manifest_path = sounds_dir / "MANIFEST.json"
    
    # manifest-checksum-verify-on-load: Load and verify manifest with checksums
    manifest = load_and_verify_audio_manifest(str(manifest_path), str(sounds_dir))
    
    artifacts = {
        "sounds_dir": sounds_dir,
        "manifest_path": manifest_path,
        "wav_files": wav_files,
        "manifest": manifest
    }
    
    yield artifacts


@pytest.fixture(scope="session")
def compiled_makepalookup_harness(tmp_path_factory):
    """Session-scoped fixture that compiles makepalookup test harness once.
    
    Compiles the C test harness for makepalookup() bounds checking and caches
    the binary for the entire pytest session. This avoids recompiling on every
    test discovery or test method, reducing pytest startup from ~2-4s per file
    to 1 shared compile per session.
    
    Yields:
        Path to the compiled executable (auto-cleaned by pytest tmp_path cleanup)
    """
    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <limits.h>
#include <assert.h>

/* Test harness to verify makepalookup() bounds guard logic */

#define MAXPALOOKUPS 256

/* Simulate the guard from SRC/ENGINE.C:7568 */
int test_guard_triggers(long palnum) {
    /* Replicate the guard: if (palnum < 0 || palnum >= MAXPALOOKUPS) return; */
    if (palnum < 0 || palnum >= MAXPALOOKUPS) {
        return 1; /* Guard triggered (should return early) */
    }
    return 0; /* Guard did NOT trigger (function proceeds) */
}

int main() {
    int pass_count = 0, fail_count = 0;
    int i;
    long palnum;
    int triggered;
    
    printf("Testing makepalookup() bounds guard logic...\n");
    printf("MAXPALOOKUPS = %d\n\n", MAXPALOOKUPS);
    
    /* Test cases: guard MUST trigger */
    struct {
        long palnum;
        const char *desc;
    } guard_must_trigger[] = {
        { -1, "palnum = -1" },
        { -100, "palnum = -100" },
        { -128, "palnum = -128 (signed-char min)" },
        { INT_MIN, "palnum = INT_MIN" },
        { MAXPALOOKUPS, "palnum = 256 (MAXPALOOKUPS)" },
        { MAXPALOOKUPS + 1, "palnum = 257 (MAXPALOOKUPS+1)" },
        { 512, "palnum = 512 (well above max)" },
    };
    int num_must_trigger = sizeof(guard_must_trigger) / sizeof(guard_must_trigger[0]);
    
    for (i = 0; i < num_must_trigger; i++) {
        palnum = guard_must_trigger[i].palnum;
        triggered = test_guard_triggers(palnum);
        
        if (triggered) {
            printf("[PASS] %s -> guard triggered (correct)\n", guard_must_trigger[i].desc);
            pass_count++;
        } else {
            printf("[FAIL] %s -> guard did NOT trigger (BUG!)\n", guard_must_trigger[i].desc);
            fail_count++;
        }
    }
    
    printf("\n");
    
    /* Test cases: guard must NOT trigger */
    struct {
        long palnum;
        const char *desc;
    } guard_must_not_trigger[] = {
        { 0, "palnum = 0 (min valid)" },
        { 1, "palnum = 1" },
        { 127, "palnum = 127 (mid-range)" },
        { 255, "palnum = 255 (MAXPALOOKUPS-1, max valid)" },
    };
    int num_must_not_trigger = sizeof(guard_must_not_trigger) / sizeof(guard_must_not_trigger[0]);
    
    for (i = 0; i < num_must_not_trigger; i++) {
        palnum = guard_must_not_trigger[i].palnum;
        triggered = test_guard_triggers(palnum);
        
        if (!triggered) {
            printf("[PASS] %s -> guard did NOT trigger (correct)\n", guard_must_not_trigger[i].desc);
            pass_count++;
        } else {
            printf("[FAIL] %s -> guard triggered (BUG!)\n", guard_must_not_trigger[i].desc);
            fail_count++;
        }
    }
    
    printf("\n");
    printf("Results: %d passed, %d failed\n", pass_count, fail_count);
    
    if (fail_count > 0) {
        fprintf(stderr, "BOUNDS GUARD TEST FAILED\n");
        return 1;
    }
    
    printf("ALL BOUNDS GUARD CHECKS PASSED\n");
    return 0;
}
"""
    
    tmpdir = tmp_path_factory.mktemp("c_harness")
    compiler = os.environ.get("STRUCT_TEST_CC", "gcc")
    _skip_if_no_cc(compiler)
    c_file = tmpdir / "makepalookup_bounds.c"
    out_file = tmpdir / "makepalookup_bounds"
    
    # Write C code
    c_file.write_text(c_code, encoding="utf-8")
    
    # Compile
    result = subprocess.run(
        [compiler, "-std=gnu89", "-x", "c", str(c_file), "-o", str(out_file)],
        capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, (
        f"Compilation failed with {compiler}:\n{result.stderr}"
    )
    
    yield out_file


@pytest.fixture(scope="session")
def compiled_keepalive_error_harness(tmp_path_factory):
    """Session-scoped fixture that compiles keepalive error test harness once.
    
    Compiles the C test harness for net_socket_is_keepalive_error() and caches
    the binary for the entire pytest session. This avoids recompiling on every
    test discovery, reducing overhead significantly.
    
    Yields:
        Path to the compiled executable (auto-cleaned by pytest tmp_path cleanup)
    """
    test_code = textwrap.dedent(r'''
    #include <stdio.h>
    #include <errno.h>
    #include <string.h>
    
    #ifdef _WIN32
    #include <winsock2.h>
    #else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #endif
    
    /* Forward declare the function we're testing */
    int net_socket_is_keepalive_error(int err);
    
    /* POSIX implementation */
    #ifndef _WIN32
    int net_socket_is_keepalive_error(int err)
    {
        return (err == ETIMEDOUT || err == ECONNRESET);
    }
    #else
    /* Windows implementation */
    int net_socket_is_keepalive_error(int err)
    {
        return (err == WSAETIMEDOUT || err == WSAECONNRESET);
    }
    #endif
    
    int main(void)
    {
        int pass = 0;
        int fail = 0;
        
        /* Test positive cases (should return 1) */
        #ifndef _WIN32
        /* POSIX tests */
        if (net_socket_is_keepalive_error(ETIMEDOUT) == 1) {
            printf("PASS: ETIMEDOUT -> 1\n");
            pass++;
        } else {
            printf("FAIL: ETIMEDOUT -> %d (expected 1)\n", net_socket_is_keepalive_error(ETIMEDOUT));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(ECONNRESET) == 1) {
            printf("PASS: ECONNRESET -> 1\n");
            pass++;
        } else {
            printf("FAIL: ECONNRESET -> %d (expected 1)\n", net_socket_is_keepalive_error(ECONNRESET));
            fail++;
        }
        
        /* Test negative cases (should return 0) */
        if (net_socket_is_keepalive_error(EAGAIN) == 0) {
            printf("PASS: EAGAIN -> 0\n");
            pass++;
        } else {
            printf("FAIL: EAGAIN -> %d (expected 0)\n", net_socket_is_keepalive_error(EAGAIN));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(EWOULDBLOCK) == 0) {
            printf("PASS: EWOULDBLOCK -> 0\n");
            pass++;
        } else {
            printf("FAIL: EWOULDBLOCK -> %d (expected 0)\n", net_socket_is_keepalive_error(EWOULDBLOCK));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(EINTR) == 0) {
            printf("PASS: EINTR -> 0\n");
            pass++;
        } else {
            printf("FAIL: EINTR -> %d (expected 0)\n", net_socket_is_keepalive_error(EINTR));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(ENOTCONN) == 0) {
            printf("PASS: ENOTCONN -> 0\n");
            pass++;
        } else {
            printf("FAIL: ENOTCONN -> %d (expected 0)\n", net_socket_is_keepalive_error(ENOTCONN));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(0) == 0) {
            printf("PASS: 0 -> 0\n");
            pass++;
        } else {
            printf("FAIL: 0 -> %d (expected 0)\n", net_socket_is_keepalive_error(0));
            fail++;
        }
        #else
        /* Windows tests */
        if (net_socket_is_keepalive_error(WSAETIMEDOUT) == 1) {
            printf("PASS: WSAETIMEDOUT -> 1\n");
            pass++;
        } else {
            printf("FAIL: WSAETIMEDOUT -> %d (expected 1)\n", net_socket_is_keepalive_error(WSAETIMEDOUT));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(WSAECONNRESET) == 1) {
            printf("PASS: WSAECONNRESET -> 1\n");
            pass++;
        } else {
            printf("FAIL: WSAECONNRESET -> %d (expected 1)\n", net_socket_is_keepalive_error(WSAECONNRESET));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(0) == 0) {
            printf("PASS: 0 -> 0\n");
            pass++;
        } else {
            printf("FAIL: 0 -> %d (expected 0)\n", net_socket_is_keepalive_error(0));
            fail++;
        }
        #endif
        
        printf("Results: %d passed, %d failed\n", pass, fail);
        return (fail == 0) ? 0 : 1;
    }
    ''')
    
    tmpdir = tmp_path_factory.mktemp("c_harness")
    src_file = tmpdir / 'test_keepalive_error.c'
    exe_file = tmpdir / 'test_keepalive_error'
    
    # Write test source
    src_file.write_text(test_code, encoding="utf-8")
    
    # Compile
    _skip_if_no_cc('gcc')
    compile_cmd = [
        'gcc',
        '-o', str(exe_file),
        str(src_file),
        '-Wall', '-Wextra', '-pedantic',
    ]
    
    result = subprocess.run(
        compile_cmd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    
    yield exe_file


@pytest.fixture(scope="session")
def compiled_sha256_harness(tmp_path_factory):
    """Session-scoped fixture that compiles SHA256 test harness once.
    
    Compiles a C test harness that links against compat/sha256.c and compat/sha256.h,
    testing SHA-256, HMAC-SHA256, and HKDF-SHA256 functions.
    
    Yields:
        Path to the compiled executable (auto-cleaned by pytest tmp_path cleanup)
    """
    test_code = textwrap.dedent(r'''
    #include <stdio.h>
    #include <stdint.h>
    #include <string.h>
    #include "sha256.h"
    
    /* Test 1: SHA-256 of "abc" (NIST test vector) */
    static int test_sha256_abc(void) {
        uint8_t digest[SHA256_DIGEST_SIZE];
        const uint8_t test_dummy_key_abc[] = "abc";
        
        /* Expected: ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad */
        const uint8_t expected[SHA256_DIGEST_SIZE] = {
            0xba, 0x78, 0x16, 0xbf, 0x8f, 0x01, 0xcf, 0xea,
            0x41, 0x41, 0x40, 0xde, 0x5d, 0xae, 0x22, 0x23,
            0xb0, 0x03, 0x61, 0xa3, 0x96, 0x17, 0x7a, 0x9c,
            0xb4, 0x10, 0xff, 0x61, 0xf2, 0x00, 0x15, 0xad
        };
        
        sha256_oneshot(test_dummy_key_abc, 3, digest);
        
        if (memcmp(digest, expected, SHA256_DIGEST_SIZE) == 0) {
            printf("PASS: SHA256(abc) matches NIST test vector\n");
            return 1;
        } else {
            printf("FAIL: SHA256(abc) mismatch\n");
            return 0;
        }
    }
    
    /* Test 2: HMAC-SHA256 (RFC 4231, Test Case 1) */
    static int test_hmac_sha256_rfc4231_tc1(void) {
        /* Key: 0x0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b (20 bytes) */
        uint8_t key[20];
        int i;
        for (i = 0; i < 20; i++) key[i] = 0x0b;
        
        /* Message: "Hi There" */
        const uint8_t msg[] = "Hi There";
        
        /* Expected output (RFC 4231 Test Case 1):
         * b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7 */
        const uint8_t expected[HMAC_SHA256_SIZE] = {
            0xb0, 0x34, 0x4c, 0x61, 0xd8, 0xdb, 0x38, 0x53,
            0x5c, 0xa8, 0xaf, 0xce, 0xaf, 0x0b, 0xf1, 0x2b,
            0x88, 0x1d, 0xc2, 0x00, 0xc9, 0x83, 0x3d, 0xa7,
            0x26, 0xe9, 0x37, 0x6c, 0x2e, 0x32, 0xcf, 0xf7
        };
        
        uint8_t hmac[HMAC_SHA256_SIZE];
        hmac_sha256(key, sizeof(key), msg, sizeof(msg) - 1, hmac);
        
        if (memcmp(hmac, expected, HMAC_SHA256_SIZE) == 0) {
            printf("PASS: HMAC-SHA256 (RFC 4231 TC1) matches expected output\n");
            return 1;
        } else {
            printf("FAIL: HMAC-SHA256 (RFC 4231 TC1) mismatch\n");
            return 0;
        }
    }
    
    /* Test 3: HKDF-SHA256 (RFC 5869 Test Case 1) */
    static int test_hkdf_sha256_rfc5869_tc1(void) {
        /* RFC 5869 Test Case 1 (SHA-256) */
        /* IKM (Input Keying Material): 0x0b... (22 bytes) */
        uint8_t ikm[22];
        int i;
        for (i = 0; i < 22; i++) ikm[i] = 0x0b;
        
        /* Salt: 0x000102... (13 bytes) */
        uint8_t salt[13];
        for (i = 0; i < 13; i++) salt[i] = (uint8_t)i;
        
        /* Info: 0xf0f1... (10 bytes) */
        uint8_t info[10];
        for (i = 0; i < 10; i++) info[i] = (uint8_t)(0xf0 + i);
        
        /* L = 42 (42-byte output) */
        uint8_t okm[42];
        
        /* Expected OKM (RFC 5869, first 42 bytes):
         * 3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865 */
        const uint8_t expected[42] = {
            0x3c, 0xb2, 0x5f, 0x25, 0xfa, 0xac, 0xd5, 0x7a,
            0x90, 0x43, 0x4f, 0x64, 0xd0, 0x36, 0x2f, 0x2a,
            0x2d, 0x2d, 0x0a, 0x90, 0xcf, 0x1a, 0x5a, 0x4c,
            0x5d, 0xb0, 0x2d, 0x56, 0xec, 0xc4, 0xc5, 0xbf,
            0x34, 0x00, 0x72, 0x08, 0xd5, 0xb8, 0x87, 0x18,
            0x58, 0x65
        };
        
        hkdf_sha256(salt, sizeof(salt), ikm, sizeof(ikm), info, sizeof(info), okm, sizeof(okm));
        
        if (memcmp(okm, expected, 42) == 0) {
            printf("PASS: HKDF-SHA256 (RFC 5869 TC1) matches expected output\n");
            return 1;
        } else {
            printf("FAIL: HKDF-SHA256 (RFC 5869 TC1) mismatch\n");
            return 0;
        }
    }
    
    int main(void) {
        int pass = 0, fail = 0;
        
        printf("=== SHA256 Integration Tests ===\n\n");
        
        if (test_sha256_abc()) pass++; else fail++;
        if (test_hmac_sha256_rfc4231_tc1()) pass++; else fail++;
        if (test_hkdf_sha256_rfc5869_tc1()) pass++; else fail++;
        
        printf("\n=== Results: %d passed, %d failed ===\n", pass, fail);
        return (fail == 0) ? 0 : 1;
    }
    ''')
    
    tmpdir = tmp_path_factory.mktemp("sha256_harness")
    src_file = tmpdir / 'test_sha256.c'
    exe_file = tmpdir / 'test_sha256'
    
    # Write test source
    src_file.write_text(test_code, encoding="utf-8")
    
    # Compile with compat/sha256.c
    project_root = Path(PROJECT_ROOT)
    sha256_src = project_root / 'compat' / 'sha256.c'
    sha256_hdr_dir = project_root / 'compat'
    
    _skip_if_no_cc('gcc')
    compile_cmd = [
        'gcc',
        '-std=gnu11',
        '-I', str(sha256_hdr_dir),
        '-o', str(exe_file),
        str(src_file),
        str(sha256_src),
        '-Wall', '-Wextra', '-pedantic',
    ]
    
    result = subprocess.run(
        compile_cmd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"SHA256 harness compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    
    yield exe_file


def pytest_addoption(parser):
    """Add --runslow option to pytest CLI."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow tests (subprocess-heavy, C compilation); default: skip"
    )


def pytest_collection_modifyitems(config, items):
    """Skip slow tests unless --runslow is passed."""
    try:
        if config.getoption("--runslow"):
            # Run all tests
            return
    except ValueError:
        # Option not registered yet (can happen with early pytest initialization)
        pass
    
    # Skip all tests marked as slow
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


# ============================================================================
# Shared headless playtest fixture
# ============================================================================

def sdl2_available():
    """Check if libSDL2 is available in the runtime linker path."""
    import ctypes

    windows_candidates = [
        Path(PROJECT_ROOT) / "SDL2.dll",
        Path(PROJECT_ROOT) / "build" / "SDL2.dll",
        Path(PROJECT_ROOT) / "build" / "Release" / "SDL2.dll",
    ]
    for dll_path in windows_candidates:
        if dll_path.is_file():
            try:
                ctypes.CDLL(str(dll_path))
                return True
            except OSError:
                pass

    for lib_name in (
        "libSDL2-2.0.so.0",
        "libSDL2-2.0.0.dylib",
        "SDL2.dll",
    ):
        try:
            ctypes.CDLL(lib_name)
            return True
        except OSError:
            pass
    return False


def pytest_configure(config):
    """Create a per-pytest-session id for headless playtest reruns."""
    if not hasattr(config, "workerinput"):
        config._headless_session_id = uuid.uuid4().hex


def pytest_configure_node(node):
    """Share the headless session id with xdist workers."""
    session_id = getattr(node.config, "_headless_session_id", uuid.uuid4().hex)
    node.workerinput["headless_session_id"] = session_id


def get_sdl2_lib_path():
    """Try to find SDL2 library path from ctypes/system locations."""
    windows_candidates = [
        Path(PROJECT_ROOT),
        Path(PROJECT_ROOT) / "build",
        Path(PROJECT_ROOT) / "build" / "Release",
    ]
    for path in windows_candidates:
        if (path / "SDL2.dll").is_file():
            return str(path)

    macos_paths = [
        "/opt/homebrew/lib",
        "/usr/local/lib",
    ]
    for path in macos_paths:
        sdl2_file = os.path.join(path, "libSDL2-2.0.0.dylib")
        if os.path.isfile(sdl2_file):
            return path

    linux_paths = [
        "/home/linuxbrew/.linuxbrew/lib",
        "/usr/lib",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/local/lib",
    ]
    for path in linux_paths:
        sdl2_file = os.path.join(path, "libSDL2-2.0.so.0")
        if os.path.isfile(sdl2_file):
            return path

    try:
        result = subprocess.run(
            ["ldconfig", "-p"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.split("\n"):
            if "libSDL2-2.0.so.0" in line:
                parts = line.split(" => ")
                if len(parts) == 2:
                    lib_path = parts[1].strip()
                    if lib_path:
                        return os.path.dirname(lib_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["where", "SDL2.dll"] if os.name == "nt" else ["which", "SDL2.dll"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            dll_path = result.stdout.strip()
            if dll_path:
                return os.path.dirname(dll_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


@pytest.fixture(scope="session")
def headless_run(worker_id, pytestconfig):
    """Launch Duke3D headless once, capture frames, return results dict."""
    import glob
    import shutil
    from filelock import FileLock

    binary_path_value = str(resolve_binary_path(Path(PROJECT_ROOT)))
    grp_path_value = os.path.join(PROJECT_ROOT, "DUKE3D.GRP")

    if not os.path.isfile(binary_path_value):
        pytest.skip(f"Game binary not found: {binary_path_value}")
    if not os.path.isfile(grp_path_value):
        pytest.skip(f"GRP file not found: {grp_path_value}")
    if not sdl2_available():
        pytest.skip("libSDL2-2.0.so.0 not found in runtime linker path")

    session_id = os.environ.get("DUKE3D_HEADLESS_RUN_ID")
    if not session_id:
        workerinput = getattr(pytestconfig, "workerinput", None) or {}
        session_id = workerinput.get(
            "headless_session_id",
            getattr(pytestconfig, "_headless_session_id", "default"),
        )

    captures_dir = os.path.join(PROJECT_ROOT, "captures")
    lock_file = os.path.join(PROJECT_ROOT, f".headless_run.{session_id}.lock")
    done_marker = os.path.join(PROJECT_ROOT, f".headless_run.{session_id}.done")

    def _do_headless_run():
        if os.path.isdir(captures_dir):
            shutil.rmtree(captures_dir)
        os.makedirs(captures_dir, exist_ok=True)

        env = os.environ.copy()
        env.update({
            "SDL_VIDEODRIVER": "dummy",
            "DUKE3D_HEADLESS": "1",
            "DUKE3D_SKIP_LOGO": "1",
            "DUKE3D_FRAME_LIMIT": "20",
            "DUKE3D_CAPTURE_INTERVAL": "5",
        })

        sdl2_path = get_sdl2_lib_path()
        if sdl2_path:
            current_ld = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = (
                f"{sdl2_path}:{current_ld}" if current_ld else sdl2_path
            )

        try:
            result = subprocess.run(
                [binary_path_value],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                timeout=15,
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired as exc:
            exit_code = -1
            result = exc

        frame_paths = sorted(glob.glob(os.path.join(captures_dir, "*.bmp")))
        stdout = getattr(result, "stdout", b"") or b""
        stderr = getattr(result, "stderr", b"") or b""
        return {
            "exit_code": exit_code,
            "frame_paths": frame_paths,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
        }

    with FileLock(lock_file):
        if not os.path.exists(done_marker):
            result = _do_headless_run()
            Path(done_marker).touch()
            return result

    frame_paths = sorted(glob.glob(os.path.join(captures_dir, "*.bmp")))
    return {
        "exit_code": 0,
        "frame_paths": frame_paths,
        "stdout": "",
        "stderr": "",
    }

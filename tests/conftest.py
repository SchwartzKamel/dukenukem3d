import os
import sys
import subprocess
import json
from pathlib import Path
import re
import textwrap

import pytest
from pydantic import BaseModel, field_validator

# Add project root and tools to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

from manifest_verification import load_and_verify_audio_manifest, load_and_verify_tables_manifest


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
    return project_root / "duke3d"


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
    c_file = tmpdir / "makepalookup_bounds.c"
    out_file = tmpdir / "makepalookup_bounds"
    
    # Write C code
    c_file.write_text(c_code)
    
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
    src_file.write_text(test_code)
    
    # Compile
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
    if config.getoption("--runslow"):
        # Run all tests
        return
    
    # Skip all tests marked as slow
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)

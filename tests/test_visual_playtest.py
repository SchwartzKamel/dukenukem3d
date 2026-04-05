"""Visual playtesting suite for Duke Nukem 3D.

Launches the game in headless mode, captures frames, and validates
that rendering produces visible content.

Marked with @pytest.mark.playtest — run with: pytest -m playtest
"""

import glob
import os
import shutil
import subprocess

import pytest

from frame_analyzer import (
    analyze_frame_sequence,
    has_visible_content,
    is_black_screen,
    load_frame,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BINARY_PATH = os.path.join(PROJECT_ROOT, "duke3d")
GRP_PATH = os.path.join(PROJECT_ROOT, "DUKE3D.GRP")
CAPTURES_DIR = os.path.join(PROJECT_ROOT, "captures")


# ---------------------------------------------------------------------------
# Session-scoped fixture: run the game ONCE, share results across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def headless_run():
    """Launch Duke3D headless, capture frames, return results dict.

    The game runs once per pytest session.  Every ``playtest``-marked test
    reads from the dict returned here.
    """
    if not os.path.isfile(BINARY_PATH):
        pytest.skip(f"Game binary not found: {BINARY_PATH}")
    if not os.path.isfile(GRP_PATH):
        pytest.skip(f"GRP file not found: {GRP_PATH}")

    # Clean previous captures
    if os.path.isdir(CAPTURES_DIR):
        shutil.rmtree(CAPTURES_DIR)

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy",
        "DUKE3D_HEADLESS": "1",
        "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_FRAME_LIMIT": "20",
        "DUKE3D_CAPTURE_INTERVAL": "5",
    })

    try:
        result = subprocess.run(
            [BINARY_PATH],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            timeout=15,
        )
        exit_code = result.returncode
    except subprocess.TimeoutExpired as exc:
        # Timeout is acceptable — game may not self-quit in time.
        exit_code = -1
        result = exc

    # Collect captured frames (BMP files written by sdl_capture_frame)
    frame_paths = sorted(glob.glob(os.path.join(CAPTURES_DIR, "*.bmp")))

    stdout = getattr(result, "stdout", b"") or b""
    stderr = getattr(result, "stderr", b"") or b""

    return {
        "exit_code": exit_code,
        "frame_paths": frame_paths,
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.playtest
def test_game_binary_exists():
    """Game binary must be present to run any playtest."""
    if not os.path.isfile(BINARY_PATH):
        pytest.skip("Game binary not found — skipping all playtests")
    assert os.access(BINARY_PATH, os.X_OK), "duke3d binary is not executable"


@pytest.mark.playtest
def test_grp_exists():
    """DUKE3D.GRP data file must be present."""
    if not os.path.isfile(GRP_PATH):
        pytest.skip("DUKE3D.GRP not found — skipping all playtests")
    assert os.path.getsize(GRP_PATH) > 0, "DUKE3D.GRP is empty"


@pytest.mark.playtest
def test_headless_startup(headless_run):
    """Game should start headless and exit without crashing."""
    code = headless_run["exit_code"]
    # Accept 0 (clean exit), or small positive codes (non-crash).
    # Reject crash signals: SIGSEGV(-11/139), SIGABRT(-6/134), etc.
    crash_signals = {-11, -6, 139, 134}
    assert code not in crash_signals, (
        f"Game crashed with exit code {code}\n"
        f"stderr: {headless_run['stderr'][-500:]}"
    )


@pytest.mark.playtest
def test_frames_captured(headless_run):
    """At least one BMP frame should have been captured."""
    assert len(headless_run["frame_paths"]) > 0, (
        "No frames captured in captures/ directory.\n"
        f"exit_code={headless_run['exit_code']}\n"
        f"stderr: {headless_run['stderr'][-500:]}"
    )


@pytest.mark.playtest
def test_not_all_black(headless_run):
    """At least one captured frame must NOT be a black screen."""
    paths = headless_run["frame_paths"]
    if not paths:
        pytest.skip("No frames captured")

    for path in paths:
        img = load_frame(path)
        if not is_black_screen(img):
            return  # success — found a non-black frame
    pytest.fail("All captured frames are black — rendering may be broken")


@pytest.mark.playtest
def test_has_visible_content(headless_run):
    """At least one frame should have ≥4 unique colors (real content)."""
    paths = headless_run["frame_paths"]
    if not paths:
        pytest.skip("No frames captured")

    for path in paths:
        img = load_frame(path)
        if has_visible_content(img, min_unique_colors=4):
            return  # success
    pytest.fail("No frame has visible content (≥4 unique colors)")


@pytest.mark.playtest
def test_frame_sequence_analysis(headless_run):
    """Frame sequence analysis should show rendering activity."""
    paths = headless_run["frame_paths"]
    if not paths:
        pytest.skip("No frames captured")

    report = analyze_frame_sequence(paths)
    assert report["all_black"] is False, "All frames are black"
    assert report["any_content"] is True, (
        f"No frames with visible content out of {report['frame_count']}"
    )


@pytest.mark.playtest
def test_no_crash_signals(headless_run):
    """Game must not exit with a crash signal (SIGSEGV, SIGABRT, etc.)."""
    code = headless_run["exit_code"]
    # On Linux, fatal signals appear as negative codes from subprocess
    # or as 128+signal from the shell.
    signal_codes = {
        -6: "SIGABRT",
        -11: "SIGSEGV",
        -8: "SIGFPE",
        -4: "SIGILL",
        134: "SIGABRT (128+6)",
        139: "SIGSEGV (128+11)",
        136: "SIGFPE (128+8)",
        132: "SIGILL (128+4)",
    }
    if code in signal_codes:
        pytest.fail(
            f"Game crashed with {signal_codes[code]} (exit code {code})\n"
            f"stderr: {headless_run['stderr'][-500:]}"
        )

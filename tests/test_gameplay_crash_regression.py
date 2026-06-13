"""Regression test: gameplay-loop crash due to 32-bit tempscrptr pointer truncation.

Root cause (fixed in engine-r16-gamedef-scrptr-width):
  GAMEDEF.C parsecommand() declared `tempscrptr` as `long *`. On Windows x64 /
  MSVC, `long` is 32 bits. Storing `(intptr_t)scriptptr` (a 64-bit pointer) via
  a 32-bit pointer silently truncates the upper 32 bits. When the runtime
  `parseifelse` later reads the branch-target back as `intptr_t`, it gets a
  zero-extended 32-bit address, which is not mapped → access violation write /
  read crash at 0x000000000xxxxxxx inside the main gameplay loop.

Repro: launch `duke3d.exe /v1 /l1 /s2` headless — the game enters the level,
runs one frame of actor script, and crashes in parseifelse.  After the fix the
process must exit cleanly (exit code 0 or 1 without the C0000005 crash marker in
the startup log).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── helpers ──────────────────────────────────────────────────────────────────

def _resolve_binary() -> Path:
    exe = "duke3d.exe" if sys.platform == "win32" else "duke3d"
    for candidate in [
        PROJECT_ROOT / "build" / "Release" / exe,
        PROJECT_ROOT / "build" / exe,
        PROJECT_ROOT / exe,
    ]:
        if candidate.is_file():
            return candidate
    return PROJECT_ROOT / "build" / exe  # canonical; used in skip message


def _startup_log_path() -> Path:
    return PROJECT_ROOT / "atomic_shell_startup.log"


def _run_gameplay(extra_env=None, timeout=30) -> dict:
    """Run duke3d headless with /v1 /l1 /s2 (warp-to-level) and return result."""
    binary = _resolve_binary()
    if not binary.is_file():
        pytest.skip(f"Binary not found: {binary}")
    grp = PROJECT_ROOT / "DUKE3D.GRP"
    if not grp.is_file():
        pytest.skip("DUKE3D.GRP not found")

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy",
        "DUKE3D_HEADLESS":  "1",
        "DUKE3D_SKIP_LOGO": "1",
        # Run only 5 frames — enough to execute one script tick but fast
        "DUKE3D_FRAME_LIMIT":      "5",
        "DUKE3D_CAPTURE_INTERVAL": "5",
    })
    if extra_env:
        env.update(extra_env)

    try:
        proc = subprocess.run(
            [str(binary), "/v1", "/l1", "/s2"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.decode(errors="replace"),
            "stderr": proc.stderr.decode(errors="replace"),
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -9, "stdout": "", "stderr": "timeout"}


def _read_startup_log() -> str:
    log = _startup_log_path()
    if log.is_file():
        try:
            return log.read_text(errors="replace")
        except OSError:
            return ""
    return ""


# ── regression tests ──────────────────────────────────────────────────────────

@pytest.mark.playtest
@pytest.mark.serial
def test_gameplay_warp_no_crash():
    """Warp to Volume 1 / Level 1 / Skill 2 must not crash with exit code 1 AND
    a CRASH marker in the startup log.  The old bug produced exit code 1 with
    'CRASH: Exception 0xC0000005' in atomic_shell_startup.log because
    parsecommand() stored script branch-target pointers via a 32-bit `long *`
    tempscrptr, truncating the upper 32 bits on x64."""
    result = _run_gameplay()

    log_text = _read_startup_log()
    has_crash_marker = "CRASH: Exception 0xC0000005" in log_text or \
                       "CRASH: Access violation" in log_text

    # The bug: exit_code==1 AND crash marker present
    assert not (result["exit_code"] == 1 and has_crash_marker), (
        "Gameplay crash regression detected!\n"
        "exit_code=1 with CRASH marker in startup log.\n"
        "Root cause: parsecommand() tempscrptr was `long *` (32-bit on MSVC x64).\n"
        f"Log tail:\n{log_text[-800:]}"
    )


@pytest.mark.playtest
@pytest.mark.serial
def test_gameplay_warp_no_crash_marker_in_log():
    """Startup log must not contain a C0000005 access-violation crash line after
    a warp-to-level run.  This guards the specific pointer-truncation crash."""
    _run_gameplay()   # run regardless of exit code; we check the log

    log_text = _read_startup_log()
    assert "CRASH: Exception 0xC0000005" not in log_text, (
        "Startup log contains an access-violation crash marker after warp run.\n"
        f"Log tail:\n{log_text[-800:]}"
    )
    assert "CRASH: Access violation" not in log_text, (
        "Startup log contains an access-violation crash marker after warp run.\n"
        f"Log tail:\n{log_text[-800:]}"
    )

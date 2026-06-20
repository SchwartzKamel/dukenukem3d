"""Crash capture — every crash a player makes during a session must be persisted, even across
restarts. atomic_shell_startup.log is truncated on each launch (fopen "w"), so a memory-hacking
session's earlier crashes would be clobbered; the crash handler therefore ALSO writes a
timestamped minidump (crashes\\crash_YYYYMMDD-HHMMSS.dmp) and appends a one-line record to
crashes\\crash_log.txt (append mode) so a session's crashes accumulate for review.

Deterministic signal: the engine has a dev-only self-test hook — DUKE3D_CRASH_TEST=1 forces a
controlled access violation right after the Windows crash handler is installed. This test runs
the binary with that flag and asserts both crash artifacts are produced (off for players).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # engine/


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


def _run_crash(tmp_path, extra_env):
    """Copy the runtime payload into tmp_path, run the engine with the crash self-test
    enabled, and return (returncode, tmp_path)."""
    if sys.platform != "win32":
        pytest.skip("native Windows crash handler")
    try:
        solver = _solver()
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    binary = solver._resolve_binary()
    grp = PROJECT_ROOT / "DUKE3D.GRP"
    if binary is None or not grp.is_file():
        pytest.skip("duke3d.exe / DUKE3D.GRP not built")

    shutil.copy(grp, tmp_path / "DUKE3D.GRP")
    for name in ("SDL2.dll", "DUKE3D.CFG"):
        src = PROJECT_ROOT / name
        if src.is_file():
            shutil.copy(src, tmp_path / name)

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy", "DUKE3D_HEADLESS": "1", "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_SILENT_ERRORS": "1", "DUKE3D_FRAME_LIMIT": "50",
    })
    env.update(extra_env)
    proc = subprocess.Popen([str(binary)], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        rc = proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        rc = None
    return rc, tmp_path


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_crash_self_test_writes_dump_and_log(tmp_path):
    """DUKE3D_CRASH_TEST=1 forces a crash; a minidump + an appended crash_log.txt line appear."""
    rc, run_dir = _run_crash(tmp_path, {"DUKE3D_CRASH_TEST": "1"})

    crashes = run_dir / "crashes"
    assert crashes.is_dir(), "crashes\\ directory was not created by the crash handler"

    log = crashes / "crash_log.txt"
    assert log.is_file(), "crashes\\crash_log.txt was not written"
    text = log.read_text(errors="replace")
    assert "CRASH" in text, f"crash_log.txt has no CRASH record:\n{text!r}"
    # Access-violation code from a null write.
    assert "0xC0000005" in text, f"expected an access-violation record in crash_log.txt:\n{text!r}"

    dumps = list(crashes.glob("crash_*.dmp"))
    assert dumps, "no crashes\\crash_*.dmp minidump was written"
    assert any(d.stat().st_size > 0 for d in dumps), "minidump file is empty"

    # The forced crash terminates via ExitProcess(1) -> non-zero exit.
    assert rc not in (0, None), f"expected a non-zero crash exit code, got {rc}"


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_no_crash_artifacts_without_self_test(tmp_path):
    """Without DUKE3D_CRASH_TEST the self-test must not fire (no spurious crash for players)."""
    rc, run_dir = _run_crash(tmp_path, {})
    log = run_dir / "crashes" / "crash_log.txt"
    # A clean headless run may exit for other reasons, but it must not record a forced crash.
    if log.is_file():
        assert "0xC0000005" not in log.read_text(errors="replace"), (
            "an access violation was recorded without DUKE3D_CRASH_TEST — the self-test must be "
            "strictly env-gated and players must not crash spuriously"
        )

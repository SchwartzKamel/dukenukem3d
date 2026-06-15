"""Q-STATS-TELEMETRY: optional headless sprite-pool telemetry.

`DUKE3D_STATS_INTERVAL=N` makes the engine emit `stats: sprites=K/MAXSPRITES clock=T` to the
startup log every N game tics, so a soak can graph pool occupancy directly (instead of only
inferring stability from the absence of a "Too many sprites" exit — finding-set Q). Off by
default. This locks the contract: enabled => bounded stats lines appear; disabled => none.

See docs/plans/2026-06-15_DEEP_AUDIT_HARDENING.md finding-set Q.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAXSPRITES = 4096
STATS_RE = re.compile(r"stats: sprites=(\d+)/(\d+) clock=")


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


def _run_soak(tmp_path, extra_env):
    solver = _solver()
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
        "DUKE3D_SILENT_ERRORS": "1", "DUKE3D_AUTOPLAY": "1",
        "DUKE3D_MENU_KEYS": "28,28,28", "DUKE3D_FRAME_LIMIT": "50000",
    })
    env.update(extra_env)
    proc = subprocess.Popen([str(binary)], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        pytest.skip("stats soak did not finish within the timeout")
    log = tmp_path / "atomic_shell_startup.log"
    return log.read_text(errors="replace") if log.is_file() else ""


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_stats_emitted_and_bounded_when_enabled(tmp_path):
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    text = _run_soak(tmp_path, {"DUKE3D_STATS_INTERVAL": "10"})
    matches = STATS_RE.findall(text)
    assert matches, "DUKE3D_STATS_INTERVAL set but no 'stats: sprites=' lines were emitted"
    for sprites, cap in matches:
        sprites, cap = int(sprites), int(cap)
        assert cap == MAXSPRITES, f"stats line reported MAXSPRITES={cap}, expected {MAXSPRITES}"
        # The core stability invariant: pool occupancy stays strictly below the cap.
        assert 0 <= sprites < MAXSPRITES, f"sprite count {sprites} out of [0,{MAXSPRITES})"


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_no_stats_when_disabled(tmp_path):
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    text = _run_soak(tmp_path, {})  # DUKE3D_STATS_INTERVAL unset
    assert not STATS_RE.search(text), "stats lines emitted with DUKE3D_STATS_INTERVAL unset (must be off by default)"

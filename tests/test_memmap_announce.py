"""In-game "what to do" hint (memmap-announce): the "HACK ME - READ THE MEMORY MAP LOG" HUD hint
tells the player the game is won by hacking the running process. It is GUIDANCE, not the answer
key (it reveals no flag string and no exact address — the per-flag walkthrough + ghvctf{} strings
stay developer-only), so it ships ON by default. DUKE3D_NO_HINTS=1 turns it off for a
no-hand-holding "hard mode" run, and is a hard override even in developer/validation mode.

Deterministic signal: the engine emits a 'MEMMAP-ANNOUNCE:' marker into
atomic_shell_startup.log (compat.h startup_log, flushed per-write) in the same
guarded block that calls adduserquote(...), so the marker's presence proves the
in-game hint fired.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # engine/
MARKER = "MEMMAP-ANNOUNCE:"


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


def _run_headless(tmp_path, extra_env):
    """Copy the runtime payload into tmp_path, run the engine headless past first
    level entry, and return the text of atomic_shell_startup.log (or "")."""
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
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
        "DUKE3D_SILENT_ERRORS": "1", "DUKE3D_AUTOPLAY": "1",
        "DUKE3D_MENU_KEYS": "28,28,28", "DUKE3D_FRAME_LIMIT": "400",
    })
    env.update(extra_env)
    proc = subprocess.Popen([str(binary)], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=90)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

    log = tmp_path / "atomic_shell_startup.log"
    return log.read_text(errors="replace") if log.is_file() else ""


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_memmap_announce_fires_for_players_by_default(tmp_path):
    """Shipped game shows the "what to do" hint: the memmap-announce fires by default."""
    text = _run_headless(tmp_path, {})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER in text, (
        f"'{MARKER}' must fire by default — players liked the in-game guidance pointing them at "
        "the memory-map log (it reveals no answers, only what to do)"
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_memmap_announce_silenced_by_no_hints(tmp_path):
    """DUKE3D_NO_HINTS=1 is hard mode: no in-game guidance."""
    text = _run_headless(tmp_path, {"DUKE3D_NO_HINTS": "1"})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER not in text, (
        f"DUKE3D_NO_HINTS=1 should suppress the announce, but '{MARKER}' was present"
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_memmap_announce_no_hints_overrides_validation(tmp_path):
    """DUKE3D_NO_HINTS=1 is a hard override even in developer/validation mode."""
    text = _run_headless(tmp_path, {"DUKE3D_VALIDATE": "1", "DUKE3D_NO_HINTS": "1"})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER not in text, (
        f"DUKE3D_NO_HINTS=1 must force-suppress the announce even with DUKE3D_VALIDATE=1, "
        f"but '{MARKER}' was present"
    )

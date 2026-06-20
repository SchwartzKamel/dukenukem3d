"""CTF integrity — G5 graduated stuck-nudge. The escalating hint spells out the hack ("freeze
your health", "set the boss HP to 0", "use Cheat Engine or scouter"), so it is a spoiler
walkthrough — a DEVELOPER/validation aid, NOT part of the shipped challenge. Off by default;
fires only in developer/validation mode (DUKE3D_ENABLE_CHEATS / DUKE3D_VALIDATE /
DUKE3D_SHOW_HINTS). DUKE3D_NO_HINTS=1 force-suppresses; stuck threshold tunable via
DUKE3D_HINT_STUCK_SECS.

Deterministic signal: the engine emits a 'G5-HINT:' marker into
atomic_shell_startup.log (compat.h startup_log, flushed per-write) in the same
guarded block that calls adduserquote(...). Under plain DUKE3D_AUTOPLAY the player
never hacks, so 0 flags capture (m-hackonly) -> the player is "stuck" -> the nudge
fires (when enabled).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # engine/
MARKER = "G5-HINT:"


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


def _run_headless(tmp_path, extra_env):
    """Copy the runtime payload into tmp_path, run the engine headless, and return
    the text of atomic_shell_startup.log (or "")."""
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
        "DUKE3D_MENU_KEYS": "28,28,28", "DUKE3D_FRAME_LIMIT": "10000",
        # low stuck threshold so the nudge fires quickly within the headless run
        # (game-tics accrue over the run; ~400 tics elapse here, well past 1s=30tics)
        "DUKE3D_HINT_STUCK_SECS": "1",
    })
    env.update(extra_env)
    proc = subprocess.Popen([str(binary)], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

    log = tmp_path / "atomic_shell_startup.log"
    return log.read_text(errors="replace") if log.is_file() else ""


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_g5_hint_silent_for_players_by_default(tmp_path):
    """A stuck player gets NO spoiler walkthrough by default (shipped challenge)."""
    text = _run_headless(tmp_path, {})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER not in text, (
        f"'{MARKER}' must NOT fire by default — the graduated hint is a developer aid that "
        "spells out the hack; players should get a challenge"
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_g5_hint_fires_in_validation_mode_when_stuck(tmp_path):
    """With the developer hint opt-in, a stuck player receives the escalating nudge."""
    text = _run_headless(tmp_path, {"DUKE3D_SHOW_HINTS": "1"})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER in text, (
        f"expected '{MARKER}' in atomic_shell_startup.log — DUKE3D_SHOW_HINTS=1 + a stuck "
        "player (autoplay, no hacking -> 0 captures) should receive the graduated hint"
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_g5_hint_no_hints_overrides_validation(tmp_path):
    """DUKE3D_NO_HINTS=1 is a hard override even with the opt-in on."""
    text = _run_headless(tmp_path, {"DUKE3D_SHOW_HINTS": "1", "DUKE3D_NO_HINTS": "1"})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER not in text, (
        f"DUKE3D_NO_HINTS=1 must force-suppress the g5-hint nudge, but '{MARKER}' was present"
    )

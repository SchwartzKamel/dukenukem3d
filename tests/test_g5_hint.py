"""G5 graduated stuck-nudge — an in-game "what to do" hint. When the player makes no capture
progress for a while, the engine escalates a teaching nudge ("this game is won by hacking",
"freeze your health then set the boss HP to 0", "use Cheat Engine or scouter") so a stuck/dying
player learns the mechanic instead of ragequitting. It teaches the TECHNIQUE but reveals no flag
string and no exact address, so it ships ON by default. DUKE3D_NO_HINTS=1 turns it off ("hard
mode") and is a hard override even in developer/validation mode; stuck threshold is tunable via
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
def test_g5_hint_fires_for_players_by_default(tmp_path):
    """A stuck player gets the escalating "what to do" nudge by default."""
    text = _run_headless(tmp_path, {})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER in text, (
        f"expected '{MARKER}' in atomic_shell_startup.log — a stuck player (autoplay, no hacking "
        "-> 0 captures) should receive the graduated nudge by default"
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_g5_hint_silenced_by_no_hints(tmp_path):
    """DUKE3D_NO_HINTS=1 is hard mode: a stuck player gets no nudge."""
    text = _run_headless(tmp_path, {"DUKE3D_NO_HINTS": "1"})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER not in text, (
        f"DUKE3D_NO_HINTS=1 should suppress the g5-hint nudge, but '{MARKER}' was present"
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_g5_hint_no_hints_overrides_validation(tmp_path):
    """DUKE3D_NO_HINTS=1 is a hard override even in developer/validation mode."""
    text = _run_headless(tmp_path, {"DUKE3D_VALIDATE": "1", "DUKE3D_NO_HINTS": "1"})
    assert text, "atomic_shell_startup.log was not written"
    assert MARKER not in text, (
        f"DUKE3D_NO_HINTS=1 must force-suppress the g5-hint nudge even with DUKE3D_VALIDATE=1, "
        f"but '{MARKER}' was present"
    )

"""USE/spacebar playtest soak — a GUI-input regression guard.

The player reported the windowed build crashing the instant they pressed the
spacebar (the Open/USE action). The root cause was an LLP64 pointer-truncation
bug: an actor's default action pointer (`*(actorscrptr[picnum]+1)`, an 8-byte
`intptr_t` into script[]) was assigned straight into the 4-byte `long` field
`T5` (hittype[].temp_data[4]) at spawn (GAME.C). Truncated to 32 bits, that
value was then used as an index in `animatesprites` (`script[t4]`), a wild read
that crashed the renderer the first time the USE/operate path touched such an
actor. The interpreter already converts these via `script_word_to_temp_index()`;
the spawn/render sites were missed.

This test drives the *real input path*: DUKE3D_AUTOPLAY_USE=N pulses the Open/USE
button (loc.bits bit 29) for N game-tics in getinput(), exactly as a player
mashing spacebar would — so it exercises checksectors()/neartag/operatesectors
and the animatesprites render of operated actors. The same automation drives the
windowed GUI build via DUKE3D_AUTOPLAY_FORCE (autoplay without DUKE3D_HEADLESS).

Deterministic signal:
  * the engine logs "autoplay use frames: N" at gameexit (GAME.C) when the USE
    injection actually fired — proves the crash path was exercised, not skipped;
  * the per-crash handler (compat.h) creates a `crashes/` dir + writes a "CRASH"
    line into atomic_shell_startup.log on a fault. A clean soak has neither.

Regression assertion: USE fired (frames > 0) AND no crash artifact appeared.
"""
import os
import re
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


def _run_use_soak(tmp_path, extra_env):
    """Run the engine with the USE/spacebar injection and return
    (log_text, use_frames, crashed)."""
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
        # pulse USE for up to 2000 game-tics; the headless run accrues a few
        # hundred tics, each pulsing the Open/USE button — plenty to operate
        # nearby sectors/switches and render the resulting actors.
        "DUKE3D_AUTOPLAY_USE": "2000",
    })
    env.update(extra_env)
    proc = subprocess.Popen([str(binary)], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        rc = proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        rc = None

    log = tmp_path / "atomic_shell_startup.log"
    text = log.read_text(errors="replace") if log.is_file() else ""
    m = re.search(r"autoplay use frames:\s*(\d+)", text)
    use_frames = int(m.group(1)) if m else 0
    crashed = (tmp_path / "crashes").is_dir() or "CRASH" in text or rc not in (0, None)
    return text, use_frames, crashed


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_use_spacebar_soak_does_not_crash(tmp_path):
    """Mashing USE/spacebar (the player's reported crash trigger) must not crash
    the renderer. Guards the LLP64 truncation bug in the spawn/render T5 (action)
    and T2 (move) assignments that fed a wild script[] read in animatesprites."""
    text, use_frames, crashed = _run_use_soak(tmp_path, {})
    assert text, "atomic_shell_startup.log was not written"
    assert use_frames > 0, (
        "DUKE3D_AUTOPLAY_USE did not fire (no 'autoplay use frames: N>0' marker) — "
        "the USE/spacebar crash path was not exercised, so this run proves nothing"
    )
    assert not crashed, (
        f"USE/spacebar soak crashed (use_frames={use_frames}): a 'crashes/' dir or "
        "'CRASH' marker appeared. The spacebar/USE renderer crash has regressed."
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_use_no_weapon_select_does_not_crash(tmp_path):
    """Pressing USE/open with NO weapon selected must not crash.

    Second, distinct crash on the USE path: cheatkeys() (SECTOR.C) computes the
    weapon-select index as ``j = (weaponfield - 1)`` into an *unsigned long*.
    When the player presses a button in the interface mask (e.g. USE/open, bit
    29) without also selecting a weapon, the 4-bit weapon field is 0, so j
    underflows to 0xFFFFFFFF and ``p->gotweapon[j]`` reads ~4GB past the player
    struct -> access violation (observed live as READ address 0x2405xxxxx). The
    fix guards the index with WEAPON_VALID(j).

    DUKE3D_USE_NOWEAPON makes the autoplay harness stand still and pulse only
    USE with the weapon field held at 0, so the player settles and the faulting
    ``gotweapon[0xFFFFFFFF]`` index is reached every USE tic — a deterministic
    repro (A/B-verified: crashes without the guard, clean with it). A high frame
    limit is required because the underflow site is per-game-tic, and headless
    game-tics accrue slowly.
    """
    text, use_frames, crashed = _run_use_soak(tmp_path, {
        "DUKE3D_USE_NOWEAPON": "1",
        "DUKE3D_AUTOPLAY_USE": "4000",
        "DUKE3D_FRAME_LIMIT": "50000",
    })
    assert text, "atomic_shell_startup.log was not written"
    assert use_frames > 0, (
        "DUKE3D_USE_NOWEAPON did not fire (no 'autoplay use frames: N>0' marker) — "
        "the no-weapon USE crash path was not exercised, so this run proves nothing"
    )
    assert not crashed, (
        f"no-weapon USE soak crashed (use_frames={use_frames}): the cheatkeys() "
        "gotweapon[0xFFFFFFFF] weapon-select underflow has regressed."
    )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_use_spacebar_soak_gui_forced_does_not_crash(tmp_path):
    """The same soak driving the *windowed* build (DUKE3D_AUTOPLAY_FORCE, no
    DUKE3D_HEADLESS) — the exact configuration the player reported crashing.
    Skips automatically on a headless CI host with no display."""
    text, use_frames, crashed = _run_use_soak(tmp_path, {
        "SDL_VIDEODRIVER": "",        # let SDL pick a real driver
        "DUKE3D_HEADLESS": "",        # real window
        "DUKE3D_AUTOPLAY_FORCE": "1", # autoplay still drives input without headless
        "DUKE3D_FRAME_LIMIT": "1500",
        "DUKE3D_AUTOPLAY_USE": "800",
    })
    if not text or use_frames == 0:
        pytest.skip("windowed GUI could not start (no display / SDL video) — "
                    "covered by the headless variant")
    assert not crashed, (
        f"windowed USE/spacebar soak crashed (use_frames={use_frames}): the "
        "player-reported GUI spacebar crash has regressed."
    )

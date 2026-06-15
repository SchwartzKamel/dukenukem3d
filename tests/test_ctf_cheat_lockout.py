"""CTF integrity (finding-set Y) — every flag must be memory-hack-gated (user directive
"all 5 should be hack gated"). Two pieces here:

* ctf-cheat-lockout: the in-game cheat-code system (DNCLIP/DNSTUFF) is OFF by default so
  it can't bypass flags 1/3; DUKE3D_ENABLE_CHEATS=1 re-enables it for debugging. Signal:
  the 'CHEATS:' marker in atomic_shell_startup.log.
* vault anti-brute-force (flag 4): a WRONG non-zero vault guess re-randomizes ctf_vault_code,
  so brute-forcing vault_input.txt never converges — the player must SCAN the live code.
  Signal: the 'code re-randomized' marker.

The intended memory-hacks still capture all 5 flags (e2e, separate).
See docs/plans/2026-06-15_CTF_INTEGRITY_AUDIT.md.
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


def _run(tmp_path, extra_env):
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
    env.pop("DUKE3D_ENABLE_CHEATS", None)        # ensure default-off unless the test sets it
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
def test_cheats_locked_by_default(tmp_path):
    """No DUKE3D_ENABLE_CHEATS -> the cheat-code system is locked (flags require hacking)."""
    text = _run(tmp_path, {})
    assert text, "engine wrote no startup log"
    assert "CHEATS: locked" in text, f"cheats must be locked by default; tail:\n{text[-600:]}"
    assert "CHEATS: ENABLED" not in text


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_cheats_reenabled_by_env(tmp_path):
    """DUKE3D_ENABLE_CHEATS=1 re-enables the cheat-code system (debug escape hatch)."""
    text = _run(tmp_path, {"DUKE3D_ENABLE_CHEATS": "1"})
    assert text, "engine wrote no startup log"
    assert "CHEATS: ENABLED" in text, f"env must re-enable cheats; tail:\n{text[-600:]}"


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_vault_wrong_guess_rerandomizes(tmp_path):
    """Flag 4 anti-brute-force: a wrong non-zero vault guess re-randomizes ctf_vault_code,
    so brute-forcing vault_input.txt can never converge (forces the intended memory-scan)."""
    # Pre-place a wrong guess so the first ~1 s vault check re-randomizes the code.
    (tmp_path / "vault_input.txt").write_text("1\n")
    text = _run(tmp_path, {"DUKE3D_FRAME_LIMIT": "8000"})
    assert text, "engine wrote no startup log"
    assert "code re-randomized" in text, (
        f"a wrong vault guess must re-randomize the code (anti-brute-force); tail:\n{text[-800:]}")

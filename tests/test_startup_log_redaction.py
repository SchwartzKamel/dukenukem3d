"""CTF integrity — the player startup log must not leak flag answers.

`atomic_shell_startup.log` is a plaintext file written into the game folder on every
launch (compat.h startup_log, fopen "w"). At level entry GAME.C initialises the Flag-5
vault code and syncs the Flag-3/4/5 teleport targets. Logging those *values* hands a
player the answers without any memory-hacking — a non-memory-hack bypass, which the CTF
forbids ("all flags must be hack-gated").

So the value/coordinate detail is gated behind _validation_mode() (DUKE3D_VALIDATE=1 or
cheats): developers/the e2e solver still get the full detail, while the shipped player
build logs only a redacted "initialised / synced" confirmation with no value, address, or
coordinate. The e2e solver does NOT read this file (it reads the memmap log + live
process memory), so gating it cannot break flag capture.

Deterministic signal: launch the engine headless past first level entry and read the
startup log. The unconditional 'CHEATS:' marker (emitted immediately before the vault
init) anchors that the CTF init block ran, so an absent leak token is a real redaction,
not a level that failed to load.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # engine/

# Anchor proving the CTF init block at level entry executed (logged unconditionally right
# before the vault-code init). Absence of a leak token only means "redacted" if this is present.
ANCHOR = "CHEATS:"

# Tokens that leak a flag answer — present ONLY in developer/validation mode, never in the
# shipped player log. vault_code= (Flag 5 answer) + addr=0x (its address); the ghost/timer/
# vault "synced to sector ... -> (x,y,z)" / "timer target (x,y)" coordinate lines (Flag 3/4/5
# teleport destinations a player would write straight into the position memory).
LEAK_TOKENS = [
    "vault_code=",
    "addr=0x",
    "synced to sector",   # CTF-1 ghost target coordinates
    "timer target (",     # CTF G1-A timer-room coordinates
    "vault target (",     # CTF G1-A vault-room coordinates
]

# Redacted confirmations the player build logs instead — prove the gating else-branch ran.
PLAYER_MARKERS = [
    "vault code initialised",
    "ghost teleport target ready",
    "arena targets synced",
]


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


def _run_headless(tmp_path, extra_env, drop_validate):
    """Copy the runtime payload into tmp_path, run the engine headless past first level
    entry, and return the text of atomic_shell_startup.log (or "")."""
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
    if drop_validate:
        # The player run must not silently unlock the full log via an inherited dev switch.
        env.pop("DUKE3D_VALIDATE", None)
        env.pop("DUKE3D_ENABLE_CHEATS", None)
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
def test_player_startup_log_redacts_ctf_answers(tmp_path):
    """Shipped player run: the startup log leaks no vault code, address, or target
    coordinate — finding those by hacking IS the challenge."""
    text = _run_headless(tmp_path, {}, drop_validate=True)
    if not text or ANCHOR not in text:
        pytest.skip("CTF init block did not run within the frame budget (level not entered)")
    for tok in LEAK_TOKENS:
        assert tok not in text, (
            f"player startup log leaks CTF answer token {tok!r} — vault code / target "
            "coordinates must be developer-only (DUKE3D_VALIDATE), never handed to players"
        )
    for marker in PLAYER_MARKERS:
        assert marker in text, (
            f"player startup log missing redacted confirmation {marker!r} — the gating "
            "else-branch should still log that the value was initialised, just not its value"
        )


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_validation_startup_log_keeps_ctf_detail(tmp_path):
    """Developer/validation run (DUKE3D_VALIDATE=1): the full vault code + target
    coordinates are restored, so the build stays debuggable and the e2e harness's
    expectations of validation-mode verbosity hold."""
    text = _run_headless(tmp_path, {"DUKE3D_VALIDATE": "1"}, drop_validate=False)
    if not text or ANCHOR not in text:
        pytest.skip("CTF init block did not run within the frame budget (level not entered)")
    assert "vault_code=" in text, "validation startup log should restore the vault code value"
    assert "vault target (" in text, "validation startup log should restore the vault target coords"
    assert "timer target (" in text, "validation startup log should restore the timer target coords"

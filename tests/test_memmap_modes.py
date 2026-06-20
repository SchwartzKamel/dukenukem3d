"""CTF integrity — tiered memory-map verbosity.

The memory-map log always lists every `key = 0xADDR` line (the hackable surface). The
`# EASY MODE …` cheatsheet and `# FLAG 1..6 …` per-flag walkthrough (with the flag strings) are
SPOILERS, so by DEFAULT (the shipped game) they are REDACTED — the player gets addresses, not
answers. Full "training" verbosity returns in developer/validation mode or via
DUKE3D_MEMMAP_MODE=training; DUKE3D_MEMMAP_MODE=spoiler_light forces redaction.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Address keys that MUST survive in both modes (the solver/players need them).
REQUIRED_KEYS = ["player_posx", "player_health", "ctf_timer",
                 "ctf_vault_code", "ctf_boss1_sprite"]
# Spoiler hint markers that must be present in training and ABSENT in spoiler_light.
SPOILER_MARKERS = ["EASY MODE", "FLAG 1"]


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


def _run_and_read_memmap(tmp_path, mode):
    """Launch the engine headless (optionally with DUKE3D_MEMMAP_MODE=mode) in an isolated
    working dir; return the text of the memory-map log it writes, or None."""
    solver = _solver()
    binary = solver._resolve_binary()
    grp = PROJECT_ROOT / "DUKE3D.GRP"
    if binary is None or not grp.is_file():
        pytest.skip("duke3d.exe / DUKE3D.GRP not built")

    workdir = tmp_path / (mode or "training")
    workdir.mkdir()
    shutil.copy(grp, workdir / "DUKE3D.GRP")
    for name in ("SDL2.dll", "DUKE3D.CFG"):
        src = PROJECT_ROOT / name
        if src.is_file():
            shutil.copy(src, workdir / name)

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy", "DUKE3D_HEADLESS": "1", "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_SILENT_ERRORS": "1", "DUKE3D_AUTOPLAY": "1",
        "DUKE3D_MENU_KEYS": "28,28,28", "DUKE3D_FRAME_LIMIT": "600",
    })
    if mode is not None:
        env["DUKE3D_MEMMAP_MODE"] = mode

    proc = subprocess.Popen([str(binary)], cwd=str(workdir), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=90)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

    memmap = workdir / "atomic_shell_memory_map.log"
    if not memmap.is_file():
        pytest.skip("memory map not produced (level did not load within the frame budget)")
    return memmap.read_text(errors="replace")


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_training_mode_has_keys_and_hints(tmp_path):
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    # Full verbosity is now a developer opt-in (the shipped default is redacted), so request it.
    text = _run_and_read_memmap(tmp_path, mode="training")
    for key in REQUIRED_KEYS:
        assert key in text, f"training memmap missing key {key!r}"
    for marker in SPOILER_MARKERS:
        assert marker in text, f"training memmap should contain hint {marker!r}"
    assert "# memmap mode: training" in text


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_default_is_redacted_for_players(tmp_path):
    """Unset MEMMAP_MODE with no validation unlock (the shipped player run) => redacted:
    addresses kept, but the EASY-MODE/per-flag walkthrough and flag strings stripped."""
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    text = _run_and_read_memmap(tmp_path, mode=None)  # unset + no validation == redacted
    for key in REQUIRED_KEYS:
        assert key in text, f"default memmap dropped key {key!r} (must keep all addresses)"
    for marker in SPOILER_MARKERS:
        assert marker not in text, (
            f"default memmap leaks spoiler {marker!r} — the shipped game must redact the "
            "walkthrough so players get a challenge, not the answer"
        )
    assert "ghvctf{" not in text, "default memmap leaks a flag string to players"
    assert "# memmap mode: spoiler_light" in text


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_spoiler_light_keeps_keys_drops_hints(tmp_path):
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    text = _run_and_read_memmap(tmp_path, mode="spoiler_light")
    # keys preserved …
    for key in REQUIRED_KEYS:
        assert key in text, f"spoiler_light memmap dropped key {key!r} (must keep all keys)"
    # … but the spoiler hints redacted.
    for marker in SPOILER_MARKERS:
        assert marker not in text, \
            f"spoiler_light memmap still leaks hint {marker!r} (should be redacted)"
    # no flag strings either
    assert "ghvctf{" not in text, "spoiler_light memmap leaks a flag string"
    assert "# memmap mode: spoiler_light" in text

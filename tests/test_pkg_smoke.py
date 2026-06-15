"""PKG-SMOKE — packaged-layout headless smoke test (Finding-set-F).

Copies the *shippable* runtime layout (renamed exe + SDL2.dll + GRP + CFG) into a
clean temp directory and boots the engine headless there, with no dependency on
the source/build tree as the working directory. It asserts the engine reaches the
CTF arena and writes its runtime artifacts (the memory-map log and the D1 event
funnel) into that packaged CWD — the thing that would silently break if a runtime
file path were ever hard-coded to the build tree instead of the current directory.

This is the unattended early-warning for "the zip we ship doesn't actually run":
it exercises the real packaged filename (atomic_shell.exe) from an isolated CWD,
so a packaging/path regression fails a deterministic test instead of a user.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_binary():
    for c in (PROJECT_ROOT / "build" / "Release" / "duke3d.exe",
              PROJECT_ROOT / "build" / "duke3d.exe",
              PROJECT_ROOT / "duke3d.exe"):
        if c.is_file():
            return c
    return None


def _run_packaged(workdir, timeout=70.0):
    """Stage the shippable layout in `workdir`, boot headless into the CTF arena,
    and return the runtime-artifact paths once they appear (or after `timeout`).

    Returns None if the engine binary or GRP is missing (caller skips)."""
    binary = _resolve_binary()
    grp = PROJECT_ROOT / "DUKE3D.GRP"           # bundles CTF1.MAP
    if binary is None or not grp.is_file():
        return None

    # mirror the shippable package: the *renamed* exe + runtime deps, clean CWD.
    exe = workdir / "atomic_shell.exe"
    shutil.copy(binary, exe)
    shutil.copy(grp, workdir / "DUKE3D.GRP")
    for name in ("SDL2.dll", "DUKE3D.CFG"):
        src = PROJECT_ROOT / name
        if src.is_file():
            shutil.copy(src, workdir / name)

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy", "DUKE3D_HEADLESS": "1",
        "DUKE3D_SKIP_LOGO": "1", "DUKE3D_SILENT_ERRORS": "1",
        "DUKE3D_AUTOPLAY": "1",
        "DUKE3D_MENU_KEYS": "28,28,28",   # Enter x3 -> NEW GAME -> CTF arena
    })

    memmap = workdir / "atomic_shell_memory_map.log"
    events = workdir / "atomic_shell_events.jsonl"
    proc = subprocess.Popen([str(exe)], cwd=str(workdir), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if (memmap.is_file() and events.is_file()
                    and "level_enter" in events.read_text(errors="replace")):
                break
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    return {"workdir": workdir,
            "startup": workdir / "atomic_shell_startup.log",
            "memmap": memmap, "events": events}


@pytest.mark.playtest
@pytest.mark.serial
def test_packaged_layout_boots_and_writes_runtime_logs(tmp_path):
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    if _resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    res = _run_packaged(tmp_path)
    if res is None:
        pytest.skip("engine binary or DUKE3D.GRP missing")

    present = sorted(p.name for p in tmp_path.iterdir())
    assert res["memmap"].is_file(), (
        "packaged headless boot did not write atomic_shell_memory_map.log into the "
        f"packaged CWD; files present: {present}")
    mm = res["memmap"].read_text(errors="replace")
    # the memmap is only fully written once the CTF level has loaded; these keys
    # prove the arena booted (not just the menu) and the writer ran to completion.
    assert "player_struct_cur" in mm and "ctf_boss1_sprite" in mm, mm[:600]

    assert res["events"].is_file(), (
        "packaged boot did not write the D1 event funnel atomic_shell_events.jsonl; "
        f"files present: {present}")
    ev = res["events"].read_text(errors="replace")
    assert "level_enter" in ev, ev[:600]

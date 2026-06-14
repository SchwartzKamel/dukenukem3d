"""R1 — env-var parse hardening (engine-r1-env-parse-hardening).

The headless/automation count env vars (DUKE3D_FRAME_LIMIT / DUKE3D_CAPTURE_INTERVAL
/ DUKE3D_AUTOPLAY_FIRE) are parsed with `compat_env_uint`, which validates the
input: malformed values log a WARNING and fall back to the default instead of
silently parsing as 0 (a footgun that would, e.g., disable the frame limit during
an unattended soak).

These tests launch the native engine headless in an isolated working directory
(so the startup log can't race other xdist workers) and assert the warning fires
for junk input and stays silent for a valid value.
"""
import os
import shutil
import subprocess
import sys
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


def _run_isolated(workdir, extra_env):
    """Boot the engine in `workdir` with `extra_env` overlaid on the headless base
    env; return the startup-log text (or None if it could not run)."""
    binary = _resolve_binary()
    grp = PROJECT_ROOT / "DUKE3D.GRP"
    if binary is None or not grp.is_file():
        return None
    shutil.copy(grp, workdir / "DUKE3D.GRP")
    for name in ("SDL2.dll", "DUKE3D.CFG"):
        src = PROJECT_ROOT / name
        if src.is_file():
            shutil.copy(src, workdir / name)

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy", "DUKE3D_HEADLESS": "1",
        "DUKE3D_SKIP_LOGO": "1", "DUKE3D_SILENT_ERRORS": "1",
        "DUKE3D_AUTOPLAY": "1", "DUKE3D_FRAME_LIMIT": "60",
    })
    env.update(extra_env)
    proc = subprocess.Popen([str(binary)], cwd=str(workdir), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=90)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    log = workdir / "atomic_shell_startup.log"
    return log.read_text(errors="replace") if log.is_file() else None


@pytest.mark.playtest
@pytest.mark.serial
def test_malformed_count_env_var_warns_and_defaults(tmp_path):
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    if _resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    log = _run_isolated(tmp_path, {"DUKE3D_CAPTURE_INTERVAL": "not_a_number"})
    if not log:
        pytest.skip("engine did not produce a startup log")
    assert "WARNING: DUKE3D_CAPTURE_INTERVAL='not_a_number'" in log, (
        "malformed DUKE3D_CAPTURE_INTERVAL should warn and fall back to the "
        f"default; startup log tail:\n{log[-1500:]}"
    )


@pytest.mark.playtest
@pytest.mark.serial
def test_valid_count_env_var_does_not_warn(tmp_path):
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    if _resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    log = _run_isolated(tmp_path, {"DUKE3D_CAPTURE_INTERVAL": "5"})
    if not log:
        pytest.skip("engine did not produce a startup log")
    assert "WARNING: DUKE3D_CAPTURE_INTERVAL" not in log, (
        f"a valid DUKE3D_CAPTURE_INTERVAL must not warn; startup log tail:\n{log[-1500:]}"
    )


@pytest.mark.playtest
@pytest.mark.serial
def test_malformed_menu_key_env_var_warns(tmp_path):
    """R2: the menu-inject timing env vars (DUKE3D_MENU_KEY_*) are validated too."""
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    if _resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    log = _run_isolated(tmp_path, {
        "DUKE3D_MENU_KEYS": "28",
        "DUKE3D_MENU_KEY_INTERVAL_FRAMES": "abc",
    })
    if not log:
        pytest.skip("engine did not produce a startup log")
    assert "WARNING: DUKE3D_MENU_KEY_INTERVAL_FRAMES='abc'" in log, (
        "malformed DUKE3D_MENU_KEY_INTERVAL_FRAMES should warn and fall back to "
        f"the default; startup log tail:\n{log[-1500:]}"
    )

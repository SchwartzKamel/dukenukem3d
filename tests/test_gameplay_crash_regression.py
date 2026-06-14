"""Regression test: gameplay-loop crash due to 32-bit tempscrptr pointer truncation.

Root cause (fixed in engine-r16-gamedef-scrptr-width):
  GAMEDEF.C parsecommand() declared `tempscrptr` as `long *`. On Windows x64 /
  MSVC, `long` is 32 bits. Storing `(intptr_t)scriptptr` (a 64-bit pointer) via
  a 32-bit pointer silently truncates the upper 32 bits. When the runtime
  `parseifelse` later reads the branch-target back as `intptr_t`, it gets a
  zero-extended 32-bit address, which is not mapped → access violation write /
  read crash at 0x000000000xxxxxxx inside the main gameplay loop.

Repro: launch `duke3d.exe /v1 /l1 /s2` headless — the game enters the level,
runs one frame of actor script, and crashes in parseifelse.  After the fix the
process must exit cleanly (exit code 0 or 1 without the C0000005 crash marker in
the startup log).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── helpers ──────────────────────────────────────────────────────────────────

def _resolve_binary() -> Path:
    exe = "duke3d.exe" if sys.platform == "win32" else "duke3d"
    for candidate in [
        PROJECT_ROOT / "build" / "Release" / exe,
        PROJECT_ROOT / "build" / exe,
        PROJECT_ROOT / exe,
    ]:
        if candidate.is_file():
            return candidate
    return PROJECT_ROOT / "build" / exe  # canonical; used in skip message


def _startup_log_path() -> Path:
    return PROJECT_ROOT / "atomic_shell_startup.log"


def _run_gameplay(extra_env=None, timeout=30, frame_limit="5", autoplay=False, fire=0,
                  capture_interval="5") -> dict:
    """Run duke3d headless with /v1 /l1 /s2 (warp-to-level) and return result.

    fire: DUKE3D_AUTOPLAY_FIRE tic cap (0 = off). Forces the weapon to discharge
    for that many game tics — bounded by tics so it stays deterministic under
    parallel/wall-clock load.
    """
    binary = _resolve_binary()
    if not binary.is_file():
        pytest.skip(f"Binary not found: {binary}")
    grp = PROJECT_ROOT / "DUKE3D.GRP"
    if not grp.is_file():
        pytest.skip("DUKE3D.GRP not found")

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy",
        "DUKE3D_HEADLESS":  "1",
        "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_SILENT_ERRORS": "1",
        # Default to a short run; callers can raise frame_limit for deeper coverage.
        "DUKE3D_FRAME_LIMIT":      frame_limit,
        "DUKE3D_CAPTURE_INTERVAL": capture_interval,
    })
    if autoplay:
        env["DUKE3D_AUTOPLAY"] = "1"
    if fire:
        # Force the Fire bit for `fire` game tics so the weapon discharges.
        env["DUKE3D_AUTOPLAY_FIRE"] = str(int(fire))
    if extra_env:
        env.update(extra_env)

    try:
        proc = subprocess.run(
            [str(binary), "/v1", "/l1", "/s2"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.decode(errors="replace"),
            "stderr": proc.stderr.decode(errors="replace"),
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -9, "stdout": "", "stderr": "timeout"}


def _read_startup_log() -> str:
    log = _startup_log_path()
    if log.is_file():
        try:
            return log.read_text(errors="replace")
        except OSError:
            return ""
    return ""


# ── regression tests ──────────────────────────────────────────────────────────

@pytest.mark.playtest
@pytest.mark.serial
def test_gameplay_warp_no_crash():
    """Warp to Volume 1 / Level 1 / Skill 2 must not crash with exit code 1 AND
    a CRASH marker in the startup log.  The old bug produced exit code 1 with
    'CRASH: Exception 0xC0000005' in atomic_shell_startup.log because
    parsecommand() stored script branch-target pointers via a 32-bit `long *`
    tempscrptr, truncating the upper 32 bits on x64."""
    result = _run_gameplay()

    log_text = _read_startup_log()
    has_crash_marker = "CRASH: Exception 0xC0000005" in log_text or \
                       "CRASH: Access violation" in log_text

    # The bug: exit_code==1 AND crash marker present
    assert not (result["exit_code"] == 1 and has_crash_marker), (
        "Gameplay crash regression detected!\n"
        "exit_code=1 with CRASH marker in startup log.\n"
        "Root cause: parsecommand() tempscrptr was `long *` (32-bit on MSVC x64).\n"
        f"Log tail:\n{log_text[-800:]}"
    )


@pytest.mark.playtest
@pytest.mark.serial
def test_gameplay_warp_no_crash_marker_in_log():
    """Startup log must not contain a C0000005 access-violation crash line after
    a warp-to-level run.  This guards the specific pointer-truncation crash."""
    _run_gameplay()   # run regardless of exit code; we check the log

    log_text = _read_startup_log()
    assert "CRASH: Exception 0xC0000005" not in log_text, (
        "Startup log contains an access-violation crash marker after warp run.\n"
        f"Log tail:\n{log_text[-800:]}"
    )
    assert "CRASH: Access violation" not in log_text, (
        "Startup log contains an access-violation crash marker after warp run.\n"
        f"Log tail:\n{log_text[-800:]}"
    )


@pytest.mark.playtest
@pytest.mark.serial
def test_gameplay_warp_autoplay_no_crash():
    """Focus-free autoplay path (DUKE3D_AUTOPLAY=1) must run without AV markers."""
    result = _run_gameplay(timeout=45, frame_limit="120", autoplay=True)

    log_text = _read_startup_log()
    has_crash_marker = "CRASH: Exception 0xC0000005" in log_text or \
                       "CRASH: Access violation" in log_text

    assert result["exit_code"] != -9, "Autoplay run timed out"
    assert not has_crash_marker, (
        "Autoplay gameplay produced an access-violation crash marker.\n"
        f"Log tail:\n{log_text[-800:]}"
    )


@pytest.mark.playtest
@pytest.mark.serial
def test_gameplay_warp_autoplay_fire_no_crash():
    """Discharging the weapon under autoplay must not crash.

    The normal autoplay path masks out the Fire bit (PLAYER.C getinput) to avoid
    projectile spam, so the weapon-fire code (shoot/hitscan/projectile-actor
    spawn + impact + shell ejection) was never exercised headless — exactly the
    path behind the user-reported "using the gun crashes us" defect on Win64.

    DUKE3D_AUTOPLAY_FIRE=N forces the weapon to discharge for N *game tics*. We
    cap at a small, deterministic count well below the ~46-tic threshold where a
    deeper, still-unfixed player-sprite corruption sets in under sustained fire
    (tracked as the intptr_t-migration "E1" in docs/agent/SAST_TRIAGE.md). Tic-
    bounding (not frame-bounding) keeps this green under parallel/wall-clock load,
    where render frames would otherwise drift into the deep-corruption regime.
    """
    result = _run_gameplay(timeout=90, frame_limit="6000", autoplay=True, fire=12,
                           capture_interval="0")

    log_text = _read_startup_log()
    has_crash_marker = "CRASH: Exception 0xC0000005" in log_text or \
                       "CRASH: Access violation" in log_text

    assert result["exit_code"] != -9, "Autoplay-fire run timed out"
    assert not has_crash_marker, (
        "Autoplay weapon-fire produced an access-violation crash marker.\n"
        f"Log tail:\n{log_text[-800:]}"
    )

    # The run must not end via the bogus sprite-exhaustion exit caused by an
    # out-of-range spawner sector (fixed in spawn()'s j>=0 branch).
    assert "Too many sprites spawned" not in log_text, (
        "Weapon fire hit the 'Too many sprites spawned.' exit — spawn() is "
        "not recovering an out-of-range spawner sector.\n"
        f"Log tail:\n{log_text[-800:]}"
    )

    # Guard against a vacuous pass: the engine logs how many tics the soak
    # actually forced fire. It must be > 0, otherwise the weapon-fire code was
    # never exercised and "no crash" proves nothing.
    fire_match = re.search(r"autoplay fire frames: (\d+)", log_text)
    assert fire_match and int(fire_match.group(1)) > 0, (
        "Fire soak did not actually discharge the weapon "
        "(no 'autoplay fire frames: N>0' in startup log) — test would be vacuous.\n"
        f"Log tail:\n{log_text[-800:]}"
    )

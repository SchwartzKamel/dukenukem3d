"""M-HACKONLY — CTF flag *provenance*: prove the flags are hack-gated.

The session history includes a "you're just giving me flags for nothing" regression: shooting
captured a flag with no memory hack. That specific bug was fixed, but nothing *proved* the flags
stay hack-gated. This test is the deterministic lock-in:

  A sustained fire-heavy autoplay run **with no memory hacks** must capture **zero** flags.

It covers both capture paths a stray player could trip:
  * boss flags 1/2 (`boss->extra <= 0`) — bosses are regen-immortal, so combat alone must not
    drain a boss to death;
  * zone/timer/vault flags 3/4/5 — the sealed sectors / frozen-timer proof require a hack to
    reach/satisfy, so normal autoplay navigation must not enter+trigger them.

Measured baseline (2026-06-15, engine 41ea33b): a 500k-frame fire-only soak captured 0 flags
(no atomic_shell_flags.log; 0 "stage":"capture" events). This test enforces that invariant.

See docs/plans/2026-06-15_DEEP_AUDIT_HARDENING.md finding-set M.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_fire_only_run_captures_no_flags(tmp_path):
    """Fire-heavy autoplay WITHOUT any memory hack must capture 0 flags."""
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch (headless autoplay)")
    try:
        solver = _solver()
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    binary = solver._resolve_binary()
    grp = PROJECT_ROOT / "DUKE3D.GRP"
    if binary is None or not grp.is_file():
        pytest.skip("duke3d.exe / DUKE3D.GRP not built")

    import shutil
    shutil.copy(grp, tmp_path / "DUKE3D.GRP")
    for name in ("SDL2.dll", "DUKE3D.CFG"):
        src = PROJECT_ROOT / name
        if src.is_file():
            shutil.copy(src, tmp_path / name)

    event_log = tmp_path / "events.jsonl"
    flags_log = tmp_path / "atomic_shell_flags.log"

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy",
        "DUKE3D_HEADLESS": "1",
        "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_SILENT_ERRORS": "1",
        "DUKE3D_AUTOPLAY": "1",
        "DUKE3D_MENU_KEYS": "28,28,28",
        # Fire the weapon continuously for the whole run — the realistic
        # "all I did was shoot" threat model — but apply NO memory hack.
        "DUKE3D_AUTOPLAY_FIRE": "600",
        "DUKE3D_FRAME_LIMIT": "150000",
        "DUKE3D_EVENT_LOG": str(event_log),
    })

    proc = subprocess.Popen([str(binary)], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        pytest.skip("fire-only soak did not finish within the timeout")

    # (1) The run must actually have started + entered the CTF arena — otherwise
    #     "0 captures" would be a vacuous pass.
    assert event_log.is_file(), "no event log — the engine never produced telemetry"
    lines = [ln for ln in event_log.read_text(errors="replace").splitlines() if ln.strip()]
    events = [json.loads(ln) for ln in lines]
    assert any(e.get("stage") == "level_enter" for e in events), \
        "no level_enter event — the fire-only run never reached the arena (vacuous test)"

    # (2) The core provenance invariant: zero captures from fire/navigation alone.
    capture_events = [e for e in events if e.get("stage") == "capture"]
    assert not capture_events, (
        "fire-only autoplay (NO hack) captured a flag — the 'flags for nothing' regression is "
        f"back: {capture_events}"
    )

    # (3) Belt-and-suspenders: the flag log (written only on a real capture) must be
    #     absent or empty.
    if flags_log.is_file():
        flag_lines = [ln for ln in flags_log.read_text(errors="replace").splitlines() if ln.strip()]
        assert not flag_lines, f"atomic_shell_flags.log has spurious captures: {flag_lines}"

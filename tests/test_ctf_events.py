"""D1 — flag-funnel telemetry: a headless solve run must produce a well-formed
atomic_shell_events.jsonl funnel for all 5 flags (layers on the I1 solve harness).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVENTS_LOG = PROJECT_ROOT / "atomic_shell_events.jsonl"
ALLOWED_STAGES = {"level_enter", "enter", "arm", "unlock", "progress", "capture"}


def _solver():
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    import e2e_solve_flags as solver
    return solver


@pytest.mark.playtest
@pytest.mark.serial
def test_solve_run_emits_wellformed_funnel(tmp_path):
    if sys.platform != "win32":
        pytest.skip("solve harness is Windows-only (WriteProcessMemory)")
    try:
        solver = _solver()
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    if solver._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")

    # isolate the event log per run (DUKE3D_EVENT_LOG) so the shared PROJECT_ROOT
    # log can't be raced by other engine tests under xdist.
    event_log = tmp_path / "events.jsonl"
    captured = solver.solve([0, 1, 2, 3, 4], verbose=False,
                            extra_env={"DUKE3D_EVENT_LOG": str(event_log)})
    assert all(captured.get(n) for n in range(5)), f"not all flags captured: {captured}"

    assert event_log.is_file(), "event log was not written"
    lines = [ln for ln in event_log.read_text(errors="replace").splitlines() if ln.strip()]
    assert lines, "events log is empty"

    events = []
    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(f"line {i} is not valid JSON: {exc}\n{line}")
        for field in ("ts", "clk", "flag", "stage", "detail"):
            assert field in obj, f"line {i} missing '{field}': {obj}"
        assert isinstance(obj["clk"], int) and isinstance(obj["flag"], int)
        assert obj["stage"] in ALLOWED_STAGES, f"unexpected stage: {obj['stage']}"
        events.append(obj)

    # clk monotonic non-decreasing (in-game time)
    clks = [e["clk"] for e in events]
    assert clks == sorted(clks), f"clk not monotonic: {clks}"

    # exactly one session marker
    assert sum(1 for e in events if e["stage"] == "level_enter") == 1, \
        "expected exactly one level_enter event"

    # every flag has a capture event
    captured_flags = {e["flag"] for e in events if e["stage"] == "capture"}
    assert captured_flags == {0, 1, 2, 3, 4}, f"capture events for: {captured_flags}"

    # funnel stages for the sector-based flags
    def stages_for(flag):
        return {e["stage"] for e in events if e["flag"] == flag}
    assert {"enter", "arm"} <= stages_for(2), f"flag 2 funnel: {stages_for(2)}"
    assert {"enter"} <= stages_for(3), f"flag 3 funnel: {stages_for(3)}"
    assert {"enter", "unlock"} <= stages_for(4), f"flag 4 funnel: {stages_for(4)}"

    # no (flag, stage) duplicates (the engine de-dups per session)
    keys = [(e["flag"], e["stage"]) for e in events]
    assert len(keys) == len(set(keys)), f"duplicate funnel events: {keys}"


@pytest.mark.playtest
@pytest.mark.serial
def test_events_opt_out(tmp_path):
    """DUKE3D_EVENTS=0 must write no event log (isolated working dir)."""
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

    import shutil
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
        "DUKE3D_EVENTS": "0",
    })
    proc = subprocess.Popen([str(binary)], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=90)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

    assert not (tmp_path / "atomic_shell_events.jsonl").exists(), \
        "DUKE3D_EVENTS=0 must suppress the event log, but it was written"

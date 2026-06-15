"""ctf-complete (finding-set AA1) — the all-flags completion moment + data point.

When the player captures all five flags, the engine emits a one-shot `all_captured`
funnel event (flag -1) carrying the completion clock (the time-to-complete data point
for analytics/leaderboard) and shows a payoff HUD banner. Validated end-to-end via the
solve harness:
  * full solve (5/5)      -> the `all_captured` event IS present.
  * partial solve (1 flag) -> it is ABSENT (proves it requires ALL flags, not any) —
                              the non-vacuous control.

The event is emitted BEFORE the flags.log write (compat/ctf.c), so it survives the
harness's kill-on-5th-flag (same flush-before-kill discipline as the per-flag capture
event). Windows-only (the solver uses WriteProcessMemory).
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _solver():
    if sys.platform != "win32":
        pytest.skip("solve harness is Windows-only (WriteProcessMemory)")
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    try:
        import e2e_solve_flags as solver
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    if solver._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    if not (PROJECT_ROOT / "DUKE3D.GRP").is_file():
        pytest.skip("DUKE3D.GRP not generated")
    return solver


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_all_captured_event_emitted_on_full_solve(tmp_path):
    """Capturing all 5 flags emits the one-shot all_captured completion event."""
    solver = _solver()
    ev = tmp_path / "events.jsonl"
    captured = solver.solve([0, 1, 2, 3, 4], verbose=True,
                            extra_env={"DUKE3D_EVENT_LOG": str(ev)})
    assert all(captured.get(n) for n in range(5)), f"not all flags captured: {captured}"
    text = ev.read_text(errors="replace") if ev.exists() else ""
    assert '"stage":"all_captured"' in text, (
        f"no all_captured completion event after 5/5 in the funnel:\n{text}")
    assert '"flag":-1' in text, (
        f"all_captured event missing the session flag (-1):\n{text}")


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_all_captured_absent_on_partial_solve(tmp_path):
    """Non-vacuous control: with only 1/5 flags captured, completion must NOT fire."""
    solver = _solver()
    ev = tmp_path / "events.jsonl"
    captured = solver.solve([0], verbose=True,
                            extra_env={"DUKE3D_EVENT_LOG": str(ev)})
    assert captured.get(0), f"flag 0 not captured (control setup failed): {captured}"
    text = ev.read_text(errors="replace") if ev.exists() else ""
    assert '"stage":"capture"' in text, (
        f"no capture event at all — event-log path may be broken:\n{text}")
    assert '"stage":"all_captured"' not in text, (
        f"all_captured fired with only 1/5 flags captured:\n{text}")

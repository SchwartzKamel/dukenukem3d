"""Tests for tools/ctf_analytics.py (roadmap D3).

A synthetic cohort with KNOWN funnel outcomes pins the exact metrics (pure, no
engine), and an integration test runs a real headless solve and asserts every flag
has capture_rate 1.0. Layers on the D1/I1 harness.
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(PROJECT_ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import ctf_analytics as ca  # noqa: E402


def _ev(clk, flag, stage):
    return json.dumps({"ts": "t", "clk": clk, "flag": flag, "stage": stage,
                       "detail": "d"})


# 3 sessions: A=5/5, B=enters timer (flag2) but never captures it, C=flag0 only.
_SESSION_A = [
    _ev(0, -1, "level_enter"),
    _ev(10, 0, "capture"), _ev(20, 1, "capture"),
    _ev(30, 2, "enter"), _ev(30, 2, "arm"), _ev(40, 2, "capture"),
    _ev(50, 3, "enter"), _ev(60, 3, "capture"),
    _ev(70, 4, "enter"), _ev(80, 4, "unlock"), _ev(90, 4, "capture"),
]
_SESSION_B = [_ev(0, -1, "level_enter"), _ev(5, 2, "enter"), _ev(5, 2, "arm")]
_SESSION_C = [_ev(0, -1, "level_enter"), _ev(12, 0, "capture")]
_COHORT = _SESSION_A + _SESSION_B + _SESSION_C


def test_parse_sessions_splits_on_level_enter():
    sessions = ca.parse_sessions(_COHORT)
    assert len(sessions) == 3
    assert [len(s) for s in sessions] == [11, 3, 2]


def test_compute_metrics_known_cohort():
    m = ca.compute_metrics(ca.parse_sessions(_COHORT))
    s = m["summary"]
    assert s["sessions"] == 3
    assert s["completion_rate"] == pytest.approx(1 / 3)
    assert s["flags_captured_dist"] == {5: 1, 0: 1, 1: 1}

    pf = m["per_flag"]
    # flag 0 captured in A (ttc 10) and C (ttc 12) -> rate 2/3, median 11
    assert pf[0]["capture_rate"] == pytest.approx(2 / 3)
    assert pf[0]["reached"]["capture"] == 2
    assert pf[0]["ttc"]["median"] == 11
    assert pf[0]["ttc"]["count"] == 2
    # flag 1 captured in A only
    assert pf[1]["capture_rate"] == pytest.approx(1 / 3)
    assert pf[1]["ttc"]["median"] == 20
    # flag 2: entered+armed in A and B (2 each), captured in A (1) -> dropoff 1/1
    assert pf[2]["capture_rate"] == pytest.approx(1 / 3)
    assert pf[2]["reached"]["enter"] == 2 and pf[2]["reached"]["arm"] == 2
    assert pf[2]["dropoff"] == {"enter": 1, "arm": 1}
    assert pf[2]["ttc"]["median"] == 40
    # flag 4: full funnel in A only
    assert pf[4]["reached"] == {"enter": 1, "arm": 0, "unlock": 1, "capture": 1}


def test_empty_cohort_is_safe():
    m = ca.compute_metrics([])
    assert m["summary"]["sessions"] == 0
    assert m["per_flag"][0]["capture_rate"] == 0.0
    assert m["per_flag"][0]["ttc"]["median"] is None


def test_main_cli(tmp_path, capsys):
    log = tmp_path / "events.jsonl"
    log.write_text("\n".join(_COHORT), encoding="utf-8")
    out_json = tmp_path / "metrics.json"
    assert ca.main([str(log), "--json", str(out_json)]) == 0
    printed = capsys.readouterr().out
    assert "cap_rate" in printed and "completion_rate" in printed
    saved = json.loads(out_json.read_text())
    assert saved["summary"]["sessions"] == 3


@pytest.mark.playtest
@pytest.mark.serial
def test_real_solve_run_metrics(tmp_path):
    """A real headless solve yields capture_rate 1.0 for all 5 flags."""
    if sys.platform != "win32":
        pytest.skip("solve harness is Windows-only (WriteProcessMemory)")
    try:
        import e2e_solve_flags as solver
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    if solver._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")

    event_log = tmp_path / "events.jsonl"
    captured = solver.solve([0, 1, 2, 3, 4], verbose=False,
                            extra_env={"DUKE3D_EVENT_LOG": str(event_log)})
    assert all(captured.get(n) for n in range(5)), captured
    assert event_log.is_file(), "event log not written"

    metrics = ca.compute_metrics(ca.parse_sessions(event_log.read_text().splitlines()))
    assert metrics["summary"]["sessions"] == 1
    for flag in range(5):
        assert metrics["per_flag"][flag]["capture_rate"] == 1.0, (flag, metrics)
    assert metrics["summary"]["completion_rate"] == 1.0

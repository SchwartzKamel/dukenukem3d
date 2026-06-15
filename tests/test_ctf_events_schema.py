"""Unit tests for tools/ctf_events_schema.py — the reusable D1 telemetry schema
validator. Pure-Python, no engine: proves it accepts a valid funnel and catches
malformed lines / bad stages / non-monotonic clk (D1-SCHEMA, Finding set E)."""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(PROJECT_ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import ctf_events_schema as ces  # noqa: E402

_GOOD = [
    '{"ts":"2026-06-14T00:00:00","clk":0,"flag":-1,"stage":"level_enter","detail":"CTF1"}',
    '{"ts":"2026-06-14T00:00:01","clk":12,"flag":2,"stage":"enter","detail":"timer_room"}',
    '{"ts":"2026-06-14T00:00:01","clk":20,"flag":2,"stage":"capture","detail":"ghvctf{x}"}',
]


def test_valid_log_has_no_errors():
    assert ces.validate_events(_GOOD) == []
    assert ces.validate_events(_GOOD + ["", "  "]) == []  # blank lines ignored


def test_invalid_json_is_caught():
    errors = ces.validate_events(['{"ts":"x","clk":0,'])
    assert errors and "JSON" in errors[0]


def test_missing_field_is_caught():
    errors = ces.validate_events(['{"ts":"x","clk":0,"flag":0,"stage":"capture"}'])
    assert any("detail" in e for e in errors), errors


def test_bad_stage_is_caught():
    errors = ces.validate_events(
        ['{"ts":"x","clk":0,"flag":0,"stage":"teleport","detail":"d"}'])
    assert any("stage" in e for e in errors), errors


def test_wrong_type_is_caught():
    errors = ces.validate_events(
        ['{"ts":"x","clk":"zero","flag":0,"stage":"capture","detail":"d"}'])
    assert any("clk" in e for e in errors), errors


def test_non_monotonic_clk_is_caught():
    rows = [
        '{"ts":"x","clk":50,"flag":0,"stage":"enter","detail":"d"}',
        '{"ts":"x","clk":10,"flag":0,"stage":"capture","detail":"d"}',
    ]
    errors = ces.validate_events(rows)
    assert any("monotonic" in e for e in errors), errors


def test_bool_is_not_a_valid_int_field():
    errors = ces.validate_events(
        ['{"ts":"x","clk":true,"flag":0,"stage":"capture","detail":"d"}'])
    assert any("clk" in e for e in errors), errors


def test_main_cli(tmp_path, capsys):
    good = tmp_path / "events.jsonl"
    good.write_text("\n".join(_GOOD), encoding="utf-8")
    assert ces.main([str(good)]) == 0
    assert "OK" in capsys.readouterr().out

    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"ts":"x"}', encoding="utf-8")
    assert ces.main([str(bad)]) == 1
    assert ces.main([]) == 2  # usage error

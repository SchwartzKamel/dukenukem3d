#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ctf_events_schema.py — validate the D1 telemetry log (atomic_shell_events.jsonl).

The engine emits one JSON object per line via ctf_event() (engine/compat/ctf.c):
`{ts, clk, flag, stage, detail}`. This is a reusable schema validator so future
field/escaping/stage drift in the funnel is caught cheaply, in tests and from the
CLI, rather than only by an ad-hoc check in one test.

Usage:  python ctf_events_schema.py atomic_shell_events.jsonl
Exit 0 = every line conforms; 1 = schema violations (printed); 2 = usage error.
"""
import json
import sys

# Mirrors the stage set emitted by GAME.C's CTF tick + ctf_emit_flag.
ALLOWED_STAGES = {"level_enter", "enter", "arm", "unlock", "progress", "capture"}

# (field, python type). bool is excluded from the int fields explicitly below.
_FIELDS = (("ts", str), ("clk", int), ("flag", int), ("stage", str), ("detail", str))


def validate_events(lines):
    """Return a list of human-readable schema violations (empty == valid).

    Checks, per non-blank line: valid JSON object; all required fields present and
    correctly typed; `stage` in ALLOWED_STAGES; and `clk` monotonic non-decreasing
    across the log (in-game time never goes backwards).
    """
    errors = []
    prev_clk = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {i}: invalid JSON ({exc})")
            continue
        if not isinstance(obj, dict):
            errors.append(f"line {i}: not a JSON object")
            continue
        for field, typ in _FIELDS:
            if field not in obj:
                errors.append(f"line {i}: missing field '{field}'")
                continue
            val = obj[field]
            # bool is a subclass of int — reject it for the numeric fields
            if typ is int and isinstance(val, bool):
                errors.append(f"line {i}: field '{field}' must be int, got bool")
            elif not isinstance(val, typ):
                errors.append(f"line {i}: field '{field}' must be {typ.__name__}, "
                              f"got {type(val).__name__}")
        if obj.get("stage") not in ALLOWED_STAGES:
            errors.append(f"line {i}: unknown stage {obj.get('stage')!r}")
        clk = obj.get("clk")
        if isinstance(clk, int) and not isinstance(clk, bool):
            if prev_clk is not None and clk < prev_clk:
                errors.append(f"line {i}: clk {clk} < previous {prev_clk} "
                              "(not monotonic)")
            prev_clk = clk
    return errors


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: ctf_events_schema.py <atomic_shell_events.jsonl>", file=sys.stderr)
        return 2
    try:
        with open(argv[0], "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as exc:
        print(f"cannot read {argv[0]}: {exc}", file=sys.stderr)
        return 2
    errors = validate_events(lines)
    if errors:
        print(f"event log schema FAILED ({argv[0]}):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"event log schema OK ({argv[0]}): {len(lines)} line(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

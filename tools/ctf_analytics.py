#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ctf_analytics.py — turn the D1 funnel into metrics (roadmap D3).

Consumes one or more `atomic_shell_events.jsonl` logs (from D1's `ctf_event`) and
computes, across the cohort of sessions: per-flag capture rate, time-to-capture,
funnel drop-off, and a session roll-up. This is the data-driven payoff that feeds
difficulty tuning (P3) and A/B comparison (D2).

Usage:
  python ctf_analytics.py [--json OUT.json] [--csv OUT.csv] FILE [FILE...]

`compute_metrics` is a pure function (no I/O) — the unit-test target. Exit 0 on
success; 2 on a usage error.
"""
import argparse
import json
import statistics
import sys

FLAGS = (0, 1, 2, 3, 4)
FLAG_NAMES = {0: "godmode", 1: "shield_down", 2: "frozen_clock",
              3: "ghost_walk", 4: "vault"}
# Per-flag points — mirrors the DC32 platform flags_config.yaml `points:` (godmode 3,
# shield_down 5, frozen_clock 5, ghost_walk 7, vault 10). Used to weight the efficiency score.
WEIGHTS = {0: 3, 1: 5, 2: 5, 3: 7, 4: 10}
# score = points * SCORE_POINT_UNIT - time_tics, so completion dominates and speed breaks ties
# (the unit exceeds any realistic session length in tics, ~55 min @ 30 Hz).
SCORE_POINT_UNIT = 100000
_INTERMEDIATE = ("enter", "arm", "unlock")
_STAGES = _INTERMEDIATE + ("capture",)


def parse_sessions(lines, stats=None):
    """Split JSONL event lines into sessions on each `level_enter` marker.

    Malformed lines are skipped (analytics is descriptive, not a validator — use
    ctf_events_schema.validate_events for strict checking). Events before the first
    level_enter form their own leading session.

    When `stats` (a dict) is provided it is populated with `total` (non-blank
    lines seen), `parsed`, and `skipped` counts plus a `skipped_detail` list of
    `(lineno, reason)` for the first few bad lines — so callers (and the CLI
    `--strict` mode) can surface otherwise-silent data loss.
    """
    sessions = []
    cur = None
    total = parsed = skipped = 0
    skipped_detail = []
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        total += 1
        try:
            obj = json.loads(line)
        except (ValueError, TypeError) as exc:
            skipped += 1
            if len(skipped_detail) < 10:
                skipped_detail.append((lineno, f"invalid JSON: {exc}"))
            continue
        if not isinstance(obj, dict):
            skipped += 1
            if len(skipped_detail) < 10:
                skipped_detail.append((lineno, "not a JSON object"))
            continue
        parsed += 1
        if obj.get("stage") == "level_enter":
            if cur is not None:
                sessions.append(cur)
            cur = []
        if cur is None:
            cur = []
        cur.append(obj)
    if cur is not None:
        sessions.append(cur)
    if stats is not None:
        stats.update(total=total, parsed=parsed, skipped=skipped,
                     skipped_detail=skipped_detail)
    return sessions


def _percentile(sorted_vals, pct):
    """Nearest-rank percentile of a pre-sorted list (or None if empty)."""
    if not sorted_vals:
        return None
    k = int(round((pct / 100.0) * (len(sorted_vals) - 1)))
    k = max(0, min(len(sorted_vals) - 1, k))
    return sorted_vals[k]


def _agg(values):
    if not values:
        return {"count": 0, "median": None, "p90": None, "min": None, "max": None}
    s = sorted(values)
    return {"count": len(s), "median": statistics.median(s),
            "p90": _percentile(s, 90), "min": s[0], "max": s[-1]}


def _session_start_clk(session):
    le = next((e for e in session if e.get("stage") == "level_enter"), None)
    if le is not None and isinstance(le.get("clk"), int):
        return le["clk"]
    return session[0].get("clk", 0) if session else 0


def compute_metrics(sessions):
    """Pure: sessions -> {'per_flag': {...}, 'summary': {...}}."""
    n = len(sessions)
    per_flag = {}
    for flag in FLAGS:
        reached = {st: 0 for st in _STAGES}
        ttcs = []
        for session in sessions:
            t0 = _session_start_clk(session)
            stages_here = {e.get("stage") for e in session if e.get("flag") == flag}
            for st in _STAGES:
                if st in stages_here:
                    reached[st] += 1
            cap = next((e for e in session if e.get("flag") == flag
                        and e.get("stage") == "capture"), None)
            if cap is not None and isinstance(cap.get("clk"), int):
                ttcs.append(cap["clk"] - t0)
        captures = reached["capture"]
        per_flag[flag] = {
            "name": FLAG_NAMES[flag],
            "sessions": n,
            "reached": reached,
            "capture_rate": (captures / n) if n else 0.0,
            "ttc": _agg(ttcs),
            "dropoff": {st: reached[st] - captures
                        for st in _INTERMEDIATE if reached[st] > captures},
        }

    # session roll-up
    dist = {}
    completions = 0
    for session in sessions:
        c = len({e.get("flag") for e in session
                 if e.get("stage") == "capture" and isinstance(e.get("flag"), int)
                 and e.get("flag") in FLAGS})
        dist[c] = dist.get(c, 0) + 1
        if c == len(FLAGS):
            completions += 1
    summary = {"sessions": n,
               "completion_rate": (completions / n) if n else 0.0,
               "flags_captured_dist": dist}
    return {"per_flag": per_flag, "summary": summary}


def score_session(session):
    """Pure: one session's events -> {points, flags, time_tics, score} (D-SCORE / W).

    points    = Σ WEIGHTS[f] over distinct flags whose stage == "capture".
    flags     = number of distinct captured flags.
    time_tics = last_capture_clk - level_enter_clk (0 if no capture).
    score     = points * SCORE_POINT_UNIT - time_tics  (completion dominates; among
                equal points, less time scores higher).
    """
    t0 = _session_start_clk(session)
    captured = set()
    last_cap_clk = None
    for e in session:
        if e.get("stage") != "capture":
            continue
        f = e.get("flag")
        if isinstance(f, bool) or not isinstance(f, int) or f not in WEIGHTS:
            continue
        captured.add(f)
        clk = e.get("clk")
        if isinstance(clk, int) and not isinstance(clk, bool):
            if last_cap_clk is None or clk > last_cap_clk:
                last_cap_clk = clk
    points = sum(WEIGHTS[f] for f in captured)
    time_tics = (last_cap_clk - t0) if last_cap_clk is not None else 0
    return {"points": points, "flags": len(captured), "time_tics": time_tics,
            "score": points * SCORE_POINT_UNIT - time_tics}


def leaderboard(sessions):
    """Pure: sessions -> ranked [{rank, score, points, flags, time_tics}] sorted by
    (points desc, time_tics asc) — the unambiguous key; `score` is the display value.
    Stable for equal keys; `rank` is 1..N contiguous."""
    scored = [score_session(s) for s in sessions]
    order = sorted(range(len(scored)),
                   key=lambda i: (-scored[i]["points"], scored[i]["time_tics"]))
    out = []
    for rank, i in enumerate(order, 1):
        row = dict(scored[i])
        row["rank"] = rank
        out.append(row)
    return out


def _format_table(metrics):
    rows = ["flag             cap_rate  sessions  ttc_median  reached(E/A/U/C)"]
    for flag in FLAGS:
        m = metrics["per_flag"][flag]
        r = m["reached"]
        rows.append(
            f"{flag} {m['name']:<13} {m['capture_rate']:>7.2f}  {m['sessions']:>8}  "
            f"{str(m['ttc']['median']):>10}  "
            f"{r['enter']}/{r['arm']}/{r['unlock']}/{r['capture']}")
    s = metrics["summary"]
    rows.append(f"\nsessions={s['sessions']}  completion_rate={s['completion_rate']:.2f}  "
                f"flags_captured_dist={s['flags_captured_dist']}")
    return "\n".join(rows)


def _format_leaderboard(lb):
    rows = ["rank  score      points  flags  time_tics"]
    for r in lb:
        rows.append(f"{r['rank']:>4}  {r['score']:>9}  {r['points']:>6}  "
                    f"{r['flags']:>5}  {r['time_tics']:>9}")
    return "\n".join(rows)


def _write_csv(metrics, path):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["flag", "name", "sessions", "capture_rate", "ttc_median",
                    "ttc_p90", "reached_enter", "reached_arm", "reached_unlock",
                    "reached_capture"])
        for flag in FLAGS:
            m = metrics["per_flag"][flag]
            r = m["reached"]
            w.writerow([flag, m["name"], m["sessions"], m["capture_rate"],
                        m["ttc"]["median"], m["ttc"]["p90"], r["enter"], r["arm"],
                        r["unlock"], r["capture"]])


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="CTF flag-funnel analytics (D3)")
    ap.add_argument("files", nargs="*", help="atomic_shell_events.jsonl log(s)")
    ap.add_argument("--json", help="write the metrics as JSON to this path")
    ap.add_argument("--csv", help="write the per-flag table as CSV to this path")
    ap.add_argument("--strict", action="store_true",
                    help="exit nonzero if any event line could not be parsed")
    ap.add_argument("--leaderboard", action="store_true",
                    help="also print a per-session efficiency-score leaderboard")
    args = ap.parse_args(argv)
    if not args.files:
        ap.error("at least one event-log file is required")
        return 2

    lines = []
    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines.extend(f.readlines())
        except OSError as exc:
            print(f"cannot read {path}: {exc}", file=sys.stderr)
            return 2

    stats = {}
    sessions = parse_sessions(lines, stats)
    metrics = compute_metrics(sessions)
    print(_format_table(metrics))
    lb = leaderboard(sessions) if args.leaderboard else None
    if lb is not None:
        print("\n" + _format_leaderboard(lb))
    if args.json:
        out = dict(metrics)
        if lb is not None:
            out["leaderboard"] = lb
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    if args.csv:
        _write_csv(metrics, args.csv)

    skipped = stats.get("skipped", 0)
    if skipped:
        print(f"\nskipped {skipped} malformed line(s) of {stats.get('total', 0)} "
              "(use ctf_events_schema.py to validate)")
        print(f"warning: skipped {skipped} malformed line(s) of "
              f"{stats.get('total', 0)}", file=sys.stderr)
        for lineno, reason in stats.get("skipped_detail", []):
            print(f"  line {lineno}: {reason}", file=sys.stderr)
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

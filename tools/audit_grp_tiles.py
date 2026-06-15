#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""audit_grp_tiles.py — validate every TILES*.ART tile archive inside a GRP (g-tile-audit).

For each ART entry it asserts the BUILD tile format is self-consistent: the concatenated
pixel data length equals sum(sizx*sizy) over the header's tile-size arrays (plus version
and bounds sanity). This catches asset-gen regressions — a truncated or over-long tile is
corrupt art the engine would mis-read. Runs in the suite (CI) and the staging smoke.

Usage:
  python tools/audit_grp_tiles.py [--grp DUKE3D.GRP]

Exit 0 if every ART validates; 1 if any fails; 2 on usage/IO error.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grp_format import read_grp
from art_format import read_art_file


def audit_grp(grp_bytes):
    """Validate every TILES*.ART entry in a GRP image.

    Returns (ok: bool, lines: list[str]) — one human-readable line per ART (or a single
    error line if no ART is present). ok is False if any ART is structurally invalid."""
    files = read_grp(grp_bytes)
    arts = sorted(n for n in files
                  if n.upper().startswith("TILES") and n.upper().endswith(".ART"))
    if not arts:
        return False, ["no TILES*.ART entry found in GRP"]
    ok = True
    lines = []
    for name in arts:
        try:
            info = read_art_file(files[name])
            px = sum(w * h for w, h, _ in info["tiles"])
            lines.append(
                f"OK   {name}: {len(info['tiles'])} tiles, {px} pixel bytes "
                f"(tiles {info['localtilestart']}..{info['localtileend']})")
        except ValueError as exc:
            ok = False
            lines.append(f"FAIL {name}: {exc}")
    return ok, lines


def main():
    ap = argparse.ArgumentParser(
        description="Validate GRP tile archives (sizx*sizy == pixel data bytes)")
    ap.add_argument("--grp", default="DUKE3D.GRP",
                    help="path to the GRP to audit (default: DUKE3D.GRP)")
    args = ap.parse_args()
    if not os.path.isfile(args.grp):
        print(f"audit_grp_tiles: GRP not found: {args.grp}", file=sys.stderr)
        return 2
    with open(args.grp, "rb") as f:
        ok, lines = audit_grp(f.read())
    for ln in lines:
        print(ln)
    print(f"\n{'PASS' if ok else 'FAIL'}: {len(lines)} ART archive(s) audited")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""repack_con.py — surgically swap CON file(s) inside an existing DUKE3D.GRP.

Replaces GAME.CON (and/or DEFS.CON / USER.CON) inside an existing GRP **without
regenerating any art** — every texture/sprite/sound entry is copied through
byte-for-byte. This is the safe build path for a CON-only gameplay edit (e.g.
boss-dmg-tune) that must NOT trigger the AI->procedural art regression of
`generate_assets.py --no-ai`. See docs/plans/2026-06-15_GRP-CON-REPACK_SPEC.md.

Usage:
  python tools/repack_con.py --grp DUKE3D.GRP --con generated_assets/GAME.CON \
      [--con generated_assets/USER.CON] [-o out.grp]

The GRP entry name is the CON file's basename, uppercased (e.g. GAME.CON). With no
-o the input --grp is overwritten in place. Exit 0 on success; 2 on usage/IO error.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grp_format import read_grp, replace_files


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Surgical CON-only GRP repack")
    ap.add_argument("--grp", required=True, help="path to the existing DUKE3D.GRP")
    ap.add_argument("--con", action="append", default=[], required=True,
                    help="CON file to inject (basename -> uppercased GRP entry); repeatable")
    ap.add_argument("-o", "--out", help="output GRP path (default: overwrite --grp)")
    args = ap.parse_args(argv)

    try:
        with open(args.grp, "rb") as f:
            grp = f.read()
    except OSError as exc:
        print(f"cannot read {args.grp}: {exc}", file=sys.stderr)
        return 2

    overrides = {}
    for con in args.con:
        name = os.path.basename(con).upper()
        try:
            with open(con, "rb") as f:
                overrides[name] = f.read()
        except OSError as exc:
            print(f"cannot read {con}: {exc}", file=sys.stderr)
            return 2

    try:
        new_grp = replace_files(grp, overrides)
    except (KeyError, ValueError) as exc:
        print(f"repack failed: {exc}", file=sys.stderr)
        return 2

    out = args.out or args.grp
    try:
        with open(out, "wb") as f:
            f.write(new_grp)
    except OSError as exc:
        print(f"cannot write {out}: {exc}", file=sys.stderr)
        return 2

    print(f"repacked {len(overrides)} file(s) ({', '.join(sorted(overrides))}) into "
          f"{out}  ({len(new_grp)} bytes, {len(read_grp(new_grp))} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

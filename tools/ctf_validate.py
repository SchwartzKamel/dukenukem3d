#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ctf_validate.py — assert the CTF arena map matches the engine's CTF contract.

This is a standing validation signal that catches generator/engine drift — the
exact bug class behind CTF-1 (the ghost-target desync). The engine
(`engine/source/GAME.C` CTF tick + `ACTORS.C` boss scan) requires the map to
contain exactly:

  - one timer sector  (sector lotag 0x544D)  — Flag 2 (frozen clock)
  - one ghost sector  (sector lotag 0x4754)  — Flag 3 (ghost walk)
  - one vault sector  (sector lotag 0x5641)  — Flag 4 (vault)
  - a Meatbag boss sprite (sprite hitag 0x0CF1) — Flag 0 (godmode)
  - a Warden  boss sprite (sprite hitag 0x0CF2) — Flag 1 (shield down)

and the ghost sector's wall centroid must equal the teleport target the engine
syncs into `ctf_ghost_target` at level load, i.e. (53072, 3072).

Usage:
  python ctf_validate.py            # validate generate_ctf_map.assemble_map()
  python ctf_validate.py CTF1.MAP   # validate a .MAP file

Exit 0 = contract holds; non-zero + diagnostics on any mismatch.
"""
import os
import struct
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# --- contract constants (mirror GAME.C / ACTORS.C / generate_ctf_map.py) ----
LOTAG_TIMER = 0x544D
LOTAG_GHOST = 0x4754
LOTAG_VAULT = 0x5641
HITAG_BOSS1 = 0x0CF1
HITAG_BOSS2 = 0x0CF2
GHOST_CENTROID = (53072, 3072)
GHOST_CENTROID_TOL = 64  # BUILD units

# struct layouts must match engine/tools/map_format.py (_pack_sector/_pack_wall/
# _pack_sprite). If they ever drift, parsing the real generated map fails the
# accompanying test_ctf_validate, surfacing the drift.
_SECTOR_FMT = "<hhiihhhhbBBBhhbBBBBBhhh"   # 40 bytes
_WALL_FMT = "<iihhhhhhbBBBBBhhh"           # 32 bytes
_SPRITE_FMT = "<iiihhbBBBBBbbhhhhhhhhhh"   # 44 bytes
_SECTOR_SZ = struct.calcsize(_SECTOR_FMT)
_WALL_SZ = struct.calcsize(_WALL_FMT)
_SPRITE_SZ = struct.calcsize(_SPRITE_FMT)


class MapParseError(ValueError):
    """Raised when the MAP bytes are structurally malformed."""


def parse_map(data):
    """Parse BUILD MAP v7 bytes into {'sectors','walls','sprites'} lists of dicts.

    Only the fields the CTF contract needs are surfaced. Raises MapParseError on
    a truncated/over-short buffer.
    """
    assert _SECTOR_SZ == 40 and _WALL_SZ == 32 and _SPRITE_SZ == 44, "struct drift"
    off = 0

    def need(n):
        if off + n > len(data):
            raise MapParseError(f"truncated MAP: need {n} bytes at offset {off}, "
                                f"have {len(data) - off}")

    need(20)
    version = struct.unpack_from("<i", data, 0)[0]
    if version != 7:
        raise MapParseError(f"unexpected MAP version {version} (expected 7)")
    off = 20  # version(4) + posx/y/z(12) + ang/cursectnum(4)

    need(2)
    numsectors = struct.unpack_from("<h", data, off)[0]
    off += 2
    sectors = []
    for _ in range(numsectors):
        need(_SECTOR_SZ)
        f = struct.unpack_from(_SECTOR_FMT, data, off)
        sectors.append({"wallptr": f[0], "wallnum": f[1],
                        "lotag": f[20] & 0xFFFF, "hitag": f[21] & 0xFFFF})
        off += _SECTOR_SZ

    need(2)
    numwalls = struct.unpack_from("<h", data, off)[0]
    off += 2
    walls = []
    for _ in range(numwalls):
        need(_WALL_SZ)
        f = struct.unpack_from(_WALL_FMT, data, off)
        walls.append({"x": f[0], "y": f[1]})
        off += _WALL_SZ

    need(2)
    numsprites = struct.unpack_from("<h", data, off)[0]
    off += 2
    sprites = []
    for _ in range(numsprites):
        need(_SPRITE_SZ)
        f = struct.unpack_from(_SPRITE_FMT, data, off)
        sprites.append({"picnum": f[4], "sectnum": f[13],
                        "lotag": f[20] & 0xFFFF, "hitag": f[21] & 0xFFFF})
        off += _SPRITE_SZ

    return {"sectors": sectors, "walls": walls, "sprites": sprites}


def _sector_centroid(parsed, sector):
    """Average (x, y) of a sector's walls."""
    walls = parsed["walls"]
    wp, wn = sector["wallptr"], sector["wallnum"]
    if wn <= 0 or wp < 0 or wp + wn > len(walls):
        return None
    xs = sum(walls[i]["x"] for i in range(wp, wp + wn))
    ys = sum(walls[i]["y"] for i in range(wp, wp + wn))
    return (xs // wn, ys // wn)


def validate_ctf_map(data):
    """Return a list of human-readable contract violations (empty == valid)."""
    errors = []
    try:
        parsed = parse_map(data)
    except MapParseError as exc:
        return [f"MAP parse failed: {exc}"]

    sectors, sprites = parsed["sectors"], parsed["sprites"]

    # --- exactly one of each tagged room ---------------------------------
    for tag, name in ((LOTAG_TIMER, "timer"), (LOTAG_GHOST, "ghost"),
                      (LOTAG_VAULT, "vault")):
        matches = [s for s in sectors if s["lotag"] == tag]
        if len(matches) != 1:
            errors.append(f"expected exactly 1 {name} sector (lotag 0x{tag:04X}), "
                          f"found {len(matches)}")

    # --- both boss sprites present ---------------------------------------
    for tag, name in ((HITAG_BOSS1, "Meatbag/BOSS1"), (HITAG_BOSS2, "Warden/BOSS2")):
        matches = [s for s in sprites if s["hitag"] == tag]
        if len(matches) < 1:
            errors.append(f"missing {name} boss sprite (hitag 0x{tag:04X})")

    # --- ghost-room centroid matches the synced teleport target ----------
    ghosts = [s for s in sectors if s["lotag"] == LOTAG_GHOST]
    if len(ghosts) == 1:
        centroid = _sector_centroid(parsed, ghosts[0])
        if centroid is None:
            errors.append("ghost sector has no valid wall loop for a centroid")
        else:
            dx = abs(centroid[0] - GHOST_CENTROID[0])
            dy = abs(centroid[1] - GHOST_CENTROID[1])
            if dx > GHOST_CENTROID_TOL or dy > GHOST_CENTROID_TOL:
                errors.append(
                    f"ghost centroid {centroid} drifted from the engine-synced "
                    f"ctf_ghost_target {GHOST_CENTROID} (tol {GHOST_CENTROID_TOL})")

    return errors


def _load_map_bytes(path):
    if path:
        with open(path, "rb") as f:
            return f.read()
    from generate_ctf_map import assemble_map
    return assemble_map()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    path = argv[0] if argv else None
    data = _load_map_bytes(path)
    errors = validate_ctf_map(data)
    src = path if path else "generate_ctf_map.assemble_map()"
    if errors:
        print(f"CTF map contract FAILED ({src}):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"CTF map contract OK ({src}): timer/ghost/vault sectors + both bosses "
          f"+ ghost centroid {GHOST_CENTROID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

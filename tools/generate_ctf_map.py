"""generate_ctf_map.py — Create CTF1.MAP for Atomic Shell hackable challenges.

Produces a BUILD engine v7 map with 5 challenge rooms:
    Room 0: Spawn / briefing
    Room 1: Boss Arena  — BOSS1 (Meatbag, hitag 0xCF1) + BOSS2 (Warden, hitag 0xCF2)
    Room 2: Timer Room  — sector lotag 0x544D (triggers ctf_timer countdown)
    Room 3: Vault Room  — sector lotag 0x5641 (vault door)
    Room 4: Ghost Room  — sector lotag 0x4754 (sealed, reachable only by teleport)

Usage::

    python engine/tools/generate_ctf_map.py

Writes dist/staging/CTF1.MAP  (creates dist/staging/ if needed).
"""

import os
import struct
import sys

# ---------------------------------------------------------------------------
# Make map_format importable from this script
# ---------------------------------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from map_format import _pack_sector, _pack_wall, _pack_sprite, _pack_map


# ---------------------------------------------------------------------------
# Tile / picnum constants (matching NAMES.H)
# ---------------------------------------------------------------------------
BOSS1       = 2630   # The Meatbag
BOSS2       = 2710   # The Warden
APLAYER     = 1405   # Player start marker (picnum)

# Wall / floor textures  (using procedurally generated tiles 0-16)
WALL_STEEL   = 0
WALL_NEON    = 3
WALL_TECH    = 4
WALL_DARK    = 11
FLOOR_METAL  = 1
CEIL_PIPE    = 2
FLOOR_TECH   = 5
FLOOR_LAVA   = 15


# ---------------------------------------------------------------------------
# CTF sector tag constants  (must match GAME.C)
# ---------------------------------------------------------------------------
LOTAG_TIMER  = 0x544D  # Flag 3: countdown timer room
LOTAG_GHOST  = 0x4754  # Flag 4: sealed ghost room
LOTAG_VAULT  = 0x5641  # Flag 5: vault room


# ---------------------------------------------------------------------------
# Room layout  (all dimensions in BUILD world units; 1 tile = 1024 units)
# ---------------------------------------------------------------------------
#
#   [Spawn(0)] <--> [Boss Arena(1)] <--> [Timer Room(2)] <--> [Vault(3)]
#
#   Ghost Room(4) — sealed, no portal, sits at a distant Y coordinate
#
# Each room is ROOM_W wide and ROOM_H tall (Y-axis).
# They are arranged horizontally (X-axis).

ROOM_W  = 10240   # 10 tiles wide
ROOM_H  = 10240   # 10 tiles tall
CEIL_Z  = -(48 << 8)   # ceiling height (negative = up)
FLOOR_Z = 0

# X origins of each connected room (increasing X = east)
# Room 0 starts at x=0, y=0 (player spawn in center)
ROOMS_X = [0, ROOM_W, 2 * ROOM_W, 3 * ROOM_W]  # spawn, boss, timer, vault
ROOMS_Y = 0  # all share y=0 baseline; room extends from y to y+ROOM_H

# Ghost room sits south of spawn, completely isolated
GHOST_X = 50000   # far away, only reachable by writing X/Y in memory
GHOST_Y = 0
GHOST_W = 6144
GHOST_H = 6144


def build_room(x0, y0, w, h,
               wall_pic=WALL_STEEL,
               floor_pic=FLOOR_METAL, ceil_pic=CEIL_PIPE,
               ceil_z=CEIL_Z, floor_z=FLOOR_Z,
               lotag=0, hitag=0,
               portal_east_sector=-1, portal_west_sector=-1):
    """Return (sector_bytes, wall_bytes_list, first_wall_index).

    A rectangular room with optional east/west portals.

    Portal walls share an opening: this generator creates a full 4-wall room
    and marks the portal wall with nextsector / nextwall.  The caller must
    ensure that the neighbour room's portal wall index is consistent.

    Wall order: 0=north, 1=east, 2=south, 3=west
    """
    walls = []

    verts = [
        (x0,     y0),      # NW
        (x0 + w, y0),      # NE
        (x0 + w, y0 + h),  # SE
        (x0,     y0 + h),  # SW
    ]

    for wi in range(4):
        vx, vy = verts[wi]
        point2 = (wi + 1) % 4   # relative; caller adjusts to global index

        nextwall_idx = -1
        nextsect     = -1

        if wi == 1 and portal_east_sector >= 0:   # east wall → east neighbour west wall (wi=3)
            nextsect     = portal_east_sector
            # nextwall = base_wall_of_east_sector + 3  — filled in after all walls known
            nextwall_idx = -2   # sentinel: to be patched

        if wi == 3 and portal_west_sector >= 0:   # west wall → west neighbour east wall (wi=1)
            nextsect     = portal_west_sector
            nextwall_idx = -3   # sentinel: to be patched

        walls.append(dict(
            x=vx, y=vy, point2=point2,
            nextwall=nextwall_idx, nextsector=nextsect,
            picnum=wall_pic, xrepeat=8, yrepeat=8,
            lotag=lotag if wi == 0 else 0,
        ))

    sector = _pack_sector(
        wallptr=0,          # patched later
        wallnum=4,
        ceilingz=ceil_z,
        floorz=floor_z,
        ceilingpicnum=ceil_pic,
        floorpicnum=floor_pic,
        lotag=lotag,
        hitag=hitag,
    )

    return sector, walls


def assemble_map():
    """Assemble the full CTF map and return bytes."""

    all_sectors  = []
    all_walls    = []
    all_sprites  = []
    sector_wall_base = []   # first wall index of each sector

    # -----------------------------------------------------------------------
    # Build 4 connected rooms (spawn, boss, timer, vault)
    # -----------------------------------------------------------------------
    num_connected = 4
    for si in range(num_connected):
        x0 = ROOMS_X[si]
        y0 = ROOMS_Y

        east_sect = si + 1 if si < num_connected - 1 else -1
        west_sect = si - 1 if si > 0 else -1

        lotag = 0
        if si == 2:   lotag = LOTAG_TIMER   # Flag 3
        if si == 3:   lotag = LOTAG_VAULT    # Flag 5

        floor_pic = FLOOR_TECH  if si in (1, 3) else FLOOR_METAL
        ceil_pic  = CEIL_PIPE
        wall_pic  = WALL_DARK   if si == 1 else WALL_STEEL

        sector_bytes, room_walls = build_room(
            x0, y0, ROOM_W, ROOM_H,
            wall_pic=wall_pic,
            floor_pic=floor_pic,
            ceil_pic=ceil_pic,
            lotag=lotag,
            portal_east_sector=east_sect,
            portal_west_sector=west_sect,
        )

        wbase = len(all_walls)
        sector_wall_base.append(wbase)
        all_sectors.append(sector_bytes)
        all_walls.extend(room_walls)

    # Ghost room (sector 4) — isolated, no portals
    ghost_sector_bytes, ghost_walls = build_room(
        GHOST_X, GHOST_Y, GHOST_W, GHOST_H,
        wall_pic=WALL_NEON,
        floor_pic=FLOOR_TECH,
        ceil_pic=CEIL_PIPE,
        lotag=LOTAG_GHOST,   # Flag 4
    )
    ghost_sect_idx = len(all_sectors)
    ghost_wbase    = len(all_walls)
    sector_wall_base.append(ghost_wbase)
    all_sectors.append(ghost_sector_bytes)
    all_walls.extend(ghost_walls)

    # -----------------------------------------------------------------------
    # Patch wall point2, nextwall, and sector wallptr offsets
    # -----------------------------------------------------------------------
    # First pass: resolve relative point2 to global wall index
    wall_offset = 0
    for si in range(len(all_sectors)):
        wbase = sector_wall_base[si]
        num_w = 4
        for wi in range(num_w):
            w = all_walls[wbase + wi]
            # Resolve point2 (was relative 0-3, now global)
            w['point2'] = wbase + (wi + 1) % num_w

            # Resolve portal nextwall sentinels
            if w['nextsector'] >= 0:
                ns = w['nextsector']
                ns_wbase = sector_wall_base[ns]
                if w['nextwall'] == -2:   # east portal → west wall of east neighbour
                    w['nextwall'] = ns_wbase + 3
                elif w['nextwall'] == -3: # west portal → east wall of west neighbour
                    w['nextwall'] = ns_wbase + 1

    # Second pass: rebuild sector bytes with correct wallptr
    rebuilt_sectors = []
    for si in range(len(all_sectors)):
        wbase = sector_wall_base[si]
        # Re-unpack and repack sector with correct wallptr
        # Sector struct: hh ii hh hh bBBB hh bBBB BB hhh  (40 bytes)
        s = all_sectors[si]
        fields = struct.unpack("<hh ii hh hh bBBB hh bBBB BB hhh", s)
        fields = list(fields)
        fields[0] = wbase   # wallptr
        rebuilt_sectors.append(struct.pack("<hh ii hh hh bBBB hh bBBB BB hhh", *fields))

    # Pack walls
    packed_walls = []
    for w in all_walls:
        packed_walls.append(_pack_wall(
            w['x'], w['y'], w['point2'],
            nextwall=w['nextwall'], nextsector=w['nextsector'],
            picnum=w['picnum'], xrepeat=w.get('xrepeat', 8), yrepeat=w.get('yrepeat', 8),
            lotag=w.get('lotag', 0),
        ))

    # -----------------------------------------------------------------------
    # Sprites
    # -----------------------------------------------------------------------

    # Player start (spawn room, sector 0 center)
    spawn_cx = ROOMS_X[0] + ROOM_W // 2
    spawn_cy = ROOMS_Y + ROOM_H // 2
    all_sprites.append(_pack_sprite(
        x=spawn_cx, y=spawn_cy, z=FLOOR_Z - (32 << 8),
        picnum=APLAYER,
        cstat=0, shade=0,
        xrepeat=32, yrepeat=32,
        sectnum=0, statnum=0,
        ang=512,
    ))

    # Boss arena sprites (sector 1)
    boss_cx = ROOMS_X[1] + ROOM_W // 2
    boss_cy = ROOMS_Y + ROOM_H // 2

    # BOSS1 — The Meatbag (health regen boss)
    # hitag = 0x0CF1 → CTF regen trigger
    # extra = 9999 → initial health
    all_sprites.append(_pack_sprite(
        x=boss_cx - 1500, y=boss_cy,
        z=FLOOR_Z,                # feet on the floor (was -14336, above the ceiling)
        picnum=BOSS1,
        cstat=0, shade=-5,
        xrepeat=80, yrepeat=80,
        sectnum=1, statnum=1,   # statnum=1 → active actor
        ang=1536,               # face west (toward player)
        hitag=0x0CF1,
        extra=9999,             # initial health
    ))

    # BOSS2 — The Warden (RPG-only boss)
    # hitag = 0x0CF2 → CTF RPG-only trigger
    all_sprites.append(_pack_sprite(
        x=boss_cx + 1500, y=boss_cy,
        z=FLOOR_Z,                # feet on the floor (was above the ceiling)
        picnum=BOSS2,
        cstat=0, shade=-5,
        xrepeat=80, yrepeat=80,
        sectnum=1, statnum=1,
        ang=1536,
        hitag=0x0CF2,
        extra=5000,
    ))

    # Timer room decoration (sector 2)
    timer_cx = ROOMS_X[2] + ROOM_W // 2
    timer_cy = ROOMS_Y + ROOM_H // 2
    # A hostile actor to create urgency while frozen clock ticks
    all_sprites.append(_pack_sprite(
        x=timer_cx, y=timer_cy,
        z=FLOOR_Z,                # feet on the floor
        picnum=BOSS1,           # BOSS1 regular (no hitag = not CTF regen)
        cstat=0, shade=10,
        xrepeat=48, yrepeat=48,
        sectnum=2, statnum=1,
        ang=1536,
        extra=200,
    ))

    # Vault room — a sign sprite hinting at vault_input.txt
    vault_cx = ROOMS_X[3] + ROOM_W // 2
    vault_cy = ROOMS_Y + ROOM_H // 2
    all_sprites.append(_pack_sprite(
        x=vault_cx, y=vault_cy - 2000,
        z=FLOOR_Z - (32 << 8),
        picnum=9,               # holo terminal
        cstat=0, shade=-20,
        xrepeat=48, yrepeat=48,
        sectnum=3, statnum=0,
        ang=512,
        lotag=0x5641,           # vault door marker
    ))

    # Ghost room — just a bright glow sprite (reward)
    ghost_cx = GHOST_X + GHOST_W // 2
    ghost_cy = GHOST_Y + GHOST_H // 2
    all_sprites.append(_pack_sprite(
        x=ghost_cx, y=ghost_cy,
        z=FLOOR_Z - (24 << 8),
        picnum=8,               # glowing pickup
        cstat=0, shade=-30,
        xrepeat=64, yrepeat=64,
        sectnum=ghost_sect_idx, statnum=0,
    ))

    # -----------------------------------------------------------------------
    # Assemble MAP
    # -----------------------------------------------------------------------
    return _pack_map(
        sectors=rebuilt_sectors,
        walls=packed_walls,
        sprites=all_sprites,
        player_x=spawn_cx,
        player_y=spawn_cy,
        player_z=FLOOR_Z - (32 << 8),
        player_ang=512,
        player_sect=0,
    )


if __name__ == "__main__":
    out_dir = os.path.join(_here, "..", "..", "dist", "staging")
    out_dir = os.path.normpath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "CTF1.MAP")
    data = assemble_map()

    with open(out_path, "wb") as f:
        f.write(data)

    print(f"CTF1.MAP written: {out_path}  ({len(data)} bytes)")
    print(f"Sectors: 5  Walls: {5*4}  Sprites: 6")
    print()
    print("Room layout:")
    print("  Sector 0: Spawn room")
    print("  Sector 1: Boss Arena  (BOSS1 hitag=0xCF1, BOSS2 hitag=0xCF2)")
    print("  Sector 2: Timer Room  (lotag=0x544D)")
    print("  Sector 3: Vault Room  (lotag=0x5641)")
    print("  Sector 4: Ghost Room  (lotag=0x4754, isolated — teleport only)")
    print()
    print("Ghost room teleport target:")
    print(f"  X = {GHOST_X + GHOST_W // 2}")
    print(f"  Y = {GHOST_Y + GHOST_H // 2}")
    print(f"  Z = {FLOOR_Z - (32 << 8)}")
    print()
    print("Load in-game with:  warp to E1L1 then load CTF1.MAP")

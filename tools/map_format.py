"""MAP file creator for BUILD engine (map version 7).

Creates a simple playable test map: a rectangular room with textured
walls, floor, ceiling and the player start in the centre.
"""

import struct


def _pack_sector(wallptr, wallnum, ceilingz, floorz,
                 ceilingstat=0, floorstat=0,
                 ceilingpicnum=2, ceilingheinum=0,
                 ceilingshade=0, ceilingpal=0,
                 ceilingxpanning=0, ceilingypanning=0,
                 floorpicnum=1, floorheinum=0,
                 floorshade=0, floorpal=0,
                 floorxpanning=0, floorypanning=0,
                 visibility=64, filler=0,
                 lotag=0, hitag=0, extra=-1):
    """Pack a 40-byte sector structure."""
    return struct.pack(
        "<hh ii hh hh bBBB hh bBBB BB hhh",
        wallptr, wallnum,
        ceilingz, floorz,
        ceilingstat, floorstat,
        ceilingpicnum, ceilingheinum,
        ceilingshade, ceilingpal, ceilingxpanning, ceilingypanning,
        floorpicnum, floorheinum,
        floorshade, floorpal, floorxpanning, floorypanning,
        visibility, filler,
        lotag, hitag, extra,
    )


def _pack_wall(x, y, point2, nextwall=-1, nextsector=-1,
               cstat=0, picnum=0, overpicnum=0,
               shade=0, pal=0, xrepeat=8, yrepeat=8,
               xpanning=0, ypanning=0,
               lotag=0, hitag=0, extra=-1):
    """Pack a 32-byte wall structure."""
    return struct.pack(
        "<ii hhh h hh bBBBBB hhh",
        x, y,
        point2, nextwall, nextsector,
        cstat,
        picnum, overpicnum,
        shade, pal, xrepeat, yrepeat, xpanning, ypanning,
        lotag, hitag, extra,
    )


def _pack_sprite(x, y, z, cstat=0, picnum=0,
                 shade=0, pal=0, clipdist=32, filler=0,
                 xrepeat=64, yrepeat=64, xoffset=0, yoffset=0,
                 sectnum=0, statnum=0, ang=0,
                 owner=-1, xvel=0, yvel=0, zvel=0,
                 lotag=0, hitag=0, extra=-1):
    """Pack a 44-byte sprite structure."""
    return struct.pack(
        "<iii h h bBBB BB bb hh h hhhh hhh",
        x, y, z,
        cstat,
        picnum,
        shade, pal, clipdist, filler,
        xrepeat, yrepeat, xoffset, yoffset,
        sectnum, statnum,
        ang,
        owner, xvel, yvel, zvel,
        lotag, hitag, extra,
    )


def create_test_map():
    """Create a cyberpunk megastructure test room.

    A larger room (24576x24576 BUILD units) with dark steel walls, neon
    circuit accents, corroded metal floor, and pipe ceiling.  Sprites
    placed for visual interest: toxic waste pools, holo terminals, and
    item pickups.

    Returns:
        bytes of a complete MAP v7 file.
    """
    # Player start
    posx, posy = 0, 0
    posz = -(32 << 8)  # standard standing height
    ang = 512  # face north
    cursectnum = 0

    sectors = []
    walls = []
    sprites = []

    # --- Outer room (sector 0) --- larger than before
    half = 12288
    outer_verts = [
        (-half, -half),
        (half, -half),
        (half, half),
        (-half, half),
    ]

    wall_start = len(walls)
    num_outer_walls = len(outer_verts)
    # Alternate dark steel (0) and neon circuit (3) accent walls
    wall_tiles = [0, 3, 0, 3]
    for i, (vx, vy) in enumerate(outer_verts):
        next_idx = wall_start + (i + 1) % num_outer_walls
        walls.append(_pack_wall(vx, vy, next_idx,
                                picnum=wall_tiles[i], xrepeat=8, yrepeat=8))

    sectors.append(_pack_sector(
        wallptr=wall_start,
        wallnum=num_outer_walls,
        ceilingz=-(64 << 10),   # ceiling high up
        floorz=0,               # floor at z=0
        ceilingpicnum=2,        # exposed pipe ceiling
        floorpicnum=1,          # corroded metal floor
        visibility=96,
        ceilingshade=-5,
        floorshade=0,
    ))

    # --- Sprites for visual interest ---

    # Toxic waste pools in corners
    toxic_positions = [
        (-8000, -8000),
        (8000, -8000),
        (8000, 8000),
        (-8000, 8000),
    ]
    for cx, cy in toxic_positions:
        sprites.append(_pack_sprite(
            x=cx, y=cy, z=0,
            picnum=8,   # toxic waste pool
            cstat=32,   # floor-aligned
            shade=-15,
            xrepeat=64, yrepeat=64,
            sectnum=0, statnum=0,
        ))

    # Holo terminals along the walls
    terminal_positions = [
        (-4000, -half + 512, 512),   # north wall, face south
        (4000, -half + 512, 512),
        (-4000, half - 512, 1536),   # south wall, face north
        (4000, half - 512, 1536),
    ]
    for tx, ty, tang in terminal_positions:
        sprites.append(_pack_sprite(
            x=tx, y=ty, z=-(32 << 8),
            picnum=9,   # holographic terminal
            cstat=0,
            shade=-25,
            xrepeat=48, yrepeat=48,
            ang=tang,
            sectnum=0, statnum=0,
        ))

    # Item pickups scattered around the room
    item_sprites = [
        (0, -3000, 20),    # stim-pack health
        (0, 3000, 21),     # plasma cell ammo
        (-3000, 0, 22),    # nano-shield armor
        (3000, 0, 26),     # pulse pistol
        (-5000, -5000, 23),  # access chip blue
        (5000, 5000, 24),    # access chip red
    ]
    for ix, iy, ipic in item_sprites:
        sprites.append(_pack_sprite(
            x=ix, y=iy, z=-(16 << 8),
            picnum=ipic,
            cstat=0,
            shade=-20,
            xrepeat=32, yrepeat=32,
            sectnum=0, statnum=0,
        ))

    # --- Pack MAP header ---
    data = struct.pack("<i", 7)  # mapversion
    data += struct.pack("<ii i", posx, posy, posz)
    data += struct.pack("<hh", ang, cursectnum)

    # Sectors
    data += struct.pack("<h", len(sectors))
    for s in sectors:
        data += s

    # Walls
    data += struct.pack("<h", len(walls))
    for w in walls:
        data += w

    # Sprites
    data += struct.pack("<h", len(sprites))
    for sp in sprites:
        data += sp

    return data

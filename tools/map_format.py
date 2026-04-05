"""MAP file creator for BUILD engine (map version 7).

Creates playable maps: a simple test room (``create_test_map``) and fully
procedural multi-room levels for all four episodes (``create_level_map``).
"""

import random
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


# ---------------------------------------------------------------------------
# Episode theme definitions for procedural level generation
# ---------------------------------------------------------------------------

_EPISODE_THEMES = {
    1: {  # City – dark steel, neon circuits, urban
        'wall_pics': [0, 3, 4, 11],
        'floor_pic': 1, 'ceil_pic': 2,
        'vis': 64, 'ceil_shade': -5, 'floor_shade': 0,
        'base_ceil': -(48 << 8), 'pal': 0,
        'deco_pics': [8, 9, 11],
    },
    2: {  # Space station – tech panels, hex floors
        'wall_pics': [4, 7, 16, 3],
        'floor_pic': 5, 'ceil_pic': 2,
        'vis': 48, 'ceil_shade': -10, 'floor_shade': -5,
        'base_ceil': -(40 << 8), 'pal': 0,
        'deco_pics': [9, 16, 7],
    },
    3: {  # Underground – concrete, bio-growth, lava
        'wall_pics': [10, 14, 13, 12],
        'floor_pic': 12, 'ceil_pic': 13,
        'vis': 96, 'ceil_shade': 5, 'floor_shade': 5,
        'base_ceil': -(56 << 8), 'pal': 0,
        'deco_pics': [13, 15, 14],
    },
    4: {  # Hell – magma, rust, organic decay
        'wall_pics': [13, 14, 15, 8],
        'floor_pic': 15, 'ceil_pic': 13,
        'vis': 80, 'ceil_shade': 10, 'floor_shade': 10,
        'base_ceil': -(52 << 8), 'pal': 1,
        'deco_pics': [15, 8, 13],
    },
}

# Direction → (my wall index, neighbour's wall index)
_PORTAL_MAP = {
    (0, -1): (0, 2),   # north neighbour
    (1, 0):  (1, 3),   # east neighbour
    (0, 1):  (2, 0),   # south neighbour
    (-1, 0): (3, 1),   # west neighbour
}

_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _random_walk(rng, num_rooms):
    """Generate *num_rooms* grid positions via a connected random walk."""
    positions = [(0, 0)]
    visited = {(0, 0)}
    attempts = 0
    while len(positions) < num_rooms and attempts < 5000:
        attempts += 1
        src = rng.choice(positions)
        d = rng.choice(_DIRECTIONS)
        npos = (src[0] + d[0], src[1] + d[1])
        if npos not in visited:
            positions.append(npos)
            visited.add(npos)
    return positions


def _pack_map(sectors, walls, sprites, player_x, player_y, player_z,
              player_ang=512, player_sect=0):
    """Assemble sectors/walls/sprites into a complete MAP v7 byte-string."""
    data = struct.pack("<i", 7)
    data += struct.pack("<iii", player_x, player_y, player_z)
    data += struct.pack("<hh", player_ang, player_sect)

    data += struct.pack("<h", len(sectors))
    for s in sectors:
        data += s

    data += struct.pack("<h", len(walls))
    for w in walls:
        data += w

    data += struct.pack("<h", len(sprites))
    for sp in sprites:
        data += sp

    return data


def create_level_map(episode, level):
    """Create a procedurally generated multi-room level.

    Each episode has a distinct visual theme:

    * Episode 1 (City) – dark steel, neon circuits, urban feel
    * Episode 2 (Space Station) – tech panels, hex floors, low ceilings
    * Episode 3 (Underground) – concrete, bio-growth, lava vents
    * Episode 4 (Hell) – magma, rust, organic decay

    Every map contains a player-start sprite (picnum 0) in the first room
    and an exit-switch sprite (lotag 65535) in the last room so the level
    is completable.

    Args:
        episode: Episode number (1-4).
        level:   Level number (1-11).

    Returns:
        ``bytes`` – a complete MAP v7 file.
    """
    rng = random.Random(episode * 1000 + level * 31 + 42)

    theme = _EPISODE_THEMES.get(episode, _EPISODE_THEMES[1])

    # Room count grows with level number (3 → 8 rooms)
    num_rooms = 3 + level // 2
    room_size = 8192 + rng.randint(-1500, 1500)

    # --- layout ----------------------------------------------------------
    positions = _random_walk(rng, num_rooms)
    pos_to_idx = {pos: i for i, pos in enumerate(positions)}

    sectors = []
    walls = []
    sprites = []
    floor_heights = []

    for i, (gx, gy) in enumerate(positions):
        x = gx * room_size
        y = gy * room_size
        s = room_size

        verts = [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]
        wall_start = len(walls)

        wall_pic = theme['wall_pics'][i % len(theme['wall_pics'])]

        for w_idx in range(4):
            vx, vy = verts[w_idx]
            point2 = wall_start + (w_idx + 1) % 4

            nextwall = -1
            nextsector = -1
            for (dx, dy), (my_w, their_w) in _PORTAL_MAP.items():
                if my_w == w_idx:
                    nbr = pos_to_idx.get((gx + dx, gy + dy), -1)
                    if nbr >= 0:
                        nextsector = nbr
                        nextwall = 4 * nbr + their_w
                    break

            walls.append(_pack_wall(
                vx, vy, point2,
                nextwall=nextwall, nextsector=nextsector,
                picnum=wall_pic, xrepeat=8, yrepeat=8,
            ))

        # Vary floor / ceiling per room for visual interest
        floor_z = rng.choice([0, 0, 0, 512, 1024, -512, -1024])
        ceil_offset = rng.randint(-4096, 4096)
        floor_heights.append(floor_z)

        sectors.append(_pack_sector(
            wallptr=wall_start,
            wallnum=4,
            ceilingz=theme['base_ceil'] + ceil_offset,
            floorz=floor_z,
            ceilingpicnum=theme['ceil_pic'],
            floorpicnum=theme['floor_pic'],
            visibility=theme['vis'],
            ceilingshade=theme['ceil_shade'],
            floorshade=theme['floor_shade'],
        ))

        # --- per-room decorative sprites ---------------------------------
        cx = x + s // 2
        cy = y + s // 2

        # Item pickups in middle rooms
        if 0 < i < len(positions) - 1:
            item_pic = rng.choice([20, 21, 22, 23, 24, 26])
            sprites.append(_pack_sprite(
                x=cx + rng.randint(-s // 4, s // 4),
                y=cy + rng.randint(-s // 4, s // 4),
                z=floor_z - (16 << 8),
                picnum=item_pic,
                xrepeat=32, yrepeat=32,
                sectnum=i,
            ))

        # Episode-flavoured decoration every few rooms
        deco_pic = theme['deco_pics'][i % len(theme['deco_pics'])]
        if i % 3 == 0 and i != 0:
            sprites.append(_pack_sprite(
                x=cx + rng.randint(-2000, 2000),
                y=cy + rng.randint(-2000, 2000),
                z=floor_z,
                picnum=deco_pic, cstat=32, shade=-15,
                xrepeat=48, yrepeat=48,
                sectnum=i,
            ))

    # --- player start (always first sprite, picnum 0) --------------------
    p0 = positions[0]
    px = p0[0] * room_size + room_size // 2
    py = p0[1] * room_size + room_size // 2
    pz = floor_heights[0] - (32 << 8)
    sprites.insert(0, _pack_sprite(
        x=px, y=py, z=pz,
        picnum=0, ang=512,
        sectnum=0,
    ))

    # --- exit switch in last room ----------------------------------------
    last = positions[-1]
    last_idx = len(positions) - 1
    ex = last[0] * room_size + room_size // 2
    ey = last[1] * room_size + room_size // 2
    sprites.append(_pack_sprite(
        x=ex, y=ey, z=floor_heights[last_idx] - (24 << 8),
        picnum=9, lotag=-1,
        xrepeat=48, yrepeat=48,
        sectnum=last_idx,
    ))

    return _pack_map(sectors, walls, sprites, px, py, pz)

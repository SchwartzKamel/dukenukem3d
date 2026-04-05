"""Demo file (.dmo) format for Duke Nukem 3D.

Demo format (from source/GAME.C):
  Header (675 bytes for single-player):
    - 4 bytes: frame count (int32 LE)
    - 1 byte:  BYTEVERSION (116 for full, 27 for shareware)
    - 1 byte:  volume number
    - 1 byte:  level number
    - 1 byte:  player skill
    - 1 byte:  cooperative mode
    - 1 byte:  friendly fire flag
    - 2 bytes: multimode / number of players (short LE)
    - 2 bytes: monsters off flag (short LE)
    - 4 bytes: respawn monsters (int32 LE)
    - 4 bytes: respawn items (int32 LE)
    - 4 bytes: respawn inventory (int32 LE)
    - 4 bytes: player AI setting (int32 LE)
    - 512 bytes: user names (16 players * 32 chars)
    - 4 bytes: auto-run mode (int32 LE)
    - 128 bytes: board filename (custom map, null-padded)
    - 1 byte per player: aim mode

  Frame data (10 bytes per player per frame):
    - 1 byte:  avel  (signed char, angle velocity)
    - 1 byte:  horz  (signed char, horizon)
    - 2 bytes: fvel  (short LE, forward velocity)
    - 2 bytes: svel  (short LE, side velocity)
    - 4 bytes: bits  (uint32 LE, button bits)
"""

import struct

# BYTEVERSION from source/DUKE3D.H
BYTEVERSION_FULL = 116
BYTEVERSION_SHAREWARE = 27

MAXPLAYERS = 16
USERNAME_LEN = 32
BOARD_FILENAME_LEN = 128

# Per-frame input record size (sizeof(input) from DUKE3D.H)
INPUT_RECORD_SIZE = 10

# Header field sizes
HEADER_FIXED_SIZE = (
    4      # frame count
    + 1    # BYTEVERSION
    + 1    # volume
    + 1    # level
    + 1    # skill
    + 1    # coop
    + 1    # ffire
    + 2    # multimode
    + 2    # monsters off
    + 4    # respawn monsters
    + 4    # respawn items
    + 4    # respawn inventory
    + 4    # player AI
    + MAXPLAYERS * USERNAME_LEN  # user names (512)
    + 4    # auto-run
    + BOARD_FILENAME_LEN  # board filename (128)
)

assert HEADER_FIXED_SIZE == 674


def create_demo_header(
    num_frames=0,
    version=BYTEVERSION_FULL,
    volume=0,
    level=0,
    skill=2,
    coop=0,
    ffire=0,
    multimode=1,
    monsters_off=0,
    respawn_monsters=0,
    respawn_items=0,
    respawn_inventory=0,
    player_ai=0,
    auto_run=0,
    board_filename=b"",
    player_names=None,
    aim_modes=None,
):
    """Build a demo file header.

    Returns:
        bytes: The complete header (674 + multimode bytes).
    """
    buf = b""
    buf += struct.pack("<i", num_frames)
    buf += struct.pack("B", version)
    buf += struct.pack("B", volume)
    buf += struct.pack("B", level)
    buf += struct.pack("B", skill)
    buf += struct.pack("B", coop)
    buf += struct.pack("B", ffire)
    buf += struct.pack("<h", multimode)
    buf += struct.pack("<h", monsters_off)
    buf += struct.pack("<i", respawn_monsters)
    buf += struct.pack("<i", respawn_items)
    buf += struct.pack("<i", respawn_inventory)
    buf += struct.pack("<i", player_ai)

    # User names: 16 players * 32 chars each
    if player_names is None:
        player_names = [b""] * MAXPLAYERS
    names_block = b""
    for i in range(MAXPLAYERS):
        name = player_names[i] if i < len(player_names) else b""
        names_block += name[:USERNAME_LEN].ljust(USERNAME_LEN, b"\x00")
    buf += names_block

    buf += struct.pack("<i", auto_run)
    buf += board_filename[:BOARD_FILENAME_LEN].ljust(
        BOARD_FILENAME_LEN, b"\x00"
    )

    # Per-player aim modes
    if aim_modes is None:
        aim_modes = bytes(multimode)
    buf += aim_modes[:multimode].ljust(multimode, b"\x00")

    return buf


def create_demo_stub(
    version=BYTEVERSION_FULL,
    volume=0,
    level=0,
    skill=2,
):
    """Create a minimal valid .dmo file with zero frames.

    The game reads the frame count from offset 0.  A count of zero causes
    demo playback to end immediately (the read loop exits when reccnt == 0),
    which is exactly what we want for a stub.

    Args:
        version: BYTEVERSION (116=full, 27=shareware).
        volume:  Episode/volume number.
        level:   Level number within the episode.
        skill:   Difficulty (0-3, default 2 = medium).

    Returns:
        bytes: A complete .dmo file.
    """
    return create_demo_header(
        num_frames=0,
        version=version,
        volume=volume,
        level=level,
        skill=skill,
    )


def create_demo_frame(avel=0, horz=0, fvel=0, svel=0, bits=0):
    """Encode a single input record (10 bytes).

    Returns:
        bytes: Packed input struct.
    """
    return struct.pack("<bbhhI", avel, horz, fvel, svel, bits)


def create_timbre_stub():
    """Create a minimal d3dtimbr.tmb stub.

    The game's loadtmb() reads the file into an 8000-byte buffer and passes
    it to MUSIC_RegisterTimbreBank().  The timbre bank format is an array of
    instrument definitions used by the OPL FM synthesizer.  An all-zeros
    file is safe — it simply means all instruments map to silence.

    Returns:
        bytes: 256 zero bytes (minimal valid timbre bank).
    """
    return b"\x00" * 256

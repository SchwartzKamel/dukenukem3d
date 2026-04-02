"""Tests for MAP file generation."""
import struct
from map_format import create_test_map


def test_map_version():
    """MAP file has version 7."""
    data = create_test_map()
    version = struct.unpack_from("<i", data, 0)[0]
    assert version == 7


def test_map_has_sectors():
    """MAP file has at least one sector."""
    data = create_test_map()
    # Skip: version(4) + posx(4) + posy(4) + posz(4) + ang(2) + cursectnum(2) = 20
    numsectors = struct.unpack_from("<h", data, 20)[0]
    assert numsectors >= 1


def test_map_has_walls():
    """MAP file has walls."""
    data = create_test_map()
    numsectors = struct.unpack_from("<h", data, 20)[0]
    # Skip past sector data: 22 + numsectors * 40
    wall_offset = 22 + numsectors * 40
    numwalls = struct.unpack_from("<h", data, wall_offset)[0]
    assert numwalls >= 3  # minimum for a closed sector


def test_map_player_position():
    """Player starts at a reasonable position."""
    data = create_test_map()
    posx, posy, posz = struct.unpack_from("<iii", data, 4)
    # Position should be within reasonable BUILD engine range
    assert -65536 <= posx <= 65536
    assert -65536 <= posy <= 65536


def test_map_sector_size():
    """Each sector is exactly 40 bytes."""
    data = create_test_map()
    numsectors = struct.unpack_from("<h", data, 20)[0]
    wall_offset = 22 + numsectors * 40
    # Verify we can read numwalls at expected offset
    numwalls = struct.unpack_from("<h", data, wall_offset)[0]
    assert numwalls > 0  # if sector size was wrong, this would be garbage


def test_map_wall_size():
    """Walls are 32 bytes each, sprites are 44 bytes each."""
    data = create_test_map()
    numsectors = struct.unpack_from("<h", data, 20)[0]
    wall_offset = 22 + numsectors * 40
    numwalls = struct.unpack_from("<h", data, wall_offset)[0]
    sprite_count_offset = wall_offset + 2 + numwalls * 32
    # Should be able to read sprite count at expected offset
    numsprites = struct.unpack_from("<h", data, sprite_count_offset)[0]
    assert numsprites >= 0
    # Total size should match
    expected_size = sprite_count_offset + 2 + numsprites * 44
    assert len(data) == expected_size

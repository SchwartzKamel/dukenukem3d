"""Tests for MAP file generation."""
import struct
import pytest
from map_format import create_test_map, create_level_map


# ---- Helpers for parsing MAP data ----------------------------------------

def _parse_map_header(data):
    """Return (version, posx, posy, posz, ang, cursectnum)."""
    ver = struct.unpack_from("<i", data, 0)[0]
    posx, posy, posz = struct.unpack_from("<iii", data, 4)
    ang, csn = struct.unpack_from("<hh", data, 16)
    return ver, posx, posy, posz, ang, csn


def _parse_map_counts(data):
    """Return (numsectors, numwalls, numsprites, total_expected_size)."""
    numsectors = struct.unpack_from("<h", data, 20)[0]
    wall_off = 22 + numsectors * 40
    numwalls = struct.unpack_from("<h", data, wall_off)[0]
    sprite_off = wall_off + 2 + numwalls * 32
    numsprites = struct.unpack_from("<h", data, sprite_off)[0]
    expected = sprite_off + 2 + numsprites * 44
    return numsectors, numwalls, numsprites, expected


def _find_sprite_picnums(data):
    """Return list of picnum values for every sprite in the map."""
    numsectors = struct.unpack_from("<h", data, 20)[0]
    wall_off = 22 + numsectors * 40
    numwalls = struct.unpack_from("<h", data, wall_off)[0]
    sprite_off = wall_off + 2 + numwalls * 32
    numsprites = struct.unpack_from("<h", data, sprite_off)[0]
    base = sprite_off + 2
    picnums = []
    for i in range(numsprites):
        # sprite struct: x(4)+y(4)+z(4)+cstat(2)+picnum(2) → picnum at +12
        picnum = struct.unpack_from("<h", data, base + i * 44 + 12)[0]
        picnums.append(picnum)
    return picnums


# ---- Existing create_test_map tests (unchanged) -------------------------

def test_map_version():
    """MAP file has version 7."""
    data = create_test_map()
    version = struct.unpack_from("<i", data, 0)[0]
    assert version == 7


def test_map_has_sectors():
    """MAP file has at least one sector."""
    data = create_test_map()
    numsectors = struct.unpack_from("<h", data, 20)[0]
    assert numsectors >= 1


def test_map_has_walls():
    """MAP file has walls."""
    data = create_test_map()
    numsectors = struct.unpack_from("<h", data, 20)[0]
    wall_offset = 22 + numsectors * 40
    numwalls = struct.unpack_from("<h", data, wall_offset)[0]
    assert numwalls >= 3  # minimum for a closed sector


def test_map_player_position():
    """Player starts at a reasonable position."""
    data = create_test_map()
    posx, posy, posz = struct.unpack_from("<iii", data, 4)
    assert -65536 <= posx <= 65536
    assert -65536 <= posy <= 65536


def test_map_sector_size():
    """Each sector is exactly 40 bytes."""
    data = create_test_map()
    numsectors = struct.unpack_from("<h", data, 20)[0]
    wall_offset = 22 + numsectors * 40
    numwalls = struct.unpack_from("<h", data, wall_offset)[0]
    assert numwalls > 0  # if sector size was wrong, this would be garbage


def test_map_wall_size():
    """Walls are 32 bytes each, sprites are 44 bytes each."""
    data = create_test_map()
    numsectors = struct.unpack_from("<h", data, 20)[0]
    wall_offset = 22 + numsectors * 40
    numwalls = struct.unpack_from("<h", data, wall_offset)[0]
    sprite_count_offset = wall_offset + 2 + numwalls * 32
    numsprites = struct.unpack_from("<h", data, sprite_count_offset)[0]
    assert numsprites >= 0
    expected_size = sprite_count_offset + 2 + numsprites * 44
    assert len(data) == expected_size


# ---- create_level_map tests ---------------------------------------------

_ALL_LEVELS = [(ep, lv) for ep in range(1, 5) for lv in range(1, 12)]


@pytest.mark.parametrize("episode,level", _ALL_LEVELS)
def test_level_map_version(episode, level):
    """Every generated level is MAP version 7."""
    data = create_level_map(episode, level)
    assert struct.unpack_from("<i", data, 0)[0] == 7


@pytest.mark.parametrize("episode,level", _ALL_LEVELS)
def test_level_map_structure_valid(episode, level):
    """Sector/wall/sprite counts are consistent with file size."""
    data = create_level_map(episode, level)
    ns, nw, nsp, expected = _parse_map_counts(data)
    assert ns >= 3, "level should have at least 3 rooms"
    assert nw >= 12, "level should have at least 12 walls (3 rooms × 4)"
    assert nsp >= 2, "need at least player start + exit switch"
    assert len(data) == expected


@pytest.mark.parametrize("episode,level", _ALL_LEVELS)
def test_level_map_has_player_start(episode, level):
    """First sprite is a player-start marker (picnum 0)."""
    data = create_level_map(episode, level)
    picnums = _find_sprite_picnums(data)
    assert picnums[0] == 0, "first sprite must be player start (picnum 0)"


@pytest.mark.parametrize("episode,level", _ALL_LEVELS)
def test_level_map_has_exit_switch(episode, level):
    """Last sprite is an exit switch with lotag 65535 (0xFFFF)."""
    data = create_level_map(episode, level)
    ns, nw, nsp, _ = _parse_map_counts(data)
    wall_off = 22 + ns * 40
    sprite_off = wall_off + 2 + nw * 32 + 2
    last_sprite = sprite_off + (nsp - 1) * 44
    # lotag is at byte offset 38 within the 44-byte sprite struct
    lotag_u = struct.unpack_from("<H", data, last_sprite + 38)[0]
    assert lotag_u == 65535


@pytest.mark.parametrize("episode,level", _ALL_LEVELS)
def test_level_map_player_position_reasonable(episode, level):
    """Player starts within reasonable BUILD engine coordinates."""
    data = create_level_map(episode, level)
    _, px, py, pz, _, _ = _parse_map_header(data)
    assert -500000 <= px <= 500000
    assert -500000 <= py <= 500000


def test_level_maps_all_unique():
    """All 44 maps produce distinct data (no duplicates)."""
    seen = set()
    for ep in range(1, 5):
        for lv in range(1, 12):
            data = create_level_map(ep, lv)
            seen.add(data)
    assert len(seen) == 44


def test_level_maps_deterministic():
    """Same (episode, level) always produces the same map."""
    a = create_level_map(2, 5)
    b = create_level_map(2, 5)
    assert a == b


def test_level_map_rooms_increase_with_level():
    """Higher levels produce more sectors (rooms)."""
    low = create_level_map(1, 1)
    high = create_level_map(1, 11)
    ns_low = struct.unpack_from("<h", low, 20)[0]
    ns_high = struct.unpack_from("<h", high, 20)[0]
    assert ns_high > ns_low


@pytest.mark.parametrize("episode", [1, 2, 3, 4])
def test_level_map_episode_themes_differ(episode):
    """Maps from different episodes at the same level produce different data."""
    others = {1, 2, 3, 4} - {episode}
    my_data = create_level_map(episode, 5)
    for other in others:
        assert create_level_map(other, 5) != my_data

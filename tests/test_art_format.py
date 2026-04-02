"""Tests for BUILD engine ART file creation."""
import struct
from art_format import create_art_file, rgb_to_column_major


def test_art_file_header():
    """ART file has correct header fields."""
    tiles = [(8, 8, 0, bytes(64))]  # one 8x8 tile
    data = create_art_file(tiles, localtilestart=0)
    version, numtiles_legacy, start, end = struct.unpack_from("<iiii", data, 0)
    assert version == 1
    assert numtiles_legacy == 0  # legacy field, always 0
    assert start == 0
    assert end == 0  # localtilestart + len(tiles) - 1
    assert end - start + 1 == 1  # actual tile count


def test_art_file_single_tile():
    """Single tile is packed correctly."""
    pixels = bytes(range(64))  # 8x8 = 64 bytes
    tiles = [(8, 8, 0, pixels)]
    data = create_art_file(tiles, localtilestart=0)
    # Header: 16 bytes + tilesizx(2) + tilesizy(2) + picanm(4) + pixels(64)
    assert len(data) == 16 + 2 + 2 + 4 + 64


def test_art_file_empty_tile():
    """Empty (0x0) tile produces no pixel data."""
    tiles = [(0, 0, 0, b"")]
    data = create_art_file(tiles, localtilestart=0)
    assert len(data) == 16 + 2 + 2 + 4  # header + sizes + picanm, no pixels


def test_art_file_multiple_tiles():
    """Multiple tiles are stored sequentially."""
    tiles = [
        (8, 8, 0, bytes(64)),
        (16, 16, 0, bytes(256)),
        (0, 0, 0, b""),  # empty
    ]
    data = create_art_file(tiles, localtilestart=0)
    _, _, start, end = struct.unpack_from("<iiii", data, 0)
    tile_count = end - start + 1
    assert tile_count == 3


def test_rgb_to_column_major():
    """Column-major conversion produces correct byte ordering."""
    # 2x3 image, row-major input
    # Row 0: [10, 20], Row 1: [30, 40], Row 2: [50, 60]
    # Column-major: Col 0 [10, 30, 50], Col 1 [20, 40, 60]
    row_major = bytes([10, 20, 30, 40, 50, 60])
    result = rgb_to_column_major(row_major, 2, 3)
    assert result == bytes([10, 30, 50, 20, 40, 60])


def test_rgb_to_column_major_square():
    """Column-major conversion for a square tile."""
    # 4x4 tile
    data = bytes(range(16))
    result = rgb_to_column_major(data, 4, 4)
    # Column 0: [0, 4, 8, 12], Column 1: [1, 5, 9, 13], etc.
    expected = bytes([0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15])
    assert result == expected

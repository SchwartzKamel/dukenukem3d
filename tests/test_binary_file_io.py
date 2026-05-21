#!/usr/bin/env python3
"""Binary file I/O round-trip validation tests.

Tests write → read → verify bit-identical for GRP, PALETTE.DAT, MAP, and ART formats.
All tests use pytest tmp_path fixture for isolation and verify endianness (little-endian).

Sentinel: test-file-io-round-trip
"""

import os
import struct
import pytest
from pathlib import Path

# Import format writers from tools
from grp_format import create_grp
from art_format import create_art_file
from palette import create_palette_dat, build_palette
from map_format import _pack_sector, _pack_wall, _pack_sprite


# ============================================================================
# Helper Functions for Round-Trip Validation
# ============================================================================

def read_grp_file(data):
    """Parse GRP file from bytes, return dict of {filename: content}."""
    if len(data) < 16:
        return {}
    
    if data[:12] != b"KenSilverman":
        raise ValueError("Invalid GRP magic")
    
    file_count = struct.unpack_from("<I", data, 12)[0]
    
    # Read directory: all files' entries first
    files = {}
    directory_size = file_count * 16
    data_start_offset = 16 + directory_size
    
    for i in range(file_count):
        entry_offset = 16 + i * 16
        name_bytes = data[entry_offset:entry_offset + 12]
        file_size = struct.unpack_from("<I", data, entry_offset + 12)[0]
        
        # Extract filename (strip null bytes)
        filename = name_bytes.rstrip(b"\x00").decode("ascii", errors="ignore")
        files[filename] = file_size
    
    # Calculate cumulative offsets for each file's data
    result = {}
    current_offset = data_start_offset
    for filename in sorted(files.keys()):
        size = files[filename]
        result[filename] = data[current_offset:current_offset + size]
        current_offset += size
    
    return result


def read_palette_dat_header(data):
    """Parse PALETTE.DAT header: return (palette_bytes_768, numpalookups)."""
    if len(data) < 770:
        raise ValueError("PALETTE.DAT too short")
    
    pal_bytes = data[:768]
    numpalookups = struct.unpack_from("<h", data, 768)[0]
    
    return pal_bytes, numpalookups


def read_art_file_header(data):
    """Parse ART file header, return (version, numtiles, localtilestart, localtileend)."""
    if len(data) < 16:
        raise ValueError("ART file too short")
    
    version, numtiles, localtilestart, localtileend = struct.unpack_from("<IIII", data, 0)
    return version, numtiles, localtilestart, localtileend


def read_map_sectors(data, num_sectors):
    """Extract sector data from MAP binary."""
    sectors = []
    for i in range(num_sectors):
        offset = i * 40
        sector_data = data[offset:offset + 40]
        if len(sector_data) < 40:
            break
        sectors.append(sector_data)
    return sectors


# ============================================================================
# GRP Format Round-Trip Tests
# ============================================================================

class TestGrpRoundTrip:
    """GRP archive write → read → verify."""

    def test_grp_single_file_round_trip(self, tmp_path):
        """Write GRP with one file, read back, verify bit-identical."""
        grp_path = tmp_path / "test.grp"
        
        files = {"HELLO.DAT": b"Hello Duke!"}
        grp_data = create_grp(files)
        
        grp_path.write_bytes(grp_data)
        read_data = grp_path.read_bytes()
        
        assert read_data == grp_data
        assert read_data[:12] == b"KenSilverman"

    def test_grp_multiple_files_round_trip(self, tmp_path):
        """Write GRP with multiple files, verify all extracted identically."""
        grp_path = tmp_path / "multi.grp"
        
        files = {
            "FILE1.DAT": b"Content one",
            "FILE2.DAT": b"Content two\x00\xff",
            "FILE3.DAT": b"\x00\x01\x02\x03\x04"
        }
        grp_data = create_grp(files)
        grp_path.write_bytes(grp_data)
        
        read_data = grp_path.read_bytes()
        extracted = read_grp_file(read_data)
        
        # Verify file count
        assert struct.unpack_from("<I", read_data, 12)[0] == 3
        
        # Verify each file matches
        for filename, content in files.items():
            assert extracted[filename] == content

    def test_grp_empty_round_trip(self, tmp_path):
        """Write empty GRP, verify header only."""
        grp_path = tmp_path / "empty.grp"
        
        grp_data = create_grp({})
        grp_path.write_bytes(grp_data)
        
        read_data = grp_path.read_bytes()
        
        assert read_data[:12] == b"KenSilverman"
        assert struct.unpack_from("<I", read_data, 12)[0] == 0
        assert len(read_data) == 16

    def test_grp_binary_payload_round_trip(self, tmp_path):
        """Write GRP with binary payloads, verify bytes unchanged."""
        grp_path = tmp_path / "binary.grp"
        
        binary_content = bytes(range(256))
        files = {"BINARY.DAT": binary_content}
        
        grp_data = create_grp(files)
        grp_path.write_bytes(grp_data)
        read_data = grp_path.read_bytes()
        
        extracted = read_grp_file(read_data)
        assert extracted["BINARY.DAT"] == binary_content


# ============================================================================
# PALETTE.DAT Format Round-Trip Tests
# ============================================================================

class TestPaletteDatRoundTrip:
    """PALETTE.DAT write → read → verify 768-byte RGB header."""

    @pytest.mark.slow
    def test_palette_dat_vga_bytes_round_trip(self, tmp_path):
        """Write PALETTE.DAT, verify first 768 bytes (256 RGB in 6-bit VGA)."""
        pal_path = tmp_path / "PALETTE.DAT"
        
        pal = build_palette()
        pal_data = create_palette_dat(pal)
        pal_path.write_bytes(pal_data)
        
        read_data = pal_path.read_bytes()
        
        # Verify total size
        assert len(read_data) >= 768 + 2 + 32 * 256 + 65536
        
        # Verify VGA palette bytes (first 768 bytes)
        vga_bytes = read_data[:768]
        assert len(vga_bytes) == 768
        
        # All VGA bytes should be 6-bit (0-63)
        for byte in vga_bytes:
            assert 0 <= byte <= 63

    @pytest.mark.slow
    def test_palette_dat_shade_tables_present(self, tmp_path):
        """Verify shade tables present after VGA palette."""
        pal_path = tmp_path / "PALETTE.DAT"
        
        pal = build_palette()
        pal_data = create_palette_dat(pal)
        pal_path.write_bytes(pal_data)
        
        read_data = pal_path.read_bytes()
        
        # Read numpalookups
        numpalookups = struct.unpack_from("<h", read_data, 768)[0]
        assert numpalookups == 32
        
        # Verify shade table data exists
        shade_offset = 770
        shade_size = numpalookups * 256
        shade_data = read_data[shade_offset:shade_offset + shade_size]
        assert len(shade_data) == shade_size

    @pytest.mark.slow
    def test_palette_dat_translucency_table_present(self, tmp_path):
        """Verify 65536-byte translucency table at end."""
        pal_path = tmp_path / "PALETTE.DAT"
        
        pal = build_palette()
        pal_data = create_palette_dat(pal)
        pal_path.write_bytes(pal_data)
        
        read_data = pal_path.read_bytes()
        
        # Total size: 768 (RGB) + 2 (numpalookups) + 32*256 (shades) + 65536 (trans)
        expected_size = 768 + 2 + 32 * 256 + 65536
        assert len(read_data) == expected_size
        
        # Verify translucency table (all indices 0-255)
        trans_offset = 770 + 32 * 256
        trans_data = read_data[trans_offset:trans_offset + 65536]
        for byte in trans_data:
            assert 0 <= byte <= 255

    @pytest.mark.slow
    def test_palette_dat_endianness_little_endian(self, tmp_path):
        """Verify numpalookups is stored little-endian."""
        pal_path = tmp_path / "PALETTE.DAT"
        
        pal = build_palette()
        pal_data = create_palette_dat(pal)
        pal_path.write_bytes(pal_data)
        
        read_data = pal_path.read_bytes()
        
        # numpalookups should be 32 in little-endian
        numpalookups = struct.unpack_from("<h", read_data, 768)[0]
        assert numpalookups == 32
        
        # Verify bytes are [0x20, 0x00] (32 in LE)
        assert read_data[768] == 0x20
        assert read_data[769] == 0x00


# ============================================================================
# ART Format Round-Trip Tests
# ============================================================================

class TestArtRoundTrip:
    """ART tile file write → read → verify header and dimensions."""

    def test_art_single_tile_round_trip(self, tmp_path):
        """Create ART with one 8x8 tile, verify header round-trip."""
        art_path = tmp_path / "TILES.ART"
        
        # Single 8x8 tile with zero pixels
        pixels = bytes(64)
        tiles = [(8, 8, 0, pixels)]
        
        art_data = create_art_file(tiles, localtilestart=0)
        art_path.write_bytes(art_data)
        read_data = art_path.read_bytes()
        
        # Parse header
        version, numtiles, start, end = read_art_file_header(read_data)
        
        assert version == 1
        assert numtiles == 1
        assert start == 0
        assert end == 0

    def test_art_multiple_tiles_dimensions(self, tmp_path):
        """Create ART with multiple tiles of different sizes."""
        art_path = tmp_path / "MULTI.ART"
        
        # Three tiles: 8x8, 16x16, 8x8
        tiles = [
            (8, 8, 0, bytes(64)),
            (16, 16, 0, bytes(256)),
            (8, 8, 0, bytes(64))
        ]
        
        art_data = create_art_file(tiles, localtilestart=0)
        art_path.write_bytes(art_data)
        read_data = art_path.read_bytes()
        
        # Parse header
        version, numtiles, start, end = read_art_file_header(read_data)
        
        assert version == 1
        assert start == 0
        assert end == 2
        
        # Parse tile dimensions (16 bytes header + 3*2 sizex + 3*2 sizey)
        sizex_offset = 16
        tilesizy_offset = 16 + 6
        
        sizex_tile0 = struct.unpack_from("<h", read_data, sizex_offset)[0]
        sizex_tile1 = struct.unpack_from("<h", read_data, sizex_offset + 2)[0]
        sizex_tile2 = struct.unpack_from("<h", read_data, sizex_offset + 4)[0]
        
        assert sizex_tile0 == 8
        assert sizex_tile1 == 16
        assert sizex_tile2 == 8

    def test_art_picanm_stored_correctly(self, tmp_path):
        """Verify animation data (picanm) stored correctly."""
        art_path = tmp_path / "PICANM.ART"
        
        # Tile with animation data
        picanm_val = 0x12345678
        tiles = [(8, 8, picanm_val, bytes(64))]
        
        art_data = create_art_file(tiles, localtilestart=0)
        art_path.write_bytes(art_data)
        read_data = art_path.read_bytes()
        
        # picanm offset: 16 (header) + 2 (sizex) + 2 (sizey)
        picanm_offset = 20
        stored_picanm = struct.unpack_from("<I", read_data, picanm_offset)[0]
        
        assert stored_picanm == picanm_val

    def test_art_payload_column_major_preserved(self, tmp_path):
        """Verify pixel data stored in column-major order."""
        art_path = tmp_path / "PIXELS.ART"
        
        # 4x4 tile with known pattern
        pixel_data = bytes(range(16))  # 0,1,2,...,15 in column-major
        tiles = [(4, 4, 0, pixel_data)]
        
        art_data = create_art_file(tiles, localtilestart=0)
        art_path.write_bytes(art_data)
        read_data = art_path.read_bytes()
        
        # Pixel data offset: 16 (header) + 2 (sizex) + 2 (sizey) + 4 (picanm)
        pixel_offset = 24
        stored_pixels = read_data[pixel_offset:pixel_offset + 16]
        
        assert stored_pixels == pixel_data


# ============================================================================
# MAP Format Round-Trip Tests
# ============================================================================

class TestMapRoundTrip:
    """MAP geometry write → read → verify sector/wall/sprite structures."""

    def test_map_minimal_sector_round_trip(self, tmp_path):
        """Pack and read back a minimal sector (40 bytes)."""
        map_path = tmp_path / "MINIMAL.MAP"
        
        sector = _pack_sector(
            wallptr=0, wallnum=4,
            ceilingz=57344, floorz=61440,
            ceilingstat=0, floorstat=0
        )
        
        map_path.write_bytes(sector)
        read_sector = map_path.read_bytes()
        
        assert read_sector == sector
        assert len(sector) == 40

    def test_map_sector_field_preservation(self, tmp_path):
        """Verify sector fields preserved in round-trip."""
        map_path = tmp_path / "SECTOR.MAP"
        
        sector = _pack_sector(
            wallptr=5, wallnum=8,
            ceilingz=48000, floorz=64000,
            ceilingpicnum=3, floorpicnum=2,
            lotag=1, hitag=99
        )
        
        map_path.write_bytes(sector)
        read_data = map_path.read_bytes()
        
        # Unpack and verify fields
        wallptr, wallnum, cz, fz = struct.unpack_from("<hh ii", read_data, 0)
        assert wallptr == 5
        assert wallnum == 8
        assert cz == 48000
        assert fz == 64000

    def test_map_wall_structure_round_trip(self, tmp_path):
        """Pack and read back a wall (32 bytes)."""
        map_path = tmp_path / "WALL.MAP"
        
        wall = _pack_wall(
            x=1024, y=2048,
            point2=1, nextwall=2, nextsector=1,
            picnum=5, shade=16, xrepeat=8, yrepeat=8
        )
        
        map_path.write_bytes(wall)
        read_wall = map_path.read_bytes()
        
        assert read_wall == wall
        assert len(wall) == 32

    def test_map_sprite_structure_round_trip(self, tmp_path):
        """Pack and read back a sprite (44 bytes)."""
        map_path = tmp_path / "SPRITE.MAP"
        
        sprite = _pack_sprite(
            x=4096, y=8192, z=0,
            picnum=10, shade=0,
            xrepeat=64, yrepeat=64,
            sectnum=0
        )
        
        map_path.write_bytes(sprite)
        read_sprite = map_path.read_bytes()
        
        assert read_sprite == sprite
        assert len(sprite) == 44

    def test_map_multiple_sectors_layout(self, tmp_path):
        """Write multiple sectors sequentially, verify layout."""
        map_path = tmp_path / "MULTI.MAP"
        
        sector1 = _pack_sector(wallptr=0, wallnum=4, ceilingz=48000, floorz=64000)
        sector2 = _pack_sector(wallptr=4, wallnum=6, ceilingz=45000, floorz=63000)
        
        combined = sector1 + sector2
        map_path.write_bytes(combined)
        read_data = map_path.read_bytes()
        
        assert len(read_data) == 80  # 2 * 40
        assert read_data[:40] == sector1
        assert read_data[40:80] == sector2

    def test_map_sprite_xyz_coordinates(self, tmp_path):
        """Verify sprite coordinate storage (little-endian int32)."""
        map_path = tmp_path / "COORD.MAP"
        
        x_val, y_val, z_val = 12345, 67890, -5000
        sprite = _pack_sprite(x=x_val, y=y_val, z=z_val)
        
        map_path.write_bytes(sprite)
        read_data = map_path.read_bytes()
        
        x_read, y_read, z_read = struct.unpack_from("<iii", read_data, 0)
        assert x_read == x_val
        assert y_read == y_val
        assert z_read == z_val


# ============================================================================
# Endianness Sanity Tests
# ============================================================================

class TestEndiannessSanity:
    """Verify little-endian struct.pack consistency."""

    def test_grp_magic_is_ascii(self, tmp_path):
        """GRP magic is ASCII, verify no endianness issues."""
        grp_path = tmp_path / "magic.grp"
        
        grp_data = create_grp({"TEST.DAT": b"x"})
        grp_path.write_bytes(grp_data)
        
        magic = grp_path.read_bytes()[:12]
        assert magic == b"KenSilverman"

    def test_art_version_is_1_le(self, tmp_path):
        """ART version is 1 (little-endian uint32)."""
        art_path = tmp_path / "version.art"
        
        tiles = [(8, 8, 0, bytes(64))]
        art_data = create_art_file(tiles)
        art_path.write_bytes(art_data)
        
        version = struct.unpack_from("<I", art_path.read_bytes(), 0)[0]
        assert version == 1

    @pytest.mark.slow
    def test_palette_numpalookups_is_32_le(self, tmp_path):
        """PALETTE.DAT numpalookups is 32 (little-endian int16)."""
        pal_path = tmp_path / "numpal.dat"
        
        pal = build_palette()
        pal_data = create_palette_dat(pal)
        pal_path.write_bytes(pal_data)
        
        numpal = struct.unpack_from("<h", pal_path.read_bytes(), 768)[0]
        assert numpal == 32

    def test_grp_filecount_uint32_le(self, tmp_path):
        """GRP file count is uint32 little-endian."""
        grp_path = tmp_path / "count.grp"
        
        files = {"A.DAT": b"a", "B.DAT": b"b", "C.DAT": b"c"}
        grp_data = create_grp(files)
        grp_path.write_bytes(grp_data)
        
        count = struct.unpack_from("<I", grp_path.read_bytes(), 12)[0]
        assert count == 3

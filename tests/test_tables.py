"""Tests for TABLES.DAT generation."""
import struct
import math
from tables import create_tables_dat


def test_tables_dat_size():
    """TABLES.DAT should be exactly 9728 bytes."""
    data = create_tables_dat()
    assert len(data) == 9728


def test_sine_table_at_zero():
    """sin(0) should be 0."""
    data = create_tables_dat()
    sintable = struct.unpack_from("<2048h", data, 0)
    assert sintable[0] == 0


def test_sine_table_at_quarter():
    """sin(512) = sin(pi/2) should be near 16383."""
    data = create_tables_dat()
    sintable = struct.unpack_from("<2048h", data, 0)
    # Index 512 = pi/2, should be max positive
    assert abs(sintable[512] - 16383) < 2


def test_sine_table_at_half():
    """sin(1024) = sin(pi) should be near 0."""
    data = create_tables_dat()
    sintable = struct.unpack_from("<2048h", data, 0)
    assert abs(sintable[1024]) < 2


def test_sine_table_symmetry():
    """sin values have expected symmetry."""
    data = create_tables_dat()
    sintable = struct.unpack_from("<2048h", data, 0)
    # sin(x) = -sin(x + 1024) approximately
    for i in range(100):
        assert abs(sintable[i] + sintable[i + 1024]) < 3

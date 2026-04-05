"""Tests for demo file (.dmo) and timbre (.tmb) stub generation."""
import struct

from demo_format import (
    BYTEVERSION_FULL,
    BYTEVERSION_SHAREWARE,
    HEADER_FIXED_SIZE,
    INPUT_RECORD_SIZE,
    create_demo_frame,
    create_demo_header,
    create_demo_stub,
    create_timbre_stub,
)


# ---------------------------------------------------------------------------
# Demo header tests
# ---------------------------------------------------------------------------

def test_demo_stub_starts_with_zero_frame_count():
    """A stub demo has zero frames so playback exits immediately."""
    data = create_demo_stub()
    frame_count = struct.unpack_from("<i", data, 0)[0]
    assert frame_count == 0


def test_demo_stub_version_full():
    """Default version byte is 116 (full/registered)."""
    data = create_demo_stub()
    assert data[4] == BYTEVERSION_FULL


def test_demo_stub_version_shareware():
    """Shareware version byte is 27."""
    data = create_demo_stub(version=BYTEVERSION_SHAREWARE)
    assert data[4] == BYTEVERSION_SHAREWARE


def test_demo_stub_header_size():
    """Single-player stub header is exactly 675 bytes (674 fixed + 1 aim)."""
    data = create_demo_stub()
    assert len(data) == HEADER_FIXED_SIZE + 1  # multimode=1


def test_demo_stub_level_info():
    """Volume, level, and skill are stored correctly."""
    data = create_demo_stub(volume=1, level=3, skill=3)
    assert data[5] == 1   # volume
    assert data[6] == 3   # level
    assert data[7] == 3   # skill


def test_demo_stub_single_player():
    """Multimode field is 1 for single-player demo."""
    data = create_demo_stub()
    multimode = struct.unpack_from("<h", data, 10)[0]
    assert multimode == 1


def test_demo_stub_no_frame_data():
    """With zero frames, there is no frame data after the header."""
    data = create_demo_stub()
    expected_size = HEADER_FIXED_SIZE + 1  # header only, no frames
    assert len(data) == expected_size


def test_demo_header_custom_names():
    """Player names are stored in the header."""
    names = [b"DUKE"] + [b""] * 15
    data = create_demo_header(player_names=names)
    # Names start at offset 30 (after 26 bytes of fields + 4 bytes player_ai)
    name_offset = 4 + 1 + 1 + 1 + 1 + 1 + 1 + 2 + 2 + 4 + 4 + 4 + 4
    assert name_offset == 30
    assert data[name_offset:name_offset + 4] == b"DUKE"


def test_demo_header_board_filename_padded():
    """Board filename is null-padded to 128 bytes."""
    data = create_demo_header(board_filename=b"E1L1.MAP")
    # Board filename offset: 30 + 512 (names) + 4 (autorun) = 546
    board_offset = 30 + 512 + 4
    assert data[board_offset:board_offset + 8] == b"E1L1.MAP"
    assert data[board_offset + 8:board_offset + 128] == b"\x00" * 120


# ---------------------------------------------------------------------------
# Input frame tests
# ---------------------------------------------------------------------------

def test_demo_frame_size():
    """Each input record is exactly 10 bytes."""
    frame = create_demo_frame()
    assert len(frame) == INPUT_RECORD_SIZE


def test_demo_frame_values():
    """Frame encodes avel, horz, fvel, svel, bits correctly."""
    frame = create_demo_frame(avel=5, horz=-3, fvel=100, svel=-50, bits=0xFF)
    avel, horz, fvel, svel, bits = struct.unpack("<bbhhI", frame)
    assert avel == 5
    assert horz == -3
    assert fvel == 100
    assert svel == -50
    assert bits == 0xFF


def test_demo_frame_zero_idle():
    """A zero-input frame represents an idle player."""
    frame = create_demo_frame()
    assert frame == b"\x00" * INPUT_RECORD_SIZE


# ---------------------------------------------------------------------------
# Timbre stub tests
# ---------------------------------------------------------------------------

def test_timbre_stub_not_empty():
    """TMB stub must be non-empty."""
    data = create_timbre_stub()
    assert len(data) > 0


def test_timbre_stub_max_size():
    """TMB stub must fit in the 8000-byte buffer used by loadtmb()."""
    data = create_timbre_stub()
    assert len(data) <= 8000


def test_timbre_stub_is_bytes():
    """TMB stub returns bytes."""
    data = create_timbre_stub()
    assert isinstance(data, bytes)


# ---------------------------------------------------------------------------
# Two distinct demo stubs (demo0 vs demo1)
# ---------------------------------------------------------------------------

def test_two_demo_stubs_different_levels():
    """demo0 and demo1 can target different levels."""
    d0 = create_demo_stub(volume=0, level=0)
    d1 = create_demo_stub(volume=0, level=1)
    assert d0[6] == 0  # level 0
    assert d1[6] == 1  # level 1
    assert d0 != d1

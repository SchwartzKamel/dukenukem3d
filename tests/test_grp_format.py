"""Tests for GRP archive format."""
import struct
import pytest
from grp_format import create_grp


# Parametrized file count sets for edge case coverage
_GRP_FILE_COUNTS = [0, 1, 3, 5, 10]
_GRP_FILE_SIZES = [0, 1, 100, 1000, 10000]


def test_grp_magic():
    """GRP file starts with KenSilverman magic."""
    data = create_grp({"TEST.DAT": b"hello"})
    assert data[:12] == b"KenSilverman"


@pytest.mark.parametrize("count", _GRP_FILE_COUNTS)
def test_grp_file_count_parametrized(count):
    """GRP header has correct file count for various counts."""
    if count == 0:
        files = {}
    else:
        files = {f"FILE{i:02d}.DAT": bytes([i] * (i + 1)) for i in range(count)}
    data = create_grp(files)
    file_count = struct.unpack_from("<I", data, 12)[0]
    assert file_count == count


def test_grp_file_count():
    """GRP header has correct file count."""
    files = {"A.DAT": b"aaa", "B.DAT": b"bbb", "C.DAT": b"ccc"}
    data = create_grp(files)
    count = struct.unpack_from("<I", data, 12)[0]
    assert count == 3


@pytest.mark.parametrize("size", _GRP_FILE_SIZES)
def test_grp_single_file_sizes(size):
    """Single file of various sizes is stored and retrievable."""
    content = bytes(range(256)) * (size // 256 + 1)
    content = content[:size]
    data = create_grp({"TEST.DAT": content})
    # Magic(12) + count(4) + entry(16) + data
    assert len(data) == 12 + 4 + 16 + len(content)
    # Verify file data at end
    if size > 0:
        assert data[-len(content):] == content


def test_grp_single_file():
    """Single file is stored and retrievable."""
    content = b"Hello Duke!"
    data = create_grp({"HELLO.TXT": content})
    # Magic(12) + count(4) + entry(16) + data
    assert len(data) == 12 + 4 + 16 + len(content)
    # Verify file data at end
    assert data[-len(content):] == content


def test_grp_filename_padding():
    """Filenames are null-padded to 12 bytes."""
    data = create_grp({"A.B": b"x"})
    # First entry starts at offset 16
    name_bytes = data[16:28]
    assert name_bytes[:3] == b"A.B"
    assert name_bytes[3:] == b"\x00" * 9


@pytest.mark.parametrize("count", [1, 3, 5])
def test_grp_multiple_files_data_counts(count):
    """Multiple files' data is concatenated correctly for various counts."""
    files = {f"FILE{i:02d}.DAT": bytes([i]) * (i + 1) for i in range(count)}
    data = create_grp(files)
    # Data offset: 12 + 4 + (count * 16)
    data_offset = 12 + 4 + (count * 16)
    file_data = data[data_offset:]
    # Verify each file's data is present
    for i in range(count):
        expected = bytes([i]) * (i + 1)
        assert expected in file_data


def test_grp_multiple_files_data():
    """Multiple files' data is concatenated correctly."""
    files = {"A.DAT": b"aaa", "B.DAT": b"bbbb"}
    data = create_grp(files)
    # Data offset: 12 + 4 + (2 * 16) = 48
    file_data = data[48:]
    assert b"aaa" in file_data
    assert b"bbbb" in file_data


def test_grp_empty():
    """GRP with no files is valid."""
    data = create_grp({})
    assert data[:12] == b"KenSilverman"
    count = struct.unpack_from("<I", data, 12)[0]
    assert count == 0
    assert len(data) == 16

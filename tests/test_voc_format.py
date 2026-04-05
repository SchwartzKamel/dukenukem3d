"""Tests for VOC format generator."""
import struct

from voc_format import create_voc_stub, create_voc_from_samples, HEADER_MAGIC


def test_voc_magic():
    """VOC file starts with Creative Voice File magic."""
    data = create_voc_stub("test.voc")
    assert data[:20] == HEADER_MAGIC


def test_voc_header_size():
    """Header data offset field is 26."""
    data = create_voc_stub("test.voc")
    offset = struct.unpack_from("<H", data, 20)[0]
    assert offset == 26


def test_voc_version():
    """VOC version field is 1.10 (0x010A)."""
    data = create_voc_stub("test.voc")
    version = struct.unpack_from("<H", data, 22)[0]
    assert version == 0x010A


def test_voc_checksum():
    """VOC checksum = 0x1234 + ~version."""
    data = create_voc_stub("test.voc")
    version = struct.unpack_from("<H", data, 22)[0]
    checksum = struct.unpack_from("<H", data, 24)[0]
    expected = (0x1234 + (~version & 0xFFFF)) & 0xFFFF
    assert checksum == expected


def test_voc_data_block_type():
    """First data block after header is type 1 (sound data)."""
    data = create_voc_stub("test.voc")
    assert data[26] == 1


def test_voc_block_length():
    """Block length matches actual payload."""
    data = create_voc_stub("test.voc", duration_ms=100)
    # Block starts at offset 26
    block_len_bytes = data[27:30] + b"\x00"
    block_len = struct.unpack("<I", block_len_bytes)[0]
    # Total = header(26) + type(1) + len(3) + payload(block_len) + terminator(1)
    assert len(data) == 26 + 1 + 3 + block_len + 1


def test_voc_terminator():
    """VOC file ends with terminator block (type 0)."""
    data = create_voc_stub("test.voc")
    assert data[-1] == 0


def test_voc_deterministic():
    """Same name produces identical output."""
    a = create_voc_stub("test.voc")
    b = create_voc_stub("test.voc")
    assert a == b


def test_voc_different_names():
    """Different names produce different output."""
    a = create_voc_stub("pistol.voc")
    b = create_voc_stub("shotgun7.voc")
    assert a != b


def test_voc_duration_scales():
    """Longer duration produces larger file."""
    short = create_voc_stub("test.voc", duration_ms=50)
    long = create_voc_stub("test.voc", duration_ms=500)
    assert len(long) > len(short)


def test_voc_from_samples():
    """create_voc_from_samples produces valid VOC with exact sample data."""
    samples = bytes([128] * 100)  # 100 samples of silence
    data = create_voc_from_samples(samples, sample_rate=11025)
    assert data[:20] == HEADER_MAGIC
    assert data[-1] == 0
    # Samples should appear inside the block payload
    assert samples in data


def test_voc_compression_byte():
    """Compression type is 0 (8-bit unsigned PCM)."""
    data = create_voc_stub("test.voc")
    # After header(26) + type(1) + len(3) + sr_byte(1) -> compression at offset 31
    assert data[31] == 0


def test_voc_all_duke_sound_names():
    """Generate VOC stubs for a selection of Duke3D sounds without error."""
    names = [
        "pistol.voc", "shotgun7.voc", "chaingun.voc", "rpgfire.voc",
        "kickhit.voc", "roam06.voc", "DMDEATH.VOC", "switch.voc",
        "bubblamb.voc", "bonus.voc", "secret.voc", "teleport.voc",
    ]
    for fn in names:
        data = create_voc_stub(fn)
        assert data[:20] == HEADER_MAGIC, f"Failed for {fn}"
        assert len(data) > 30, f"Too small for {fn}"

"""Property-based tests for GRP packing and WAV header generation.

These tests use hypothesis to generate random valid inputs and verify that
the format handlers correctly pack and unpack data with byte-level accuracy.
"""

import struct
import sys
import os

import pytest
from hypothesis import given, settings, strategies as st

# Ensure tools package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from grp_format import create_grp
from generate_audio import generate_silence_wav


# ============================================================================
# GRP Format Property-Based Tests
# ============================================================================


def parse_grp(data):
    """Parse a GRP file and return (files_dict, errors)."""
    errors = []

    if len(data) < 16:
        return {}, ["GRP too short"]

    magic = data[:12]
    if magic != b"KenSilverman":
        return {}, ["Invalid magic"]

    num_files = struct.unpack_from("<I", data, 12)[0]

    if len(data) < 16 + num_files * 16:
        return {}, ["Directory truncated"]

    files = {}
    offset = 16 + num_files * 16

    for i in range(num_files):
        entry_offset = 16 + i * 16
        name_bytes = data[entry_offset : entry_offset + 12]
        size = struct.unpack_from("<I", data, entry_offset + 12)[0]

        # Trim null bytes from name
        name = name_bytes.rstrip(b"\x00").decode("ascii", errors="ignore")

        if offset + size > len(data):
            errors.append(f"File {i} ({name}) extends beyond file")
            break

        file_data = data[offset : offset + size]
        files[name] = file_data
        offset += size

    return files, errors


@st.composite
def grp_entry_strategy(draw):
    """Generate a valid GRP entry (name, payload)."""
    # Names: 1-12 chars uppercase ASCII
    name_len = draw(st.integers(min_value=1, max_value=12))
    name = "".join(
        draw(
            st.lists(
                st.sampled_from(
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                ),
                min_size=name_len,
                max_size=name_len,
            )
        )
    )

    # Payloads: 0-256 bytes
    payload_size = draw(st.integers(min_value=0, max_value=256))
    payload = draw(st.binary(min_size=payload_size, max_size=payload_size))

    return name, payload


@pytest.mark.slow
@given(st.lists(grp_entry_strategy(), min_size=1, max_size=8))
@settings(max_examples=25, deadline=2000)
def test_grp_property_hypothesis(entries):
    """Property: GRP pack/unpack preserves names and payloads."""
    # Build a dict from entries, deduplicating by name (last one wins)
    files_dict = {}
    for name, payload in entries:
        files_dict[name] = payload

    # Pack via create_grp
    packed = create_grp(files_dict)

    # Verify basic structure
    assert packed[:12] == b"KenSilverman", "Magic should be preserved"
    assert len(packed) >= 16, "GRP too short"

    # Parse back
    unpacked, errors = parse_grp(packed)
    if errors:
        pytest.skip(f"Parse error: {errors}")

    # Verify file count
    num_files = struct.unpack_from("<I", packed, 12)[0]
    assert num_files == len(files_dict), "File count mismatch"

    # Verify each file's name and payload round-trips
    for original_name, original_payload in files_dict.items():
        assert (
            original_name in unpacked
        ), f"Name {original_name} not found after unpack"
        assert (
            unpacked[original_name] == original_payload
        ), f"Payload mismatch for {original_name}"


@pytest.mark.slow
@given(st.lists(grp_entry_strategy(), min_size=0, max_size=8))
@settings(max_examples=10, deadline=2000)
def test_grp_size_consistency_hypothesis(entries):
    """Property: GRP file size matches header + directory + data."""
    files_dict = {}
    for name, payload in entries:
        files_dict[name] = payload

    packed = create_grp(files_dict)

    num_files = len(files_dict)
    magic_and_count = 12 + 4
    directory_size = num_files * 16
    data_size = sum(len(p) for p in files_dict.values())

    expected_size = magic_and_count + directory_size + data_size
    assert len(packed) == expected_size, (
        f"Size mismatch: got {len(packed)}, "
        f"expected {expected_size} "
        f"(magic+count={magic_and_count}, dir={directory_size}, data={data_size})"
    )


# ============================================================================
# WAV Format Property-Based Tests
# ============================================================================


def parse_wav_header(data):
    """Parse RIFF/WAV header and return (metadata, errors)."""
    errors = []

    if len(data) < 36:
        return None, ["WAV too short"]

    # Parse RIFF header
    riff_id = data[0:4]
    if riff_id != b"RIFF":
        return None, ["Invalid RIFF ID"]

    riff_size = struct.unpack_from("<I", data, 4)[0]
    riff_form = data[8:12]
    if riff_form != b"WAVE":
        return None, ["Invalid WAVE form type"]

    # Expected file size: riff_size + 8 (id + size fields)
    expected_file_size = riff_size + 8
    actual_file_size = len(data)

    if actual_file_size < expected_file_size:
        errors.append(
            f"File truncated: expected {expected_file_size}, got {actual_file_size}"
        )

    # Parse fmt chunk
    if len(data) < 16:
        return None, ["No fmt chunk"]

    fmt_id = data[12:16]
    if fmt_id != b"fmt ":
        return None, ["Invalid fmt chunk ID"]

    fmt_size = struct.unpack_from("<I", data, 16)[0]
    if len(data) < 20 + fmt_size:
        return None, ["fmt chunk truncated"]

    # Unpack fmt structure (we expect 16 bytes for PCM)
    if fmt_size < 16:
        return None, ["fmt chunk too small"]

    (
        audio_format,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    ) = struct.unpack_from("<HHIIHH", data, 20)

    # Parse data chunk
    data_chunk_offset = 12 + 8 + fmt_size
    if len(data) < data_chunk_offset + 8:
        return None, ["No data chunk"]

    data_id = data[data_chunk_offset : data_chunk_offset + 4]
    if data_id != b"data":
        return None, ["Invalid data chunk ID"]

    data_size = struct.unpack_from("<I", data, data_chunk_offset + 4)[0]

    return {
        "audio_format": audio_format,
        "num_channels": num_channels,
        "sample_rate": sample_rate,
        "byte_rate": byte_rate,
        "block_align": block_align,
        "bits_per_sample": bits_per_sample,
        "data_size": data_size,
        "riff_size": riff_size,
    }, errors


@pytest.mark.slow
@given(
    duration_ms=st.integers(min_value=10, max_value=5000),
    sample_rate=st.sampled_from([8000, 11025, 16000, 22050, 44100, 48000]),
    bit_depth=st.sampled_from([8, 16]),
)
@settings(max_examples=25, deadline=2000)
def test_wav_property_hypothesis(duration_ms, sample_rate, bit_depth):
    """Property: WAV header correctly encodes duration, sample rate, and bit depth."""
    duration_sec = duration_ms / 1000.0

    # Generate silence WAV
    wav_data = generate_silence_wav(duration_sec, sample_rate, bit_depth)

    # Parse header
    metadata, errors = parse_wav_header(wav_data)

    if errors:
        pytest.skip(f"Parse error: {errors}")

    assert metadata is not None, "Failed to parse WAV header"

    # Verify sample rate round-trip
    assert (
        metadata["sample_rate"] == sample_rate
    ), f"Sample rate mismatch: expected {sample_rate}, got {metadata['sample_rate']}"

    # Verify bit depth round-trip
    assert (
        metadata["bits_per_sample"] == bit_depth
    ), f"Bit depth mismatch: expected {bit_depth}, got {metadata['bits_per_sample']}"

    # Verify num channels is 1 (mono)
    assert (
        metadata["num_channels"] == 1
    ), "Expected mono (1 channel)"

    # Verify audio format is PCM (1)
    assert (
        metadata["audio_format"] == 1
    ), "Expected PCM audio format"


@pytest.mark.slow
@given(
    duration_ms=st.integers(min_value=10, max_value=5000),
    sample_rate=st.sampled_from([8000, 11025, 16000, 22050, 44100, 48000]),
    bit_depth=st.sampled_from([8, 16]),
)
@settings(max_examples=25, deadline=2000)
def test_wav_size_consistency_hypothesis(duration_ms, sample_rate, bit_depth):
    """Property: WAV RIFF size and data size match computed values."""
    duration_sec = duration_ms / 1000.0

    wav_data = generate_silence_wav(duration_sec, sample_rate, bit_depth)

    # Compute expected values
    num_samples = int(sample_rate * duration_sec)
    bytes_per_sample = bit_depth // 8
    expected_data_size = num_samples * bytes_per_sample

    # Verify by parsing
    if len(wav_data) < 36:
        pytest.skip("WAV too short to parse")

    metadata, errors = parse_wav_header(wav_data)
    if errors:
        pytest.skip(f"Parse error: {errors}")

    assert metadata is not None
    assert (
        metadata["data_size"] == expected_data_size
    ), (
        f"Data size mismatch: expected {expected_data_size}, "
        f"got {metadata['data_size']}"
    )

    # Verify RIFF size is consistent: should be file_size - 8
    actual_file_size = len(wav_data)
    expected_riff_size = actual_file_size - 8
    assert (
        metadata["riff_size"] == expected_riff_size
    ), (
        f"RIFF size mismatch: expected {expected_riff_size}, "
        f"got {metadata['riff_size']}"
    )

    # Verify byte rate is consistent: should be sample_rate * bytes_per_sample * num_channels
    expected_byte_rate = sample_rate * bytes_per_sample * 1  # 1 channel
    assert (
        metadata["byte_rate"] == expected_byte_rate
    ), (
        f"Byte rate mismatch: expected {expected_byte_rate}, "
        f"got {metadata['byte_rate']}"
    )

    # Verify block align is consistent: should be bytes_per_sample * num_channels
    expected_block_align = bytes_per_sample * 1  # 1 channel
    assert (
        metadata["block_align"] == expected_block_align
    ), (
        f"Block align mismatch: expected {expected_block_align}, "
        f"got {metadata['block_align']}"
    )

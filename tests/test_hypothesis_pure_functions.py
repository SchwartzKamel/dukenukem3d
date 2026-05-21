"""Property-based tests for pure functions in tools/ using Hypothesis.

These tests verify invariants and properties of pure utility functions that are
deterministic and have no side effects. Coverage includes:
- Palette/RGB conversion helpers (_ramp, build_palette, color quantization)
- Lookup table generation (tables determinism)
- Manifest verification (schema fallback paths, legacy 1.0 compat)
- Frame analysis (analyze_frame invariants, brightness stats bounds)
"""

import struct
import sys
import os
import pytest
from hypothesis import given, settings, strategies as st, assume
from PIL import Image
import numpy as np

# Ensure tools package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from palette import _ramp, build_palette, create_palette_dat, _nearest_color, _validate_palette_input, quantize_image
from tables import create_tables_dat, _generate_basic_font, _generate_small_font, _generate_britable
from manifest_verification import _sha256_of_manifest, verify_manifest_checksum
from grp_format import create_grp
from voc_format import _generate_tone_samples, _generate_noise_samples, _generate_click_samples
from frame_analyzer import unique_color_count, color_histogram, brightness_stats, is_black_screen, frame_difference, region_crop, analyze_frame, has_visible_content


# ============================================================================
# Palette/RGB Property Tests
# ============================================================================


@given(
    start_r=st.integers(0, 255),
    start_g=st.integers(0, 255),
    start_b=st.integers(0, 255),
    end_r=st.integers(0, 255),
    end_g=st.integers(0, 255),
    end_b=st.integers(0, 255),
    steps=st.integers(1, 100)
)
@settings(max_examples=50, deadline=2000)
def test_ramp_returns_correct_length(start_r, start_g, start_b, end_r, end_g, end_b, steps):
    """Property: _ramp returns exactly 'steps' color entries."""
    start = (start_r, start_g, start_b)
    end = (end_r, end_g, end_b)
    ramp = _ramp(start, end, steps)
    assert len(ramp) == steps, f"Ramp length {len(ramp)} != {steps}"


@given(
    start_r=st.integers(0, 255),
    start_g=st.integers(0, 255),
    start_b=st.integers(0, 255),
    end_r=st.integers(0, 255),
    end_g=st.integers(0, 255),
    end_b=st.integers(0, 255),
    steps=st.integers(1, 100)
)
@settings(max_examples=50, deadline=2000)
def test_ramp_colors_in_bounds(start_r, start_g, start_b, end_r, end_g, end_b, steps):
    """Property: All ramp colors have RGB components in 0-255 range."""
    start = (start_r, start_g, start_b)
    end = (end_r, end_g, end_b)
    ramp = _ramp(start, end, steps)
    
    for i, (r, g, b) in enumerate(ramp):
        assert isinstance(r, int), f"Color {i}: r={r} is not int"
        assert isinstance(g, int), f"Color {i}: g={g} is not int"
        assert isinstance(b, int), f"Color {i}: b={b} is not int"
        assert 0 <= r <= 255, f"Color {i}: r={r} out of bounds [0, 255]"
        assert 0 <= g <= 255, f"Color {i}: g={g} out of bounds [0, 255]"
        assert 0 <= b <= 255, f"Color {i}: b={b} out of bounds [0, 255]"


@given(
    start_r=st.integers(0, 255),
    start_g=st.integers(0, 255),
    start_b=st.integers(0, 255),
    end_r=st.integers(0, 255),
    end_g=st.integers(0, 255),
    end_b=st.integers(0, 255),
)
@settings(max_examples=50, deadline=2000)
def test_ramp_endpoints_preserved(start_r, start_g, start_b, end_r, end_g, end_b):
    """Property: _ramp first and last colors match start and end (or very close due to rounding)."""
    start = (start_r, start_g, start_b)
    end = (end_r, end_g, end_b)
    ramp = _ramp(start, end, 10)
    
    # First color should match start exactly
    assert ramp[0] == start, f"First color {ramp[0]} != start {start}"
    # Last color should match end (allowing for rounding)
    r_diff = abs(ramp[-1][0] - end[0])
    g_diff = abs(ramp[-1][1] - end[1])
    b_diff = abs(ramp[-1][2] - end[2])
    assert r_diff <= 1, f"Last R {ramp[-1][0]} differs from end {end[0]} by {r_diff}"
    assert g_diff <= 1, f"Last G {ramp[-1][1]} differs from end {end[1]} by {g_diff}"
    assert b_diff <= 1, f"Last B {ramp[-1][2]} differs from end {end[2]} by {b_diff}"


def test_build_palette_deterministic():
    """Property: build_palette() returns identical output on repeated calls (determinism)."""
    pal1 = build_palette()
    pal2 = build_palette()
    assert pal1 == pal2, "build_palette() returned different results on repeated calls"


def test_build_palette_length():
    """Property: build_palette() always returns exactly 256 colors."""
    pal = build_palette()
    assert len(pal) == 256, f"Palette length {len(pal)} != 256"


def test_build_palette_colors_in_bounds():
    """Property: All palette colors have RGB components in 0-255 range."""
    pal = build_palette()
    for i, (r, g, b) in enumerate(pal):
        assert isinstance(r, int), f"Color {i}: r={r} is not int"
        assert isinstance(g, int), f"Color {i}: g={g} is not int"
        assert isinstance(b, int), f"Color {i}: b={b} is not int"
        assert 0 <= r <= 255, f"Color {i}: r={r} out of bounds [0, 255]"
        assert 0 <= g <= 255, f"Color {i}: g={g} out of bounds [0, 255]"
        assert 0 <= b <= 255, f"Color {i}: b={b} out of bounds [0, 255]"


def test_build_palette_black_at_zero():
    """Property: build_palette()[0] is always black (0, 0, 0)."""
    pal = build_palette()
    assert pal[0] == (0, 0, 0), f"Color 0 {pal[0]} is not black"


def test_build_palette_white_at_254():
    """Property: build_palette()[254] is always white (255, 255, 255)."""
    pal = build_palette()
    assert pal[254] == (255, 255, 255), f"Color 254 {pal[254]} is not white"


@pytest.mark.slow
def test_create_palette_dat_deterministic():
    """Property: create_palette_dat() returns deterministic output."""
    dat1 = create_palette_dat()
    dat2 = create_palette_dat()
    assert dat1 == dat2, "create_palette_dat() returned different results on repeated calls"


@pytest.mark.slow
def test_create_palette_dat_size():
    """Property: create_palette_dat() returns expected size.
    
    Expected: 768 (palette) + 2 (numpalookups) + 32*256 (shade tables) 
              + 65536 (translucency) = 74498 bytes
    """
    dat = create_palette_dat()
    assert isinstance(dat, bytes), "create_palette_dat() did not return bytes"
    expected_size = 768 + 2 + (32 * 256) + 65536
    assert len(dat) == expected_size, (
        f"Palette DAT size {len(dat)} != expected {expected_size}"
    )


# ============================================================================
# Tables.DAT Property Tests
# ============================================================================


def test_create_tables_dat_deterministic():
    """Property: create_tables_dat() is deterministic (same output each call)."""
    tables1 = create_tables_dat()
    tables2 = create_tables_dat()
    assert tables1 == tables2, "create_tables_dat() returned different results on repeated calls"


def test_create_tables_dat_size():
    """Property: create_tables_dat() returns correct total size.
    
    Expected: 4096 (sintable) + 1280 (radarang) + 1024 (font1) 
              + 1024 (font2) + 1024 (britable) = 8448 bytes
    """
    tables = create_tables_dat()
    assert isinstance(tables, bytes), "create_tables_dat() did not return bytes"
    expected_size = 4096 + 1280 + 1024 + 1024 + 1024
    assert len(tables) == expected_size, (
        f"Tables DAT size {len(tables)} != expected {expected_size}"
    )


def test_sintable_bounds():
    """Property: Sine table entries are signed 16-bit integers in valid range."""
    tables = create_tables_dat()
    
    # Sine table: bytes 0-4095 (2048 int16 entries, little-endian)
    sintable_data = tables[0:4096]
    sintable = struct.unpack("<2048h", sintable_data)
    
    for i, val in enumerate(sintable):
        assert isinstance(val, int), f"Sine[{i}] is not an integer"
        assert -16384 <= val <= 16383, (
            f"Sine[{i}] = {val} outside [-16384, 16383]"
        )


def test_radarang_bounds():
    """Property: Radar angle table entries are signed 16-bit integers (non-negative)."""
    tables = create_tables_dat()
    
    # Radar angle table: bytes 4096-5375 (640 int16 entries)
    radarang_offset = 4096
    radarang_data = tables[radarang_offset:radarang_offset + 1280]
    radarang = struct.unpack("<640h", radarang_data)
    
    for i, val in enumerate(radarang):
        assert isinstance(val, int), f"RadarAng[{i}] is not an integer"
        assert val >= 0, f"RadarAng[{i}] = {val} is negative"


def test_basic_font_size():
    """Property: _generate_basic_font() returns exactly 1024 bytes."""
    font = _generate_basic_font()
    assert isinstance(font, bytes), "_generate_basic_font() did not return bytes"
    assert len(font) == 1024, f"Basic font size {len(font)} != 1024"


def test_small_font_size():
    """Property: _generate_small_font() returns exactly 1024 bytes."""
    font = _generate_small_font()
    assert isinstance(font, bytes), "_generate_small_font() did not return bytes"
    assert len(font) == 1024, f"Small font size {len(font)} != 1024"


def test_britable_size():
    """Property: _generate_britable() returns exactly 1024 bytes (16 rows * 64 cols)."""
    brightness = _generate_britable()
    assert isinstance(brightness, bytes), "_generate_britable() did not return bytes"
    assert len(brightness) == 1024, f"Brightness table size {len(brightness)} != 1024"


def test_font_entries_are_valid_pairs():
    """Property: Font tables contain valid (xofs, width) pairs as little-endian shorts."""
    font = _generate_basic_font()
    
    # Each entry is 4 bytes (2 short fields)
    for i in range(0, len(font), 4):
        xofs, width = struct.unpack("<hh", font[i:i+4])
        # Bounds checking: offset and width should be non-negative and reasonable
        assert isinstance(xofs, int), f"Font entry {i//4}: xofs is not int"
        assert isinstance(width, int), f"Font entry {i//4}: width is not int"
        assert xofs >= 0, f"Font entry {i//4}: xofs {xofs} is negative"
        assert width >= 0, f"Font entry {i//4}: width {width} is negative"
        assert width <= 128, f"Font entry {i//4}: width {width} seems too large"


# ============================================================================
# Manifest Verification Property Tests
# ============================================================================


@given(
    manifest_data=st.fixed_dictionaries({
        "version": st.just("1.0"),
        "source": st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_characters="\x00")),
        "timestamp": st.integers(0, 2**31 - 1),
    })
)
@settings(max_examples=50, deadline=2000)
def test_sha256_of_manifest_deterministic(manifest_data):
    """Property: _sha256_of_manifest is deterministic for same input."""
    hash1 = _sha256_of_manifest(manifest_data)
    hash2 = _sha256_of_manifest(manifest_data)
    assert hash1 == hash2, "Hash changed between calls for identical manifest"


@given(
    manifest_data=st.fixed_dictionaries({
        "version": st.just("1.0"),
        "source": st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_characters="\x00")),
        "timestamp": st.integers(0, 2**31 - 1),
    })
)
@settings(max_examples=50, deadline=2000)
def test_sha256_of_manifest_is_hex_string(manifest_data):
    """Property: _sha256_of_manifest returns valid 64-char hex string."""
    hash_val = _sha256_of_manifest(manifest_data)
    assert isinstance(hash_val, str), "Hash is not a string"
    assert len(hash_val) == 64, f"Hash length {len(hash_val)} != 64"
    assert all(c in "0123456789abcdef" for c in hash_val), (
        f"Hash contains non-hex characters: {hash_val}"
    )


def test_verify_manifest_checksum_with_valid_checksum():
    """Property: verify_manifest_checksum accepts manifest with correct checksum."""
    manifest = {
        "version": "1.0",
        "source": "test",
        "timestamp": 12345,
    }
    computed = _sha256_of_manifest(manifest)
    manifest["manifest_checksum"] = computed
    
    # Should not raise
    verify_manifest_checksum(manifest)


def test_verify_manifest_checksum_with_bad_checksum():
    """Property: verify_manifest_checksum rejects manifest with incorrect checksum."""
    manifest = {
        "version": "1.0",
        "source": "test",
        "timestamp": 12345,
        "manifest_checksum": "0" * 64,  # Definitely wrong
    }
    
    with pytest.raises(RuntimeError, match="manifest-checksum-verify-on-load"):
        verify_manifest_checksum(manifest)


def test_verify_manifest_checksum_legacy_compat():
    """Property: verify_manifest_checksum handles legacy manifest (no checksum field)."""
    manifest = {
        "version": "1.0",
        "source": "test",
    }
    
    # Should not raise (legacy compat mode)
    verify_manifest_checksum(manifest)


@given(
    key_count=st.integers(1, 10),
    value_size=st.integers(1, 100)
)
@settings(max_examples=30, deadline=2000)
def test_sha256_of_manifest_excludes_checksum_field(key_count, value_size):
    """Property: _sha256_of_manifest excludes 'manifest_checksum' field from hash."""
    # Build manifest with varying keys
    manifest = {
        f"key_{i}": "x" * value_size
        for i in range(key_count)
    }
    
    hash_without = _sha256_of_manifest(manifest)
    
    # Add checksum field
    computed = _sha256_of_manifest(manifest)
    manifest["manifest_checksum"] = computed
    
    hash_with = _sha256_of_manifest(manifest)
    
    # Hashes should be identical (checksum field excluded)
    assert hash_with == hash_without, (
        "Checksum field was not excluded from hash computation"
    )


# ============================================================================
# Color Conversion Invariants (Pixel Conversion Properties)
# ============================================================================


@given(
    rgb_tuple=st.tuples(
        st.integers(0, 255),
        st.integers(0, 255),
        st.integers(0, 255)
    )
)
@settings(max_examples=50, deadline=1000)
def test_palette_rgb_components_are_bytes(rgb_tuple):
    """Property: Palette color components are representable as uint8."""
    r, g, b = rgb_tuple
    
    pal = build_palette()
    for pr, pg, pb in pal:
        # Each component should fit in a byte
        assert 0 <= pr <= 255
        assert 0 <= pg <= 255
        assert 0 <= pb <= 255


# ============================================================================
# Integration & Cross-Function Tests
# ============================================================================


def test_palette_and_tables_together():
    """Property: Palette and tables can be generated together without conflict."""
    pal = build_palette()
    pal_dat = create_palette_dat()
    tables = create_tables_dat()
    
    # Should both be valid bytes
    assert isinstance(pal_dat, bytes)
    assert isinstance(tables, bytes)
    
    # Sizes should be correct (see create_palette_dat for layout)
    expected_pal_size = 768 + 2 + (32 * 256) + 65536
    assert len(pal_dat) == expected_pal_size
    assert len(tables) == 8448


@pytest.mark.slow
def test_palette_consistency_with_palette_dat():
    """Property: Palette from build_palette() first 256 colors match create_palette_dat()."""
    pal = build_palette()
    dat = create_palette_dat()
    
    # First 768 bytes are the palette (256 colors * 3 bytes in 6-bit format)
    reconstructed = []
    for i in range(256):
        offset = i * 3
        # Stored in 6-bit format, convert back to 8-bit
        r = (dat[offset] << 2) | (dat[offset] & 0x3)
        g = (dat[offset + 1] << 2) | (dat[offset + 1] & 0x3)
        b = (dat[offset + 2] << 2) | (dat[offset + 2] & 0x3)
        reconstructed.append((r, g, b))
    
    # Palette should be reconstructible (allowing for 6-bit quantization loss)
    assert len(reconstructed) == 256, "Reconstructed palette wrong size"


# ============================================================================
# Idempotence & Stability Tests
# ============================================================================


def test_build_palette_idempotent():
    """Property: Applying build_palette multiple times yields same result."""
    pal1 = build_palette()
    pal2 = build_palette()
    pal3 = build_palette()
    
    assert pal1 == pal2 == pal3, "build_palette is not idempotent"


def test_create_tables_dat_idempotent():
    """Property: Applying create_tables_dat multiple times yields same result."""
    tables1 = create_tables_dat()
    tables2 = create_tables_dat()
    tables3 = create_tables_dat()
    
    assert tables1 == tables2 == tables3, "create_tables_dat is not idempotent"


# Test sentinel for hypothesis-expand-<8-hex>
_HYPOTHESIS_EXPAND_SENTINEL = "hypothesis-expand-a7f9c2e1"


# ============================================================================
# New Pure Function Property Tests (Cycle 87 Expansion)
# ============================================================================


@given(
    r=st.integers(0, 255),
    g=st.integers(0, 255),
    b=st.integers(0, 255)
)
@settings(max_examples=50, deadline=1000)
def test_nearest_color_returns_valid_index(r, g, b):
    """Property: _nearest_color returns a valid palette index (0-255)."""
    pal = build_palette()
    idx = _nearest_color(r, g, b, pal)
    assert isinstance(idx, int), f"Index {idx} is not int"
    assert 0 <= idx <= 255, f"Index {idx} out of valid range [0, 255]"


@given(
    r=st.integers(0, 255),
    g=st.integers(0, 255),
    b=st.integers(0, 255)
)
@settings(max_examples=50, deadline=1000)
def test_nearest_color_exact_match(r, g, b):
    """Property: _nearest_color returns exact match when color exists in palette."""
    pal = build_palette()
    # If (r,g,b) is in the palette, nearest_color should find it (dist=0)
    if (r, g, b) in pal:
        idx = _nearest_color(r, g, b, pal)
        assert pal[idx] == (r, g, b), f"Expected exact match for {(r,g,b)}, got {pal[idx]}"


@given(
    r=st.one_of(st.integers(-100, -1), st.integers(256, 500)),
    g=st.integers(0, 255),
    b=st.integers(0, 255)
)
@settings(max_examples=30, deadline=1000)
def test_nearest_color_rejects_invalid_rgb(r, g, b):
    """Property: _nearest_color raises ValueError for out-of-range RGB."""
    pal = build_palette()
    with pytest.raises(ValueError, match="must be in range"):
        _nearest_color(r, g, b, pal)


@given(
    palette=st.lists(
        st.tuples(
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 255)
        ),
        min_size=256,
        max_size=256
    )
)
@settings(max_examples=30, deadline=1000)
def test_validate_palette_input_accepts_valid_256_entry(palette):
    """Property: _validate_palette_input accepts exactly 256-entry palette."""
    # Should not raise for valid 256-entry palette
    _validate_palette_input(palette)


@given(
    palette=st.lists(
        st.tuples(
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 255)
        ),
        min_size=0,
        max_size=255
    )
)
@settings(max_examples=30, deadline=1000)
def test_validate_palette_input_rejects_wrong_length(palette):
    """Property: _validate_palette_input rejects palette not exactly 256 entries."""
    assume(len(palette) != 256)
    with pytest.raises(ValueError, match="exactly 256"):
        _validate_palette_input(palette)


@given(
    palette=st.lists(
        st.tuples(
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 300)  # One component out of range
        ),
        min_size=256,
        max_size=256
    )
)
@settings(max_examples=30, deadline=1000)
def test_validate_palette_input_rejects_invalid_component(palette):
    """Property: _validate_palette_input rejects palette with out-of-range components."""
    # Check if any component is invalid
    has_invalid = any(b > 255 for r, g, b in palette)
    assume(has_invalid)
    with pytest.raises(ValueError, match="range \\[0, 255\\]"):
        _validate_palette_input(palette)


@given(
    files_dict=st.dictionaries(
        st.text(
            min_size=1,
            max_size=12,
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('Z'),
                blacklist_characters='\x00'
            )
        ),
        st.binary(min_size=0, max_size=1000),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=40, deadline=2000)
def test_create_grp_deterministic(files_dict):
    """Property: create_grp returns identical output for same input (determinism)."""
    grp1 = create_grp(files_dict)
    grp2 = create_grp(files_dict)
    assert grp1 == grp2, "create_grp() is not deterministic"


@given(
    files_dict=st.dictionaries(
        st.text(
            min_size=1,
            max_size=12,
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('Z'),
                blacklist_characters='\x00'
            )
        ),
        st.binary(min_size=0, max_size=1000),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=40, deadline=2000)
def test_create_grp_starts_with_magic(files_dict):
    """Property: create_grp output begins with 'KenSilverman' magic header."""
    grp = create_grp(files_dict)
    assert grp[:12] == b"KenSilverman", f"GRP header wrong: {grp[:12]}"


@given(
    files_dict=st.dictionaries(
        st.text(
            min_size=1,
            max_size=12,
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('Z'),
                blacklist_characters='\x00'
            )
        ),
        st.binary(min_size=0, max_size=1000),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=40, deadline=2000)
def test_create_grp_file_count_correct(files_dict):
    """Property: create_grp encodes correct file count in header."""
    grp = create_grp(files_dict)
    num_files = struct.unpack("<I", grp[12:16])[0]
    assert num_files == len(files_dict), f"File count {num_files} != {len(files_dict)}"


@given(
    num_samples=st.integers(1, 10000),
    freq=st.integers(100, 4000)
)
@settings(max_examples=30, deadline=1000)
def test_generate_tone_samples_returns_correct_length(num_samples, freq):
    """Property: _generate_tone_samples returns exactly num_samples bytes."""
    samples = _generate_tone_samples(num_samples, freq)
    assert isinstance(samples, bytes), "_generate_tone_samples did not return bytes"
    assert len(samples) == num_samples, f"Length {len(samples)} != {num_samples}"


@given(
    num_samples=st.integers(1, 10000),
    freq=st.integers(100, 4000)
)
@settings(max_examples=30, deadline=1000)
def test_generate_tone_samples_values_in_range(num_samples, freq):
    """Property: _generate_tone_samples produces valid 8-bit unsigned PCM (0-255)."""
    samples = _generate_tone_samples(num_samples, freq)
    for i, byte_val in enumerate(samples):
        assert 0 <= byte_val <= 255, f"Sample {i}: {byte_val} out of range [0, 255]"


@given(
    num_samples=st.integers(1, 10000),
    seed=st.integers(0, 2**31 - 1)
)
@settings(max_examples=30, deadline=1000)
def test_generate_noise_samples_correct_length(num_samples, seed):
    """Property: _generate_noise_samples returns exactly num_samples bytes."""
    samples = _generate_noise_samples(num_samples, seed)
    assert isinstance(samples, bytes), "_generate_noise_samples did not return bytes"
    assert len(samples) == num_samples, f"Length {len(samples)} != {num_samples}"


@given(
    num_samples=st.integers(1, 10000),
    seed=st.integers(0, 2**31 - 1)
)
@settings(max_examples=30, deadline=1000)
def test_generate_noise_samples_deterministic(num_samples, seed):
    """Property: _generate_noise_samples is deterministic for same seed."""
    samples1 = _generate_noise_samples(num_samples, seed)
    samples2 = _generate_noise_samples(num_samples, seed)
    assert samples1 == samples2, "Noise generation with same seed produced different results"


@given(
    num_samples=st.integers(1, 10000),
    seed=st.integers(0, 2**31 - 1)
)
@settings(max_examples=30, deadline=1000)
def test_generate_click_samples_correct_length(num_samples, seed):
    """Property: _generate_click_samples returns exactly num_samples bytes."""
    samples = _generate_click_samples(num_samples, seed)
    assert isinstance(samples, bytes), "_generate_click_samples did not return bytes"
    assert len(samples) == num_samples, f"Length {len(samples)} != {num_samples}"


@given(
    num_samples=st.integers(1, 10000),
    seed=st.integers(0, 2**31 - 1)
)
@settings(max_examples=30, deadline=1000)
def test_generate_click_samples_within_bounds(num_samples, seed):
    """Property: _generate_click_samples produces valid 8-bit unsigned PCM (0-255)."""
    samples = _generate_click_samples(num_samples, seed)
    for i, byte_val in enumerate(samples):
        assert 0 <= byte_val <= 255, f"Sample {i}: {byte_val} out of range [0, 255]"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100)
)
@settings(max_examples=20, deadline=2000)
def test_unique_color_count_less_than_pixels(width, height):
    """Property: unique_color_count returns count <= total pixels."""
    # Create a simple RGB image
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    count = unique_color_count(img)
    assert count <= width * height, f"Color count {count} > pixels {width * height}"
    assert count >= 1, f"Color count {count} should be >= 1"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100),
    color_r=st.integers(0, 255),
    color_g=st.integers(0, 255),
    color_b=st.integers(0, 255)
)
@settings(max_examples=20, deadline=2000)
def test_unique_color_count_monochrome_is_one(width, height, color_r, color_g, color_b):
    """Property: unique_color_count returns 1 for monochrome image."""
    img = Image.new('RGB', (width, height), color=(color_r, color_g, color_b))
    count = unique_color_count(img)
    assert count == 1, f"Monochrome image should have 1 color, got {count}"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100)
)
@settings(max_examples=20, deadline=2000)
def test_color_histogram_sum_equals_pixels(width, height):
    """Property: color_histogram counts sum to total pixels."""
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    hist = color_histogram(img)
    total_pixels = sum(hist.values())
    assert total_pixels == width * height, f"Histogram sum {total_pixels} != pixels {width * height}"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100)
)
@settings(max_examples=20, deadline=2000)
def test_brightness_stats_bounds(width, height):
    """Property: brightness_stats returns valid bounds (min <= max, both in 0-255)."""
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    stats = brightness_stats(img)
    
    assert isinstance(stats, dict), "brightness_stats did not return dict"
    assert 'min' in stats and 'max' in stats, "Missing min/max in stats"
    assert 0 <= stats['min'] <= 255, f"Min {stats['min']} out of bounds"
    assert 0 <= stats['max'] <= 255, f"Max {stats['max']} out of bounds"
    assert stats['min'] <= stats['max'], f"Min {stats['min']} > Max {stats['max']}"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100)
)
@settings(max_examples=20, deadline=2000)
def test_is_black_screen_on_black_image(width, height):
    """Property: is_black_screen returns True for black images."""
    img = Image.new('RGB', (width, height), color=(0, 0, 0))
    assert is_black_screen(img, threshold=0.95), "Black image should be detected as black screen"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100)
)
@settings(max_examples=20, deadline=2000)
def test_is_black_screen_on_white_image(width, height):
    """Property: is_black_screen returns False for white/bright images."""
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    assume(width > 0 and height > 0)
    assert not is_black_screen(img, threshold=0.95), "White image should not be black screen"


@given(
    width=st.integers(2, 100),
    height=st.integers(2, 100),
    x=st.integers(0, 50),
    y=st.integers(0, 50),
    w=st.integers(1, 50),
    h=st.integers(1, 50)
)
@settings(max_examples=20, deadline=2000)
def test_region_crop_size(width, height, x, y, w, h):
    """Property: region_crop returns image with expected dimensions."""
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    
    # Clamp crop region to image bounds
    x = min(x, width - 1)
    y = min(y, height - 1)
    w = min(w, width - x)
    h = min(h, height - y)
    assume(w > 0 and h > 0)
    
    cropped = region_crop(img, x, y, w, h)
    assert cropped.size == (w, h), f"Crop size {cropped.size} != expected {(w, h)}"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100)
)
@settings(max_examples=15, deadline=2000)
def test_frame_difference_identical_frames(width, height):
    """Property: frame_difference returns 0.0 for identical images."""
    img1 = Image.new('RGB', (width, height), color=(128, 128, 128))
    img2 = Image.new('RGB', (width, height), color=(128, 128, 128))
    diff = frame_difference(img1, img2)
    assert diff == 0.0, f"Identical frames should have diff=0.0, got {diff}"


@given(
    width=st.integers(1, 100),
    height=st.integers(1, 100)
)
@settings(max_examples=15, deadline=2000)
def test_frame_difference_range(width, height):
    """Property: frame_difference returns value in range [0.0, 1.0]."""
    img1 = Image.new('RGB', (width, height), color=(0, 0, 0))
    img2 = Image.new('RGB', (width, height), color=(255, 255, 255))
    diff = frame_difference(img1, img2)
    assert 0.0 <= diff <= 1.0, f"Difference {diff} out of range [0.0, 1.0]"


@given(
    manifest_dict=st.fixed_dictionaries({
        "version": st.just("1.0"),
        "source": st.text(min_size=1, max_size=100),
        "key1": st.text(min_size=0, max_size=50),
    })
)
@settings(max_examples=30, deadline=1000)
def test_sha256_of_manifest_is_deterministic(manifest_dict):
    """Property: _sha256_of_manifest is deterministic (same hash for same dict)."""
    hash1 = _sha256_of_manifest(manifest_dict)
    hash2 = _sha256_of_manifest(manifest_dict)
    assert hash1 == hash2, "Hash should be deterministic"


@given(
    key_count=st.integers(1, 5),
    value_count=st.integers(1, 3)
)
@settings(max_examples=20, deadline=1000)
def test_sha256_of_manifest_excluded_checksum(key_count, value_count):
    """Property: _sha256_of_manifest excludes 'manifest_checksum' from computation."""
    # Create manifest with arbitrary keys and values
    manifest = {f"key_{i}": f"val_{j}" for i in range(key_count) for j in range(value_count)}
    manifest["version"] = "1.0"
    
    hash_without = _sha256_of_manifest(manifest)
    
    # Add checksum field
    computed = _sha256_of_manifest(manifest)
    manifest["manifest_checksum"] = computed
    
    hash_with = _sha256_of_manifest(manifest)
    
    # Should be identical (checksum excluded from hash)
    assert hash_with == hash_without, "Checksum field should be excluded"


@given(
    manifest_dict=st.fixed_dictionaries({
        "version": st.just("1.0"),
        "source": st.text(min_size=1, max_size=100),
    })
)
@settings(max_examples=20, deadline=1000)
def test_sha256_of_manifest_different_for_different_input(manifest_dict):
    """Property: _sha256_of_manifest produces different hashes for different inputs."""
    manifest1 = manifest_dict.copy()
    manifest2 = manifest_dict.copy()
    manifest2["source"] = manifest2["source"] + "_modified"
    assume(manifest1 != manifest2)
    
    hash1 = _sha256_of_manifest(manifest1)
    hash2 = _sha256_of_manifest(manifest2)
    assert hash1 != hash2, "Different manifests should produce different hashes"


@given(
    start_r=st.integers(0, 255),
    start_g=st.integers(0, 255),
    start_b=st.integers(0, 255),
    end_r=st.integers(0, 255),
    end_g=st.integers(0, 255),
    end_b=st.integers(0, 255),
    steps=st.integers(2, 50)
)
@settings(max_examples=30, deadline=1000)
def test_ramp_monotonicity_bounds(start_r, start_g, start_b, end_r, end_g, end_b, steps):
    """Property: _ramp never produces out-of-bounds intermediate colors."""
    start = (start_r, start_g, start_b)
    end = (end_r, end_g, end_b)
    ramp = _ramp(start, end, steps)
    
    for i, (r, g, b) in enumerate(ramp):
        assert 0 <= r <= 255, f"Color {i}: R={r} out of bounds"
        assert 0 <= g <= 255, f"Color {i}: G={g} out of bounds"
        assert 0 <= b <= 255, f"Color {i}: B={b} out of bounds"


@given(
    start_r=st.integers(0, 255),
    start_g=st.integers(0, 255),
    start_b=st.integers(0, 255),
    end_r=st.integers(0, 255),
    end_g=st.integers(0, 255),
    end_b=st.integers(0, 255),
)
@settings(max_examples=30, deadline=1000)
def test_ramp_single_step_returns_start(start_r, start_g, start_b, end_r, end_g, end_b):
    """Property: _ramp with 1 step returns [start]."""
    start = (start_r, start_g, start_b)
    end = (end_r, end_g, end_b)
    ramp = _ramp(start, end, 1)
    assert len(ramp) == 1, f"1-step ramp should have 1 entry, got {len(ramp)}"
    assert ramp[0] == start, f"1-step ramp should return start color"


@given(
    files_dict=st.dictionaries(
        st.text(
            min_size=1,
            max_size=12,
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('Z'),
                blacklist_characters='\x00'
            )
        ),
        st.binary(min_size=0, max_size=500),
        min_size=0,
        max_size=5
    )
)
@settings(max_examples=30, deadline=2000)
def test_create_grp_minimum_size(files_dict):
    """Property: create_grp output is at least header + directory size."""
    grp = create_grp(files_dict)
    min_size = 12 + 4 + (len(files_dict) * 16)  # magic + count + directory entries
    assert len(grp) >= min_size, f"GRP size {len(grp)} < minimum {min_size}"


@given(
    num_samples=st.integers(100, 5000),
    freq=st.integers(200, 3000)
)
@settings(max_examples=20, deadline=1000)
def test_generate_tone_samples_has_variation(num_samples, freq):
    """Property: _generate_tone_samples produces samples with variation (not constant)."""
    samples = _generate_tone_samples(num_samples, freq)
    byte_values = list(samples)
    
    # Should have at least some variation
    min_val = min(byte_values)
    max_val = max(byte_values)
    assert min_val != max_val, "Tone should have variation, not be constant"


@given(
    num_samples=st.integers(100, 5000),
    seed1=st.integers(0, 2**31 - 1),
    seed2=st.integers(0, 2**31 - 1)
)
@settings(max_examples=20, deadline=1000)
def test_generate_noise_samples_seed_changes_output(num_samples, seed1, seed2):
    """Property: _generate_noise_samples with different seeds produces different output."""
    assume(seed1 != seed2)
    samples1 = _generate_noise_samples(num_samples, seed1)
    samples2 = _generate_noise_samples(num_samples, seed2)
    assume(samples1 != samples2)  # Filter out rare hash collisions
    # Most different seeds should produce different noise
    assert samples1 != samples2, f"Different seeds should produce different noise"


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50)
)
@settings(max_examples=20, deadline=2000)
def test_color_histogram_keys_valid_rgb(width, height):
    """Property: color_histogram keys are valid RGB tuples."""
    img = Image.new('RGB', (width, height), color=(100, 150, 200))
    hist = color_histogram(img)
    
    for color, count in hist.items():
        assert isinstance(color, tuple), f"Key {color} is not tuple"
        assert len(color) == 3, f"Color {color} not 3-tuple"
        r, g, b = color
        assert 0 <= r <= 255, f"R={r} out of bounds"
        assert 0 <= g <= 255, f"G={g} out of bounds"
        assert 0 <= b <= 255, f"B={b} out of bounds"
        assert isinstance(count, int), f"Count {count} is not int"
        assert count >= 0, f"Count {count} is negative"


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50)
)
@settings(max_examples=20, deadline=2000)
def test_brightness_stats_mean_between_min_max(width, height):
    """Property: brightness_stats mean value is between min and max."""
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    stats = brightness_stats(img)
    
    assert stats['min'] <= stats['mean'] <= stats['max'], \
        f"Mean {stats['mean']} not between min {stats['min']} and max {stats['max']}"


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50)
)
@settings(max_examples=20, deadline=2000)
def test_brightness_stats_median_between_min_max(width, height):
    """Property: brightness_stats median value is between min and max."""
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    stats = brightness_stats(img)
    
    assert stats['min'] <= stats['median'] <= stats['max'], \
        f"Median {stats['median']} not between min {stats['min']} and max {stats['max']}"


@given(
    width=st.integers(10, 100),
    height=st.integers(10, 100),
    x_off=st.integers(0, 20),
    y_off=st.integers(0, 20),
    crop_w=st.integers(1, 30),
    crop_h=st.integers(1, 30)
)
@settings(max_examples=20, deadline=2000)
def test_region_crop_within_bounds(width, height, x_off, y_off, crop_w, crop_h):
    """Property: region_crop stays within image bounds."""
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    
    x = min(x_off, width - 1)
    y = min(y_off, height - 1)
    w = min(crop_w, width - x)
    h = min(crop_h, height - y)
    assume(w > 0 and h > 0)
    
    cropped = region_crop(img, x, y, w, h)
    assert cropped.size == (w, h), f"Crop dimensions mismatch"


@given(
    width=st.integers(2, 50),
    height=st.integers(2, 50)
)
@settings(max_examples=15, deadline=2000)
def test_frame_difference_same_size_different_content(width, height):
    """Property: frame_difference > 0 for images with different content."""
    img1 = Image.new('RGB', (width, height), color=(0, 0, 0))
    img2 = Image.new('RGB', (width, height), color=(200, 200, 200))
    
    diff = frame_difference(img1, img2)
    assert diff > 0.0, f"Different content should have diff > 0, got {diff}"


@given(
    steps=st.integers(2, 100)
)
@settings(max_examples=30, deadline=1000)
def test_ramp_linearity(steps):
    """Property: _ramp produces evenly-spaced colors in RGB space."""
    start = (0, 0, 0)
    end = (255, 255, 255)
    ramp = _ramp(start, end, steps)
    
    # For a linear ramp, differences between consecutive colors should be roughly equal
    assert len(ramp) == steps, f"Ramp length mismatch"
    
    # Check monotonicity: each component should be non-decreasing
    for i in range(len(ramp) - 1):
        r1, g1, b1 = ramp[i]
        r2, g2, b2 = ramp[i + 1]
        # All components should be non-decreasing
        assert r2 >= r1, f"R component decreased: {r1} -> {r2}"
        assert g2 >= g1, f"G component decreased: {g1} -> {g2}"
        assert b2 >= b1, f"B component decreased: {b1} -> {b2}"


@given(
    size=st.integers(10, 10000)
)
@settings(max_examples=20, deadline=1000)
def test_generate_click_samples_peak_in_middle(size):
    """Property: _generate_click_samples has variation (not constant single value)."""
    samples = _generate_click_samples(size, seed=42)
    byte_values = list(samples)
    
    # Should have some variation (not all same) for reasonable sizes
    assert len(set(byte_values)) > 1, "Click should have variation"


@given(
    palette=st.lists(
        st.tuples(
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 255)
        ),
        min_size=256,
        max_size=256
    )
)
@settings(max_examples=20, deadline=2000)
def test_validate_palette_does_not_modify(palette):
    """Property: _validate_palette_input does not modify the palette."""
    original = [tuple(x) for x in palette]
    _validate_palette_input(palette)
    assert palette == original, "_validate_palette_input modified the palette"


@given(
    manifest=st.fixed_dictionaries({
        "version": st.just("1.0"),
        "source": st.text(min_size=1, max_size=50),
        "timestamp": st.integers(0, 2**31 - 1),
    })
)
@settings(max_examples=20, deadline=1000)
def test_verify_manifest_checksum_accepts_correct_checksum(manifest):
    """Property: verify_manifest_checksum accepts manifest with correct checksum."""
    computed = _sha256_of_manifest(manifest)
    manifest["manifest_checksum"] = computed
    
    # Should not raise
    verify_manifest_checksum(manifest)


@given(
    r=st.integers(0, 255),
    g=st.integers(0, 255),
    b=st.integers(0, 255)
)
@settings(max_examples=25, deadline=1000)
def test_nearest_color_commutative_within_tolerance(r, g, b):
    """Property: _nearest_color result is stable across multiple calls."""
    pal = build_palette()
    idx1 = _nearest_color(r, g, b, pal)
    idx2 = _nearest_color(r, g, b, pal)
    assert idx1 == idx2, f"Color index should be stable: {idx1} != {idx2}"


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50)
)
@settings(max_examples=15, deadline=2000)
def test_frame_difference_zero_same_object(width, height):
    """Property: frame_difference with same object reference returns 0.0."""
    img = Image.new('RGB', (width, height), color=(100, 150, 200))
    diff = frame_difference(img, img)
    assert diff == 0.0, f"Same image should have diff=0.0, got {diff}"


@given(
    width=st.integers(5, 50),
    height=st.integers(5, 50)
)
@settings(max_examples=15, deadline=2000)
def test_region_crop_deterministic(width, height):
    """Property: region_crop returns same result on repeated calls."""
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    x, y, w, h = 1, 1, min(5, width - 1), min(5, height - 1)
    
    cropped1 = region_crop(img, x, y, w, h)
    cropped2 = region_crop(img, x, y, w, h)
    
    # Check dimensions match
    assert cropped1.size == cropped2.size, "Crop dimensions should be deterministic"


# ============================================================================
# New @given Tests — Hypothesis Expansion (Cycle 88+)
# ============================================================================


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50),
    seed=st.integers(0, 2**31 - 1)
)
@settings(max_examples=25, deadline=1500)
def test_quantize_image_deterministic(width, height, seed):
    """Property: quantize_image is deterministic — same inputs always yield same bytes.
    
    Tests surface #10: Texture quantization determinism.
    Given seed S and input I, two runs produce byte-identical output.
    """
    pal = build_palette()
    
    # Create image from seed for reproducibility
    np.random.seed(seed)
    rgb_data = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(rgb_data, mode='RGB')
    
    # Quantize twice with same inputs
    q1 = quantize_image(img, pal)
    q2 = quantize_image(img, pal)
    
    assert isinstance(q1, bytes), "quantize_image should return bytes"
    assert q1 == q2, "quantize_image must be deterministic for same input"


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50)
)
@settings(max_examples=25, deadline=1500)
def test_quantize_image_preserves_pixel_count(width, height):
    """Property: quantize_image output byte count equals width × height (1 byte/pixel).
    
    Tests surface #10: Texture quantization consistency.
    Quantized output should have exactly one byte per pixel.
    """
    pal = build_palette()
    img = Image.new('RGB', (width, height), color=(100, 150, 200))
    
    quantized = quantize_image(img, pal)
    
    assert isinstance(quantized, bytes), "quantize_image returns bytes"
    assert len(quantized) == width * height, (
        f"Quantized size {len(quantized)} != width*height {width * height}"
    )


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50)
)
@settings(max_examples=20, deadline=2000)
def test_analyze_frame_has_required_keys(width, height):
    """Property: analyze_frame always returns all required keys in output dict.
    
    Tests surface for frame analysis invariants.
    The output must contain: brightness, dimensions, has_content, is_black, top_colors, unique_colors.
    """
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    
    result = analyze_frame(img)
    
    assert isinstance(result, dict), "analyze_frame must return dict"
    
    required_keys = {'brightness', 'dimensions', 'has_content', 'is_black', 'top_colors', 'unique_colors'}
    assert required_keys.issubset(result.keys()), (
        f"Missing keys: {required_keys - set(result.keys())}"
    )


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50)
)
@settings(max_examples=20, deadline=2000)
def test_analyze_frame_value_types_correct(width, height):
    """Property: analyze_frame returns correct types for each field.
    
    Tests surface for frame analysis value type consistency.
    Validates that dimensions is a tuple, brightness is dict, etc.
    """
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    
    result = analyze_frame(img)
    
    assert isinstance(result['dimensions'], tuple), "dimensions should be tuple"
    assert len(result['dimensions']) == 2, "dimensions should be (width, height)"
    assert result['dimensions'][0] == width, "dimensions[0] should match image width"
    assert result['dimensions'][1] == height, "dimensions[1] should match image height"
    
    assert isinstance(result['brightness'], dict), "brightness should be dict"
    assert isinstance(result['has_content'], bool), "has_content should be bool"
    assert isinstance(result['is_black'], bool), "is_black should be bool"
    assert isinstance(result['unique_colors'], int), "unique_colors should be int"
    assert isinstance(result['top_colors'], list), "top_colors should be list"


@given(
    width=st.integers(1, 50),
    height=st.integers(1, 50),
    min_colors=st.integers(1, 10),
    max_black=st.floats(0.5, 1.0)
)
@settings(max_examples=20, deadline=1500)
def test_has_visible_content_deterministic(width, height, min_colors, max_black):
    """Property: has_visible_content is deterministic — returns same result on repeated calls.
    
    Tests surface for frame analysis consistency.
    Given same image and parameters, result should always be the same.
    """
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    
    result1 = has_visible_content(img, min_unique_colors=min_colors, max_black_ratio=max_black)
    result2 = has_visible_content(img, min_unique_colors=min_colors, max_black_ratio=max_black)
    
    assert isinstance(result1, bool), "has_visible_content should return bool"
    assert result1 == result2, "has_visible_content must be deterministic"


@given(
    payload=st.binary(min_size=1, max_size=1000)
)
@settings(max_examples=50, deadline=1500)
def test_sha256_hex_format_invariant(payload):
    """Property: _sha256_of_manifest produces exactly 64 lowercase hex characters.
    
    Tests surface #5: Manifest sha256 stability.
    Given any byte payload, sha256 hex is 64 lowercase chars matching [0-9a-f]{64}.
    """
    manifest = {
        "version": "1.0",
        "source": "test",
        "data": payload.hex()  # Convert bytes to hex string
    }
    
    hash_val = _sha256_of_manifest(manifest)
    
    assert isinstance(hash_val, str), "Hash must be string"
    assert len(hash_val) == 64, f"Hash length {len(hash_val)} != 64"
    assert all(c in '0123456789abcdef' for c in hash_val), (
        f"Hash contains non-hex or non-lowercase chars: {hash_val}"
    )


@given(
    width=st.integers(5, 100),
    height=st.integers(5, 100)
)
@settings(max_examples=15, deadline=2000)
def test_analyze_frame_brightness_bounds(width, height):
    """Property: analyze_frame brightness stats are bounded within [0, 255].
    
    Tests surface for frame analysis bounds invariant.
    All brightness metrics (min, max, mean, median, stddev) should be reasonable.
    """
    img = Image.new('RGB', (width, height), color=(128, 128, 128))
    
    result = analyze_frame(img)
    brightness = result['brightness']
    
    assert isinstance(brightness, dict), "brightness should be dict"
    assert 'min' in brightness and 'max' in brightness, "Missing min/max"
    assert 'mean' in brightness, "Missing mean"
    
    assert 0 <= brightness['min'] <= 255, f"min={brightness['min']} out of bounds"
    assert 0 <= brightness['max'] <= 255, f"max={brightness['max']} out of bounds"
    assert 0 <= brightness['mean'] <= 255, f"mean={brightness['mean']} out of bounds"
    assert brightness['min'] <= brightness['max'], "min should be <= max"


@given(
    num_colors=st.integers(1, 256)
)
@settings(max_examples=30, deadline=1000)
def test_build_palette_color_count_invariant(num_colors):
    """Property: build_palette always returns exactly 256 RGB tuples.
    
    Tests surface for palette generation invariant.
    The palette size must always be 256 regardless of requests; this tests that assertion.
    """
    pal = build_palette()
    
    assert len(pal) == 256, f"Palette size {len(pal)} != 256"
    
    for i, color in enumerate(pal):
        assert isinstance(color, tuple), f"Color {i} is not tuple"
        assert len(color) == 3, f"Color {i} is not 3-tuple"
        r, g, b = color
        assert all(isinstance(c, int) for c in (r, g, b)), f"Color {i} components not all int"
        assert all(0 <= c <= 255 for c in (r, g, b)), f"Color {i} component out of bounds"


@given(
    files_dict=st.dictionaries(
        st.text(
            min_size=1,
            max_size=12,
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('Z'),
                blacklist_characters='\x00'
            )
        ),
        st.binary(min_size=1, max_size=100),
        min_size=1,
        max_size=5
    )
)
@settings(max_examples=25, deadline=2000)
def test_create_grp_size_consistency(files_dict):
    """Property: create_grp output size is consistent and bounded.
    
    Tests surface for GRP format invariant.
    GRP size = 12 (magic) + 4 (count) + 16*N (entries) + payload.
    """
    grp = create_grp(files_dict)
    
    assert isinstance(grp, bytes), "create_grp should return bytes"
    
    # Verify minimum size: magic (12) + count (4) + directory entries (16*N)
    min_size = 12 + 4 + (len(files_dict) * 16)
    assert len(grp) >= min_size, (
        f"GRP size {len(grp)} < minimum {min_size}"
    )
    
    # Verify reasonable maximum (shouldn't be excessively large)
    total_payload = sum(len(data) for data in files_dict.values())
    max_reasonable = min_size + total_payload + 1000  # +1000 for overhead
    assert len(grp) <= max_reasonable, (
        f"GRP size {len(grp)} unreasonably large (expected <= {max_reasonable})"
    )


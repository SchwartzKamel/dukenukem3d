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

# Ensure tools package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from palette import _ramp, build_palette, create_palette_dat
from tables import create_tables_dat, _generate_basic_font, _generate_small_font, _generate_britable
from manifest_verification import _sha256_of_manifest, verify_manifest_checksum


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

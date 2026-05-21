"""Tests for palette generation and quantization."""
from palette import build_palette, create_palette_dat, quantize_image, _nearest_color, _validate_palette_input
from PIL import Image
import pytest


def test_palette_has_256_colors():
    """Palette contains exactly 256 RGB entries."""
    pal = build_palette()
    assert len(pal) == 256
    for r, g, b in pal:
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255


def test_palette_index_zero_is_black():
    """Index 0 should be black (transparent/background)."""
    pal = build_palette()
    assert pal[0] == (0, 0, 0)


def test_palette_dat_starts_with_rgb():
    """PALETTE.DAT begins with 768 bytes of VGA palette (0-63 range)."""
    pal = build_palette()
    dat = create_palette_dat(pal)
    assert len(dat) >= 768
    # VGA palette values are 6-bit (0-63)
    for i in range(768):
        assert 0 <= dat[i] <= 63, f"Byte {i} = {dat[i]} exceeds VGA 6-bit range"


def test_quantize_image_returns_correct_size():
    """Quantized image has same dimensions as input."""
    pal = build_palette()
    img = Image.new("RGB", (16, 16), (255, 0, 0))
    result = quantize_image(img, pal)
    assert len(result) == 16 * 16


def test_quantize_black_maps_to_zero():
    """Pure black should map to palette index 0."""
    pal = build_palette()
    img = Image.new("RGB", (4, 4), (0, 0, 0))
    result = quantize_image(img, pal)
    # All pixels should be index 0 (or near-black index)
    assert all(b == 0 for b in result)


def test_quantize_produces_valid_indices():
    """All quantized indices are within 0-255 range."""
    pal = build_palette()
    img = Image.new("RGB", (8, 8))
    # Fill with various colors
    px = img.load()
    for y in range(8):
        for x in range(8):
            px[x, y] = (x * 32, y * 32, (x + y) * 16)
    result = quantize_image(img, pal)
    assert all(0 <= b <= 255 for b in result)


def test_nearest_color_valid_rgb():
    """_nearest_color accepts valid RGB values (0-255)."""
    pal = build_palette()
    # Test boundary values and normal values
    assert 0 <= _nearest_color(0, 0, 0, pal) <= 255
    assert 0 <= _nearest_color(255, 255, 255, pal) <= 255
    assert 0 <= _nearest_color(128, 128, 128, pal) <= 255
    assert 0 <= _nearest_color(255, 0, 0, pal) <= 255


def test_nearest_color_invalid_rgb_out_of_range():
    """_nearest_color raises ValueError for out-of-range RGB values."""
    pal = build_palette()
    
    # Test out-of-range values
    with pytest.raises(ValueError, match="RGB values must be in range"):
        _nearest_color(256, 128, 128, pal)
    
    with pytest.raises(ValueError, match="RGB values must be in range"):
        _nearest_color(128, -1, 128, pal)
    
    with pytest.raises(ValueError, match="RGB values must be in range"):
        _nearest_color(128, 128, 300, pal)
    
    with pytest.raises(ValueError, match="RGB values must be in range"):
        _nearest_color(-1, -1, -1, pal)


# ============================================================================
# Palette validation tests (asset-r17)
# ============================================================================

def test_validate_palette_input_accepts_valid_palette():
    """_validate_palette_input accepts a valid 256-entry palette."""
    pal = build_palette()
    # Should not raise
    _validate_palette_input(pal)


def test_validate_palette_input_rejects_wrong_count_too_few():
    """_validate_palette_input rejects palette with < 256 entries."""
    pal = build_palette()[:255]  # 255 entries
    with pytest.raises(ValueError, match="exactly 256 entries.*got 255"):
        _validate_palette_input(pal)


def test_validate_palette_input_rejects_wrong_count_too_many():
    """_validate_palette_input rejects palette with > 256 entries."""
    pal = build_palette() + [(255, 255, 255)]  # 257 entries
    with pytest.raises(ValueError, match="exactly 256 entries.*got 257"):
        _validate_palette_input(pal)


def test_validate_palette_input_rejects_non_tuple_entry():
    """_validate_palette_input rejects non-tuple palette entries."""
    pal = build_palette()
    pal[100] = [255, 128, 64]  # List instead of tuple (but still valid structure)
    # Lists are actually allowed since we check for (list, tuple)
    # Let's make it invalid by using a non-sequence
    pal[100] = 12345
    with pytest.raises(ValueError, match=r"Palette\[100\]: Expected RGB tuple"):
        _validate_palette_input(pal)


def test_validate_palette_input_rejects_wrong_rgb_width_too_few():
    """_validate_palette_input rejects RGB tuples with < 3 components."""
    pal = build_palette()
    pal[50] = (255, 128)  # 2 components
    with pytest.raises(ValueError, match=r"Palette\[50\]: RGB tuple must have exactly 3 components.*got 2"):
        _validate_palette_input(pal)


def test_validate_palette_input_rejects_wrong_rgb_width_too_many():
    """_validate_palette_input rejects RGB tuples with > 3 components."""
    pal = build_palette()
    pal[75] = (255, 128, 64, 32)  # 4 components
    with pytest.raises(ValueError, match=r"Palette\[75\]: RGB tuple must have exactly 3 components.*got 4"):
        _validate_palette_input(pal)


def test_validate_palette_input_rejects_out_of_range_high():
    """_validate_palette_input rejects RGB component > 255."""
    pal = build_palette()
    pal[20] = (256, 128, 64)  # First component out of range
    with pytest.raises(ValueError, match=r"Palette\[20\]\[0\]: RGB component must be in range \[0, 255\].*got 256"):
        _validate_palette_input(pal)
    
    pal = build_palette()
    pal[20] = (128, 300, 64)  # Second component out of range
    with pytest.raises(ValueError, match=r"Palette\[20\]\[1\]: RGB component must be in range \[0, 255\].*got 300"):
        _validate_palette_input(pal)
    
    pal = build_palette()
    pal[20] = (128, 64, 1000)  # Third component out of range
    with pytest.raises(ValueError, match=r"Palette\[20\]\[2\]: RGB component must be in range \[0, 255\].*got 1000"):
        _validate_palette_input(pal)


def test_validate_palette_input_rejects_out_of_range_negative():
    """_validate_palette_input rejects negative RGB components."""
    pal = build_palette()
    pal[100] = (-1, 128, 64)  # Negative first component
    with pytest.raises(ValueError, match=r"Palette\[100\]\[0\]: RGB component must be in range \[0, 255\].*got -1"):
        _validate_palette_input(pal)
    
    pal = build_palette()
    pal[100] = (128, -50, 64)  # Negative second component
    with pytest.raises(ValueError, match=r"Palette\[100\]\[1\]: RGB component must be in range \[0, 255\].*got -50"):
        _validate_palette_input(pal)


def test_validate_palette_input_rejects_non_int_component():
    """_validate_palette_input rejects non-integer RGB components."""
    pal = build_palette()
    pal[150] = (255.5, 128, 64)  # Float instead of int
    with pytest.raises(ValueError, match=r"Palette\[150\]\[0\]: RGB component must be int"):
        _validate_palette_input(pal)
    
    pal = build_palette()
    pal[150] = (255, "128", 64)  # String instead of int
    with pytest.raises(ValueError, match=r"Palette\[150\]\[1\]: RGB component must be int"):
        _validate_palette_input(pal)


def test_validate_palette_input_warns_duplicate_black():
    """_validate_palette_input warns when duplicate black (0,0,0) appears outside index 0."""
    pal = build_palette()
    pal[200] = (0, 0, 0)  # Duplicate black at index 200
    
    with pytest.warns(UserWarning, match="duplicates the transparent key at index 0"):
        _validate_palette_input(pal)


def test_validate_palette_input_warns_only_once():
    """_validate_palette_input warns only once for multiple duplicates."""
    pal = build_palette()
    pal[200] = (0, 0, 0)
    pal[201] = (0, 0, 0)
    
    with pytest.warns(UserWarning) as record:
        _validate_palette_input(pal)
    
    # Should have only one warning (checked at first duplicate)
    warning_messages = [str(w.message) for w in record]
    assert len(warning_messages) == 1


def test_validate_palette_input_no_warning_for_index_zero():
    """_validate_palette_input does not warn for (0,0,0) at index 0 or 255."""
    import warnings
    pal = build_palette()  # Index 0 and 255 are (0, 0, 0) by definition
    # Should not produce a warning for indices 0 and 255
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _validate_palette_input(pal)
        # Filter to only warnings about duplicates
        dup_warnings = [warn for warn in w if "duplicate" in str(warn.message).lower()]
        assert len(dup_warnings) == 0


def test_create_palette_dat_calls_validation_with_custom_palette():
    """create_palette_dat validates custom palette input."""
    bad_pal = build_palette()
    bad_pal = bad_pal[:255]  # Too few entries
    
    with pytest.raises(ValueError, match="exactly 256 entries"):
        create_palette_dat(bad_pal)


@pytest.mark.slow
def test_create_palette_dat_no_validation_for_default_palette():
    """create_palette_dat uses default palette without validation when None."""
    # Should not raise, using default palette
    dat = create_palette_dat(None)
    assert isinstance(dat, bytes)
    assert len(dat) > 768


@pytest.mark.slow
def test_create_palette_dat_accepts_valid_custom_palette():
    """create_palette_dat accepts valid custom 256-entry palette."""
    pal = build_palette()
    dat = create_palette_dat(pal)
    assert isinstance(dat, bytes)
    assert len(dat) >= 768


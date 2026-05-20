"""Tests for palette generation and quantization."""
from palette import build_palette, create_palette_dat, quantize_image, _nearest_color
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


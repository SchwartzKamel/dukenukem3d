"""Tests for palette generation and quantization."""
from palette import build_palette, create_palette_dat, quantize_image
from PIL import Image


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

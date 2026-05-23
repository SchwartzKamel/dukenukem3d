"""Performance tests for palette quantization (perf-r29-palette-quantize-baseline)."""
import time
import pytest
from PIL import Image
from palette import build_palette, quantize_image


@pytest.mark.slow
def test_quantize_1920x1080_under_500ms():
    """Quantize 1920x1080 RGB image within 500ms wallclock time.
    
    Validates perf-r29-palette-quantize-numpy vectorization target:
    expected 4-6x speedup over per-pixel PIL access implementation.
    """
    palette = build_palette()
    
    # Generate 1920x1080 RGB test image (6.2M pixels)
    img = Image.new("RGB", (1920, 1080))
    px = img.load()
    
    # Fill with synthetic gradient pattern
    for y in range(1080):
        for x in range(1920):
            r = (x * 255) // 1920
            g = (y * 255) // 1080
            b = ((x + y) * 255) // 3000
            px[x, y] = (r, g, b)
    
    # Measure quantization wallclock time
    start = time.perf_counter()
    result = quantize_image(img, palette)
    elapsed = time.perf_counter() - start
    
    # Verify result
    assert len(result) == 1920 * 1080, "Output size must match input dimensions"
    assert all(0 <= b <= 255 for b in result), "All indices must be in valid range"
    
    # Performance assertion: < 500ms
    assert elapsed < 0.5, f"Quantization took {elapsed:.3f}s, expected < 0.5s"

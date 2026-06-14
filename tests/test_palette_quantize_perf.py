"""Performance tests for palette quantization (perf-r29-palette-quantize-baseline)."""
import time
import numpy as np
import pytest
from PIL import Image
from palette import build_palette, quantize_image


@pytest.mark.slow
def test_quantize_1920x1080_under_budget():
    """Quantize 1920x1080 RGB within a wallclock budget (vectorization guard).

    Validates the numpy-vectorized path: it must be dramatically faster than the
    per-pixel implementation (~40s) and must not regress to the old
    (num_pixels, 256, 3) materialization (~10s, multi-GB). The absolute budget
    is intentionally generous because this is timed while the rest of the suite
    runs in parallel (xdist) — best-of-N absorbs transient CPU contention while
    still catching a real (order-of-magnitude) regression.
    """
    palette = build_palette()

    # Build a 1920x1080 RGB gradient quickly (numpy, not per-pixel PIL access).
    xs = np.arange(1920, dtype=np.int64)
    ys = np.arange(1080, dtype=np.int64)
    r = ((xs * 255) // 1920).astype(np.uint8)[np.newaxis, :].repeat(1080, axis=0)
    g = ((ys * 255) // 1080).astype(np.uint8)[:, np.newaxis].repeat(1920, axis=1)
    b = (((xs[np.newaxis, :] + ys[:, np.newaxis]) * 255) // 3000).astype(np.uint8)
    arr = np.stack([r, g, b], axis=2)
    img = Image.fromarray(arr, "RGB")

    quantize_image(img, palette)  # warm up (one-time numpy/BLAS init)

    # Best-of-N wallclock so concurrent xdist load doesn't cause false failures.
    best = float("inf")
    result = None
    for _ in range(5):
        start = time.perf_counter()
        result = quantize_image(img, palette)
        best = min(best, time.perf_counter() - start)

    assert len(result) == 1920 * 1080, "Output size must match input dimensions"
    assert all(0 <= b <= 255 for b in result[:4096]), "Indices must be valid"

    # Budget tolerant of parallel load; a regression (per-pixel ~40s, or the old
    # multi-GB materialization ~10s) is still caught comfortably.
    assert best < 2.0, f"Quantization took {best:.3f}s (best of 5), expected < 2.0s"

# SPDX-License-Identifier: GPL-2.0-or-later
"""Frame analysis library for Duke Nukem 3D AI playtesting.

Analyzes BMP frame captures from the game's headless mode to validate
that rendering is working correctly.

Test Parametrization Contract (perf-r16-frame-analyzer-parametrization):
═════════════════════════════════════════════════════════════════════════

The test suite for frame_analyzer uses a consolidated parametrization strategy
to ensure determinism and catch race conditions in ThreadPoolExecutor-based
batch processing. DO NOT add ad-hoc or scattered parametrization variants.

Canonical Frame Count Test Matrix: [1, 3, 5]
────────────────────────────────────────────
  - num_frames=1: Boundary case (minimal parallelization, linear execution path)
  - num_frames=3: Small realistic workload (light parallelization)
  - num_frames=5: Medium workload (more contention, exercises thread pool)

Purpose:
  • Verify determinism of analyze_frame_sequence() across multiple runs
  • Catch non-determinism and race conditions in parallel frame loading
  • Validate ThreadPoolExecutor correctness without excessive test iterations

Current Test Implementation:
  • tests/test_frame_analyzer.py::TestAnalyzeFrameSequence::test_analyze_frame_sequence_deterministic
    - @pytest.mark.parametrize("num_frames", [1, 3, 5])
    - Creates N synthetic BMP frames, analyzes 3× in sequence, verifies identical outputs
    - Ensures bitwise-identical results (frame order independence)

Future Additions:
  1. If you need to test analyze_frame_sequence with different frame counts:
     → Extend the existing parametrized test or add a comment explaining deviation
  
  2. If you're adding parametrization to a NEW function:
     → Document intent clearly in test docstring
     → Reference this convention
     → Coordinate via tests/conftest.py conventions section
  
  3. If you find a bug that ONLY appears at specific frame counts:
     → Add the count to this docstring's "Known Sensitivities" section below
     → Explain the root cause and why it matters

Known Sensitivities:
  (none currently documented; add as needed)

See also:
  - tests/conftest.py (test parametrization conventions section)
  - tests/test_frame_analyzer.py (parametrized test docstring)
"""
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import struct
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor


# Lazy import helpers with singleton caching
_PIL_cache = {}
_numpy_cache = {}
_scipy_cache = {}


def _import_pil():
    """Lazy import PIL modules with singleton caching."""
    if "Image" not in _PIL_cache:
        from PIL import Image, ImageFile, UnidentifiedImageError
        _PIL_cache["Image"] = Image
        _PIL_cache["ImageFile"] = ImageFile
        _PIL_cache["UnidentifiedImageError"] = UnidentifiedImageError
        # Explicitly disable truncated image loading to catch corruption early
        ImageFile.LOAD_TRUNCATED_IMAGES = False
    return _PIL_cache["Image"], _PIL_cache["ImageFile"], _PIL_cache["UnidentifiedImageError"]


def _import_numpy():
    """Lazy import numpy with singleton caching."""
    if "np" not in _numpy_cache:
        import numpy as np
        _numpy_cache["np"] = np
    return _numpy_cache["np"]


def _import_scipy():
    """Lazy import scipy.ndimage with singleton caching."""
    if "ndimage" not in _scipy_cache:
        try:
            from scipy import ndimage
            _scipy_cache["ndimage"] = ndimage
            _scipy_cache["HAS_SCIPY"] = True
        except ImportError:
            _scipy_cache["HAS_SCIPY"] = False
            _scipy_cache["ndimage"] = None
    return _scipy_cache.get("HAS_SCIPY", False), _scipy_cache.get("ndimage")


def load_frame(path: str):
    """Load a captured BMP frame with robustness to truncation/corruption.
    
    Args:
        path: Path to BMP file
        
    Returns:
        PIL Image in RGB mode
        
    Raises:
        OSError: If file cannot be read or is truncated/corrupted
        UnidentifiedImageError: If file format is not recognized
    """
    Image, ImageFile, UnidentifiedImageError = _import_pil()
    try:
        img = Image.open(path)
        img.load()  # Force load to detect truncation/corruption early
        return img.convert("RGB")
    except (OSError, UnidentifiedImageError) as e:
        print(f"[!] Frame load failed (truncated/corrupt file): {path}: {type(e).__name__}: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"[!] Frame load error: {path}: {type(e).__name__}: {e}", file=sys.stderr)
        raise


def is_black_screen(img, threshold: float = 0.95, black_cutoff: int = 10) -> bool:
    """Check if image is mostly black (broken rendering).

    Args:
        img: PIL Image
        threshold: fraction of pixels that must be near-black to be considered a black screen
        black_cutoff: RGB value below which a pixel is considered "black"
    Returns:
        True if the screen is effectively all black (rendering failure)
    """
    colors = img.getcolors(maxcolors=2**24)
    if colors is None:
        # Fallback for images with more unique colors than maxcolors
        pixels_bytes = img.tobytes()
        pixels = [tuple(pixels_bytes[i:i+3]) for i in range(0, len(pixels_bytes), 3)]
        total = len(pixels)
        if total == 0:
            return True
        black_count = sum(1 for r, g, b in pixels if r < black_cutoff and g < black_cutoff and b < black_cutoff)
        return (black_count / total) >= threshold
    
    total = sum(count for count, _ in colors)
    if total == 0:
        return True
    black_count = sum(count for count, (r, g, b) in colors if r < black_cutoff and g < black_cutoff and b < black_cutoff)
    return (black_count / total) >= threshold


def unique_color_count(img) -> int:
    """Count the number of distinct colors in the image."""
    colors = img.getcolors(maxcolors=2**24)
    if colors is None:
        # Fallback: use numpy for vectorized conversion from bytes to pixel tuples
        np = _import_numpy()
        pixels_array = np.asarray(img)
        pixels_reshaped = pixels_array.reshape(-1, 3)
        return len(np.unique(pixels_reshaped, axis=0))
    return len(colors)


def color_histogram(img) -> Dict[Tuple[int, int, int], int]:
    """Return a dict mapping (R,G,B) tuples to pixel counts."""
    colors = img.getcolors(maxcolors=2**24)
    if colors is None:
        # Fallback: use numpy for vectorized processing
        np = _import_numpy()
        pixels_array = np.asarray(img)
        pixels_reshaped = pixels_array.reshape(-1, 3)
        unique_colors, counts = np.unique(pixels_reshaped, axis=0, return_counts=True)
        hist: Dict[Tuple[int, int, int], int] = {
            tuple(color): count for color, count in zip(unique_colors, counts)
        }
        return hist
    # colors is [(count, (r, g, b)), ...]
    return {color: count for count, color in colors}


def brightness_stats(img) -> Dict[str, float]:
    """Return min, max, mean, median brightness (0-255 grayscale equivalent)."""
    gray = img.convert("L")
    # For grayscale mode, tobytes() returns raw byte values which are the pixel values
    values = list(gray.tobytes())
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0}
    return {
        "min": float(min(values)),
        "max": float(max(values)),
        "mean": statistics.mean(values),
        "median": float(statistics.median(values)),
    }


def region_crop(img, x: int, y: int, w: int, h: int):
    """Crop a region from the image."""
    return img.crop((x, y, x + w, y + h))


def has_visible_content(img, min_unique_colors: int = 4, max_black_ratio: float = 0.98) -> bool:
    """Check if the frame has meaningful visible content.

    A frame has visible content if it's not mostly black AND has enough color variety.
    """
    if is_black_screen(img, threshold=max_black_ratio):
        return False
    return unique_color_count(img) >= min_unique_colors


def frame_difference(img1, img2) -> float:
    """Compute normalized difference between two frames (0.0 = identical, 1.0 = completely different).

    Useful for detecting if the game is actually animating/progressing.
    """
    if img1.size != img2.size:
        img2 = img2.resize(img1.size)

    # Use numpy for vectorized pixel-level operations
    np = _import_numpy()
    arr1 = np.asarray(img1)
    arr2 = np.asarray(img2)
    
    # Compute absolute differences across all channels, sum per pixel, then normalize
    diff_per_channel = np.abs(arr1.astype(np.float32) - arr2.astype(np.float32))
    diff_per_pixel = np.sum(diff_per_channel, axis=2)
    total_diff = np.sum(diff_per_pixel) / (arr1.shape[0] * arr1.shape[1] * 765.0)
    
    return float(total_diff)


def detect_text_region(img, y_start: int, y_end: int) -> bool:
    """Detect if there's likely text content in a horizontal band.

    Looks for high-contrast small features typical of text rendering.
    The game renders at 320x200, so text characters are small (4-8px).
    """
    band = img.crop((0, y_start, img.width, y_end))
    gray = band.convert("L")
    
    if band.width == 0 or band.height == 0:
        return False
    
    # Convert grayscale to numpy array and compute edge magnitude using Sobel
    HAS_SCIPY, ndimage = _import_scipy()
    np = _import_numpy()
    
    if HAS_SCIPY:
        pixels_array = np.asarray(gray, dtype=np.float32)
        # Sobel edge detection in x and y directions
        edges_x = ndimage.sobel(pixels_array, axis=1)
        edges_y = ndimage.sobel(pixels_array, axis=0)
        # Compute edge magnitude
        edge_magnitude = np.sqrt(edges_x**2 + edges_y**2)
        # Count high-contrast transitions (edges)
        transition_count = int(np.sum(edge_magnitude > 40))
    else:
        # Fallback: vectorized horizontal difference (no scipy)
        pixels_array = np.asarray(gray, dtype=np.float32)
        # Compute absolute difference between adjacent pixels horizontally
        diff = np.abs(np.diff(pixels_array, axis=1))
        transition_count = int(np.sum(diff > 40))
    
    total_possible = band.width * band.height
    if total_possible == 0:
        return False
    
    transition_ratio = transition_count / total_possible
    # Text regions typically have many small contrast transitions
    return bool(transition_ratio > 0.05)


def analyze_frame(img) -> Dict:
    """Run full analysis on a frame and return a summary dict.

    Returns dict with keys:
        - is_black: bool
        - has_content: bool
        - unique_colors: int
        - brightness: dict with min/max/mean/median
        - dimensions: (w, h)
        - top_colors: list of (count, (r,g,b)) for top 10 most common colors
    """
    hist = color_histogram(img)
    sorted_colors = sorted(hist.items(), key=lambda x: x[1], reverse=True)
    top_colors = [(count, color) for color, count in sorted_colors[:10]]

    return {
        "is_black": is_black_screen(img),
        "has_content": has_visible_content(img),
        "unique_colors": unique_color_count(img),
        "brightness": brightness_stats(img),
        "dimensions": img.size,
        "top_colors": top_colors,
    }


def analyze_frame_sequence(frame_paths: List[str]) -> Dict:
    """Analyze a sequence of captured frames.

    Returns dict with:
        - frame_count: int
        - all_black: bool (True if ALL frames are black - total rendering failure)
        - any_content: bool (True if ANY frame has visible content)
        - frames_with_content: int
        - has_progression: bool (True if frames differ from each other - game is running)
        - avg_frame_diff: float (average difference between consecutive frames)
        - per_frame: list of analyze_frame() results
    """
    # Parallelize frame loading using ThreadPoolExecutor (I/O-bound operation)
    # Use min(len(frame_paths), 4) to avoid excessive threads for small sequences
    # and limit resource contention for large sequences.
    max_workers = min(len(frame_paths), 4)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        frames = list(executor.map(load_frame, frame_paths))
    
    per_frame = [analyze_frame(f) for f in frames]

    all_black = all(pf["is_black"] for pf in per_frame)
    any_content = any(pf["has_content"] for pf in per_frame)
    frames_with_content = sum(1 for pf in per_frame if pf["has_content"])

    diffs = []
    for i in range(1, len(frames)):
        diffs.append(frame_difference(frames[i - 1], frames[i]))

    avg_frame_diff = statistics.mean(diffs) if diffs else 0.0
    has_progression = any(d > 0.001 for d in diffs) if diffs else False

    return {
        "frame_count": len(frames),
        "all_black": all_black,
        "any_content": any_content,
        "frames_with_content": frames_with_content,
        "has_progression": has_progression,
        "avg_frame_diff": avg_frame_diff,
        "per_frame": per_frame,
    }


# CLI entry point for manual inspection
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python frame_analyzer.py <frame.bmp> [frame2.bmp ...]")
        sys.exit(1)

    paths = sys.argv[1:]
    if len(paths) == 1:
        img = load_frame(paths[0])
        result = analyze_frame(img)
        # Pretty-print the analysis
        for key, value in result.items():
            print(f"  {key}: {value}")
    else:
        result = analyze_frame_sequence(paths)
        print(f"Sequence analysis ({result['frame_count']} frames):")
        print(f"  All black: {result['all_black']}")
        print(f"  Any content: {result['any_content']}")
        print(f"  Frames with content: {result['frames_with_content']}")
        print(f"  Has progression: {result['has_progression']}")
        print(f"  Avg frame diff: {result['avg_frame_diff']:.4f}")

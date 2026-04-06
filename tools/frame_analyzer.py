"""Frame analysis library for Duke Nukem 3D AI playtesting.

Analyzes BMP frame captures from the game's headless mode to validate
that rendering is working correctly.
"""
from PIL import Image
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import struct
import statistics


def load_frame(path: str) -> Image.Image:
    """Load a captured BMP frame and return as RGB PIL Image."""
    img = Image.open(path)
    return img.convert("RGB")


def is_black_screen(img: Image.Image, threshold: float = 0.95, black_cutoff: int = 10) -> bool:
    """Check if image is mostly black (broken rendering).

    Args:
        img: PIL Image
        threshold: fraction of pixels that must be near-black to be considered a black screen
        black_cutoff: RGB value below which a pixel is considered "black"
    Returns:
        True if the screen is effectively all black (rendering failure)
    """
    pixels = list(img.getdata())
    total = len(pixels)
    if total == 0:
        return True
    black_count = sum(1 for r, g, b in pixels if r < black_cutoff and g < black_cutoff and b < black_cutoff)
    return (black_count / total) >= threshold


def unique_color_count(img: Image.Image) -> int:
    """Count the number of distinct colors in the image."""
    return len(set(img.getdata()))


def color_histogram(img: Image.Image) -> Dict[Tuple[int, int, int], int]:
    """Return a dict mapping (R,G,B) tuples to pixel counts."""
    hist: Dict[Tuple[int, int, int], int] = {}
    for pixel in img.getdata():
        rgb = (pixel[0], pixel[1], pixel[2])
        hist[rgb] = hist.get(rgb, 0) + 1
    return hist


def brightness_stats(img: Image.Image) -> Dict[str, float]:
    """Return min, max, mean, median brightness (0-255 grayscale equivalent)."""
    gray = img.convert("L")
    values = list(gray.getdata())
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0}
    return {
        "min": float(min(values)),
        "max": float(max(values)),
        "mean": statistics.mean(values),
        "median": float(statistics.median(values)),
    }


def region_crop(img: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    """Crop a region from the image."""
    return img.crop((x, y, x + w, y + h))


def has_visible_content(img: Image.Image, min_unique_colors: int = 4, max_black_ratio: float = 0.98) -> bool:
    """Check if the frame has meaningful visible content.

    A frame has visible content if it's not mostly black AND has enough color variety.
    """
    if is_black_screen(img, threshold=max_black_ratio):
        return False
    return unique_color_count(img) >= min_unique_colors


def frame_difference(img1: Image.Image, img2: Image.Image) -> float:
    """Compute normalized difference between two frames (0.0 = identical, 1.0 = completely different).

    Useful for detecting if the game is actually animating/progressing.
    """
    if img1.size != img2.size:
        img2 = img2.resize(img1.size)

    pixels1 = list(img1.getdata())
    pixels2 = list(img2.getdata())
    total = len(pixels1)
    if total == 0:
        return 0.0

    diff_sum = 0.0
    for (r1, g1, b1), (r2, g2, b2) in zip(pixels1, pixels2):
        diff_sum += (abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)) / 765.0  # 765 = 255*3

    return diff_sum / total


def detect_text_region(img: Image.Image, y_start: int, y_end: int) -> bool:
    """Detect if there's likely text content in a horizontal band.

    Looks for high-contrast small features typical of text rendering.
    The game renders at 320x200, so text characters are small (4-8px).
    """
    band = img.crop((0, y_start, img.width, y_end))
    gray = band.convert("L")
    pixels = list(gray.getdata())
    if not pixels:
        return False

    width = band.width
    height = band.height

    # Look for high-contrast transitions (edges) along horizontal scanlines
    transition_count = 0
    for row in range(height):
        row_start = row * width
        for col in range(1, width):
            diff = abs(pixels[row_start + col] - pixels[row_start + col - 1])
            if diff > 40:
                transition_count += 1

    total_possible = width * height
    if total_possible == 0:
        return False

    transition_ratio = transition_count / total_possible
    # Text regions typically have many small contrast transitions
    return transition_ratio > 0.05


def analyze_frame(img: Image.Image) -> Dict:
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
    frames = [load_frame(p) for p in frame_paths]
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

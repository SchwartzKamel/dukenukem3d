"""Tests for the frame analysis library."""
import pytest
from PIL import Image
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.frame_analyzer import (
    load_frame,
    is_black_screen,
    unique_color_count,
    color_histogram,
    brightness_stats,
    region_crop,
    has_visible_content,
    frame_difference,
    detect_text_region,
    analyze_frame,
    analyze_frame_sequence,
)

TESTDATA_DIR = Path(__file__).resolve().parent.parent / "testdata"


@pytest.fixture(autouse=True)
def ensure_testdata_dir():
    TESTDATA_DIR.mkdir(parents=True, exist_ok=True)
    yield


def _make_solid_image(color, size=(32, 32)):
    """Helper: create a solid-color RGB image."""
    img = Image.new("RGB", size, color)
    return img


def _make_colorful_image(size=(32, 32)):
    """Helper: create a colorful image with many distinct pixels."""
    img = Image.new("RGB", size)
    pixels = img.load()
    for y in range(size[1]):
        for x in range(size[0]):
            pixels[x, y] = ((x * 8) % 256, (y * 8) % 256, ((x + y) * 4) % 256)
    return img


class TestLoadFrame:
    def test_load_frame_bmp(self):
        """Create a small test BMP with Pillow, save it, load it back."""
        bmp_path = TESTDATA_DIR / "test_load.bmp"
        original = _make_colorful_image((16, 16))
        original.save(str(bmp_path), format="BMP")

        loaded = load_frame(str(bmp_path))
        assert loaded.mode == "RGB"
        assert loaded.size == (16, 16)
        assert list(loaded.getdata()) == list(original.getdata())
        bmp_path.unlink()

    def test_load_frame_converts_to_rgb(self):
        """Ensure non-RGB images are converted."""
        bmp_path = TESTDATA_DIR / "test_load_rgba.bmp"
        original = Image.new("RGBA", (8, 8), (255, 0, 0, 128))
        original.save(str(bmp_path), format="BMP")

        loaded = load_frame(str(bmp_path))
        assert loaded.mode == "RGB"
        bmp_path.unlink()


class TestBlackScreenDetection:
    def test_all_black_is_black(self):
        img = _make_solid_image((0, 0, 0))
        assert is_black_screen(img) is True

    def test_colorful_is_not_black(self):
        img = _make_colorful_image()
        assert is_black_screen(img) is False

    def test_near_black_with_threshold(self):
        """Image with a few non-black pixels below threshold still counts as black."""
        img = Image.new("RGB", (100, 100), (0, 0, 0))
        pixels = img.load()
        # Set 3 pixels to white (3/10000 = 0.0003, well below 0.95 threshold)
        pixels[0, 0] = (255, 255, 255)
        pixels[1, 0] = (255, 255, 255)
        pixels[2, 0] = (255, 255, 255)
        assert is_black_screen(img) is True

    def test_dark_but_not_black(self):
        """Image with dark-but-above-cutoff pixels should not be black."""
        img = _make_solid_image((15, 15, 15))
        assert is_black_screen(img) is False

    def test_custom_cutoff(self):
        img = _make_solid_image((5, 5, 5))
        assert is_black_screen(img, black_cutoff=3) is False
        assert is_black_screen(img, black_cutoff=10) is True


class TestUniqueColors:
    def test_single_color(self):
        img = _make_solid_image((128, 64, 32), size=(10, 10))
        assert unique_color_count(img) == 1

    def test_known_color_count(self):
        img = Image.new("RGB", (4, 1))
        pixels = img.load()
        pixels[0, 0] = (255, 0, 0)
        pixels[1, 0] = (0, 255, 0)
        pixels[2, 0] = (0, 0, 255)
        pixels[3, 0] = (255, 0, 0)  # duplicate
        assert unique_color_count(img) == 3

    def test_colorful_has_many(self):
        img = _make_colorful_image((32, 32))
        assert unique_color_count(img) > 10


class TestHasVisibleContent:
    def test_black_screen_no_content(self):
        img = _make_solid_image((0, 0, 0))
        assert has_visible_content(img) is False

    def test_colorful_has_content(self):
        img = _make_colorful_image()
        assert has_visible_content(img) is True

    def test_single_nonblack_color_no_content(self):
        """A solid non-black color has only 1 unique color, below min_unique_colors."""
        img = _make_solid_image((200, 100, 50))
        assert has_visible_content(img) is False

    def test_few_colors_with_variety(self):
        """Image with exactly 4 distinct non-black colors has visible content."""
        img = Image.new("RGB", (4, 1))
        pixels = img.load()
        pixels[0, 0] = (255, 0, 0)
        pixels[1, 0] = (0, 255, 0)
        pixels[2, 0] = (0, 0, 255)
        pixels[3, 0] = (255, 255, 0)
        assert has_visible_content(img) is True


class TestFrameDifference:
    def test_identical_images(self):
        img = _make_colorful_image()
        assert frame_difference(img, img.copy()) == 0.0

    def test_completely_different(self):
        black = _make_solid_image((0, 0, 0))
        white = _make_solid_image((255, 255, 255))
        assert frame_difference(black, white) == pytest.approx(1.0)

    def test_partial_difference(self):
        img1 = _make_solid_image((100, 100, 100))
        img2 = _make_solid_image((150, 100, 100))
        diff = frame_difference(img1, img2)
        assert 0.0 < diff < 1.0

    def test_different_sizes_handled(self):
        img1 = _make_colorful_image((16, 16))
        img2 = _make_colorful_image((32, 32))
        diff = frame_difference(img1, img2)
        assert isinstance(diff, float)


class TestAnalyzeFrame:
    def test_returns_expected_keys(self):
        img = _make_colorful_image()
        result = analyze_frame(img)
        expected_keys = {"is_black", "has_content", "unique_colors", "brightness", "dimensions", "top_colors"}
        assert set(result.keys()) == expected_keys

    def test_black_frame_analysis(self):
        img = _make_solid_image((0, 0, 0))
        result = analyze_frame(img)
        assert result["is_black"] is True
        assert result["has_content"] is False
        assert result["unique_colors"] == 1
        assert result["dimensions"] == (32, 32)

    def test_colorful_frame_analysis(self):
        img = _make_colorful_image()
        result = analyze_frame(img)
        assert result["is_black"] is False
        assert result["has_content"] is True
        assert result["unique_colors"] > 1

    def test_brightness_in_result(self):
        img = _make_colorful_image()
        result = analyze_frame(img)
        brightness = result["brightness"]
        assert "min" in brightness
        assert "max" in brightness
        assert "mean" in brightness
        assert "median" in brightness

    def test_top_colors_format(self):
        img = _make_colorful_image()
        result = analyze_frame(img)
        top = result["top_colors"]
        assert isinstance(top, list)
        assert len(top) <= 10
        for count, color in top:
            assert isinstance(count, int)
            assert len(color) == 3


class TestAnalyzeFrameSequence:
    def test_sequence_analysis(self):
        paths = []
        for i in range(3):
            img = _make_colorful_image((16, 16))
            # Shift colors per frame so there's progression
            pixels = img.load()
            for y in range(16):
                for x in range(16):
                    r, g, b = pixels[x, y]
                    pixels[x, y] = ((r + i * 30) % 256, g, b)
            p = TESTDATA_DIR / f"seq_frame_{i}.bmp"
            img.save(str(p), format="BMP")
            paths.append(str(p))

        result = analyze_frame_sequence(paths)
        assert result["frame_count"] == 3
        assert result["all_black"] is False
        assert result["any_content"] is True
        assert result["frames_with_content"] == 3
        assert isinstance(result["avg_frame_diff"], float)
        assert len(result["per_frame"]) == 3

        for p in paths:
            Path(p).unlink()

    def test_all_black_sequence(self):
        paths = []
        for i in range(2):
            img = _make_solid_image((0, 0, 0), size=(8, 8))
            p = TESTDATA_DIR / f"black_frame_{i}.bmp"
            img.save(str(p), format="BMP")
            paths.append(str(p))

        result = analyze_frame_sequence(paths)
        assert result["all_black"] is True
        assert result["any_content"] is False
        assert result["frames_with_content"] == 0
        assert result["has_progression"] is False

        for p in paths:
            Path(p).unlink()

    def test_progression_detected(self):
        paths = []
        img1 = _make_solid_image((100, 0, 0), size=(8, 8))
        p1 = TESTDATA_DIR / "prog_frame_0.bmp"
        img1.save(str(p1), format="BMP")
        paths.append(str(p1))

        img2 = _make_solid_image((0, 0, 200), size=(8, 8))
        p2 = TESTDATA_DIR / "prog_frame_1.bmp"
        img2.save(str(p2), format="BMP")
        paths.append(str(p2))

        result = analyze_frame_sequence(paths)
        assert result["has_progression"] is True
        assert result["avg_frame_diff"] > 0.0

        for p in paths:
            Path(p).unlink()


class TestBrightnessStats:
    def test_black_image_brightness(self):
        img = _make_solid_image((0, 0, 0))
        stats = brightness_stats(img)
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0
        assert stats["median"] == 0.0

    def test_white_image_brightness(self):
        img = _make_solid_image((255, 255, 255))
        stats = brightness_stats(img)
        assert stats["min"] == 255.0
        assert stats["max"] == 255.0
        assert stats["mean"] == 255.0
        assert stats["median"] == 255.0

    def test_mixed_brightness(self):
        img = Image.new("RGB", (2, 1))
        pixels = img.load()
        pixels[0, 0] = (0, 0, 0)
        pixels[1, 0] = (255, 255, 255)
        stats = brightness_stats(img)
        assert stats["min"] == 0.0
        assert stats["max"] == 255.0
        assert 100.0 < stats["mean"] < 155.0


class TestRegionCrop:
    def test_crop_dimensions(self):
        img = _make_colorful_image((64, 64))
        cropped = region_crop(img, 10, 10, 20, 30)
        assert cropped.size == (20, 30)

    def test_crop_content(self):
        """Cropped region should match the corresponding pixels from the original."""
        img = _make_colorful_image((32, 32))
        cropped = region_crop(img, 5, 5, 10, 10)
        original_crop = img.crop((5, 5, 15, 15))
        assert list(cropped.getdata()) == list(original_crop.getdata())

    def test_crop_full_image(self):
        img = _make_colorful_image((16, 16))
        cropped = region_crop(img, 0, 0, 16, 16)
        assert cropped.size == img.size
        assert list(cropped.getdata()) == list(img.getdata())


class TestDetectTextRegion:
    def test_no_text_in_solid(self):
        img = _make_solid_image((128, 128, 128), size=(64, 32))
        assert detect_text_region(img, 0, 32) is False

    def test_text_like_pattern_detected(self):
        """Create alternating black/white columns to simulate text edges."""
        img = Image.new("RGB", (64, 16))
        pixels = img.load()
        for y in range(16):
            for x in range(64):
                if x % 3 == 0:
                    pixels[x, y] = (255, 255, 255)
                else:
                    pixels[x, y] = (0, 0, 0)
        assert detect_text_region(img, 0, 16) is True


class TestColorHistogram:
    def test_histogram_counts(self):
        img = Image.new("RGB", (3, 1))
        pixels = img.load()
        pixels[0, 0] = (255, 0, 0)
        pixels[1, 0] = (255, 0, 0)
        pixels[2, 0] = (0, 255, 0)
        hist = color_histogram(img)
        assert hist[(255, 0, 0)] == 2
        assert hist[(0, 255, 0)] == 1
        assert len(hist) == 2

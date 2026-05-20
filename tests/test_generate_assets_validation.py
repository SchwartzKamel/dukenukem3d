"""Tests for asset generation validation."""
import pytest
import sys
import os

# Import the validation function
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from generate_assets import _validate_texture_dimensions, TEXTURE_DEFS, SPRITE_DEFS


def test_validate_texture_dimensions_passes():
    """Validation should pass with current TEXTURE_DEFS and SPRITE_DEFS."""
    # This should not raise any exception
    _validate_texture_dimensions()


def test_texture_defs_all_have_positive_dimensions():
    """All TEXTURE_DEFS should have positive width and height."""
    for tile_num, width, height, desc, prompt in TEXTURE_DEFS:
        assert width > 0, f"Tile {tile_num} ({desc}): width must be positive, got {width}"
        assert height > 0, f"Tile {tile_num} ({desc}): height must be positive, got {height}"


def test_sprite_defs_all_have_positive_dimensions():
    """All SPRITE_DEFS should have positive width and height."""
    for tile_num, width, height, desc in SPRITE_DEFS:
        assert width > 0, f"Tile {tile_num} ({desc}): width must be positive, got {width}"
        assert height > 0, f"Tile {tile_num} ({desc}): height must be positive, got {height}"


def test_texture_defs_all_within_bounds():
    """All TEXTURE_DEFS should have dimensions within max bounds (256x256)."""
    for tile_num, width, height, desc, prompt in TEXTURE_DEFS:
        assert width <= 256, f"Tile {tile_num} ({desc}): width {width} exceeds max 256"
        assert height <= 256, f"Tile {tile_num} ({desc}): height {height} exceeds max 256"


def test_sprite_defs_all_within_bounds():
    """All SPRITE_DEFS should have dimensions within max bounds (256x256)."""
    for tile_num, width, height, desc in SPRITE_DEFS:
        assert width <= 256, f"Tile {tile_num} ({desc}): width {width} exceeds max 256"
        assert height <= 256, f"Tile {tile_num} ({desc}): height {height} exceeds max 256"

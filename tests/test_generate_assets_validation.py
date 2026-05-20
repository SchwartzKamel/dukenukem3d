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


# ---------------------------------------------------------------------------
# Pydantic schema tests (asset-r6-schema-texture-sprite)
# ---------------------------------------------------------------------------

try:
    from _asset_schemas import (
        TextureDef, SpriteDef,
        validate_texture_defs, validate_sprite_defs,
    )
    _HAS_PYDANTIC = True
except ImportError:
    _HAS_PYDANTIC = False


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_validates_current_texture_defs():
    """All real TEXTURE_DEFS pass the pydantic schema."""
    validate_texture_defs(TEXTURE_DEFS)


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_validates_current_sprite_defs():
    """All real SPRITE_DEFS pass the pydantic schema."""
    validate_sprite_defs(SPRITE_DEFS)


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_rejects_negative_dimension():
    """Schema rejects negative width/height."""
    with pytest.raises(Exception):
        TextureDef(tile_num=0, width=-1, height=64, description="x", flux_prompt="x")


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_rejects_oversized_dimension():
    """Schema rejects dimensions > 256."""
    with pytest.raises(Exception):
        SpriteDef(tile_num=0, width=512, height=64, description="x")


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_rejects_empty_description():
    """Schema rejects empty descriptions."""
    with pytest.raises(Exception):
        TextureDef(tile_num=0, width=64, height=64, description="   ", flux_prompt="x")


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_rejects_tile_num_out_of_range():
    """Schema rejects tile_num > 4943."""
    with pytest.raises(Exception):
        TextureDef(tile_num=99999, width=64, height=64, description="x", flux_prompt="x")


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_rejects_extra_fields():
    """Schema is strict-mode (extra='forbid')."""
    with pytest.raises(Exception):
        TextureDef(tile_num=0, width=64, height=64, description="x",
                   flux_prompt="x", bogus_field="nope")

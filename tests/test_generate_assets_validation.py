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
    """Schema rejects tile_num > 6143."""
    with pytest.raises(Exception):
        TextureDef(tile_num=99999, width=64, height=64, description="x", flux_prompt="x")


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_rejects_extra_fields():
    """Schema is strict-mode (extra='forbid')."""
    with pytest.raises(Exception):
        TextureDef(tile_num=0, width=64, height=64, description="x",
                   flux_prompt="x", bogus_field="nope")


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_accepts_tile_num_6143_boundary():
    """Schema accepts tile_num=6143 (MAXTILES-1 from source/BUILD.H)."""
    # TextureDef should accept 6143
    tex = TextureDef(tile_num=6143, width=64, height=64, description="x", flux_prompt="x")
    assert tex.tile_num == 6143
    
    # SpriteDef should also accept 6143
    spr = SpriteDef(tile_num=6143, width=64, height=64, description="x")
    assert spr.tile_num == 6143


@pytest.mark.skipif(not _HAS_PYDANTIC, reason="pydantic not installed")
def test_schema_rejects_tile_num_6144_boundary():
    """Schema rejects tile_num=6144 (exceeds MAXTILES-1)."""
    # TextureDef should reject 6144
    with pytest.raises(Exception):
        TextureDef(tile_num=6144, width=64, height=64, description="x", flux_prompt="x")
    
    # SpriteDef should also reject 6144
    with pytest.raises(Exception):
        SpriteDef(tile_num=6144, width=64, height=64, description="x")


# ---------------------------------------------------------------------------
# Font rendering error diagnostics (asset-r8-font-render-errors)
# ---------------------------------------------------------------------------

def test_draw_text_on_image_logs_draw_point_errors():
    """Font rendering should log errors when draw.point() fails.
    
    This test verifies that the _draw_text_on_image function properly
    handles exceptions from draw.point() and logs diagnostic information
    to stderr instead of silently swallowing the error.
    """
    import sys
    from unittest.mock import Mock, patch
    from io import StringIO
    
    from generate_assets import _draw_text_on_image
    
    # Create a mock draw object that raises an exception
    mock_draw = Mock()
    mock_draw.point.side_effect = ValueError("test draw error")
    
    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    
    try:
        # Call the function - should not raise, but should log
        _draw_text_on_image(mock_draw, 50, 50, "A", (255, 0, 0))
        
        # Verify error was logged to stderr
        logged_output = sys.stderr.getvalue()
        assert "Font render error" in logged_output, \
            f"Expected 'Font render error' in stderr, got: {logged_output}"
        assert "test draw error" in logged_output, \
            f"Expected error message in stderr, got: {logged_output}"
    finally:
        sys.stderr = old_stderr



# ---------------------------------------------------------------------------
# PIL Truncation and Error Handling Tests (asset-r8-pil-truncation-handling)
# ---------------------------------------------------------------------------

def test_generate_texture_ai_handles_truncated_png(monkeypatch, capsys):
    """Test that truncated PNG raises UnidentifiedImageError and is handled gracefully.
    
    This test verifies that PIL truncation/corruption is caught and reported
    on stderr with clear diagnostics, not swallowed silently.
    """
    from unittest.mock import Mock, patch
    import base64
    
    # Import after path setup
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
    from generate_assets import generate_texture_ai
    
    # Create a deliberately-truncated PNG bytestring (valid PNG header, but missing data)
    # Valid PNG magic: 89 50 4E 47 0D 0A 1A 0A
    truncated_png = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D,  # IHDR chunk size
        0x49, 0x48, 0x44, 0x52,  # "IHDR"
        0x00, 0x00, 0x00, 0x40,  # width: 64
        0x00, 0x00, 0x00, 0x40,  # height: 64
        0x08, 0x02, 0x00, 0x00,  # bit depth, color type, etc.
        0x00,  # compression method (truncated - missing CRC and data)
    ])
    
    # Mock requests.post to return truncated PNG as base64
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "image": base64.b64encode(truncated_png).decode('ascii')
    }
    
    with patch('requests.post', return_value=mock_response):
        # Call generate_texture_ai with truncated PNG
        # Should return None and emit stderr diagnostic
        result = generate_texture_ai(
            prompt="test",
            width=64,
            height=64,
            endpoint="http://mock",
            api_key="mock"
        )
    
    assert result is None, "Should return None for truncated/corrupt images"
    captured = capsys.readouterr()
    # Check that diagnostic was printed to stderr
    assert "Image parsing failed" in captured.err or "Image processing error" in captured.err, \
        f"Should emit stderr diagnostic. Got stderr: {captured.err}, stdout: {captured.out}"


def test_load_frame_handles_truncated_bmp(tmp_path, capsys):
    """Test that frame_analyzer.load_frame handles truncated BMP files robustly.
    
    Verifies that corrupted/truncated BMP files raise OSError/UnidentifiedImageError
    with clear stderr diagnostic instead of silent failures.
    """
    from PIL import UnidentifiedImageError
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
    from frame_analyzer import load_frame
    
    # Create a deliberately-truncated BMP file
    # Valid BMP header, but truncated data
    truncated_bmp = bytes([
        0x42, 0x4D,  # "BM" signature
        0x3A, 0x00, 0x00, 0x00,  # File size (58 bytes)
        0x00, 0x00, 0x00, 0x00,  # Reserved
        0x36, 0x00, 0x00, 0x00,  # Offset to pixel data
        0x28, 0x00, 0x00, 0x00,  # DIB header size
        0x01, 0x00, 0x00, 0x00,  # Width: 1
        0x01, 0x00, 0x00, 0x00,  # Height: 1
        0x01, 0x00,  # Planes, bits per pixel (truncated - missing rest)
    ])
    
    # Write truncated BMP to temp file
    bmp_path = tmp_path / "truncated.bmp"
    bmp_path.write_bytes(truncated_bmp)
    
    # Try to load - should raise exception
    with pytest.raises((OSError, UnidentifiedImageError)):
        load_frame(str(bmp_path))
    
    # Check that stderr diagnostic was emitted
    captured = capsys.readouterr()
    assert "Frame load failed" in captured.err or "Frame load error" in captured.err, \
        f"Should emit stderr diagnostic for corrupted frame. Got stderr: {captured.err}"


def test_pil_load_truncated_images_disabled():
    """Verify that LOAD_TRUNCATED_IMAGES is explicitly disabled at module load.
    
    This prevents silent acceptance of truncated images which could mask corruption.
    """
    from PIL import ImageFile
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
    
    # Import generate_assets to verify setting
    import importlib
    import generate_assets
    importlib.reload(generate_assets)
    
    # After reload, LOAD_TRUNCATED_IMAGES should be False
    assert ImageFile.LOAD_TRUNCATED_IMAGES is False, \
        "LOAD_TRUNCATED_IMAGES should be explicitly False to catch truncation errors"


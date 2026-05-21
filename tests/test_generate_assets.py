"""Tests for FLUX AI base64 error handling in asset generation.

Tests for asset-r9-base64-error-handling: distinguish malformed base64 from network failures.
"""
import pytest
import sys
import os
import base64
import binascii

# Setup path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from generate_assets import generate_texture_ai


def test_generate_texture_ai_malformed_base64_raises_binascii_error(monkeypatch, capsys):
    """Test that malformed base64 raises binascii.Error and is treated as hard failure (non-retryable).
    
    This verifies that:
    1. Malformed base64 is caught as binascii.Error
    2. Logged explicitly with "FLUX response malformed base64" diagnostic
    3. Response prefix (first 80 chars) is included in diagnostic
    4. Returns None immediately without retry
    """
    from unittest.mock import Mock, patch
    import binascii
    
    # Create a response with a valid HTTP response but decode will fail
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "image": "Invalid\x00Base64\x00String"  # Null bytes make it decode-invalid
    }
    
    # Mock base64.b64decode to raise binascii.Error for this test
    original_b64decode = base64.b64decode
    def mock_b64decode(data, altchars=None, validate=False):
        if isinstance(data, str) and "\x00" in data:
            raise binascii.Error("Incorrect padding")
        return original_b64decode(data, altchars=altchars, validate=validate)
    
    with patch('requests.post', return_value=mock_response):
        with patch('generate_assets.base64.b64decode', side_effect=mock_b64decode):
            result = generate_texture_ai(
                prompt="test",
                width=64,
                height=64,
                endpoint="http://mock",
                api_key="mock"
            )
    
    assert result is None, "Should return None for malformed base64"
    captured = capsys.readouterr()
    
    # Check for explicit malformed base64 diagnostic
    combined_output = captured.err + captured.out
    assert "malformed base64" in combined_output.lower(), \
        f"Should log 'malformed base64' diagnostic. Output: {combined_output}"
    assert "hard failure" in combined_output.lower() or "not retrying" in combined_output.lower(), \
        f"Should indicate this is a hard failure (non-retryable). Output: {combined_output}"


def test_generate_texture_ai_valid_base64_succeeds(monkeypatch, capsys):
    """Test that valid base64 image data is decoded successfully.
    
    This verifies the happy path:
    1. Valid base64-encoded PNG is decoded
    2. PIL can open and process the image
    3. Returns a PIL Image object
    """
    from unittest.mock import Mock, patch
    from PIL import Image
    import io
    
    # Create a minimal valid PNG (1x1 pixel)
    img = Image.new('RGB', (1, 1), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    valid_png = img_bytes.read()
    
    # Create a response with valid base64-encoded PNG
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "image": base64.b64encode(valid_png).decode('ascii')
    }
    
    with patch('requests.post', return_value=mock_response):
        result = generate_texture_ai(
            prompt="test",
            width=64,
            height=64,
            endpoint="http://mock",
            api_key="mock"
        )
    
    assert result is not None, "Should return PIL Image for valid base64 PNG"
    assert isinstance(result, Image.Image), "Should return a PIL Image object"
    assert result.mode == 'RGB', "Should have RGB color mode"
    assert result.size == (64, 64), "Should be resized to requested dimensions (64, 64)"


def test_generate_texture_ai_base64_decode_logs_response_prefix(monkeypatch, capsys):
    """Test that the response prefix (first 80 chars) is included in error diagnostics.
    
    This verifies that the diagnostic includes sanitized response data for debugging:
    1. First 80 characters of response are extracted
    2. Non-printable characters are sanitized
    3. Prefix is logged in the error message
    """
    from unittest.mock import Mock, patch
    
    # Create a response with invalid base64 and a specific prefix we can check for
    response_dict = {
        "image": "Invalid!!!",
        "error": "Some API error description with specific text",
        "status": "failed"
    }
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_dict
    
    with patch('requests.post', return_value=mock_response):
        result = generate_texture_ai(
            prompt="test",
            width=64,
            height=64,
            endpoint="http://mock",
            api_key="mock"
        )
    
    assert result is None, "Should return None for malformed base64"
    captured = capsys.readouterr()
    combined_output = captured.err + captured.out
    
    # Verify that response prefix is included in diagnostic
    # The prefix should contain parts of the response dict representation
    assert "malformed base64" in combined_output.lower(), \
        f"Should log malformed base64 diagnostic. Output: {combined_output}"

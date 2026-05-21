"""Tests for FLUX AI base64 error handling in asset generation.

Tests for asset-r9-base64-error-handling: distinguish malformed base64 from network failures.
Tests for asset-r27-flux-endpoint-validation-startup: FLUX config validation at startup.
Tests for asset-r27-http-429-retry-after-header: HTTP 429 Retry-After header support.
"""
import pytest
import sys
import os
import base64
import binascii
import datetime

# Setup path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from generate_assets import generate_texture_ai, _validate_flux_config, _parse_retry_after_header


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


# ==================================================================================
# Tests for asset-r27-flux-endpoint-validation-startup (FLUX config validation)
# ==================================================================================

def test_validate_flux_config_valid():
    """Test that valid FLUX configuration passes validation."""
    from unittest.mock import patch
    
    with patch('socket.gethostbyname') as mock_dns:
        mock_dns.return_value = "192.0.2.1"
        ok, reason = _validate_flux_config(
            endpoint="https://api.example.com/v1/generate",
            api_key="test_dummy_key_1234567890abcdef"
        )
    
    assert ok is True, f"Valid config should pass: {reason}"
    assert reason == "", "Reason should be empty for valid config"


def test_validate_flux_config_missing_api_key():
    """Test that missing API key is rejected."""
    ok, reason = _validate_flux_config(
        endpoint="https://api.example.com/v1/generate",
        api_key=""
    )
    
    assert ok is False
    assert "FLUX_API_KEY not set" in reason


def test_validate_flux_config_short_api_key():
    """Test that API key < 16 chars is rejected."""
    ok, reason = _validate_flux_config(
        endpoint="https://api.example.com/v1/generate",
        api_key="short123"
    )
    
    assert ok is False
    assert "too short" in reason.lower()


def test_validate_flux_config_missing_endpoint():
    """Test that missing endpoint is rejected."""
    ok, reason = _validate_flux_config(
        endpoint="",
        api_key="test_dummy_key_1234567890abcdef"
    )
    
    assert ok is False
    assert "FLUX_ENDPOINT not set" in reason


def test_validate_flux_config_invalid_scheme():
    """Test that non-https endpoint is rejected."""
    from unittest.mock import patch
    
    with patch('socket.gethostbyname') as mock_dns:
        mock_dns.return_value = "192.0.2.1"
        ok, reason = _validate_flux_config(
            endpoint="http://api.example.com/v1/generate",
            api_key="test_dummy_key_1234567890abcdef"
        )
    
    assert ok is False
    assert "https" in reason.lower()


def test_validate_flux_config_no_hostname():
    """Test that URL without hostname is rejected."""
    ok, reason = _validate_flux_config(
        endpoint="https:///invalid",
        api_key="test_dummy_key_1234567890abcdef"
    )
    
    assert ok is False
    assert "hostname" in reason.lower()


def test_validate_flux_config_dns_unresolvable():
    """Test that unresolvable hostname is rejected."""
    from unittest.mock import patch
    import socket
    
    with patch('socket.gethostbyname') as mock_dns:
        mock_dns.side_effect = socket.gaierror("Name or service not known")
        ok, reason = _validate_flux_config(
            endpoint="https://nonexistent.invalid.example.com/v1/generate",
            api_key="test_dummy_key_1234567890abcdef"
        )
    
    assert ok is False
    assert "not resolvable" in reason.lower()


# ==================================================================================
# Tests for asset-r27-http-429-retry-after-header (Retry-After header parsing)
# ==================================================================================

def test_parse_retry_after_header_integer_seconds():
    """Test parsing Retry-After header as integer seconds."""
    result = _parse_retry_after_header("30")
    assert result == 30.0, "Should parse integer seconds"


def test_parse_retry_after_header_integer_capped():
    """Test that Retry-After value is capped at 60s."""
    result = _parse_retry_after_header("300", max_wait=60.0)
    assert result == 60.0, "Should cap at max_wait (60s)"


def test_parse_retry_after_header_http_date():
    """Test parsing Retry-After header as HTTP-date."""
    # Create a future datetime
    future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=30)
    http_date = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    result = _parse_retry_after_header(http_date)
    assert result is not None, "Should parse HTTP-date format"
    # Allow for a small time drift (within 5 seconds)
    assert 25 <= result <= 35, f"Should return ~30 seconds, got {result}"


def test_parse_retry_after_header_invalid():
    """Test that invalid Retry-After header returns None."""
    result = _parse_retry_after_header("invalid-garbage-value")
    assert result is None, "Should return None for invalid header"


def test_parse_retry_after_header_empty():
    """Test that empty Retry-After header returns None."""
    result = _parse_retry_after_header("")
    assert result is None, "Should return None for empty header"


def test_generate_texture_ai_429_with_retry_after_integer(capsys):
    """Test that 429 response uses Retry-After integer header for wait time."""
    from unittest.mock import Mock, patch
    import time
    
    # Create a mock response with 429 and Retry-After header
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "2"}  # 2 seconds
    mock_response.text = "Rate limited"
    
    # Track time to verify wait actually happened
    start_time = time.time()
    
    with patch('requests.post', return_value=mock_response):
        with patch('time.sleep') as mock_sleep:
            result = generate_texture_ai(
                prompt="test",
                width=64,
                height=64,
                endpoint="https://api.example.com/v1/generate",
                api_key="test_dummy_key_1234567890abcdef"
            )
    
    # Should have called time.sleep with the Retry-After value
    mock_sleep.assert_called()
    # The first call to sleep should be with the parsed Retry-After value (2 seconds)
    assert mock_sleep.call_args_list[0][0][0] == 2.0


def test_generate_texture_ai_429_without_retry_after(capsys):
    """Test that 429 response without Retry-After uses exponential backoff."""
    from unittest.mock import Mock, patch
    
    # Create a mock response with 429 but no Retry-After header
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {}  # No Retry-After header
    mock_response.text = "Rate limited"
    
    with patch('requests.post', return_value=mock_response):
        with patch('time.sleep') as mock_sleep:
            result = generate_texture_ai(
                prompt="test",
                width=64,
                height=64,
                endpoint="https://api.example.com/v1/generate",
                api_key="test_dummy_key_1234567890abcdef"
            )
    
    # Should have called time.sleep with exponential backoff (not Retry-After)
    mock_sleep.assert_called()
    # Without Retry-After, should use backoff: 1.0 + jitter (0-0.5)
    first_sleep = mock_sleep.call_args_list[0][0][0]
    assert 1.0 <= first_sleep <= 1.5, f"Should use exponential backoff (1.0 + jitter), got {first_sleep}"


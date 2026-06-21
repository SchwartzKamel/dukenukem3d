"""Integration tests for compat/sha256.c (HMAC-SHA256 + HKDF).

Test suite verifying that SHA-256, HMAC-SHA256, and HKDF-SHA256 functions
from compat/sha256.c work end-to-end with known-answer test vectors.

Uses the session-scoped C harness pattern from cycle 117 (compiled_sha256_harness).
"""

import subprocess
import sys

import pytest

# The compiled_sha256_harness fixture links compat/sha256.c into a standalone
# C harness. On Windows that pulls DbgHelp / _startup_log symbols only the full
# engine link provides, so the harness fails to build; skip off Linux (these
# crypto known-answer tests are validated in CI).
pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="standalone sha256.c C harness only links on Linux "
           "(validated in CI).",
)


@pytest.mark.slow
class TestSHA256Integration:
    """Test SHA-256 cryptographic functions via compiled C harness."""
    
    def test_sha256_nist_vector(self, compiled_sha256_harness):
        """Test SHA-256 with NIST test vector ("abc").
        
        Known-answer: SHA256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
        """
        result = subprocess.run(
            [str(compiled_sha256_harness)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0, f"Harness failed:\n{result.stderr}"
        assert "PASS: SHA256(abc)" in result.stdout, f"SHA256(abc) test failed:\n{result.stdout}"
    
    def test_hmac_sha256_rfc4231(self, compiled_sha256_harness):
        """Test HMAC-SHA256 with RFC 4231 Test Case 1.
        
        Known-answer: HMAC-SHA256(0x0b..., "Hi There") = b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7
        """
        result = subprocess.run(
            [str(compiled_sha256_harness)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0, f"Harness failed:\n{result.stderr}"
        assert "PASS: HMAC-SHA256 (RFC 4231 TC1)" in result.stdout, f"HMAC-SHA256 test failed:\n{result.stdout}"
    
    def test_hkdf_sha256_rfc5869(self, compiled_sha256_harness):
        """Test HKDF-SHA256 with RFC 5869 Test Case 1.
        
        Known-answer: HKDF-Extract+Expand produces expected 42-byte output.
        """
        result = subprocess.run(
            [str(compiled_sha256_harness)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0, f"Harness failed:\n{result.stderr}"
        assert "PASS: HKDF-SHA256 (RFC 5869 TC1)" in result.stdout, f"HKDF-SHA256 test failed:\n{result.stdout}"
    
    def test_all_sha256_tests_pass(self, compiled_sha256_harness):
        """Verify all SHA256 tests pass in a single harness run.
        
        Consolidates all three tests to catch any integration issues.
        """
        result = subprocess.run(
            [str(compiled_sha256_harness)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0, f"Harness failed:\n{result.stderr}"
        assert "Results: 3 passed, 0 failed" in result.stdout, f"Expected 3 passed tests:\n{result.stdout}"

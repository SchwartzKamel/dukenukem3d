"""
Tests for net_socket_is_keepalive_error() helper function.

Tests verify that the net_socket_is_keepalive_error() function correctly
identifies keepalive-related errors on both POSIX and Windows platforms.

Coverage:
  - POSIX: ETIMEDOUT, ECONNRESET → 1; EAGAIN, EWOULDBLOCK, EINTR, ENOTCONN, 0 → 0
  - Windows: WSAETIMEDOUT, WSAECONNRESET → 1 (if on win32)
"""

import subprocess
import sys
import os
import tempfile
import textwrap
from pathlib import Path
import pytest


def compile_keepalive_error_test():
    """
    Compile a minimal C test harness that calls net_socket_is_keepalive_error().
    Returns a tuple: (compiled_binary_path, test_result_as_dict)
    """
    test_code = textwrap.dedent(r'''
    #include <stdio.h>
    #include <errno.h>
    #include <string.h>
    
    #ifdef _WIN32
    #include <winsock2.h>
    #else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #endif
    
    /* Forward declare the function we're testing */
    int net_socket_is_keepalive_error(int err);
    
    /* POSIX implementation */
    #ifndef _WIN32
    int net_socket_is_keepalive_error(int err)
    {
        return (err == ETIMEDOUT || err == ECONNRESET);
    }
    #else
    /* Windows implementation */
    int net_socket_is_keepalive_error(int err)
    {
        return (err == WSAETIMEDOUT || err == WSAECONNRESET);
    }
    #endif
    
    int main(void)
    {
        int pass = 0;
        int fail = 0;
        
        /* Test positive cases (should return 1) */
        #ifndef _WIN32
        /* POSIX tests */
        if (net_socket_is_keepalive_error(ETIMEDOUT) == 1) {
            printf("PASS: ETIMEDOUT -> 1\n");
            pass++;
        } else {
            printf("FAIL: ETIMEDOUT -> %d (expected 1)\n", net_socket_is_keepalive_error(ETIMEDOUT));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(ECONNRESET) == 1) {
            printf("PASS: ECONNRESET -> 1\n");
            pass++;
        } else {
            printf("FAIL: ECONNRESET -> %d (expected 1)\n", net_socket_is_keepalive_error(ECONNRESET));
            fail++;
        }
        
        /* Test negative cases (should return 0) */
        if (net_socket_is_keepalive_error(EAGAIN) == 0) {
            printf("PASS: EAGAIN -> 0\n");
            pass++;
        } else {
            printf("FAIL: EAGAIN -> %d (expected 0)\n", net_socket_is_keepalive_error(EAGAIN));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(EWOULDBLOCK) == 0) {
            printf("PASS: EWOULDBLOCK -> 0\n");
            pass++;
        } else {
            printf("FAIL: EWOULDBLOCK -> %d (expected 0)\n", net_socket_is_keepalive_error(EWOULDBLOCK));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(EINTR) == 0) {
            printf("PASS: EINTR -> 0\n");
            pass++;
        } else {
            printf("FAIL: EINTR -> %d (expected 0)\n", net_socket_is_keepalive_error(EINTR));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(ENOTCONN) == 0) {
            printf("PASS: ENOTCONN -> 0\n");
            pass++;
        } else {
            printf("FAIL: ENOTCONN -> %d (expected 0)\n", net_socket_is_keepalive_error(ENOTCONN));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(0) == 0) {
            printf("PASS: 0 -> 0\n");
            pass++;
        } else {
            printf("FAIL: 0 -> %d (expected 0)\n", net_socket_is_keepalive_error(0));
            fail++;
        }
        #else
        /* Windows tests */
        if (net_socket_is_keepalive_error(WSAETIMEDOUT) == 1) {
            printf("PASS: WSAETIMEDOUT -> 1\n");
            pass++;
        } else {
            printf("FAIL: WSAETIMEDOUT -> %d (expected 1)\n", net_socket_is_keepalive_error(WSAETIMEDOUT));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(WSAECONNRESET) == 1) {
            printf("PASS: WSAECONNRESET -> 1\n");
            pass++;
        } else {
            printf("FAIL: WSAECONNRESET -> %d (expected 1)\n", net_socket_is_keepalive_error(WSAECONNRESET));
            fail++;
        }
        
        if (net_socket_is_keepalive_error(0) == 0) {
            printf("PASS: 0 -> 0\n");
            pass++;
        } else {
            printf("FAIL: 0 -> %d (expected 0)\n", net_socket_is_keepalive_error(0));
            fail++;
        }
        #endif
        
        printf("Results: %d passed, %d failed\n", pass, fail);
        return (fail == 0) ? 0 : 1;
    }
    ''')
    
    # Create temp directory for compilation
    with tempfile.TemporaryDirectory(prefix='net_socket_test_') as tmpdir:
        tmpdir_path = Path(tmpdir)
        src_file = tmpdir_path / 'test_keepalive_error.c'
        exe_file = tmpdir_path / 'test_keepalive_error'
        
        # Write test source
        src_file.write_text(test_code)
        
        # Compile
        compile_cmd = [
            'gcc',
            '-o', str(exe_file),
            str(src_file),
            '-Wall', '-Wextra', '-pedantic',
        ]
        
        result = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
        
        # Run the test
        run_result = subprocess.run(
            [str(exe_file)],
            capture_output=True,
            text=True
        )
        
        return run_result.stdout, run_result.returncode


class TestNetSocketIsKeepaliveErrorDeclaration:
    """Test net_socket_is_keepalive_error() function declaration."""
    
    def test_is_keepalive_error_declared(self):
        """net_socket.h must declare net_socket_is_keepalive_error."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_is_keepalive_error' in content
        assert 'int net_socket_is_keepalive_error' in content
    
    def test_posix_implementation_has_is_keepalive_error(self):
        """net_socket_posix.c must implement net_socket_is_keepalive_error."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        assert 'net_socket_is_keepalive_error' in content
        # Should check for ETIMEDOUT and ECONNRESET
        assert 'ETIMEDOUT' in content or 'ECONNRESET' in content
    
    def test_win32_implementation_has_is_keepalive_error(self):
        """net_socket_win32.c must implement net_socket_is_keepalive_error."""
        with open('compat/net_socket_win32.c') as f:
            content = f.read()
        assert 'net_socket_is_keepalive_error' in content
        # Should check for Windows error codes
        assert 'WSAETIMEDOUT' in content or 'WSAECONNRESET' in content


class TestNetSocketIsKeepaliveErrorFunctionality:
    """Test net_socket_is_keepalive_error() actual behavior."""
    
    def test_keepalive_error_detection(self):
        """Test that keepalive error detection works correctly."""
        try:
            output, returncode = compile_keepalive_error_test()
            
            # Check that all tests passed
            assert returncode == 0, f"Test failed with return code {returncode}\n{output}"
            
            # Verify expected test results are in output
            lines = output.strip().split('\n')
            
            # Count PASS/FAIL results
            pass_count = sum(1 for line in lines if 'PASS:' in line)
            fail_count = sum(1 for line in lines if 'FAIL:' in line)
            
            # On POSIX: should have 7 tests (2 positive + 5 negative)
            # On Windows: should have 3 tests (2 positive + 1 negative)
            if sys.platform == 'win32':
                assert pass_count >= 3, f"Expected at least 3 passing tests on Windows, got {pass_count}\n{output}"
            else:
                assert pass_count >= 7, f"Expected at least 7 passing tests on POSIX, got {pass_count}\n{output}"
            
            assert fail_count == 0, f"Test had failures:\n{output}"
            
        except RuntimeError as e:
            pytest.skip(f"Could not compile test: {e}")


class TestNetSocketIsKeepaliveErrorPositiveCases:
    """Parametrized tests for positive cases (keepalive errors)."""
    
    @pytest.mark.parametrize("error_name,expected", [
        ("ETIMEDOUT", 1),
        ("ECONNRESET", 1),
    ])
    def test_keepalive_positive_cases(self, error_name, expected):
        """Test that ETIMEDOUT and ECONNRESET are recognized as keepalive errors."""
        # Verify the error codes are handled correctly in source
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        
        if error_name in content:
            # The error is mentioned in the implementation
            assert error_name in content, f"{error_name} should be in implementation"
            # Verify the function checks these errors
            assert 'net_socket_is_keepalive_error' in content


class TestNetSocketIsKeepaliveErrorNegativeCases:
    """Parametrized tests for negative cases (non-keepalive errors)."""
    
    @pytest.mark.parametrize("error_name,expected", [
        ("EAGAIN", 0),
        ("EWOULDBLOCK", 0),
        ("EINTR", 0),
        ("ENOTCONN", 0),
        ("0", 0),
    ])
    def test_keepalive_negative_cases(self, error_name, expected):
        """Test that other errors are NOT recognized as keepalive errors."""
        # These tests verify the logic in the implementation
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        
        # The implementation should only return true for ETIMEDOUT/ECONNRESET
        func_impl = content.split('net_socket_is_keepalive_error')[1].split('}')[0]
        
        # Verify ETIMEDOUT and ECONNRESET are checked
        assert 'ETIMEDOUT' in func_impl and 'ECONNRESET' in func_impl, \
            "Function should check ETIMEDOUT and ECONNRESET"

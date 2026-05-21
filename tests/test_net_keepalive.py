"""Tests for TCP SO_KEEPALIVE socket option in net_socket abstraction.

These tests verify that the net_socket_enable_keepalive() function properly
enables SO_KEEPALIVE on both POSIX and Windows platforms.
"""

import os
import socket
import struct
import pytest
import ctypes
import sys


class TestNetSocketKeepAlive:
    """Test SO_KEEPALIVE socket option support."""

    def test_net_socket_h_has_enable_keepalive(self):
        """net_socket.h must declare net_socket_enable_keepalive."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_enable_keepalive' in content
        assert 'int net_socket_enable_keepalive' in content

    def test_posix_implementation_has_enable_keepalive(self):
        """net_socket_posix.c must implement net_socket_enable_keepalive."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        assert 'net_socket_enable_keepalive' in content
        assert 'SO_KEEPALIVE' in content

    def test_win32_implementation_has_enable_keepalive(self):
        """net_socket_win32.c must implement net_socket_enable_keepalive."""
        with open('compat/net_socket_win32.c') as f:
            content = f.read()
        assert 'net_socket_enable_keepalive' in content
        assert 'SO_KEEPALIVE' in content

    def test_posix_keepalive_logs_warnings(self):
        """net_socket_posix.c must log warnings on SO_KEEPALIVE failure."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        # Should log warnings if setsockopt fails
        assert 'WARNING' in content or 'fprintf(stderr' in content
        assert 'SO_KEEPALIVE' in content

    def test_win32_keepalive_logs_warnings(self):
        """net_socket_win32.c must log warnings on SO_KEEPALIVE failure."""
        with open('compat/net_socket_win32.c') as f:
            content = f.read()
        # Should log warnings if setsockopt fails
        assert 'WARNING' in content or 'fprintf(stderr' in content
        assert 'SO_KEEPALIVE' in content

    def test_posix_keepalive_includes_netinet_tcp_h(self):
        """net_socket_posix.c must include netinet/tcp.h for TCP_KEEP* constants."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        # Should include netinet/tcp.h for TCP_KEEPIDLE, etc.
        assert '#include <netinet/tcp.h>' in content

    def test_posix_keepalive_has_optional_tuning(self):
        """net_socket_posix.c should optionally set TCP_KEEPIDLE/INTVL/CNT."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        # Should conditionally set these if available on Linux
        assert '#ifdef TCP_KEEPIDLE' in content or 'TCP_KEEPIDLE' in content
        # At least one of these should be present
        has_tuning = ('TCP_KEEPIDLE' in content or 'TCP_KEEPINTVL' in content or 'TCP_KEEPCNT' in content)
        assert has_tuning

    def test_posix_keepalive_returns_int(self):
        """net_socket_enable_keepalive should return int."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        # Should return 0 on success (or error code on SO_KEEPALIVE failure)
        assert 'return 0;' in content or 'return ret' in content

    def test_posix_keepalive_does_not_abort_on_failure(self):
        """net_socket_enable_keepalive must not abort if setsockopt fails."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        # Should log warning but continue (not exit/abort)
        assert 'fprintf(stderr' in content  # Logs warning
        assert 'exit' not in content.lower() or 'exit' not in content.split('net_socket_enable_keepalive')[1].split('}')[0]

    @pytest.mark.skipif(sys.platform == 'win32', reason="Testing only on non-Windows platforms for now")
    def test_socket_keepalive_can_be_verified_with_getsockopt(self):
        """Verify that SO_KEEPALIVE can be checked with getsockopt."""
        # This is a basic sanity test that demonstrates the approach
        # The actual application would call net_socket_enable_keepalive()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Enable keepalive at Python level
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # Verify it's enabled using getsockopt
            keepalive_enabled = sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
            assert keepalive_enabled == 1, f"SO_KEEPALIVE should be 1, got {keepalive_enabled}"
        finally:
            sock.close()

    def test_header_requires_stdint_h_for_stdint_types(self):
        """net_socket.h must include stdint.h for portable int types."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert '#include <stdint.h>' in content

    def test_net_socket_implementations_compiled_to_object_files(self):
        """Both POSIX and Win32 implementations must be in build system."""
        with open('build.mk') as f:
            build_mk = f.read()
        # Should reference both or conditionally include
        assert 'net_socket' in build_mk.lower() or 'net_socket_posix.c' in build_mk or 'net_socket_win32.c' in build_mk

    def test_mmulti_c_includes_net_socket_h(self):
        """SRC/MMULTI.C must include net_socket.h for keepalive API."""
        with open('SRC/MMULTI.C') as f:
            content = f.read()
        assert '../compat/net_socket.h' in content or 'net_socket.h' in content
        assert 'net_socket_enable_keepalive' in content

    def test_mmulti_c_calls_keepalive_on_server_socket(self):
        """MMULTI.C must enable keepalive on server (listen) socket."""
        with open('SRC/MMULTI.C') as f:
            content = f.read()
        # Should have keepalive call after server socket creation
        assert content.count('net_socket_enable_keepalive') >= 1

    def test_mmulti_c_calls_keepalive_on_client_sockets(self):
        """MMULTI.C must enable keepalive on accepted client sockets."""
        with open('SRC/MMULTI.C') as f:
            content = f.read()
        # Should have multiple keepalive calls (server socket + each client socket)
        assert content.count('net_socket_enable_keepalive') >= 2

    def test_mmulti_c_calls_keepalive_on_connect_socket(self):
        """MMULTI.C client mode must enable keepalive after connect()."""
        with open('SRC/MMULTI.C') as f:
            content = f.read()
        # Should have at least 3 calls total: server socket, accepted client(s), connecting socket
        assert content.count('net_socket_enable_keepalive') >= 3

"""Tests for the net_socket compatibility layer (compat/net_socket.h).

These tests verify that:
1. The header file exists and declares the expected API surface
2. All symbol declarations are present
3. Platform-conditional compilation is correctly configured
"""

import os
import re
import pytest


class TestNetSocketHeader:
    """Test net_socket.h header presence and declarations."""

    def test_net_socket_h_exists(self):
        """net_socket.h must exist."""
        assert os.path.exists('compat/net_socket.h')

    def test_header_includes_guards(self):
        """Header must have include guards."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert '#ifndef NET_SOCKET_H' in content
        assert '#define NET_SOCKET_H' in content
        assert '#endif' in content

    def test_header_cpp_extern(self):
        """Header must support C++ with extern 'C'."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert '#ifdef __cplusplus' in content
        assert 'extern "C"' in content


class TestNetSocketAPIDeclarations:
    """Test that net_socket.h declares all required API functions."""

    def test_net_socket_init_declared(self):
        """net_socket_init() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_init' in content
        assert re.search(r'void\s+net_socket_init\s*\(\s*void\s*\)', content)

    def test_net_socket_shutdown_declared(self):
        """net_socket_shutdown() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_shutdown' in content
        assert re.search(r'void\s+net_socket_shutdown\s*\(\s*void\s*\)', content)

    def test_net_socket_create_declared(self):
        """net_socket_create() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_create' in content
        assert 'domain' in content
        assert 'type' in content
        assert 'protocol' in content

    def test_net_socket_bind_declared(self):
        """net_socket_bind() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_bind' in content
        assert 'struct sockaddr' in content

    def test_net_socket_listen_declared(self):
        """net_socket_listen() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_listen' in content
        assert 'backlog' in content

    def test_net_socket_accept_declared(self):
        """net_socket_accept() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_accept' in content

    def test_net_socket_connect_declared(self):
        """net_socket_connect() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_connect' in content

    def test_net_socket_send_declared(self):
        """net_socket_send() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_send' in content
        assert 'buf' in content or 'data' in content

    def test_net_socket_recv_declared(self):
        """net_socket_recv() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_recv' in content

    def test_net_socket_close_declared(self):
        """net_socket_close() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_close' in content

    def test_net_socket_set_nonblocking_declared(self):
        """net_socket_set_nonblocking() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_set_nonblocking' in content

    def test_net_socket_last_error_declared(self):
        """net_socket_last_error() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_last_error' in content

    def test_net_socket_is_transient_error_declared(self):
        """net_socket_is_transient_error() must be declared."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_is_transient_error' in content


class TestNetSocketTypes:
    """Test that net_socket.h declares required type definitions."""

    def test_net_socket_t_typedef(self):
        """net_socket_t must be typedef'd."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'net_socket_t' in content
        assert 'typedef' in content

    def test_net_socket_invalid_constant(self):
        """NET_SOCKET_INVALID must be defined."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert 'NET_SOCKET_INVALID' in content
        assert '#define' in content


class TestNetSocketPlatformConditionals:
    """Test platform-specific conditional compilation in header."""

    def test_header_has_win32_guards(self):
        """Header must conditionally include Winsock2 for Windows."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert '#ifdef _WIN32' in content
        assert 'winsock2.h' in content

    def test_header_has_posix_guards(self):
        """Header must conditionally include POSIX socket headers."""
        with open('compat/net_socket.h') as f:
            content = f.read()
        assert '#else' in content  # POSIX branch
        assert 'sys/socket.h' in content


class TestNetSocketImplementations:
    """Test that platform-specific implementations exist."""

    def test_net_socket_posix_c_exists(self):
        """net_socket_posix.c must exist."""
        assert os.path.exists('compat/net_socket_posix.c')

    def test_net_socket_win32_c_exists(self):
        """net_socket_win32.c must exist."""
        assert os.path.exists('compat/net_socket_win32.c')

    def test_posix_implementation_has_init(self):
        """net_socket_posix.c must implement net_socket_init()."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        assert 'net_socket_init' in content

    def test_win32_implementation_has_init(self):
        """net_socket_win32.c must implement net_socket_init()."""
        with open('compat/net_socket_win32.c') as f:
            content = f.read()
        assert 'net_socket_init' in content

    def test_posix_implementation_has_shutdown(self):
        """net_socket_posix.c must implement net_socket_shutdown()."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        assert 'net_socket_shutdown' in content

    def test_win32_implementation_has_shutdown(self):
        """net_socket_win32.c must implement net_socket_shutdown()."""
        with open('compat/net_socket_win32.c') as f:
            content = f.read()
        assert 'net_socket_shutdown' in content

    def test_win32_uses_wsa_startup(self):
        """net_socket_win32.c must use WSAStartup."""
        with open('compat/net_socket_win32.c') as f:
            content = f.read()
        assert 'WSAStartup' in content or 'WSACleanup' in content

    def test_posix_no_wsa_calls(self):
        """net_socket_posix.c should not use WSAStartup."""
        with open('compat/net_socket_posix.c') as f:
            content = f.read()
        assert 'WSAStartup' not in content


class TestBuildSystemIntegration:
    """Test that net_socket sources are integrated into build system."""

    def test_build_mk_has_net_socket_conditional(self):
        """build.mk must conditionally add net_socket_posix.c or net_socket_win32.c."""
        with open('build.mk') as f:
            content = f.read()
        # Should have conditional based on PLATFORM_WIN32
        assert 'net_socket' in content
        assert 'net_socket_posix.c' in content or 'net_socket_win32.c' in content

    def test_cmake_has_net_socket_conditional(self):
        """CMakeLists.txt must conditionally add net_socket implementations."""
        with open('CMakeLists.txt') as f:
            content = f.read()
        # Should have conditional based on WIN32
        assert 'net_socket' in content
        assert 'net_socket_posix.c' in content or 'net_socket_win32.c' in content

    def test_build_mk_win32_conditional(self):
        """build.mk must use ifdef PLATFORM_WIN32 for conditional."""
        with open('build.mk') as f:
            content = f.read()
        # POSIX line should be in else clause
        if 'net_socket_posix.c' in content:
            # Find the context around net_socket
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'net_socket' in line:
                    # Should have ifdef PLATFORM_WIN32 or similar nearby
                    context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                    assert 'ifdef' in context or 'WIN32' in context or 'else' in context

    def test_cmake_win32_conditional(self):
        """CMakeLists.txt must use if(WIN32) for conditional."""
        with open('CMakeLists.txt') as f:
            content = f.read()
        # Should have if(WIN32) ... else() ... endif()
        if 'net_socket_posix.c' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'net_socket' in line:
                    context = '\n'.join(lines[max(0, i-3):min(len(lines), i+4)])
                    assert 'if(WIN32)' in context or 'if(NOT WIN32)' in context or 'else(' in context

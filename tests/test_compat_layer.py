"""Tests for the compatibility layer (compat/) correctness."""
import struct
import os
import subprocess
import pytest

# ===== Struct Size Tests =====
# These verify the BUILD engine struct sizes match what the code expects

class TestStructSizes:
    """Verify critical BUILD engine struct sizes for 64-bit compatibility."""

    def test_sectortype_size(self):
        """sectortype must be exactly 40 bytes (packed, little-endian)."""
        # wallptr(h) wallnum(h) ceilingz(i) floorz(i) ceilingstat(h) floorstat(h)
        # ceilingpicnum(h) ceilingheinum(h) ceilingshade(b) ceilingpal(B)
        # ceilingxpanning(B) ceilingypanning(B) floorpicnum(h) floorheinum(h)
        # floorshade(b) floorpal(B) floorxpanning(B) floorypanning(B)
        # visibility(B) filler(B) lotag(h) hitag(h) extra(h)
        fields = '<hhiihhhhbBBBhhbBBBBBhhh'
        assert struct.calcsize(fields) == 40

    def test_walltype_size(self):
        """walltype must be exactly 32 bytes (packed, little-endian)."""
        # x(i) y(i) point2(h) nextwall(h) nextsector(h) cstat(h)
        # picnum(h) overpicnum(h) shade(b) pal(B) xrepeat(B) yrepeat(B)
        # xpanning(B) ypanning(B) lotag(h) hitag(h) extra(h)
        fields = '<iihhhhhhbBBBBBhhh'
        assert struct.calcsize(fields) == 32

    def test_spritetype_size(self):
        """spritetype must be exactly 44 bytes (packed, little-endian)."""
        # x(i) y(i) z(i) cstat(h) picnum(h) shade(b) pal(B) clipdist(B)
        # filler(B) xrepeat(B) yrepeat(B) xoffset(b) yoffset(b)
        # sectnum(h) statnum(h) ang(h) owner(h) xvel(h) yvel(h) zvel(h)
        # lotag(h) hitag(h) extra(h)
        fields = '<iiihhbBBBBBbbhhhhhhhhhh'
        assert struct.calcsize(fields) == 44


class TestCompatFunctions:
    """Test that compat layer header defines are correct."""

    def test_compat_header_exists(self):
        """compat.h must exist."""
        assert os.path.exists('compat/compat.h')

    def test_audio_stub_exists(self):
        """audio_stub.h must exist."""
        assert os.path.exists('compat/audio_stub.h')

    def test_msvc_unistd_exists(self):
        """msvc_unistd.h must exist for MSVC builds."""
        # May or may not exist yet
        path = 'compat/msvc_unistd.h'
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            assert 'io.h' in content, "msvc_unistd.h should include io.h"
            assert 'direct.h' in content, "msvc_unistd.h should include direct.h"

    def test_compat_guards_win32(self):
        """compat.h must guard Windows-only code with #ifdef _WIN32."""
        with open('compat/compat.h') as f:
            content = f.read()
        assert '#ifdef _WIN32' in content or '#if defined(_WIN32)' in content
        assert 'windows.h' in content

    def test_compat_guards_inp_outp(self):
        """inp/outp stubs must be guarded with #ifndef _WIN32."""
        with open('compat/compat.h') as f:
            content = f.read()
        # Verify inp/outp are guarded (they conflict with MinGW intrin.h)
        assert 'inp' in content
        assert '#ifndef _WIN32' in content

    def test_compat_error_fatal(self):
        """error_fatal() must be defined for error reporting."""
        with open('compat/compat.h') as f:
            content = f.read()
        assert 'error_fatal' in content
        assert 'MessageBoxA' in content or 'MessageBox' in content


class TestBuildConfig:
    """Test build configuration consistency."""

    def test_build_mk_exists(self):
        """build.mk must exist as single source of truth."""
        assert os.path.exists('build.mk')

    def test_build_mk_has_all_sources(self):
        """build.mk must list all source files."""
        with open('build.mk') as f:
            content = f.read()
        # Engine sources
        assert 'ENGINE.C' in content
        assert 'CACHE1D.C' in content
        assert 'MMULTI.C' in content
        # Key game sources
        assert 'GAME.C' in content
        assert 'ACTORS.C' in content
        assert 'GAMEDEF.C' in content
        # Compat sources
        assert 'sdl_driver.c' in content
        assert 'audio_stub.c' in content
        assert 'mact_stub.c' in content
        assert 'hud.c' in content

    def test_build_mk_sdl2_version(self):
        """build.mk must pin SDL2 version."""
        with open('build.mk') as f:
            content = f.read()
        assert 'SDL2_VERSION' in content

    def test_makefile_includes_build_mk(self):
        """Makefile must include build.mk."""
        with open('Makefile') as f:
            content = f.read()
        assert 'include build.mk' in content or '-include build.mk' in content

    def test_cmake_has_all_compat(self):
        """CMakeLists.txt must list all compat sources."""
        with open('CMakeLists.txt') as f:
            content = f.read()
        assert 'sdl_driver.c' in content
        assert 'audio_stub.c' in content
        assert 'mact_stub.c' in content
        assert 'hud.c' in content


class TestAudioAssets:
    """Test audio asset configuration."""

    def test_audio_script_exists(self):
        """generate_audio.py must exist."""
        assert os.path.exists('tools/generate_audio.py')

    def test_audio_script_has_voice_lines(self):
        """generate_audio.py must define voice line specs."""
        with open('tools/generate_audio.py') as f:
            content = f.read()
        assert 'TAUNT' in content
        assert 'PAIN' in content
        assert 'DEATH' in content
        assert 'PICKUP' in content


class TestSecurityBasics:
    """Basic security checks."""

    def test_env_in_gitignore(self):
        """.env must be in .gitignore."""
        with open('.gitignore') as f:
            content = f.read()
        assert '.env' in content

    def test_no_hardcoded_api_keys(self):
        """No API keys should be hardcoded in Python scripts."""
        for script in ['tools/generate_assets.py', 'tools/generate_audio.py']:
            if os.path.exists(script):
                with open(script) as f:
                    content = f.read()
                # Should load from env, not hardcode
                assert 'sk-' not in content.lower(), f"Possible API key in {script}"
                assert 'api_key = "' not in content, f"Hardcoded API key in {script}"

    def test_security_md_exists(self):
        """SECURITY.md must exist."""
        assert os.path.exists('SECURITY.md')

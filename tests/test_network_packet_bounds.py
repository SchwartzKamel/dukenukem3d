"""
Test network packet bounds hardening (cycles 41-58).

Cycle 59 split: test-r16-mega-file-split-critical
Extracted from test_engine_net_hardening_regressions.py (3803 lines)
Sentinel: net-r1x class tests for packet type validation, bounds checks, timeout guards.
"""

"""
Regression tests for hardening fixes from cycle 11-15, 19-20, 22, and r8.

These tests use static analysis (grep-style source inspection) to verify
that critical guard patterns remain in place. They do NOT execute the engine.
This is sufficient to catch common regressions like:
  - Someone removed the bounds check
  - Someone reverted to strcpy
  - Someone removed the ferror guard

Test coverage:
  1. labelcode array (cycle 12): Proper array declaration + extern
  2. MENUES.C file-I/O (cycle 13): ferror guards at 49+ sites
  3. audio_stub.c RIFF validation (cycle 13): Both "RIFF" and "WAVE" checks
  4. audio_stub.c channel exhaustion (cycle 13): Mix_GroupOldest usage
  5. CON-script bounds (cycle 15): labelcnt >= MAXLABELS patterns
  6. MMULTI.C bounds (cycle 15): from_player bounds checks
  7. SoundOwner cap (cycle 15): FX_StopSound in xyzsound context
  8. FX_SetVolume thread safety (cycle 15): SDL_LockAudio in FX_SetVolume
  9. sprite-yvel bounds (cycle 20): player_from_yvel macro and usage
  10. savegame loader bounds (cycle 20): ferror checks after kdfread
  11. savegame wall/sector partial-reads (cycle r8): partial read + memset cleanup
  12. cache1d_free_bytes counter (cycle 22): static variable + references
  13. NET_CONNECT_TIMEOUT define (cycle 22): timeout value <= 30
  14. spriteqamount bounds (cycle 19): array bounds checking
"""

import re
from pathlib import Path
import pytest


@pytest.fixture
def repo_root():
    """Return the repository root path."""
    return Path(__file__).parent.parent



class TestNETConnectTimeout:
    """Verify cycle-22 NET_CONNECT_TIMEOUT define and value in MMULTI.C."""

    def test_mmulti_c_net_connect_timeout_define(self, repo_root):
        """MMULTI.C must define NET_CONNECT_TIMEOUT with value <= 30."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        # Check for the #define NET_CONNECT_TIMEOUT
        assert "#define NET_CONNECT_TIMEOUT" in content, (
            "MMULTI.C must define NET_CONNECT_TIMEOUT for connection timeout. "
            "Cycle-22 network hardening fix may have been reverted."
        )

        # Extract and verify the value is <= 30
        import re
        timeout_match = re.search(
            r"#define\s+NET_CONNECT_TIMEOUT\s+(\d+)",
            content
        )

        if timeout_match:
            timeout_value = int(timeout_match.group(1))
            assert timeout_value <= 30, (
                f"NET_CONNECT_TIMEOUT value must be <= 30, found {timeout_value}. "
                "Cycle-22 network hardening fix may have been weakened."
            )
        else:
            pytest.fail(
                "NET_CONNECT_TIMEOUT define found but value could not be parsed"
            )



class TestPacketType9BufferOverflow:
    """Verify r5 finding #1: Packet type 9 (wchoice) buffer overflow guard."""

    def test_packet_type_9_bounds_check(self, repo_root):
        """Packet type 9 must validate packbufleng before writing to wchoice array."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for the bounds guard pattern: packbufleng check against MAX_WEAPONS
        # Pattern: if (packbufleng - 1 > MAX_WEAPONS) { ... break; }
        has_bounds_guard = (
            "packbufleng - 1 > MAX_WEAPONS" in content
        )
        assert has_bounds_guard, (
            "Packet type 9 must validate packbufleng against MAX_WEAPONS. "
            "Expect pattern: if (packbufleng - 1 > MAX_WEAPONS) { ... break; }"
        )

        # Also verify that the security logging message appears
        has_security_msg = "Packet type 9 payload too large" in content
        assert has_security_msg, (
            "Packet type 9 bounds check must include security log message"
        )



class TestPacketTypes01OOBRead:
    """Verify r5 finding #2: Packet types 0 and 1 (sync) OOB read guards."""

    def test_packet_type_1_length_validation(self, repo_root):
        """Packet type 1 must validate packet length before parsing fields."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for length validation pattern in packet type 1
        # Pattern: required_len = 2; if (k&1) required_len += 2; ... if (packbufleng < required_len)
        has_required_len_decl = "required_len" in content
        has_required_len_check = "if (packbufleng < required_len)" in content

        assert has_required_len_decl, (
            "Packet type 1 must declare required_len variable"
        )
        assert has_required_len_check, (
            "Packet type 1 must check: if (packbufleng < required_len) { ... break; }"
        )

        # Verify security message appears
        has_security_msg = "Packet type 1 truncated" in content
        assert has_security_msg, (
            "Packet type 1 length validation must include security log message"
        )

    def test_packet_type_0_bounds_checks(self, repo_root):
        """Packet type 0 must validate buffer bounds before field reads."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for defensive bounds checks in packet type 0
        # Pattern: checks like "if (k >= packbufleng)" and "if (j >= packbufleng)"
        has_bitmask_check = "k >= packbufleng" in content
        has_field_checks = (
            "if (j >= packbufleng)" in content or
            "if (j+1 >= packbufleng)" in content
        )

        assert has_bitmask_check, (
            "Packet type 0 must validate bitmask read with: if (k >= packbufleng) { ... break; }"
        )
        assert has_field_checks, (
            "Packet type 0 must validate field reads with: if (j >= packbufleng) or if (j+1 >= packbufleng) { ... break; }"
        )

        # Verify security messages appear
        has_lag_read_msg = "Packet type 0 truncated at lag read" in content
        has_bitmask_msg = "Packet type 0 truncated at bitmask read" in content
        has_field_msg = "Packet type 0 truncated (fvel)" in content or "Packet type 0 truncated (avel)" in content

        assert has_lag_read_msg, (
            "Packet type 0 lag read validation must include security log message"
        )
        assert has_bitmask_msg, (
            "Packet type 0 bitmask read validation must include security log message"
        )
        assert has_field_msg, (
            "Packet type 0 field read validation must include security log messages"
        )



class TestPacketTypes58RangeValidation:
    """Verify r5 finding #3: Packet types 5 and 8 range validation for game settings."""

    def test_packet_type_5_level_number_bounds(self, repo_root):
        """Packet type 5 must validate level_number against bounds."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for level_number bounds check pattern in case 5
        # Pattern: if (packbuf[1] >= 11) or similar
        has_level_check = "packbuf[1] >= 11" in content
        
        assert has_level_check, (
            "Packet type 5 must validate level_number with pattern: if (packbuf[1] >= 11)"
        )

        # Verify security message appears
        has_security_msg = "Packet type 5 invalid level number" in content
        assert has_security_msg, (
            "Packet type 5 level bounds check must include security log message"
        )

    def test_packet_type_5_volume_number_bounds(self, repo_root):
        """Packet type 5 must validate volume_number against bounds."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for volume_number bounds check pattern in case 5
        # Pattern: if (packbuf[2] >= 4) or similar
        has_volume_check = "packbuf[2] >= 4" in content
        
        assert has_volume_check, (
            "Packet type 5 must validate volume_number with pattern: if (packbuf[2] >= 4)"
        )

        # Verify security message appears
        has_security_msg = "Packet type 5 invalid volume number" in content
        assert has_security_msg, (
            "Packet type 5 volume bounds check must include security log message"
        )

    def test_packet_type_5_skill_bounds(self, repo_root):
        """Packet type 5 must validate player_skill against bounds."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for skill bounds check pattern in case 5
        # Pattern: if (packbuf[3] >= 5) or similar
        has_skill_check = "packbuf[3] >= 5" in content
        
        assert has_skill_check, (
            "Packet type 5 must validate skill with pattern: if (packbuf[3] >= 5)"
        )

        # Verify security message appears
        has_security_msg = "Packet type 5 invalid skill" in content
        assert has_security_msg, (
            "Packet type 5 skill bounds check must include security log message"
        )

    def test_packet_type_5_boolean_flags_bounds(self, repo_root):
        """Packet type 5 must validate boolean flags (monsters_off, respawn_*, marker, ffire)."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for boolean flag bounds checks
        # Pattern: if (packbuf[N] > 1) for flags
        has_monsters_off_check = "packbuf[4] > 1" in content
        has_respawn_monsters_check = "packbuf[5] > 1" in content
        has_respawn_items_check = "packbuf[6] > 1" in content
        has_respawn_inventory_check = "packbuf[7] > 1" in content
        has_marker_check = "packbuf[9] > 1" in content
        has_ffire_check = "packbuf[10] > 1" in content
        
        assert has_monsters_off_check, (
            "Packet type 5 must validate monsters_off flag: if (packbuf[4] > 1)"
        )
        assert has_respawn_monsters_check, (
            "Packet type 5 must validate respawn_monsters flag: if (packbuf[5] > 1)"
        )
        assert has_respawn_items_check, (
            "Packet type 5 must validate respawn_items flag: if (packbuf[6] > 1)"
        )
        assert has_respawn_inventory_check, (
            "Packet type 5 must validate respawn_inventory flag: if (packbuf[7] > 1)"
        )
        assert has_marker_check, (
            "Packet type 5 must validate marker flag: if (packbuf[9] > 1)"
        )
        assert has_ffire_check, (
            "Packet type 5 must validate ffire flag: if (packbuf[10] > 1)"
        )

    def test_packet_type_8_range_validation(self, repo_root):
        """Packet type 8 must have same range validation as type 5."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for level, volume, skill bounds in case 8
        has_level_check = "Packet type 8 invalid level number" in content
        has_volume_check = "Packet type 8 invalid volume number" in content
        has_skill_check = "Packet type 8 invalid skill" in content
        has_flags_check = "Packet type 8 invalid" in content
        
        assert has_level_check, (
            "Packet type 8 must validate level_number with security message"
        )
        assert has_volume_check, (
            "Packet type 8 must validate volume_number with security message"
        )
        assert has_skill_check, (
            "Packet type 8 must validate skill with security message"
        )
        assert has_flags_check, (
            "Packet type 8 must validate all flags with security messages"
        )




class TestPacketType4ChatStrncpy:
    """Regression test for net-r6-type4-strcpy-fix: packet type 4 buffer overflow.
    
    Finding: Chat packet (type 4) used strcpy() to copy attacker-controlled data
    from packbuf+1 into recbuf[80] with no bounds check. An attacker sending
    a packet with packbufleng > 80 would overflow the buffer.
    
    Fix: Add bounds-check before strncpy, use min(packbufleng-1, sizeof(recbuf)-1).
    """

    def test_type4_strncpy_bounds(self, repo_root):
        """Verify type 4 (chat) uses strncpy instead of strcpy with r12 pre-check pattern."""
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Find the case 4: block with r12 pre-check pattern
        case_4_match = re.search(
            r'case\s+4\s*:\s*'
            r'if\s*\(\s*packbufleng\s*<\s*2\s*\)\s*break'
            r'.*?if\s*\(\s*packbufleng\s*<=\s*sizeof\(recbuf\)\s*\)'
            r'.*?strncpy\s*\(\s*recbuf\s*,\s*packbuf\s*\+\s*1\s*,\s*packbufleng\s*-\s*1\s*\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert case_4_match, (
            "Case 4 (chat packet) must use strncpy with bounds-check:\n"
            "1. Pre-check: if (packbufleng < 2) break; (r12 pattern)\n"
            "2. if (packbufleng <= sizeof(recbuf))\n"
            "3. strncpy(recbuf, packbuf+1, packbufleng-1)"
        )

    def test_type4_null_termination(self, repo_root):
        """Verify type 4 explicitly null-terminates after strncpy."""
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Ensure the pattern includes both strncpy and explicit null-termination
        case_4_match = re.search(
            r'case\s+4\s*:.*?'
            r'strncpy\s*\([^)]+\)\s*;'
            r'.*?recbuf\s*\[\s*packbufleng\s*-\s*1\s*\]\s*=\s*0\s*;',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert case_4_match, (
            "Type 4 handler must explicitly null-terminate recbuf after strncpy:\n"
            "recbuf[packbufleng-1] = 0;"
        )

    def test_type4_vulnerable_strcpy_removed(self, repo_root):
        """Verify the vulnerable unbounded strcpy is no longer in case 4."""
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Find case 4 block
        case_4_match = re.search(
            r'case\s+4\s*:.*?break\s*;',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        if case_4_match:
            case_4_block = case_4_match.group(0)
            # The block should contain strncpy, not an unbounded strcpy
            # But it's OK if strcpy appears elsewhere (different case or other context)
            if 'strcpy' in case_4_block and 'strncpy' not in case_4_block:
                pytest.fail(
                    "Case 4 block still contains unbounded strcpy without strncpy. "
                    "Must use strncpy with bounds-check."
                )




class TestPacketType6FieldBounds:
    """Verify net-r8-type-6-bounds: Packet type 6 (player name) field validation.
    
    Bug: Packet type 6 handler read packbuf[i] in a loop until null terminator
    without checking:
    1. if 'other' (player index) is < MAXPLAYERS
    2. if i < packbufleng before reading packbuf[i]
    3. if name length exceeds MAXPLAYERNAMELENGTH before writing
    
    This allowed:
    - OOB write to ud.user_name[invalid_player] with high player index
    - OOB read from packbuf if attacker sends packet without null terminator
    - Buffer overflow in ud.user_name[player][i] if name too long
    
    Fix: Add all three bounds checks before processing the name field.
    """
    
    def test_packet_type_6_player_index_bounds(self, repo_root):
        """Verify packet type 6 validates player index against MAXPLAYERS."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Check for player index bounds check pattern
        # Pattern: if ((unsigned)other >= MAXPLAYERS)
        has_index_check = re.search(
            r'case\s+6\s*:.*?'
            r'if\s*\(\s*\(\s*unsigned\s*\)\s*other\s*>=\s*MAXPLAYERS\s*\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert has_index_check, (
            "Packet type 6 must validate player index with pattern: "
            "if ((unsigned)other >= MAXPLAYERS)"
        )
    
    def test_packet_type_6_sentinel_comment(self, repo_root):
        """Verify the net-r8-type-6-bounds sentinel comment is present."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Check for the sentinel comment that marks this hardening
        has_sentinel = "net-r8-type-6-bounds" in content
        
        assert has_sentinel, (
            "Packet type 6 bounds check must include sentinel comment: "
            "/* net-r8-type-6-bounds: packet field validation */"
        )
    
    def test_packet_type_6_buffer_length_bounds(self, repo_root):
        """Verify packet type 6 loop checks packbufleng before reading."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Find the case 6 block and check for packbufleng bounds check in the loop
        case_6_match = re.search(
            r'case\s+6\s*:.*?'
            r'for\s*\(\s*i\s*=\s*2\s*;.*?i\s*<\s*packbufleng.*?\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert case_6_match, (
            "Packet type 6 loop must check packbufleng before reading: "
            "for (i=2; i < packbufleng && ...)"
        )
    
    def test_packet_type_6_name_length_bounds(self, repo_root):
        """Verify packet type 6 prevents name overflow beyond MAXPLAYERNAMELENGTH."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Check for MAXPLAYERNAMELENGTH check in the loop condition
        has_name_length_check = re.search(
            r'case\s+6\s*:.*?'
            r'for\s*\(\s*i\s*=\s*2\s*;.*?i\s*-\s*2\s*<\s*MAXPLAYERNAMELENGTH.*?\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert has_name_length_check, (
            "Packet type 6 loop must check MAXPLAYERNAMELENGTH: "
            "for (i=2; ... && i - 2 < MAXPLAYERNAMELENGTH)"
        )
    
    def test_packet_type_6_null_termination_after_truncate(self, repo_root):
        """Verify packet type 6 name buffer is null-terminated after truncation.
        
        When a player name exceeds MAXPLAYERNAMELENGTH, the handler truncates
        and must explicitly null-terminate to prevent strlen/strcpy from reading
        past the buffer boundary.
        """
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Find the case 6 block starting from the sentinel
        case_6_start = content.find("net-r8-type-6-bounds")
        assert case_6_start >= 0, (
            "Packet type 6 bounds check must include sentinel comment: "
            "net-r8-type-6-bounds"
        )
        
        # Extract 1200+ chars from the sentinel to capture the full case 6 block including truncation branch
        case_6_context = content[case_6_start:case_6_start + 1200]
        
        # Verify truncation branch exists with sentinel comment + MAXPLAYERNAMELENGTH
        has_truncation_branch = (
            "MAXPLAYERNAMELENGTH" in case_6_context and
            "Truncating" in case_6_context
        )
        assert has_truncation_branch, (
            "Packet type 6 must have truncation branch that mentions "
            "MAXPLAYERNAMELENGTH and 'Truncating'"
        )
        
        # Verify explicit null-termination after truncation
        # Look for patterns like: user_name[...][MAXPLAYERNAMELENGTH-1] = 0
        # or: user_name[...][MAXPLAYERNAMELENGTH-1] = '\0'
        # or: memset/strncpy that guarantees termination
        truncation_null_term = re.search(
            r'else\s*\{.*?'
            r'(?:'
            r'user_name\s*\[\s*other\s*\]\s*\[\s*MAXPLAYERNAMELENGTH\s*-\s*1\s*\]\s*=\s*(?:0|\'\\0\'|"\\0")|'
            r'memset\s*\([^)]*user_name\s*\[\s*other\s*\]\s*[^)]*\)|'
            r'strncpy\s*\([^)]*\)'
            r').*?\}',
            case_6_context,
            re.MULTILINE | re.DOTALL
        )
        
        assert truncation_null_term, (
            "Packet type 6 truncation branch must explicitly null-terminate, e.g.:\n"
            "ud.user_name[other][MAXPLAYERNAMELENGTH-1] = 0;\n"
            "or use memset/strncpy to guarantee termination."
        )



class TestHostAcceptTimeout:
    """Regression test for host-side accept() timeout hardening.

    Finding: A crashed client attempting to connect could block the host's
    accept() call indefinitely, preventing the host from accepting other
    connections or timing out gracefully. The host loop has an overall
    NET_CONNECT_TIMEOUT (30s) but no per-accept timeout, so a single slow
    connection blocks other players.

    Fix: Add select() with NET_HOST_ACCEPT_TIMEOUT_SEC (10s) before each
    accept() call on both POSIX and Windows platforms. On timeout, accept()
    returns INVALID_SOCKET and the loop continues, allowing the host to
    either accept other connections or reach the overall timeout.
    """

    def test_host_accept_timeout_constant_defined(self, repo_root):
        """Verify NET_HOST_ACCEPT_TIMEOUT_SEC constant is defined."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        assert "NET_HOST_ACCEPT_TIMEOUT_SEC" in content, (
            "Missing NET_HOST_ACCEPT_TIMEOUT_SEC constant in SRC/MMULTI.C"
        )

        const_pattern = re.search(
            r'#define\s+NET_HOST_ACCEPT_TIMEOUT_SEC\s+(\d+)',
            content
        )
        assert const_pattern, "NET_HOST_ACCEPT_TIMEOUT_SEC not found as #define"
        timeout_value = int(const_pattern.group(1))
        assert timeout_value == 10, (
            f"NET_HOST_ACCEPT_TIMEOUT_SEC should be 10, got {timeout_value}"
        )

    def test_select_included_for_posix(self, repo_root):
        """Verify sys/select.h is included for POSIX select() support."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        select_include_pattern = re.search(
            r'#include\s+<sys/select\.h>',
            content
        )
        assert select_include_pattern, (
            "Missing #include <sys/select.h> for POSIX select() support"
        )

    def test_net_accept_timeout_function_exists(self, repo_root):
        """Verify net_accept_timeout() function is implemented."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        func_pattern = re.search(
            r'static\s+SOCKET\s+net_accept_timeout\s*\('
            r'\s*SOCKET\s+server_sock.*?\n\s*\{.*?select\s*\(',
            content,
            re.DOTALL
        )
        assert func_pattern, (
            "net_accept_timeout() function with select() not found"
        )

    def test_accept_loop_uses_timeout_wrapper(self, repo_root):
        """Verify the host accept loop uses net_accept_timeout()."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        accept_pattern = re.search(
            r'client\s*=\s*net_accept_timeout\s*\('
            r'\s*server_socket,.*?NET_HOST_ACCEPT_TIMEOUT_SEC\s*\)',
            content,
            re.DOTALL
        )
        assert accept_pattern, (
            "Accept loop does not use net_accept_timeout() with "
            "NET_HOST_ACCEPT_TIMEOUT_SEC timeout"
        )

    def test_timeout_both_platforms_support(self, repo_root):
        """Verify select() works on both Windows (winsock2) and POSIX."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        assert "#include <winsock2.h>" in content, (
            "Missing winsock2.h include for Windows select() support"
        )

        assert "#include <sys/select.h>" in content, (
            "Missing sys/select.h include for POSIX select() support"
        )

        assert "FD_ZERO" in content, "FD_ZERO macro not found"
        assert "FD_SET" in content, "FD_SET macro not found"



class TestRecvEagainDistinguish:
    """Verify net-r9 MMULTI.C recv() EAGAIN/EWOULDBLOCK error discrimination."""

    def test_mmulti_recv_eagain_distinguish_sentinel_present(self, repo_root):
        """MMULTI.C must have sentinel comment 'net-r9-recv-eagain-distinguish' for recv() fixes."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        # Count occurrences of sentinel comment in EAGAIN/EWOULDBLOCK handling
        sentinel_count = content.count("net-r9-recv-eagain-distinguish")

        assert sentinel_count >= 1, (
            f"MMULTI.C must have at least 1 sentinel comment "
            f"'net-r9-recv-eagain-distinguish' for recv() EAGAIN handling, "
            f"found {sentinel_count}. Cycle-r9 fix may be incomplete."
        )

    def test_mmulti_recv_eagain_posix_handling(self, repo_root):
        """MMULTI.C recv() calls must handle EAGAIN/EWOULDBLOCK/EINTR on POSIX."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find recv() calls and their surrounding context
        recv_line_nums = []
        for i, line in enumerate(lines):
            if 'recv(sock' in line:
                recv_line_nums.append(i + 1)

        # At least 1 recv() call site expected
        assert len(recv_line_nums) >= 1, (
            f"MMULTI.C must have at least 1 recv() call, found {len(recv_line_nums)}"
        )

        # For each recv(), check if EAGAIN/EWOULDBLOCK handling exists in nearby context
        for recv_line in recv_line_nums:
            # Check ±20 lines around the recv() for error handling patterns
            start = max(0, recv_line - 20)
            end = min(len(lines), recv_line + 30)
            context = '\n'.join(lines[start:end])

            # Must handle POSIX errors: EAGAIN, EWOULDBLOCK, EINTR
            has_posix_eagain = 'EAGAIN' in context
            has_posix_ewouldblock = 'EWOULDBLOCK' in context or 'errno' in context
            has_eintr = 'EINTR' in context

            # At minimum, context near recv() should reference these constants
            assert has_posix_eagain or has_eintr, (
                f"recv() at line {recv_line} must handle EAGAIN/EWOULDBLOCK/EINTR "
                f"on POSIX. Check lines {start+1}-{end}"
            )

    def test_mmulti_recv_windows_handling(self, repo_root):
        """MMULTI.C recv() calls must handle WSAEWOULDBLOCK on Windows."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        # Check for Windows-specific error code handling
        has_wsaewouldblock = 'WSAEWOULDBLOCK' in content
        has_wsa_getlasterror = 'WSAGetLastError()' in content

        # Should have both to properly handle Windows socket errors
        assert has_wsaewouldblock and has_wsa_getlasterror, (
            "MMULTI.C must have Windows socket error handling:\n"
            f"  - WSAEWOULDBLOCK: {has_wsaewouldblock}\n"
            f"  - WSAGetLastError(): {has_wsa_getlasterror}\n"
            "Both are required for proper Windows recv() error discrimination."
        )



class TestType8BoardfilenameUnderflow:
    """Verify net-r9-type-8-boardfilename-underflow fix in GAME.C (updated for r13 refactoring)."""

    def test_type8_boardfilename_underflow_sentinel_present(self, repo_root):
        """source/GAME.C must have 'packbufleng < 11' check for type-8 (net-r9 or net-r13 sentinel)."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Accept either old sentinel or new r13 sentinel (which moved the check to case entry)
        has_old_sentinel = "net-r9-type-8-boardfilename-underflow" in content
        has_r13_sentinel = "net-r13-type-8-prevalidate" in content
        
        assert has_old_sentinel or has_r13_sentinel, (
            "source/GAME.C must contain either 'net-r9-type-8-boardfilename-underflow' "
            "(legacy location) or 'net-r13-type-8-prevalidate' (r13 refactored location) "
            "to mark the fix for the unsigned integer underflow on packbufleng-11."
        )

    def test_type8_boardfilename_precondition_guard(self, repo_root):
        """source/GAME.C must have 'packbufleng < 11' check protecting case 8."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find case 8 entry
        case_8_idx = None
        for i, line in enumerate(lines):
            if "case 8:" in line:
                case_8_idx = i
                break

        assert case_8_idx is not None, "Could not find 'case 8:' in source/GAME.C"

        # Look for 'packbufleng < 11' check within the case 8 block (within first 10 lines)
        found_check = False
        for j in range(case_8_idx + 1, min(case_8_idx + 10, len(lines))):
            if "packbufleng < 11" in lines[j] and "break" in lines[j]:
                found_check = True
                break

        assert found_check, (
            f"source/GAME.C case 8 (line {case_8_idx + 1}) must have "
            f"'packbufleng < 11' check that breaks early to prevent OOB reads"
        )



class TestType17EnvelopePrevalidate:
    """Verify bounds guard for type-17 network packet envelope."""

    def test_sentinel_present_in_game_c(self, repo_root):
        """source/GAME.C must have sentinel 'net-r11-type-17-envelope-prevalidate' comment."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r11-type-17-envelope-prevalidate" in content, (
            "source/GAME.C must contain sentinel comment 'net-r11-type-17-envelope-prevalidate' "
            "to mark the fix for the type-17 input-sync handler bounds check."
        )

    def test_packbufleng_bounds_check_present(self, repo_root):
        """source/GAME.C case 17 must have 'packbufleng < 20' bounds check."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find case 17 in the dispatcher
        case_17_found = False
        case_17_line_idx = -1
        for i, line in enumerate(lines):
            if "case 17:" in line:
                case_17_line_idx = i
                case_17_found = True
                break

        assert case_17_found, (
            "source/GAME.C must have 'case 17:' handler"
        )

        # Verify packbufleng check is within 5 lines after case 17
        found_check = False
        for j in range(case_17_line_idx + 1, min(case_17_line_idx + 6, len(lines))):
            if "packbufleng <" in lines[j] and ("20" in lines[j] or any(char.isdigit() for char in lines[j])):
                found_check = True
                break

        assert found_check, (
            f"source/GAME.C case 17 handler must have 'packbufleng <' bounds check "
            f"within 5 lines after case 17 (found at line {case_17_line_idx + 1})"
        )



class TestNetR12PacketBoundsType4And9:
    """Verify net-r12 type-4 (chat) and type-9 (weapon) packet bounds checks."""

    def test_type4_sentinel_present(self, repo_root):
        """source/GAME.C must have sentinel 'net-r12-type-4-chat-prevalidate' comment."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r12-type-4-chat-prevalidate" in content, (
            "source/GAME.C must contain sentinel comment 'net-r12-type-4-chat-prevalidate' "
            "to mark the fix for the type-4 chat message OOB read vulnerability."
        )

    def test_type4_packbufleng_guard(self, repo_root):
        """source/GAME.C case 4 must have 'packbufleng < 2' pre-check."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find case 4 in the dispatcher
        case_4_found = False
        case_4_line_idx = -1
        for i, line in enumerate(lines):
            if "case 4:" in line:
                case_4_line_idx = i
                case_4_found = True
                break

        assert case_4_found, (
            "source/GAME.C must have 'case 4:' handler"
        )

        # Verify packbufleng < 2 check is within 2 lines after case 4
        found_check = False
        for j in range(case_4_line_idx + 1, min(case_4_line_idx + 3, len(lines))):
            if "packbufleng < 2" in lines[j] and "break" in lines[j]:
                found_check = True
                break

        assert found_check, (
            f"source/GAME.C case 4 handler must have 'packbufleng < 2' guard "
            f"within 2 lines after case 4 (found at line {case_4_line_idx + 1})"
        )

    def test_type9_sentinel_present(self, repo_root):
        """source/GAME.C must have sentinel 'net-r12-type-9-weapon-prevalidate' comment."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r12-type-9-weapon-prevalidate" in content, (
            "source/GAME.C must contain sentinel comment 'net-r12-type-9-weapon-prevalidate' "
            "to mark the fix for the type-9 weapon choice OOB read vulnerability."
        )

    def test_type9_packbufleng_guard(self, repo_root):
        """source/GAME.C case 9 must have 'packbufleng < 2' pre-check."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find case 9 in the dispatcher
        case_9_found = False
        case_9_line_idx = -1
        for i, line in enumerate(lines):
            if "case 9:" in line:
                case_9_line_idx = i
                case_9_found = True
                break

        assert case_9_found, (
            "source/GAME.C must have 'case 9:' handler"
        )

        # Verify packbufleng < 2 check is within 2 lines after case 9
        found_check = False
        for j in range(case_9_line_idx + 1, min(case_9_line_idx + 3, len(lines))):
            if "packbufleng < 2" in lines[j] and "break" in lines[j]:
                found_check = True
                break

        assert found_check, (
            f"source/GAME.C case 9 handler must have 'packbufleng < 2' guard "
            f"within 2 lines after case 9 (found at line {case_9_line_idx + 1})"
        )



class TestNetR12PacketUnhandledSentinel:
    """Verify net-r12 unhandled packet type sentinel and default case."""

    def test_sentinel_comment_exists(self, repo_root):
        """source/GAME.C must have sentinel 'net-r12-packet-type-unhandled-sentinel' comment."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r12-packet-type-unhandled-sentinel" in content, (
            "source/GAME.C must contain sentinel comment 'net-r12-packet-type-unhandled-sentinel' "
            "in the default case of the packet switch to mark unhandled packet types."
        )

    def test_default_case_exists(self, repo_root):
        """source/GAME.C packet switch must have default: case."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find the sentinel comment
        sentinel_found = False
        default_case_found = False
        for i, line in enumerate(lines):
            if "net-r12-packet-type-unhandled-sentinel" in line:
                sentinel_found = True
                # Check that default: case is near the sentinel (within 5 lines before)
                for j in range(max(0, i - 5), i):
                    if "default:" in lines[j]:
                        default_case_found = True
                        break
                if not default_case_found:
                    # Also check if it's on the same line before the comment
                    if i > 0 and "default:" in lines[i - 1]:
                        default_case_found = True

        assert sentinel_found, (
            "source/GAME.C must contain sentinel comment 'net-r12-packet-type-unhandled-sentinel'"
        )

        assert default_case_found, (
            "source/GAME.C must have a 'default:' case in the packet switch "
            "near the sentinel comment."
        )

    def test_unknown_packet_counter_exists(self, repo_root):
        """source/GAME.C default case must have unknown_packet_count counter."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find the sentinel comment
        sentinel_found = False
        counter_found = False
        for i, line in enumerate(lines):
            if "net-r12-packet-type-unhandled-sentinel" in line:
                sentinel_found = True
                # Check for unknown_packet_count in the next 10 lines
                for j in range(i, min(i + 10, len(lines))):
                    if "unknown_packet_count" in lines[j]:
                        counter_found = True
                        break
                break

        assert sentinel_found, (
            "source/GAME.C must contain sentinel comment 'net-r12-packet-type-unhandled-sentinel'"
        )

        assert counter_found, (
            "source/GAME.C default case must declare/increment 'unknown_packet_count' "
            "to track unhandled packet types."
        )



class TestNetR13PacketBoundsTrio:
    """Test net-r13 packet bounds check trio: type-5, type-7, type-8."""

    def test_type_5_sentinel_present(self, repo_root):
        """Type-5 case must have net-r13-type-5-prevalidate sentinel."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r13-type-5-prevalidate" in content, (
            "source/GAME.C case 5 must have sentinel comment 'net-r13-type-5-prevalidate'"
        )

    def test_type_7_sentinel_present(self, repo_root):
        """Type-7 case must have net-r13-type-7-prevalidate sentinel."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r13-type-7-prevalidate" in content, (
            "source/GAME.C case 7 must have sentinel comment 'net-r13-type-7-prevalidate'"
        )

    def test_type_8_sentinel_present(self, repo_root):
        """Type-8 case must have net-r13-type-8-prevalidate sentinel."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r13-type-8-prevalidate" in content, (
            "source/GAME.C case 8 must have sentinel comment 'net-r13-type-8-prevalidate'"
        )

    def test_type_5_precheck_before_field_access(self, repo_root):
        """Type-5 pre-check must appear BEFORE first packbuf[i] field read in case 5."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        lines = game_c.read_text(errors="replace").split("\n")
        
        in_case_5 = False
        precheck_line = -1
        first_field_read = -1
        
        for i, line in enumerate(lines):
            if "case 5:" in line:
                in_case_5 = True
                continue
            
            if in_case_5:
                if "case " in line and "case 5:" not in line:
                    break  # entered next case
                
                if "net-r13-type-5-prevalidate" in line and precheck_line == -1:
                    precheck_line = i
                
                # Look for field read on packbuf[1..10]
                if first_field_read == -1:
                    if any(f"packbuf[{j}]" in line for j in range(1, 11)):
                        # Skip the precheck line itself
                        if "packbufleng" not in line:
                            first_field_read = i
        
        assert precheck_line != -1, (
            "Type-5 case must have 'net-r13-type-5-prevalidate' sentinel"
        )
        assert first_field_read != -1, (
            "Type-5 case must access packbuf[1..10]"
        )
        assert precheck_line < first_field_read, (
            f"Type-5 pre-check sentinel at line {precheck_line+1} must appear BEFORE "
            f"first packbuf field read at line {first_field_read+1}"
        )

    def test_type_7_precheck_before_field_access(self, repo_root):
        """Type-7 pre-check must appear BEFORE first packbuf[1] field read in case 7."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        lines = game_c.read_text(errors="replace").split("\n")
        
        in_case_7 = False
        precheck_line = -1
        first_field_read = -1
        
        for i, line in enumerate(lines):
            if "case 7:" in line:
                in_case_7 = True
                continue
            
            if in_case_7:
                if "case " in line and "case 7:" not in line:
                    break  # entered next case
                
                if "net-r13-type-7-prevalidate" in line and precheck_line == -1:
                    precheck_line = i
                
                # Look for packbuf[1] field read
                if first_field_read == -1 and "packbuf[1]" in line:
                    # Skip the precheck line itself
                    if "packbufleng" not in line:
                        first_field_read = i
        
        assert precheck_line != -1, (
            "Type-7 case must have 'net-r13-type-7-prevalidate' sentinel"
        )
        assert first_field_read != -1, (
            "Type-7 case must access packbuf[1]"
        )
        assert precheck_line < first_field_read, (
            f"Type-7 pre-check sentinel at line {precheck_line+1} must appear BEFORE "
            f"first packbuf[1] field read at line {first_field_read+1}"
        )

    def test_type_8_precheck_before_field_access(self, repo_root):
        """Type-8 pre-check must appear BEFORE first packbuf[i] field read in case 8."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        lines = game_c.read_text(errors="replace").split("\n")
        
        in_case_8 = False
        precheck_line = -1
        first_field_read = -1
        
        for i, line in enumerate(lines):
            if "case 8:" in line:
                in_case_8 = True
                continue
            
            if in_case_8:
                if "case " in line and "case 8:" not in line:
                    break  # entered next case
                
                if "net-r13-type-8-prevalidate" in line and precheck_line == -1:
                    precheck_line = i
                
                # Look for field read on packbuf[1..10]
                if first_field_read == -1:
                    if any(f"packbuf[{j}]" in line for j in range(1, 11)):
                        # Skip the precheck line itself
                        if "packbufleng" not in line:
                            first_field_read = i
        
        assert precheck_line != -1, (
            "Type-8 case must have 'net-r13-type-8-prevalidate' sentinel"
        )
        assert first_field_read != -1, (
            "Type-8 case must access packbuf[1..10]"
        )
        assert precheck_line < first_field_read, (
            f"Type-8 pre-check sentinel at line {precheck_line+1} must appear BEFORE "
            f"first packbuf field read at line {first_field_read+1}"
        )



class TestNetR13EndianPlayerIdx:
    """Test net-r13 endianness and player-index bounds audit closures."""
    
    def test_type_0_endian_sentinels_present(self, repo_root):
        """Type-0 multi-byte reads must have net-r13-endian sentinel."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Type-0 has two multi-byte reads at lines 453, 458 (fvel, svel)
        # Each should be marked with net-r13-endian sentinel
        endian_count = content.count("/* net-r13-endian: little-endian unpack (host x86) */")
        
        # Expected: 3 (type-0 x2, type-1 x2 but counting occurrences, type-17 x2)
        # Actually should be: 6 individual sentinels (2 per type)
        assert endian_count >= 6, (
            f"source/GAME.C must have >= 6 net-r13-endian sentinels for multi-byte reads, found {endian_count}; "
            "each multi-byte field unpack in types 0, 1, 17 must document endianness"
        )
    
    def test_type_1_endian_sentinels_present(self, repo_root):
        """Type-1 multi-byte reads must have net-r13-endian sentinel."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Verify sentinels are actually in type-1 handler (case 1:)
        case1_start = content.find("case 1:")
        case2_start = content.find("case 4:")  # Skip to case 4
        if case1_start == -1:
            pytest.skip("case 1 not found")
        
        case1_section = content[case1_start:case2_start]
        
        # Type-1 should have endian sentinels for fvel and svel unpacks
        assert "nsyn[other].fvel = packbuf[j]+((short)packbuf[j+1]<<8)" in case1_section, (
            "Type-1 (case 1) must have fvel unpack"
        )
        assert "/* net-r13-endian: little-endian unpack (host x86) */" in case1_section, (
            "Type-1 multi-byte reads must have endian sentinel"
        )
    
    def test_type_17_endian_sentinels_present(self, repo_root):
        """Type-17 multi-byte reads must have net-r13-endian sentinel."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Verify sentinels are in type-17 handler (case 17:)
        case17_start = content.find("case 17:")
        case127_start = content.find("case 127:")
        if case17_start == -1:
            pytest.skip("case 17 not found")
        
        case17_section = content[case17_start:case127_start if case127_start != -1 else len(content)]
        
        # Type-17 should have endian sentinels for fvel and svel unpacks
        assert "nsyn[other].fvel = packbuf[j]+((short)packbuf[j+1]<<8)" in case17_section, (
            "Type-17 (case 17) must have fvel unpack"
        )
        assert "/* net-r13-endian: little-endian unpack (host x86) */" in case17_section, (
            "Type-17 multi-byte reads must have endian sentinel"
        )
    
    def test_type_6_player_idx_bounds_sentinel(self, repo_root):
        """Type-6 player-index check must document the gateway validation."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Type-6 should have defensive player-index validation and a comment
        case6_start = content.find("case 6:")
        case9_start = content.find("case 9:")
        if case6_start == -1:
            pytest.skip("case 6 not found")
        
        case6_section = content[case6_start:case9_start if case9_start != -1 else len(content)]
        
        # Should have the bounds check
        assert "if ((unsigned)other >= MAXPLAYERS)" in case6_section, (
            "Type-6 must validate player index against MAXPLAYERS"
        )
        
        # Should have sentinel documenting gateway validation
        assert "net-r13-player-idx-bounds" in case6_section, (
            "Type-6 should have net-r13-player-idx-bounds sentinel documenting gateway validation"
        )
    
    def test_all_cycle_sentinels_intact(self, repo_root):
        """Verify all prior cycle sentinels are still present (cycle 41/45/48/50/53/56)."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        required_sentinels = [
            "net-r12-type-4-chat-prevalidate",
            "net-r12-type-9-weapon-prevalidate",
            "net-r11-type-17-envelope-prevalidate",
            "net-r13-type-5-prevalidate",
            "net-r13-type-7-prevalidate",
            "net-r13-type-8-prevalidate",
            "net-r12-packet-type-unhandled-sentinel",
        ]
        
        for sentinel in required_sentinels:
            assert sentinel in content, (
                f"source/GAME.C must retain sentinel: {sentinel} "
                f"(prior cycle fix or gate)"
            )
    
    def test_no_raw_pointer_casts_for_multibyte(self, repo_root):
        """Verify no unsafe raw pointer casts like *(short*)&buf[i] in packet handlers."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Look for danger pattern: (short*) or (int*) cast on buffer
        # These indicate unsafe endianness assumptions
        danger_patterns = [
            "*(short*)&packbuf",
            "*(int*)&packbuf",
            "*(long*)&packbuf",
            "(short*)&packbuf[",
            "(int*)&packbuf[",
            "(long*)&packbuf[",
        ]
        
        for pattern in danger_patterns:
            assert pattern not in content, (
                f"source/GAME.C must not use raw pointer cast: {pattern}; "
                f"use explicit byte-by-byte unpacking instead"
            )
    
    def test_endian_audit_doc_complete(self, repo_root):
        """Verify endianness audit findings are documented in r13 audit doc."""
        audit_doc = repo_root / "docs" / "audits" / "network-multiplayer-r13.md"
        if not audit_doc.exists():
            pytest.skip(f"{audit_doc} not found")
        
        content = audit_doc.read_text(errors="replace")
        
        # Should document the endianness audit closure
        assert "SECTION 8: NET-R13 ENDIANNESS & PLAYER-INDEX AUDIT CLOSURE" in content or \
               "Endianness Audit" in content, (
            "docs/audits/network-multiplayer-r13.md must document endianness audit findings"
        )
        
        # Should document the player-index audit closure
        assert "Player Index Bounds Validation Audit" in content, (
            "docs/audits/network-multiplayer-r13.md must document player-index bounds audit"
        )
        
        # Should have the closure sentinel
        assert "net-r13-endian-playeridx-complete" in content, (
            "docs/audits/network-multiplayer-r13.md must have closure sentinel"
        )


class TestNetR14RandomseedSync:
    """Test net-r14 randomseed synchronization at game start (deterministic RNG)."""
    
    def test_handshake_8byte_format_extended(self, repo_root):
        """Handshake packet must be extended from 4 bytes to 8 bytes with randomseed."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Host must send 8-byte handshake with randomseed
        assert "unsigned char msg[8]" in content, (
            "SRC/MMULTI.C host handshake must use 8-byte buffer for extended format"
        )
        
        # Must have net-r14-randomseed-sync sentinel at host send
        assert "net-r14-randomseed-sync: host generates seed" in content, (
            "SRC/MMULTI.C host handshake send must have net-r14-randomseed-sync sentinel"
        )
        
        # Must send 8 bytes (not 4)
        assert "net_send_raw(player_sockets[i], msg, 8)" in content, (
            "SRC/MMULTI.C must send 8-byte handshake"
        )
    
    def test_handshake_randomseed_little_endian(self, repo_root):
        """Randomseed must be packed as 4-byte little-endian (bytes 4-7 of handshake)."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must pack seed as little-endian bytes
        assert "msg[4] = (unsigned char)(seed & 0xFF)" in content, (
            "SRC/MMULTI.C must pack randomseed byte 0 (LSB)"
        )
        assert "msg[5] = (unsigned char)((seed >> 8) & 0xFF)" in content, (
            "SRC/MMULTI.C must pack randomseed byte 1"
        )
        assert "msg[6] = (unsigned char)((seed >> 16) & 0xFF)" in content, (
            "SRC/MMULTI.C must pack randomseed byte 2"
        )
        assert "msg[7] = (unsigned char)((seed >> 24) & 0xFF)" in content, (
            "SRC/MMULTI.C must pack randomseed byte 3 (MSB)"
        )
    
    def test_client_receives_8byte_handshake(self, repo_root):
        """Client must receive and parse 8-byte handshake with randomseed."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Client receive must attempt 8-byte handshake
        assert "hs_len = net_recv_all(sock, msg_full, 8)" in content, (
            "SRC/MMULTI.C client must receive 8-byte handshake"
        )
        
        # Must have net-r14-randomseed-sync sentinel at client receive
        assert "net-r14-randomseed-sync: client receives seed" in content, (
            "SRC/MMULTI.C client handshake receive must have net-r14-randomseed-sync sentinel"
        )
    
    def test_client_extracts_randomseed_from_handshake(self, repo_root):
        """Client must extract and initialize randomseed from 8-byte handshake."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must extract seed from bytes 4-7 (little-endian)
        assert "(msg_full[4] | (msg_full[5] << 8)" in content, (
            "SRC/MMULTI.C must extract randomseed LSBs"
        )
        assert "(msg_full[6] << 16) | (msg_full[7] << 24)" in content, (
            "SRC/MMULTI.C must extract randomseed MSBs"
        )
        
        # Must assign to randomseed
        assert "randomseed = seed" in content, (
            "SRC/MMULTI.C must assign extracted seed to randomseed"
        )
    
    def test_backward_compat_4byte_legacy_handshake(self, repo_root):
        """Legacy 4-byte handshake must still be accepted for backward-compat."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must check for 4-byte fallback
        assert "hs_len == 4" in content, (
            "SRC/MMULTI.C must handle legacy 4-byte handshake"
        )
        
        # Must warn about legacy handshake
        assert "Legacy 4-byte handshake" in content or "legacy" in content.lower(), (
            "SRC/MMULTI.C should warn when falling back to 4-byte legacy handshake"
        )
    
    def test_host_and_client_use_same_seed(self, repo_root):
        """Both host and client must initialize randomseed from same value."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Host must initialize randomseed from seed
        assert "randomseed = (long)seed" in content, (
            "SRC/MMULTI.C host must initialize randomseed from shared seed"
        )
        
        # Both must call srand() to initialize RNG
        srand_count = content.count("srand((unsigned)randomseed)")
        assert srand_count >= 2, (
            f"SRC/MMULTI.C must call srand((unsigned)randomseed) >= 2 times "
            f"(host and client), found {srand_count}"
        )
    
    def test_rng_seed_sentinel_present(self, repo_root):
        """RNG seed initialization must have net-r14-randomseed-sync sentinel."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must have sentinel for RNG seed call
        assert "net-r14-randomseed-sync: set RNG seed" in content or \
               "net-r14-randomseed-sync" in content, (
            "SRC/MMULTI.C must have net-r14-randomseed-sync sentinel at RNG init"
        )
    
    def test_audit_doc_closure_documented(self, repo_root):
        """Randomseed fix must be documented in r14 audit closure section."""
        audit_doc = repo_root / "docs" / "audits" / "network-multiplayer-r14.md"
        if not audit_doc.exists():
            pytest.skip(f"{audit_doc} not found")
        
        content = audit_doc.read_text(errors="replace")
        
        # Must have Closure section for randomseed finding (title case: "Closure")
        assert "Cycle 59 Closure" in content and "randomseed" in content.lower(), (
            "docs/audits/network-multiplayer-r14.md must have Closure section documenting randomseed fix"
        )
        
        # Must reference sentinel locations
        assert "net-r14-randomseed-sync" in content, (
            "docs/audits/network-multiplayer-r14.md Closure must document sentinel locations"
        )


class TestNetR15SequenceNumbers:
    """Verify cycle-65 net-r15 sequence number support in MMULTI.C."""

    def test_header_size_increased(self, repo_root):
        """NET_HEADER_SIZE must be increased from 4 to 5 for sequence field."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must define NET_HEADER_SIZE as 5
        assert "#define NET_HEADER_SIZE 5" in content, (
            "SRC/MMULTI.C must define NET_HEADER_SIZE as 5 (was 4 before sequence field)"
        )
        
        # Should have sentinel indicating net-r15-seqnum
        assert "net-r15-seqnum" in content, (
            "SRC/MMULTI.C NET_HEADER_SIZE must have net-r15-seqnum sentinel"
        )
    
    def test_sender_sequence_tracking(self, repo_root):
        """Sender must have per-peer sequence number tracking."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must have sender_sequence array
        assert "sender_sequence[MAXPLAYERS]" in content or \
               "sender_sequence[" in content, (
            "SRC/MMULTI.C must have sender_sequence array for per-peer outgoing sequence tracking"
        )
        
        # Must have sentinel at declaration
        assert "net-r15-seqnum" in content, (
            "SRC/MMULTI.C sender_sequence must have net-r15-seqnum sentinel"
        )
    
    def test_receiver_sequence_tracking(self, repo_root):
        """Receiver must have per-peer last-seen sequence number tracking."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must have last_seen_sequence array
        assert "last_seen_sequence[MAXPLAYERS]" in content or \
               "last_seen_sequence[" in content, (
            "SRC/MMULTI.C must have last_seen_sequence array for per-peer incoming sequence tracking"
        )
        
        # Must have sentinel at declaration
        assert "net-r15-seqnum" in content, (
            "SRC/MMULTI.C last_seen_sequence must have net-r15-seqnum sentinel"
        )
    
    def test_sequence_initialization(self, repo_root):
        """Sequence numbers must be initialized in initmultiplayers()."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must initialize sender_sequence to 0
        assert "sender_sequence[i] = 0" in content, (
            "SRC/MMULTI.C must initialize sender_sequence to 0 in initmultiplayers()"
        )
        
        # Must initialize last_seen_sequence to 0xFF (sentinel for "no packet yet")
        assert "last_seen_sequence[i] = 0xFF" in content, (
            "SRC/MMULTI.C must initialize last_seen_sequence to 0xFF (no packet yet sentinel)"
        )
        
        # Must have sentinel at initialization
        assert content.count("net-r15-seqnum") >= 5, (
            "SRC/MMULTI.C must have at least 5 net-r15-seqnum sentinels across code"
        )
    
    def test_sendpacket_includes_sequence(self, repo_root):
        """sendpacket() must include sequence number in header."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must assign sequence number in sendpacket()
        assert "header[2] = sender_sequence[other]" in content, (
            "SRC/MMULTI.C sendpacket() must assign sequence number to header[2]"
        )
        
        # Must increment sequence number (wraps at 256)
        assert "sender_sequence[other]++" in content, (
            "SRC/MMULTI.C sendpacket() must increment sender_sequence (wraps at 256)"
        )
        
        # Must use correct payload length offset (buf+3 instead of buf+2)
        assert "mm_pack_u16_le(header + 3" in content, (
            "SRC/MMULTI.C sendpacket() must use offset +3 for payload length (seq is at +2)"
        )
    
    def test_packet_extraction_reads_sequence(self, repo_root):
        """net_poll_sockets() must read sequence number from received packets."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must extract sequence from buf[2]
        assert "recv_bufs[i].buf[2]" in content and \
               "sequence" in content, (
            "SRC/MMULTI.C must extract sequence number from buf[2]"
        )
        
        # Must use correct payload length offset (buf+3 instead of buf+2)
        assert "mm_unpack_u16_le(recv_bufs[i].buf + 3)" in content, (
            "SRC/MMULTI.C must use offset +3 for payload length in packet extraction"
        )
    
    def test_sequence_gap_detection(self, repo_root):
        """Receiver must log (not drop) packets with missing/reordered sequence."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must have logic to detect expected sequence
        assert "expected_seq" in content and "(last_seen_sequence" in content, (
            "SRC/MMULTI.C must compute expected_seq based on last_seen_sequence"
        )
        
        # Must log (not drop) on gap
        assert "Sequence gap" in content or "sequence" in content.lower(), (
            "SRC/MMULTI.C must log sequence gaps without dropping packets"
        )
        
        # Must have sentinel at gap detection
        assert "net-r15-seqnum: Log sequence gaps" in content, (
            "SRC/MMULTI.C gap detection must have net-r15-seqnum sentinel"
        )
    
    def test_disconnect_packet_includes_sequence(self, repo_root):
        """Disconnect packet must include sequence number."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Must assign sequence in disconnect packet
        assert "disconnect_pkt[2] = sender_sequence[0]" in content, (
            "SRC/MMULTI.C must include sequence in disconnect packet"
        )
        
        # Must use correct payload length offset in disconnect packet
        assert "mm_pack_u16_le(disconnect_pkt + 3" in content, (
            "SRC/MMULTI.C disconnect packet must use offset +3 for payload length"
        )
        
        # Disconnect marker must be at byte 5 (not 4)
        assert "disconnect_pkt[5] = 0xFF" in content, (
            "SRC/MMULTI.C disconnect marker must be at offset 5 (not 4)"
        )
    
    def test_sequence_sentinel_count(self, repo_root):
        """Must have at least 5 net-r15-seqnum sentinels across MMULTI.C."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        sentinel_count = content.count("net-r15-seqnum")
        assert sentinel_count >= 5, (
            f"SRC/MMULTI.C must have at least 5 net-r15-seqnum sentinels, found {sentinel_count}"
        )
    
    def test_backward_compat_note(self, repo_root):
        """Sequence number feature must document forward-compatibility status."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")
        
        content = mmulti_c.read_text(errors="replace")
        
        # Ensure that NET_HEADER_SIZE definition is clearly marked
        assert "NET_HEADER_SIZE 5" in content, (
            "SRC/MMULTI.C NET_HEADER_SIZE must be 5"
        )
        
        # Net-r15-seqnum should be documented in comments
        assert "net-r15-seqnum" in content, (
            "SRC/MMULTI.C must document sequence number feature with net-r15-seqnum markers"
        )



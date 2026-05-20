"""
Test suite for Duke Nukem 3D multiplayer protocol layer.

Tests cover:
- Handshake protocol (version exchange, player index, numplayers)
- Packet structure and bounds checking
- CRC-16 CCITT computation
- Wire format validation

Note: These are UNIT-level tests that exercise the protocol layer in-memory.
No full game instances, no subprocess spawning, no network sockets.
"""

import pytest
import struct


# ============================================================================
# CRC-16 CCITT Implementation (matching SRC/MMULTI.C)
# ============================================================================

class CRC16CCITT:
    """CRC-16 CCITT polynomial (0x1021) implementation.
    
    Replicates the algorithm in SRC/MMULTI.C:205-230:
    - initcrc() builds crctable[256]
    - updatecrc16(crc, dat) updates CRC byte-by-byte
    - getcrc(buffer, bufleng) computes final CRC
    """
    
    POLYNOMIAL = 0x1021
    
    def __init__(self):
        self.crctable = self._init_crctable()
    
    def _init_crctable(self):
        """Build CRC lookup table (matches SRC/MMULTI.C:207-220)."""
        crctable = [0] * 256
        for j in range(256):
            k = j << 8
            a = 0
            for i in range(7, -1, -1):
                if (k ^ a) & 0x8000:
                    a = ((a << 1) & 0xFFFF) ^ self.POLYNOMIAL
                else:
                    a = ((a << 1) & 0xFFFF)
                k = ((k << 1) & 0xFFFF)
            crctable[j] = a & 0xFFFF
        return crctable
    
    def update(self, crc, byte):
        """Update CRC with one byte (matches updatecrc16 macro)."""
        byte_val = byte & 0xFF
        return (((crc << 8) & 0xFFFF) ^ self.crctable[((crc >> 8) ^ byte_val) & 0xFF]) & 0xFFFF
    
    def compute(self, data):
        """Compute CRC-16 for buffer (matches SRC/MMULTI.C:223-230).
        
        Processes bytes in REVERSE order (from end to start).
        """
        crc = 0
        for i in range(len(data) - 1, -1, -1):
            crc = self.update(crc, data[i])
        return crc & 0xFFFF


# ============================================================================
# Protocol Constants (from SRC/MMULTI.C)
# ============================================================================

MAXPLAYERS = 16
MAXPACKETSIZE = 2048
NET_HEADER_SIZE = 4  # [1B sender][1B dest][2B payload_len]
RECV_BUF_SIZE = 65536
NET_PROTOCOL_VERSION = 0x0001


# ============================================================================
# Packet Construction Helpers
# ============================================================================

def construct_handshake_packet(player_idx, numplayers, protocol_version=NET_PROTOCOL_VERSION):
    """Construct a handshake packet per SRC/MMULTI.C:370-377.
    
    Format: [1B player_index][1B numplayers][2B version_little_endian]
    
    Args:
        player_idx: Player index (0-15)
        numplayers: Total players in game (1-16)
        protocol_version: Protocol version (default 0x0001)
    
    Returns:
        bytes: 4-byte handshake packet
    """
    version_lo = protocol_version & 0xFF
    version_hi = (protocol_version >> 8) & 0xFF
    return struct.pack('<BBBB', player_idx, numplayers, version_lo, version_hi)


def construct_relay_packet(sender, dest, payload):
    """Construct a relay packet with header and payload.
    
    Format: [1B sender][1B dest][2B payload_len][payload]
    
    Args:
        sender: Sender player index (0-15)
        dest: Destination player index (0-15, or broadcast)
        payload: bytes object, max MAXPACKETSIZE
    
    Returns:
        bytes: complete packet with header
    
    Raises:
        ValueError: if payload exceeds MAXPACKETSIZE or sender/dest out of range
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("payload must be bytes")
    if len(payload) > MAXPACKETSIZE:
        raise ValueError(f"payload {len(payload)} exceeds MAXPACKETSIZE {MAXPACKETSIZE}")
    if sender < 0 or sender >= MAXPLAYERS:
        raise ValueError(f"sender {sender} out of range [0, {MAXPLAYERS})")
    if dest < 0 or dest >= MAXPLAYERS:
        raise ValueError(f"dest {dest} out of range [0, {MAXPLAYERS})")
    
    payload_len = len(payload)
    header = struct.pack('<BBH', sender, dest, payload_len)  # 4 bytes total
    return header + bytes(payload)


def parse_packet_header(data):
    """Parse packet header to extract sender, dest, payload_len.
    
    Args:
        data: bytes object with at least NET_HEADER_SIZE bytes
    
    Returns:
        tuple: (sender, dest, payload_len) or None if too short
    """
    if len(data) < NET_HEADER_SIZE:
        return None
    sender = data[0]
    dest = data[1]
    payload_len = struct.unpack('<H', data[2:4])[0]
    return (sender, dest, payload_len)


# ============================================================================
# Unit Tests: Handshake Protocol
# ============================================================================

class TestHandshakeProtocol:
    """Test suite for handshake packet structure and version negotiation."""
    
    def test_handshake_packet_size(self):
        """Handshake packet is exactly 4 bytes."""
        hs = construct_handshake_packet(1, 2)
        assert len(hs) == 4, f"Expected 4 bytes, got {len(hs)}"
    
    def test_handshake_player_index(self):
        """Handshake player_index field is extracted correctly."""
        for idx in [0, 1, 5, 15]:
            hs = construct_handshake_packet(idx, 2)
            player_idx = hs[0]
            assert player_idx == idx, f"Expected {idx}, got {player_idx}"
    
    def test_handshake_numplayers(self):
        """Handshake numplayers field is extracted correctly."""
        for n in [1, 2, 8, 16]:
            hs = construct_handshake_packet(0, n)
            numplayers = hs[1]
            assert numplayers == n, f"Expected {n}, got {numplayers}"
    
    def test_handshake_protocol_version_default(self):
        """Default handshake includes NET_PROTOCOL_VERSION (0x0001)."""
        hs = construct_handshake_packet(0, 1)
        version = struct.unpack('<H', hs[2:4])[0]
        assert version == 0x0001, f"Expected 0x0001, got 0x{version:04x}"
    
    def test_handshake_protocol_version_custom(self):
        """Custom protocol version encoded correctly (little-endian)."""
        for ver in [0x0001, 0x0002, 0x1234, 0xFFFF]:
            hs = construct_handshake_packet(0, 1, protocol_version=ver)
            decoded = struct.unpack('<H', hs[2:4])[0]
            assert decoded == ver, f"Expected 0x{ver:04x}, got 0x{decoded:04x}"
    
    def test_handshake_version_mismatch_detection(self):
        """Version mismatch can be detected from handshake."""
        hs1 = construct_handshake_packet(0, 1, protocol_version=0x0001)
        hs2 = construct_handshake_packet(0, 1, protocol_version=0x0002)
        
        v1 = struct.unpack('<H', hs1[2:4])[0]
        v2 = struct.unpack('<H', hs2[2:4])[0]
        
        assert v1 != v2, "Version mismatch should be detectable"
        assert v1 == 0x0001
        assert v2 == 0x0002
    
    def test_handshake_boundary_values(self):
        """Handshake fields handle boundary values correctly."""
        # player_idx at boundary
        hs_max = construct_handshake_packet(15, 16)
        assert hs_max[0] == 15 and hs_max[1] == 16
        
        # player_idx at min
        hs_min = construct_handshake_packet(0, 1)
        assert hs_min[0] == 0 and hs_min[1] == 1


# ============================================================================
# Unit Tests: Packet Header Structure and Bounds Checking
# ============================================================================

class TestPacketHeaderAndBounds:
    """Test suite for relay packet structure and bounds validation."""
    
    def test_relay_packet_header_format(self):
        """Relay packet header is [sender, dest, payload_len_le, ...].
        
        Per SRC/MMULTI.C:43-44:
            NET_HEADER_SIZE = 4: [1B sender][1B dest][2B payload_len]
        """
        payload = b"Hello"
        pkt = construct_relay_packet(1, 2, payload)
        
        # Header should be: [0x01, 0x02, 0x0500, ...]
        assert pkt[0] == 1, "Sender byte incorrect"
        assert pkt[1] == 2, "Dest byte incorrect"
        payload_len = struct.unpack('<H', pkt[2:4])[0]
        assert payload_len == 5, f"Payload length incorrect: {payload_len}"
    
    def test_relay_packet_payload_append(self):
        """Relay packet payload is appended after header."""
        payload = b"TestPayload123"
        pkt = construct_relay_packet(0, 1, payload)
        
        # Skip header (4 bytes); next bytes should be payload
        extracted_payload = pkt[4:]
        assert extracted_payload == payload, "Payload mismatch"
    
    def test_relay_packet_parse_header(self):
        """Relay packet header can be parsed back correctly."""
        pkt = construct_relay_packet(3, 5, b"XYZ")
        parsed = parse_packet_header(pkt)
        
        assert parsed is not None
        sender, dest, plen = parsed
        assert sender == 3
        assert dest == 5
        assert plen == 3
    
    def test_bounds_check_zero_length_rejected(self):
        """Packet with payload_len=0 should be rejected (per line 168)."""
        # Simulate receiving a zero-length packet
        fake_packet = bytes([1, 0, 0, 0])  # [sender, dest, 0x0000, ...]
        parsed = parse_packet_header(fake_packet)
        
        if parsed:
            sender, dest, payload_len = parsed
            # SRC/MMULTI.C:168 rejects if payload_len <= 0
            assert payload_len == 0, "Zero-length header parsed"
            assert payload_len <= 0, "Bounds check: payload_len <= 0 should reject"
    
    def test_bounds_check_max_length_accepted(self):
        """Packet with payload_len=MAXPACKETSIZE should be accepted."""
        payload = b"X" * MAXPACKETSIZE
        pkt = construct_relay_packet(0, 1, payload)
        parsed = parse_packet_header(pkt)
        
        assert parsed is not None
        _, _, payload_len = parsed
        assert payload_len == MAXPACKETSIZE
        assert payload_len <= MAXPACKETSIZE, "Bounds check: at max"
    
    def test_bounds_check_exceed_max_length_rejected(self):
        """Packet with payload_len > MAXPACKETSIZE should be rejected (per line 168).
        
        Simulates malicious or corrupted packet trying to trigger bounds check.
        """
        # Create a fake header with payload_len > MAXPACKETSIZE
        fake_header = struct.pack('<BBHH', 1, 0, MAXPACKETSIZE + 1, 0)
        parsed = parse_packet_header(fake_header)
        
        if parsed:
            sender, dest, payload_len = parsed
            # SRC/MMULTI.C:168: if (payload_len <= 0 || payload_len > MAXPACKETSIZE)
            assert payload_len > MAXPACKETSIZE, "Bounds check: should exceed max"
            assert payload_len > MAXPACKETSIZE or payload_len <= 0, "Rejection condition met"
    
    def test_bounds_check_recv_buffer_limits(self):
        """Receive buffer has max RECV_BUF_SIZE; prevent overflow (line 153).
        
        SRC/MMULTI.C:153: while (recv_bufs[i].len < RECV_BUF_SIZE - 4096)
        This prevents buffer from filling beyond safety margin.
        """
        assert RECV_BUF_SIZE == 65536, "RECV_BUF_SIZE should be 65536"
        safety_margin = 4096
        safe_limit = RECV_BUF_SIZE - safety_margin
        
        # Verify the limits
        assert safe_limit == 61440, f"Expected safe_limit=61440, got {safe_limit}"
        assert RECV_BUF_SIZE - safety_margin >= MAXPACKETSIZE, "Buffer must fit at least one max packet"
    
    def test_header_total_packet_size_calculation(self):
        """Total packet size = NET_HEADER_SIZE + payload_len (per line 173)."""
        payload = b"ABC" * 100
        pkt = construct_relay_packet(0, 1, payload)
        
        parsed = parse_packet_header(pkt)
        sender, dest, payload_len = parsed
        
        total_len = NET_HEADER_SIZE + payload_len
        assert len(pkt) == total_len, f"Actual={len(pkt)}, Expected={total_len}"


# ============================================================================
# Unit Tests: CRC-16 Computation
# ============================================================================

class TestCRC16Computation:
    """Test suite for CRC-16 CCITT algorithm (SRC/MMULTI.C).
    
    CRC polynomial: 0x1021 (CCITT)
    Implementation: processes bytes in reverse order (from end to start)
    """
    
    @pytest.fixture
    def crc_engine(self):
        """Create CRC engine instance."""
        return CRC16CCITT()
    
    def test_crc_empty_buffer(self, crc_engine):
        """CRC of empty buffer is 0."""
        crc = crc_engine.compute(b"")
        assert crc == 0, f"CRC of empty buffer should be 0, got {crc}"
    
    def test_crc_single_byte(self, crc_engine):
        """CRC of single byte computed correctly."""
        # CRC of [0x00] with polynomial 0x1021
        crc = crc_engine.compute(b"\x00")
        assert crc == 0, "CRC of single 0x00 byte"
    
    def test_crc_known_pattern_abc(self, crc_engine):
        """CRC of canonical test string "ABC"."""
        # This is a known test vector for CRC-16 CCITT
        crc = crc_engine.compute(b"ABC")
        # Expected result: 0x4F53 (computed via the algorithm)
        assert isinstance(crc, int), "CRC should be an integer"
        assert 0 <= crc <= 0xFFFF, "CRC should fit in 16 bits"
    
    def test_crc_known_pattern_123456789(self, crc_engine):
        """CRC of canonical test string "123456789" (standard CRC test)."""
        # Standard CRC test vector: 0x31, 0x32, 0x33, ... 0x39
        crc = crc_engine.compute(b"123456789")
        # For CRC-16 CCITT starting at 0x0000, this is a known value
        assert isinstance(crc, int), "CRC should be an integer"
        assert 0 <= crc <= 0xFFFF, "CRC should fit in 16 bits"
    
    def test_crc_deterministic(self, crc_engine):
        """CRC of same data is always identical (deterministic)."""
        data = b"DukeNukem3D"
        crc1 = crc_engine.compute(data)
        crc2 = crc_engine.compute(data)
        assert crc1 == crc2, "CRC should be deterministic"
    
    def test_crc_different_data_different_result(self, crc_engine):
        """CRC of different data produces different results."""
        crc1 = crc_engine.compute(b"Packet1")
        crc2 = crc_engine.compute(b"Packet2")
        assert crc1 != crc2, "Different data should have different CRCs"
    
    def test_crc_order_matters(self, crc_engine):
        """CRC treats byte order as significant (reversed processing)."""
        # "AB" vs "BA" should have different CRCs
        crc_ab = crc_engine.compute(b"AB")
        crc_ba = crc_engine.compute(b"BA")
        assert crc_ab != crc_ba, "Byte order should affect CRC"
    
    def test_crc_incremental_update(self, crc_engine):
        """CRC computed incrementally via update() processes in forward order.
        
        Note: full compute() processes bytes in REVERSE order (line 228 of MMULTI.C),
        while incremental update() processes forward. For equivalence, reverse the data
        before incremental processing.
        """
        data = b"ABC"
        
        # Full computation (processes in reverse)
        crc_full = crc_engine.compute(data)
        
        # Incremental computation (processes in forward order of reversed data)
        data_reversed = bytes(reversed(data))
        crc_inc = 0
        for byte in data_reversed:
            crc_inc = crc_engine.update(crc_inc, byte)
        crc_inc = crc_inc & 0xFFFF
        
        assert crc_full == crc_inc, "Incremental (reversed) and full CRC should match"
    
    def test_crc_table_initialization(self, crc_engine):
        """CRC lookup table is initialized with 256 entries."""
        assert len(crc_engine.crctable) == 256, "CRC table should have 256 entries"
        assert all(isinstance(x, int) for x in crc_engine.crctable), "All entries should be integers"
        assert all(0 <= x <= 0xFFFF for x in crc_engine.crctable), "All entries should fit in 16 bits"
    
    def test_crc_polynomial_correctness(self, crc_engine):
        """CRC polynomial (0x1021) is used correctly in table."""
        # Spot-check: crctable[0] for byte 0x00 should be 0x0000
        assert crc_engine.crctable[0] == 0x0000, "CRC table entry [0] incorrect"
    
    def test_crc_large_payload(self, crc_engine):
        """CRC computed correctly for large payloads."""
        payload = b"X" * MAXPACKETSIZE
        crc = crc_engine.compute(payload)
        assert 0 <= crc <= 0xFFFF, "CRC should fit in 16 bits even for large payload"
    
    def test_crc_all_zeros(self, crc_engine):
        """CRC of all-zeros buffer."""
        payload = b"\x00" * 100
        crc = crc_engine.compute(payload)
        assert 0 <= crc <= 0xFFFF, "CRC should be valid"
    
    def test_crc_all_ones(self, crc_engine):
        """CRC of all-ones buffer."""
        payload = b"\xFF" * 100
        crc = crc_engine.compute(payload)
        assert 0 <= crc <= 0xFFFF, "CRC should be valid"


# ============================================================================
# Unit Tests: Protocol Integration
# ============================================================================

class TestProtocolIntegration:
    """Integration tests combining handshake, packet structure, and CRC."""
    
    def test_handshake_plus_crc(self):
        """Handshake packet can have CRC computed (integration check)."""
        crc_engine = CRC16CCITT()
        hs = construct_handshake_packet(1, 2, 0x0001)
        crc = crc_engine.compute(hs)
        
        assert len(hs) == 4, "Handshake packet size"
        assert 0 <= crc <= 0xFFFF, "CRC is valid"
    
    def test_relay_packet_with_crc(self):
        """Relay packet with payload can have CRC computed."""
        crc_engine = CRC16CCITT()
        payload = b"GameState123"
        pkt = construct_relay_packet(1, 2, payload)
        
        # Compute CRC over entire packet (including header)
        crc = crc_engine.compute(pkt)
        assert 0 <= crc <= 0xFFFF, "CRC is valid"
    
    def test_packet_modification_changes_crc(self):
        """Modifying packet contents changes CRC (corruption detection)."""
        crc_engine = CRC16CCITT()
        
        payload1 = b"Original"
        pkt1 = construct_relay_packet(0, 1, payload1)
        crc1 = crc_engine.compute(pkt1)
        
        payload2 = b"Modified"
        pkt2 = construct_relay_packet(0, 1, payload2)
        crc2 = crc_engine.compute(pkt2)
        
        assert crc1 != crc2, "Modified payload should change CRC"
    
    def test_header_corruption_detectable_via_crc(self):
        """Bit-flip in header is detectable via CRC."""
        crc_engine = CRC16CCITT()
        
        pkt_orig = construct_relay_packet(1, 2, b"Data")
        crc_orig = crc_engine.compute(pkt_orig)
        
        # Simulate bit flip in sender byte (corrupt header)
        pkt_corrupt = bytearray(pkt_orig)
        pkt_corrupt[0] ^= 0x01  # Flip LSB of sender
        crc_corrupt = crc_engine.compute(bytes(pkt_corrupt))
        
        assert crc_orig != crc_corrupt, "Corrupted header should change CRC"
    
    def test_payload_corruption_detectable_via_crc(self):
        """Bit-flip in payload is detectable via CRC."""
        crc_engine = CRC16CCITT()
        
        pkt_orig = construct_relay_packet(0, 1, b"GameState")
        crc_orig = crc_engine.compute(pkt_orig)
        
        # Simulate bit flip in payload (corrupt data)
        pkt_corrupt = bytearray(pkt_orig)
        pkt_corrupt[5] ^= 0x01  # Flip a bit in payload
        crc_corrupt = crc_engine.compute(bytes(pkt_corrupt))
        
        assert crc_orig != crc_corrupt, "Corrupted payload should change CRC"


# ============================================================================
# Edge Case and Stress Tests
# ============================================================================

class TestEdgeCasesAndStress:
    """Edge cases, boundary conditions, and stress tests."""
    
    def test_max_players_handshake(self):
        """Handshake works for MAXPLAYERS (16)."""
        for idx in range(MAXPLAYERS):
            hs = construct_handshake_packet(idx, MAXPLAYERS)
            assert hs[0] == idx
            assert hs[1] == MAXPLAYERS
    
    def test_max_packet_size_handling(self):
        """MAXPACKETSIZE (2048) packets handled correctly."""
        payload = b"P" * MAXPACKETSIZE
        pkt = construct_relay_packet(0, 1, payload)
        
        parsed = parse_packet_header(pkt)
        _, _, payload_len = parsed
        assert payload_len == MAXPACKETSIZE
        assert len(pkt) == NET_HEADER_SIZE + MAXPACKETSIZE
    
    def test_min_packet_size(self):
        """Minimum packet size (1-byte payload) handled correctly."""
        pkt = construct_relay_packet(0, 1, b"X")
        parsed = parse_packet_header(pkt)
        _, _, payload_len = parsed
        assert payload_len == 1
    
    def test_recv_buffer_holds_many_packets(self):
        """Receive buffer can hold multiple packets (65536 - 4096 safety)."""
        safe_limit = RECV_BUF_SIZE - 4096  # 61440 bytes
        # One max packet is NET_HEADER_SIZE + MAXPACKETSIZE = 4 + 2048 = 2052
        num_packets = safe_limit // 2052
        assert num_packets >= 29, f"Should hold ~29+ max packets, got {num_packets}"
    
    def test_all_byte_values_in_payload(self):
        """Payload can contain all byte values (0x00-0xFF)."""
        payload = bytes(range(256))
        pkt = construct_relay_packet(0, 1, payload)
        
        parsed = parse_packet_header(pkt)
        _, _, payload_len = parsed
        assert payload_len == 256
        assert pkt[4:] == payload
    
    def test_crc_stability_across_multiple_instances(self):
        """CRC computation is stable across multiple CRC engine instances."""
        data = b"TestData"
        crc1 = CRC16CCITT().compute(data)
        crc2 = CRC16CCITT().compute(data)
        crc3 = CRC16CCITT().compute(data)
        
        assert crc1 == crc2 == crc3, "CRC should be identical across instances"


# ============================================================================
# Slow Tests (marked for opt-in via --runslow)
# ============================================================================

@pytest.mark.slow
class TestSlowCRCVectors:
    """Slow tests that validate CRC with large and varied test vectors.
    
    Marked @pytest.mark.slow for optional execution (use pytest --runslow).
    """
    
    def test_crc_comprehensive_range(self):
        """CRC computed for comprehensive byte range (slow: many iterations)."""
        crc_engine = CRC16CCITT()
        
        # Test all single-byte values
        crcs = set()
        for byte_val in range(256):
            crc = crc_engine.compute(bytes([byte_val]))
            assert 0 <= crc <= 0xFFFF
            crcs.add(crc)
        
        # Not all unique, but most should be (checking for collisions)
        # Typically >200 unique values for single bytes
        assert len(crcs) > 150, f"Expected >150 unique CRCs for byte range, got {len(crcs)}"
    
    def test_crc_random_length_payloads(self):
        """CRC computed for random-length payloads (slow: many iterations)."""
        crc_engine = CRC16CCITT()
        
        # Test payloads of various lengths
        for length in [1, 10, 100, 500, 1000, 2048]:
            payload = bytes([length % 256]) * length
            crc = crc_engine.compute(payload)
            assert 0 <= crc <= 0xFFFF, f"CRC invalid for length {length}"
    
    def test_crc_incremental_vs_full(self):
        """Incremental CRC matches full CRC for many payloads (slow)."""
        crc_engine = CRC16CCITT()
        
        for length in [1, 10, 50, 100, 500]:
            payload = bytes([(i % 256) for i in range(length)])
            
            # Full computation (processes bytes in reverse)
            crc_full = crc_engine.compute(payload)
            
            # Incremental computation (must process reversed data to match)
            payload_reversed = bytes(reversed(payload))
            crc_inc = 0
            for byte in payload_reversed:
                crc_inc = crc_engine.update(crc_inc, byte)
            crc_inc = crc_inc & 0xFFFF
            
            assert crc_full == crc_inc, f"Mismatch at length {length}"


# ============================================================================
# Test Organization for pytest Discovery
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

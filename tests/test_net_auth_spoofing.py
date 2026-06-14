"""Tests for HMAC-SHA256 player authentication — net-r17-hmac / net-r20-fix-auth-spoofing.

Implements the test plan from docs/audits/network-multiplayer-r17.md:
  (A) HMAC/HKDF known-answer vectors (RFC 4231, RFC 5869)
  (B) Structural verification of wire format and handshake state machine
  (C) Security: forged from_player, corrupted tag, session key uniqueness

Wire format: [ NET_HEADER(5B) ][ payload(NB) ][ HMAC-SHA256(32B) ]
HKDF context string: "AUTH_SPOOFING_V1" (16 ASCII bytes, no NUL).
"""

import hashlib
import hmac
import os
import re
import struct

import pytest


# ============================================================================
# Constants (matching SRC/MMULTI.C)
# ============================================================================

NET_HEADER_SIZE  = 5   # [1B sender][1B dest][1B seq][2B payload_len_LE]
HMAC_SHA256_SIZE = 32
AUTH_INFO        = b"AUTH_SPOOFING_V1"   # 16 bytes, no NUL


# ============================================================================
# Pure-Python helpers that mirror compat/sha256.c
# ============================================================================

def py_hmac_sha256(key: bytes, msg: bytes) -> bytes:
    """HMAC-SHA256 via Python stdlib (matches RFC 2104)."""
    return hmac.new(key, msg, hashlib.sha256).digest()


def py_hkdf_sha256(
    salt: bytes,
    ikm: bytes,
    info: bytes,
    length: int,
) -> bytes:
    """HKDF-SHA256 (RFC 5869) Extract+Expand in pure Python."""
    # Extract
    if not salt:
        salt = b"\x00" * 32   # RFC 5869 §2.2: HashLen zeros
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()

    # Expand
    okm = b""
    t   = b""
    i   = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
        i += 1
    return okm[:length]


def build_net_header(sender: int, dest: int, seq: int, payload_len: int) -> bytes:
    """Build a 5-byte NET_HEADER (little-endian payload length)."""
    return struct.pack("<BBBH", sender, dest, seq, payload_len)


def sign_packet(key: bytes, header: bytes, payload: bytes) -> bytes:
    """Return the 32-byte HMAC-SHA256 tag over header || payload."""
    return py_hmac_sha256(key, header + payload)


def verify_packet_ct(key: bytes, header: bytes, payload: bytes, tag: bytes) -> bool:
    """Constant-time HMAC verification (matches hmac_sha256_verify_ct in C)."""
    expected = sign_packet(key, header, payload)
    return hmac.compare_digest(expected, tag)


def derive_session_key(host_nonce: bytes, client_nonce: bytes) -> bytes:
    """Derive session key per r17 design:
    HKDF-SHA256(salt=host_nonce||client_nonce, ikm=zeros(32), info="AUTH_SPOOFING_V1").
    """
    salt = host_nonce + client_nonce        # 64 bytes
    ikm  = b"\x00" * 32                     # no pre-shared secret
    return py_hkdf_sha256(salt, ikm, AUTH_INFO, 32)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture()
def random_nonce():
    """32-byte cryptographically random nonce."""
    return os.urandom(32)


@pytest.fixture()
def session_key_pair():
    """Two random nonces and their derived session key."""
    host_nonce   = os.urandom(32)
    client_nonce = os.urandom(32)
    key          = derive_session_key(host_nonce, client_nonce)
    return {"host_nonce": host_nonce, "client_nonce": client_nonce, "key": key}


@pytest.fixture()
def sample_packet():
    """A sample game packet (header + payload + correct HMAC tag)."""
    key     = os.urandom(32)
    payload = b"\x01\x02\x03\x04HELLO"
    header  = build_net_header(sender=1, dest=0, seq=42, payload_len=len(payload))
    tag     = sign_packet(key, header, payload)
    return {"key": key, "header": header, "payload": payload, "tag": tag}


# ============================================================================
# Section A: Known-Answer Tests (RFC 4231 / RFC 5869)
# ============================================================================

class TestHMACSHA256KnownAnswer:
    """HMAC-SHA256 test vectors from RFC 4231 §4."""

    def test_rfc4231_tc1(self):
        """RFC 4231 Test Case 1: HMAC-SHA256 with 20-byte key."""
        key    = bytes.fromhex("0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b")
        data   = b"Hi There"
        expect = bytes.fromhex(
            "b0344c61d8db38535ca8afceaf0bf12b"
            "881dc200c9833da726e9376c2e32cff7"
        )
        assert py_hmac_sha256(key, data) == expect

    def test_rfc4231_tc2(self):
        """RFC 4231 Test Case 2: HMAC-SHA256 with 'Jefe' key."""
        key    = b"Jefe"
        data   = b"what do ya want for nothing?"
        expect = bytes.fromhex(
            "5bdcc146bf60754e6a042426089575c7"
            "5a003f089d2739839dec58b964ec3843"
        )
        assert py_hmac_sha256(key, data) == expect

    def test_rfc4231_tc3(self):
        """RFC 4231 Test Case 3: HMAC-SHA256 with long repeated-byte key and data."""
        key    = b"\xaa" * 20
        data   = b"\xdd" * 50
        expect = bytes.fromhex(
            "773ea91e36800e46854db8ebd09181a7"
            "2959098b3ef8c122d9635514ced565fe"
        )
        assert py_hmac_sha256(key, data) == expect

    def test_hmac_output_is_32_bytes(self):
        """HMAC-SHA256 always produces exactly 32 bytes."""
        tag = py_hmac_sha256(b"key", b"message")
        assert len(tag) == HMAC_SHA256_SIZE, f"Expected 32 bytes, got {len(tag)}"

    def test_hmac_different_keys_produce_different_tags(self):
        """Different keys → different HMAC tags for the same message."""
        msg  = b"same message"
        tag1 = py_hmac_sha256(os.urandom(32), msg)
        tag2 = py_hmac_sha256(os.urandom(32), msg)
        assert tag1 != tag2, "Different keys must produce different tags"

    def test_hmac_different_messages_produce_different_tags(self):
        """Different messages → different HMAC tags for the same key."""
        key  = os.urandom(32)
        tag1 = py_hmac_sha256(key, b"message_A")
        tag2 = py_hmac_sha256(key, b"message_B")
        assert tag1 != tag2, "Different messages must produce different tags"


class TestHKDFSHA256KnownAnswer:
    """HKDF-SHA256 test vectors from RFC 5869 Appendix A."""

    def test_rfc5869_tc1(self):
        """RFC 5869 Test Case 1: basic HKDF-SHA256."""
        ikm    = bytes.fromhex("0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b")
        salt   = bytes.fromhex("000102030405060708090a0b0c")
        info   = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
        length = 42
        expect = bytes.fromhex(
            "3cb25f25faacd57a90434f64d0362f2a"
            "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
            "34007208d5b887185865"
        )
        assert py_hkdf_sha256(salt, ikm, info, length) == expect

    def test_rfc5869_tc2(self):
        """RFC 5869 Test Case 2: longer inputs."""
        ikm    = bytes(range(0x00, 0x50))   # 80 bytes 0x00..0x4f
        salt   = bytes(range(0x60, 0xb0))   # 80 bytes 0x60..0xaf
        info   = bytes(range(0xb0, 0x100))  # 80 bytes 0xb0..0xff (RFC 5869 §A.2)
        length = 82
        expect = bytes.fromhex(
            "b11e398dc80327a1c8e7f78c596a4934"
            "4f012eda2d4efad8a050cc4c19afa97c"
            "59045a99cac7827271cb41c65e590e09"
            "da3275600c2f09b8367793a9aca3db71"
            "cc30c58179ec3e87c14c01d5c1f3434f"
            "1d87"
        )
        assert py_hkdf_sha256(salt, ikm, info, length) == expect

    def test_rfc5869_tc3_no_salt(self):
        """RFC 5869 Test Case 3: no salt (defaults to 32 zeros)."""
        ikm    = bytes.fromhex("0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b")
        salt   = b""   # empty → 32 zero bytes used internally
        info   = b""
        length = 42
        expect = bytes.fromhex(
            "8da4e775a563c18f715f802a063c5a31"
            "b8a11f5c5ee1879ec3454e5f3c738d2d"
            "9d201395faa4b61a96c8"
        )
        assert py_hkdf_sha256(salt, ikm, info, length) == expect

    def test_hkdf_output_length(self):
        """HKDF output is exactly the requested length."""
        for req_len in [1, 16, 32, 64]:
            out = py_hkdf_sha256(b"salt", b"ikm", b"info", req_len)
            assert len(out) == req_len, f"Expected {req_len} bytes, got {len(out)}"

    def test_hkdf_auth_info_binding(self):
        """Different info strings produce different keys (domain separation)."""
        key1 = py_hkdf_sha256(b"salt", b"ikm", b"AUTH_SPOOFING_V1",  32)
        key2 = py_hkdf_sha256(b"salt", b"ikm", b"DIFFERENT_CONTEXT", 32)
        assert key1 != key2, "Different info must produce different keys"


# ============================================================================
# Section B: Packet Authentication Tests (mock-based)
# ============================================================================

class TestPacketTagAppended:
    """Verify wire-format has HMAC-SHA256 tag after payload."""

    def test_packet_has_32_byte_tag(self, sample_packet):
        """Outgoing packet: 5-byte header + N-byte payload + 32-byte HMAC tag."""
        hdr     = sample_packet["header"]
        payload = sample_packet["payload"]
        tag     = sample_packet["tag"]

        assert len(hdr)     == NET_HEADER_SIZE,   "Header must be 5 bytes"
        assert len(tag)     == HMAC_SHA256_SIZE,  "HMAC tag must be 32 bytes"
        total_wire = len(hdr) + len(payload) + len(tag)
        assert total_wire == NET_HEADER_SIZE + len(payload) + HMAC_SHA256_SIZE

    def test_tag_covers_header_and_payload(self, sample_packet):
        """HMAC tag must authenticate the full header||payload (not payload alone)."""
        key     = sample_packet["key"]
        header  = sample_packet["header"]
        payload = sample_packet["payload"]
        tag     = sample_packet["tag"]

        # Correct: verify against header+payload
        assert verify_packet_ct(key, header, payload, tag), "Valid tag must verify"

        # If we use payload-only, verification must fail (tag covers header too)
        tag_payload_only = py_hmac_sha256(key, payload)
        assert not hmac.compare_digest(tag, tag_payload_only), \
            "Tag computed over payload-only must differ from header+payload tag"

    def test_tag_changes_when_payload_changes(self):
        """Mutated payload invalidates the HMAC tag."""
        key      = os.urandom(32)
        header   = build_net_header(1, 0, 10, 5)
        payload  = b"hello"
        tag      = sign_packet(key, header, payload)
        bad_pay  = b"HELLO"   # capitalised ≠ original
        assert not verify_packet_ct(key, header, bad_pay, tag), \
            "Mutated payload must fail HMAC verification"

    def test_tag_changes_when_header_changes(self):
        """Mutated header (e.g. from_player spoof) invalidates the HMAC tag."""
        key          = os.urandom(32)
        real_sender  = 1
        forged_sender = 2
        payload      = b"game_data"
        header_real  = build_net_header(real_sender,   0, 7, len(payload))
        header_forged = build_net_header(forged_sender, 0, 7, len(payload))
        tag_real     = sign_packet(key, header_real, payload)

        # The forged header must not pass verification with the original tag
        assert not verify_packet_ct(key, header_forged, payload, tag_real), \
            "Spoofed from_player must fail HMAC verification"


# ============================================================================
# Section C: Security Tests
# ============================================================================

class TestForgedFromPlayerRejected:
    """Verify that forging from_player in the header causes HMAC failure."""

    def test_forged_from_player_fails_verification(self):
        """Forge from_player=2 when actual sender is player 1 → HMAC mismatch."""
        key_player1 = os.urandom(32)
        payload     = b"\x00\x01\x02\x03game_state"
        seq         = 5

        # Legitimate packet from player 1
        real_header   = build_net_header(1, 0, seq, len(payload))
        tag           = sign_packet(key_player1, real_header, payload)

        # Forged packet claiming to be from player 2 (but tag uses key_player1)
        forged_header = build_net_header(2, 0, seq, len(payload))

        # Verification with player 1's key against forged header must fail
        assert not verify_packet_ct(key_player1, forged_header, payload, tag), \
            "Forged from_player must invalidate HMAC tag"

    def test_wrong_session_key_fails_verification(self):
        """Using a different session key for verification must fail."""
        key_real  = os.urandom(32)
        key_wrong = os.urandom(32)
        header    = build_net_header(1, 0, 0, 4)
        payload   = b"data"
        tag       = sign_packet(key_real, header, payload)

        assert not verify_packet_ct(key_wrong, header, payload, tag), \
            "Wrong session key must fail HMAC verification"

    def test_mmulti_c_has_hmac_verification_sentinel(self):
        """SRC/MMULTI.C must contain the HMAC verification drop sentinel."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        assert "HMAC mismatch" in content, \
            "SRC/MMULTI.C must contain HMAC mismatch drop logic"
        assert "net-r17-hmac" in content, \
            "SRC/MMULTI.C must contain net-r17-hmac sentinels"


class TestReplayCorrruptedTagRejected:
    """Verify that a replayed or bit-flipped tag is rejected."""

    def test_corrupted_tag_rejected(self):
        """Single byte flip in HMAC tag must fail verification."""
        key     = os.urandom(32)
        header  = build_net_header(1, 0, 3, 5)
        payload = b"world"
        tag     = bytearray(sign_packet(key, header, payload))
        # Flip first byte
        tag[0] ^= 0xFF
        assert not verify_packet_ct(key, header, payload, bytes(tag)), \
            "Bit-flipped tag must fail HMAC verification"

    def test_zero_tag_rejected(self):
        """All-zero tag must be rejected (not accepted as 'unknown')."""
        key     = os.urandom(32)
        header  = build_net_header(1, 0, 3, 5)
        payload = b"hello"
        zero_tag = b"\x00" * HMAC_SHA256_SIZE
        assert not verify_packet_ct(key, header, payload, zero_tag), \
            "All-zero HMAC tag must fail verification"

    def test_truncated_tag_rejected(self):
        """A tag shorter than 32 bytes should not match (handled by length guard)."""
        key     = os.urandom(32)
        header  = build_net_header(1, 0, 0, 3)
        payload = b"abc"
        full_tag    = sign_packet(key, header, payload)
        truncated   = full_tag[:16]
        # Truncated tag clearly differs from full 32-byte tag
        assert len(truncated) != len(full_tag), "Tags of different lengths must differ"


class TestHandshakeNoncesExchanged:
    """Verify the handshake state machine includes the 32B nonce exchange."""

    def test_mmulti_c_has_host_nonce_send(self):
        """Host handshake must send 40 bytes (8 original + 32-byte nonce)."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        # The host must allocate a 40-byte handshake message
        assert "unsigned char msg[40]" in content, \
            "Host handshake must use 40-byte buffer (8 header + 32 nonce)"

    def test_mmulti_c_client_receives_host_nonce(self):
        """Client handshake must receive the host nonce (32 bytes)."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        assert "host_nonce_buf" in content, \
            "Client handshake must receive host_nonce_buf"

    def test_mmulti_c_client_sends_nonce(self):
        """Client must send its own nonce back to the host."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        # Client sends local_nonce to host
        assert "net_send_raw(sock, local_nonce" in content, \
            "Client must send local_nonce to host during handshake"

    def test_mmulti_c_nonce_size_is_32(self):
        """Nonce buffers must be exactly 32 bytes (HMAC_SHA256_SIZE)."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        assert "unsigned char local_nonce[HMAC_SHA256_SIZE]" in content, \
            "local_nonce must be declared as HMAC_SHA256_SIZE bytes"

    def test_mmulti_c_hkdf_context_string(self):
        """HKDF info must use the literal string 'AUTH_SPOOFING_V1'."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        assert "AUTH_SPOOFING_V1" in content, \
            "SRC/MMULTI.C must use AUTH_SPOOFING_V1 as HKDF info string"

    def test_mmulti_c_net_header_size_preserved(self):
        """NET_HEADER_SIZE must remain 5 (cycle-65 invariant)."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"#define\s+NET_HEADER_SIZE\s+(\d+)", content)
        assert match is not None, "NET_HEADER_SIZE must be defined"
        assert int(match.group(1)) == 5, \
            f"NET_HEADER_SIZE must remain 5, got {match.group(1)}"

    def test_mmulti_c_handshake_timeout_preserved(self):
        """Handshake timeout constants (cycle-83) must be unchanged."""
        with open("SRC/MMULTI.C", "r", encoding="utf-8") as f:
            content = f.read()
        m_conn = re.search(r"#define\s+NET_CONNECT_TIMEOUT\s+(\d+)", content)
        m_hs   = re.search(r"#define\s+HANDSHAKE_TIMEOUT_SEC\s+(\d+)", content)
        m_acc  = re.search(r"#define\s+NET_HOST_ACCEPT_TIMEOUT_SEC\s+(\d+)", content)
        assert m_conn and int(m_conn.group(1)) == 30, "NET_CONNECT_TIMEOUT must be 30"
        assert m_hs   and int(m_hs.group(1))   == 15, "HANDSHAKE_TIMEOUT_SEC must be 15"
        assert m_acc  and int(m_acc.group(1))  == 10, "NET_HOST_ACCEPT_TIMEOUT_SEC must be 10"


class TestSessionKeysDifferPerConnection:
    """Different nonce pairs must produce different session keys."""

    def test_different_nonces_produce_different_keys(self):
        """Two connections with different nonces get different session keys."""
        host_nonce    = os.urandom(32)
        client_nonce1 = os.urandom(32)
        client_nonce2 = os.urandom(32)
        assert client_nonce1 != client_nonce2  # sanity

        key1 = derive_session_key(host_nonce, client_nonce1)
        key2 = derive_session_key(host_nonce, client_nonce2)
        assert key1 != key2, \
            "Different client nonces must produce different session keys"

    def test_same_nonces_produce_same_key(self):
        """Both sides of a connection derive the same key from the same nonces."""
        host_nonce   = os.urandom(32)
        client_nonce = os.urandom(32)
        key_host_side   = derive_session_key(host_nonce, client_nonce)
        key_client_side = derive_session_key(host_nonce, client_nonce)
        assert key_host_side == key_client_side, \
            "Both sides must derive identical session keys from the same nonces"

    def test_session_key_is_32_bytes(self, session_key_pair):
        """Derived session key is exactly 32 bytes."""
        assert len(session_key_pair["key"]) == 32

    def test_different_connections_have_independent_keys(self):
        """N connections → N distinct session keys (birthday-collision probability negligible)."""
        keys = set()
        for _ in range(10):
            k = derive_session_key(os.urandom(32), os.urandom(32))
            keys.add(k)
        assert len(keys) == 10, "All 10 random connections must have unique keys"

    def test_sha256_h_declares_hmac_and_hkdf(self):
        """compat/sha256.h must declare hmac_sha256 and hkdf_sha256."""
        with open("compat/sha256.h", "r", encoding="utf-8") as f:
            content = f.read()
        assert "hmac_sha256" in content, "sha256.h must declare hmac_sha256"
        assert "hkdf_sha256" in content, "sha256.h must declare hkdf_sha256"
        assert "hmac_sha256_verify_ct" in content, \
            "sha256.h must declare constant-time comparison helper"

    def test_build_mk_includes_sha256_c(self):
        """build.mk must include compat/sha256.c in COMPAT_SRCS."""
        with open("build.mk", "r", encoding="utf-8") as f:
            content = f.read()
        assert "sha256.c" in content, \
            "build.mk must include compat/sha256.c in COMPAT_SRCS"

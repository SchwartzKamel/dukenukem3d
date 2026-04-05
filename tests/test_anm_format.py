"""Tests for ANM (Deluxe Animate LPF) file format encoder."""

import struct
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from anm_format import create_anm, create_placeholder_anm, _compress_rsd


class TestCompressRSD:
    """Test RunSkipDump compression."""

    def test_all_same_pixels(self):
        """Pixels of same value should compress to RUN operations."""
        pixels = bytes([42] * 100)
        compressed = _compress_rsd(pixels)
        # Should end with STOP marker
        assert compressed[-3:] == b"\x80\x00\x00"
        # Should be much smaller than input
        assert len(compressed) < len(pixels)

    def test_stop_marker_present(self):
        """Every compressed frame must end with STOP marker (0x80, 0x00, 0x00)."""
        for data in [bytes(10), bytes([1, 2, 3, 4, 5]), bytes([0] * 1000)]:
            compressed = _compress_rsd(data)
            assert compressed[-3:] == b"\x80\x00\x00"

    def test_empty_input(self):
        """Empty input should produce only a STOP marker."""
        compressed = _compress_rsd(b"")
        assert compressed == b"\x80\x00\x00"

    def test_varied_pixels(self):
        """Varied pixels should use DUMP operations."""
        pixels = bytes(range(50))
        compressed = _compress_rsd(pixels)
        assert compressed[-3:] == b"\x80\x00\x00"

    def test_large_run(self):
        """Runs larger than 255 should use long RUN encoding."""
        pixels = bytes([7] * 500)
        compressed = _compress_rsd(pixels)
        assert compressed[-3:] == b"\x80\x00\x00"
        assert len(compressed) < len(pixels)

    def test_mixed_content(self):
        """Mix of runs and varied data should compress correctly."""
        pixels = bytes([0] * 50 + list(range(20)) + [255] * 30)
        compressed = _compress_rsd(pixels)
        assert compressed[-3:] == b"\x80\x00\x00"

    def test_decompresses_correctly(self):
        """Verify compressed data decompresses back to original."""
        pixels = bytes([0] * 100 + [5, 10, 15, 20, 25] + [200] * 50)
        compressed = _compress_rsd(pixels)
        decompressed = _decompress_rsd(compressed, len(pixels))
        assert decompressed == pixels

    def test_full_frame_roundtrip(self):
        """Test compression of a full 320x200 frame."""
        import random
        random.seed(42)
        # Mostly black with some scattered pixels
        pixels = bytearray(64000)
        for i in range(0, 64000, 100):
            pixels[i] = random.randint(1, 255)
        compressed = _compress_rsd(bytes(pixels))
        decompressed = _decompress_rsd(compressed, 64000)
        assert decompressed == bytes(pixels)


class TestCreateAnm:
    """Test ANM file creation."""

    def test_header_magic(self):
        """ANM file must start with 'LPF ' magic bytes."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        assert anm[0:4] == b"LPF "

    def test_content_type(self):
        """Header must contain 'ANIM' content type at offset 16."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        assert anm[16:20] == b"ANIM"

    def test_dimensions(self):
        """Header must specify 320x200 dimensions."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        width = struct.unpack_from("<H", anm, 20)[0]
        height = struct.unpack_from("<H", anm, 22)[0]
        assert width == 320
        assert height == 200

    def test_record_count(self):
        """nRecords should be len(frames) + 1."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        n_records = struct.unpack_from("<I", anm, 8)[0]
        assert n_records == 2  # 1 frame + 1 no-op

    def test_palette_stored_as_bgra(self):
        """Palette should be stored in BGRA format at offset 0x100."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        palette[0] = (255, 128, 64)
        anm = create_anm([frame], palette)
        # At offset 0x100: B, G, R, padding
        assert anm[0x100] == 64   # B
        assert anm[0x101] == 128  # G
        assert anm[0x102] == 255  # R
        assert anm[0x103] == 0    # padding

    def test_lp_descriptor_at_0x500(self):
        """LP descriptor array should start at offset 0x500."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        base_record = struct.unpack_from("<H", anm, 0x500)[0]
        n_records = struct.unpack_from("<H", anm, 0x502)[0]
        assert base_record == 0
        assert n_records == 2

    def test_lp_data_at_0xb00(self):
        """Large page data should start at offset 0xB00."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        assert len(anm) > 0xB00
        # LP header at 0xB00 should match LP descriptor at 0x500
        assert anm[0xB00:0xB06] == anm[0x500:0x506]

    def test_minimum_file_size(self):
        """ANM file must be at least 0xB00 + some data."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        assert len(anm) > 0xB00

    def test_requires_frames(self):
        """Should raise error with no frames."""
        palette = [(0, 0, 0)] * 256
        with pytest.raises(ValueError, match="(?i)at least one frame"):
            create_anm([], palette)

    def test_requires_correct_palette_size(self):
        """Should raise error with wrong palette size."""
        frame = bytes(64000)
        with pytest.raises(ValueError, match="256 entries"):
            create_anm([frame], [(0, 0, 0)] * 128)

    def test_requires_correct_frame_size(self):
        """Should raise error with wrong frame size."""
        palette = [(0, 0, 0)] * 256
        with pytest.raises(ValueError, match="64000 bytes"):
            create_anm([bytes(100)], palette)

    def test_compression_type(self):
        """Header byte at offset 29 should indicate RunSkipDump (1)."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette)
        assert anm[29] == 1

    def test_fps_stored(self):
        """FPS value should be stored in header."""
        frame = bytes(64000)
        palette = [(0, 0, 0)] * 256
        anm = create_anm([frame], palette, fps=15)
        fps = struct.unpack_from("<H", anm, 68)[0]
        assert fps == 15

    def test_multi_frame(self):
        """Multiple frames should produce correct nRecords."""
        frames = [bytes(64000), bytes([1] * 64000)]
        palette = [(0, 0, 0)] * 256
        anm = create_anm(frames, palette)
        n_records = struct.unpack_from("<I", anm, 8)[0]
        assert n_records == 3  # 2 frames + 1 no-op


class TestCreatePlaceholderAnm:
    """Test placeholder ANM generation."""

    def test_creates_valid_anm(self):
        """Placeholder should produce a valid ANM file."""
        anm = create_placeholder_anm("TEST")
        assert anm[0:4] == b"LPF "
        assert anm[16:20] == b"ANIM"

    def test_default_text(self):
        """Default placeholder should generate without errors."""
        anm = create_placeholder_anm()
        assert len(anm) > 0xB00

    def test_custom_text(self):
        """Custom text placeholder should work."""
        anm = create_placeholder_anm("HELLO WORLD")
        assert anm[0:4] == b"LPF "

    def test_text_pixels_present(self):
        """Placeholder should have non-zero pixels for text."""
        anm = create_placeholder_anm("X", text_color=1)
        # Check that the LP data section contains actual frame data
        # beyond just headers (file should be larger than empty frame)
        assert len(anm) > 0xB20

    def test_all_anm_files_generate(self):
        """All game ANM files should generate without errors."""
        anm_defs = [
            "DUKE NUKEM 3D", "EPISODE 2 END", "EPISODE 3 END",
            "DUKE NUKEM TEAM", "3D REALMS", "EPISODE 4",
            "EPISODE 4-2", "EPISODE 4-3", "EPISODE 4 END",
            "EPISODE 4 END 2", "EPISODE 4 END 3",
        ]
        for text in anm_defs:
            anm = create_placeholder_anm(text=text)
            assert anm[0:4] == b"LPF ", f"Failed for: {text}"
            assert len(anm) > 0xB00, f"Too small for: {text}"


def _decompress_rsd(compressed: bytes, expected_size: int) -> bytes:
    """Reference RunSkipDump decompressor matching CPlayRunSkipDump()."""
    dst = bytearray(expected_size)
    src_i = 0
    dst_i = 0

    while src_i < len(compressed):
        cnt = compressed[src_i]
        src_i += 1

        # Interpret as signed byte
        if cnt < 128:
            signed_cnt = cnt
        else:
            signed_cnt = cnt - 256

        if signed_cnt > 0:
            # DUMP: copy cnt bytes
            for _ in range(signed_cnt):
                if dst_i < expected_size and src_i < len(compressed):
                    dst[dst_i] = compressed[src_i]
                    dst_i += 1
                    src_i += 1
        elif signed_cnt == 0:
            # RUN: count byte, pixel byte
            word_cnt = compressed[src_i]
            src_i += 1
            pixel = compressed[src_i]
            src_i += 1
            for _ in range(word_cnt):
                if dst_i < expected_size:
                    dst[dst_i] = pixel
                    dst_i += 1
        else:
            # cnt < 0
            cnt_minus_80 = cnt - 0x80
            if cnt_minus_80 == 0:
                # longOp
                if src_i + 1 >= len(compressed):
                    break
                word_cnt = struct.unpack_from("<H", compressed, src_i)[0]
                src_i += 2

                signed_word = (
                    word_cnt if word_cnt < 32768 else word_cnt - 65536
                )

                if signed_word > 0:
                    # longSkip
                    dst_i += word_cnt
                elif word_cnt == 0:
                    # STOP
                    break
                else:
                    word_cnt_clean = word_cnt - 0x8000
                    if word_cnt_clean >= 0x4000:
                        # longRun
                        run_len = word_cnt_clean - 0x4000
                        pixel = compressed[src_i]
                        src_i += 1
                        for _ in range(run_len):
                            if dst_i < expected_size:
                                dst[dst_i] = pixel
                                dst_i += 1
                    else:
                        # longDump
                        for _ in range(word_cnt_clean):
                            if dst_i < expected_size and src_i < len(compressed):
                                dst[dst_i] = compressed[src_i]
                                dst_i += 1
                                src_i += 1
            else:
                # shortSkip
                skip = cnt_minus_80
                dst_i += skip

    return bytes(dst)

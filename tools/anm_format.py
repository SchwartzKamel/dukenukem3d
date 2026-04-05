#!/usr/bin/env python3
"""ANM (Deluxe Animate LPF) file format encoder for Duke Nukem 3D.

The ANM format is used by the BUILD engine for cutscene animations.
File layout:
  [0x0000] lpfileheader (128 bytes)
  [0x0080] Padding (128 bytes)
  [0x0100] Palette (256 colors x 4 bytes BGRA = 1024 bytes)
  [0x0500] Large page descriptor array (256 x 6 bytes = 1536 bytes)
  [0x0B00] Large page 0 data (lp_descriptor + padding + records)

Each large page contains:
  - lp_descriptor (6 bytes): baseRecord, nRecords, nBytes
  - uint16 padding (2 bytes)
  - Record size table: nRecords x uint16
  - Compressed frame data (RunSkipDump encoded)
"""

import struct
from typing import List, Tuple


def _compress_rsd(pixels: bytes) -> bytes:
    """Compress pixel data using RunSkipDump algorithm.

    This matches the decompressor CPlayRunSkipDump() in ANIMLIB.C.
    Uses RUN for consecutive identical pixels and DUMP for varied pixels.
    """
    result = bytearray()
    i = 0
    n = len(pixels)

    while i < n:
        # Check for a run of identical pixels (3+ to be worth encoding as RUN)
        if i + 2 < n and pixels[i] == pixels[i + 1] == pixels[i + 2]:
            val = pixels[i]
            run_start = i
            while i < n and pixels[i] == val:
                i += 1
            run_len = i - run_start

            while run_len > 0:
                chunk = min(run_len, 16383)
                if chunk <= 255:
                    # Short RUN: 0x00, count_byte, pixel
                    result.extend([0x00, chunk, val])
                else:
                    # Long RUN: 0x80, uint16(0xC000 + count), pixel
                    result.append(0x80)
                    result.extend(struct.pack("<H", 0xC000 + chunk))
                    result.append(val)
                run_len -= chunk
        else:
            # Collect varied pixels until we hit a run of 3+
            dump_start = i
            while i < n:
                if (
                    i + 2 < n
                    and pixels[i] == pixels[i + 1] == pixels[i + 2]
                ):
                    break
                i += 1
            dump_len = i - dump_start

            while dump_len > 0:
                chunk = min(dump_len, 16383)
                offset = dump_start + (i - dump_start - dump_len)
                if chunk <= 127:
                    # Short DUMP: count (1-127), then pixel bytes
                    result.append(chunk)
                    result.extend(pixels[offset : offset + chunk])
                else:
                    # Long DUMP: 0x80, uint16(0x8000 + count), then pixels
                    result.append(0x80)
                    result.extend(struct.pack("<H", 0x8000 + chunk))
                    result.extend(pixels[offset : offset + chunk])
                dump_len -= chunk

    # STOP marker
    result.extend([0x80, 0x00, 0x00])
    return bytes(result)


def create_anm(
    frames: List[bytes],
    palette_rgb: List[Tuple[int, int, int]],
    fps: int = 10,
) -> bytes:
    """Create a valid ANM (LPF) animation file.

    Args:
        frames: List of frame pixel data, each 64000 bytes (320x200 palette
                indices). The first frame is the base image; subsequent frames
                are displayed as deltas (for simplicity we encode each as a
                full replacement).
        palette_rgb: 256 (R, G, B) tuples, values 0-255.
        fps: Playback frame rate.

    Returns:
        Complete ANM file as bytes.
    """
    if not frames:
        raise ValueError("At least one frame is required")
    if len(palette_rgb) != 256:
        raise ValueError("Palette must have exactly 256 entries")

    # We need nRecords = len(frames) + 1 because playanm() loops
    # for(i=1; i<numframes; i++) and ANIM_DrawFrame(i) decodes frames 0..i-1.
    # Frame 0 delta creates the first display image; frame 1+ are subsequent.
    # For a single-image ANM: frames[0] → record 0, record 1 = STOP no-op.
    num_display_frames = len(frames)
    n_records = num_display_frames + 1  # +1 so the loop displays the last frame

    # Compress frame data
    compressed_frames = []
    prev_pixels = bytes(64000)  # Start from blank (all zeros)
    for frame_pixels in frames:
        if len(frame_pixels) != 64000:
            raise ValueError(
                f"Frame must be 64000 bytes, got {len(frame_pixels)}"
            )
        # Each frame record: 4-byte sub-header + compressed delta
        # Sub-header byte[1]=0 means skip 4 bytes to get to compressed data
        sub_header = b"\x00\x00\x00\x00"
        compressed = _compress_rsd(frame_pixels)
        compressed_frames.append(sub_header + compressed)
        prev_pixels = frame_pixels

    # Final no-op record (STOP only) so the loop iteration count is correct
    noop_frame = b"\x00\x00\x00\x00" + b"\x80\x00\x00"  # sub-header + STOP
    compressed_frames.append(noop_frame)

    # Split records across large pages.  Each page's nBytes (total compressed
    # data) must fit in a uint16 (≤65535) and nRecords per page ≤256.
    # loadpage() also copies nBytes + nRecords*2 into thepage[0x8000] (64 KB),
    # so we cap nBytes at 65024 (65536 − 256*2) to leave room for the size
    # table even at maximum records per page.
    _MAX_PAGE_BYTES = 65024
    _MAX_PAGE_RECORDS = 256

    pages: list = []  # list of (base_record, [compressed_frame, ...])
    cur_records: list = []
    cur_bytes = 0
    base = 0

    for cf in compressed_frames:
        sz = len(cf)
        if sz > 65535:
            raise ValueError(
                f"Single record ({sz} bytes) exceeds uint16 limit "
                f"(65535).  Frame data is too complex."
            )
        if cur_records and (
            cur_bytes + sz > _MAX_PAGE_BYTES
            or len(cur_records) >= _MAX_PAGE_RECORDS
        ):
            pages.append((base, list(cur_records)))
            base += len(cur_records)
            cur_records = []
            cur_bytes = 0
        cur_records.append(cf)
        cur_bytes += sz

    if cur_records:
        pages.append((base, list(cur_records)))

    n_lps = len(pages)
    if n_lps > 256:
        raise ValueError(
            f"Animation requires {n_lps} large pages (max 256)"
        )

    # --- Build the file ---

    # 1. Header (128 bytes)
    header = bytearray(128)
    struct.pack_into("<I", header, 0, 0x2046504C)  # "LPF "
    struct.pack_into("<H", header, 4, 256)  # maxLps
    struct.pack_into("<H", header, 6, n_lps)  # nLps
    struct.pack_into("<I", header, 8, n_records)  # nRecords
    struct.pack_into("<H", header, 12, 256)  # maxRecsPerLp
    struct.pack_into("<H", header, 14, 0x0500)  # lpfTableOffset
    struct.pack_into("<I", header, 16, 0x4D494E41)  # "ANIM"
    struct.pack_into("<H", header, 20, 320)  # width
    struct.pack_into("<H", header, 22, 200)  # height
    header[24] = 0  # variant
    header[25] = 0  # version
    header[26] = 0  # hasLastDelta
    header[27] = 0  # lastDeltaValid
    header[28] = 0  # pixelType (256-color)
    header[29] = 1  # CompressionType (RunSkipDump)
    header[30] = 0  # otherRecsPerFrm
    header[31] = 1  # bitmaptype (320x200)
    # recordTypes[32] at offset 32..63 already zeroed
    struct.pack_into("<I", header, 64, n_records)  # nFrames
    struct.pack_into("<H", header, 68, fps)  # framesPerSecond
    # pad2[29] at offset 70..127 already zeroed

    # 2. Padding (128 bytes)
    padding = bytes(128)

    # 3. Palette (1024 bytes, stored as BGRA)
    palette_data = bytearray(1024)
    for i, (r, g, b) in enumerate(palette_rgb):
        palette_data[i * 4 + 0] = b
        palette_data[i * 4 + 1] = g
        palette_data[i * 4 + 2] = r
        palette_data[i * 4 + 3] = 0

    # 4. LP descriptor array (256 entries x 6 bytes = 1536 bytes)
    lp_array = bytearray(256 * 6)
    for pi, (page_base, page_records) in enumerate(pages):
        page_n_bytes = sum(len(r) for r in page_records)
        off = pi * 6
        struct.pack_into("<H", lp_array, off + 0, page_base)
        struct.pack_into("<H", lp_array, off + 2, len(page_records))
        struct.pack_into("<H", lp_array, off + 4, page_n_bytes)

    # 5. Large page data – page N starts at file offset 0x0B00 + N*0x10000
    #    Each page: lp_descriptor(6) + uint16 padding(2) + size_table + data
    #    loadpage() reads from 0xB00 + page*0x10000.
    file_data = bytearray()
    file_data.extend(header)       # 0x0000
    file_data.extend(padding)      # 0x0080
    file_data.extend(palette_data) # 0x0100
    file_data.extend(lp_array)     # 0x0500  (ends at 0x0AFF)

    for pi, (page_base, page_records) in enumerate(pages):
        page_offset = 0x0B00 + pi * 0x10000
        # Pad file_data up to this page's start offset
        if len(file_data) < page_offset:
            file_data.extend(bytes(page_offset - len(file_data)))

        page_n_recs = len(page_records)
        page_n_bytes = sum(len(r) for r in page_records)

        # LP header (8 bytes)
        lp_hdr = bytearray(8)
        struct.pack_into("<H", lp_hdr, 0, page_base)
        struct.pack_into("<H", lp_hdr, 2, page_n_recs)
        struct.pack_into("<H", lp_hdr, 4, page_n_bytes)
        struct.pack_into("<H", lp_hdr, 6, 0)  # padding
        file_data.extend(lp_hdr)

        # Record size table
        for r in page_records:
            file_data.extend(struct.pack("<H", len(r)))

        # Compressed frame data
        for r in page_records:
            file_data.extend(r)

    return bytes(file_data)


def create_placeholder_anm(
    text: str = "DUKE NUKEM 3D",
    bg_color: int = 0,
    text_color: int = 1,
    fps: int = 10,
) -> bytes:
    """Create a minimal single-frame ANM with centered text.

    Uses a simple built-in bitmap font (no PIL dependency).

    Args:
        text: Text to display centered on screen.
        bg_color: Palette index for background.
        text_color: Palette index for text.
        fps: Playback frame rate.

    Returns:
        Complete ANM file as bytes.
    """
    # Simple 5x7 bitmap font (uppercase + digits + space + punctuation)
    font = _get_bitmap_font()

    width, height = 320, 200
    pixels = bytearray(width * height)

    # Fill background
    for i in range(len(pixels)):
        pixels[i] = bg_color

    # Calculate text dimensions (each char is 5 wide + 1 spacing)
    char_w, char_h = 6, 8  # 5px char + 1px spacing, 7px char + 1px spacing
    scale = 2  # Double size for visibility
    text_upper = text.upper()
    total_w = len(text_upper) * char_w * scale - scale  # No trailing space
    total_h = char_h * scale

    start_x = (width - total_w) // 2
    start_y = (height - total_h) // 2

    for ci, ch in enumerate(text_upper):
        glyph = font.get(ch, font.get(" "))
        for row in range(7):
            for col in range(5):
                if glyph[row] & (1 << (4 - col)):
                    # Draw scaled pixel
                    px = start_x + ci * char_w * scale + col * scale
                    py = start_y + row * scale
                    for dy in range(scale):
                        for dx in range(scale):
                            x = px + dx
                            y = py + dy
                            if 0 <= x < width and 0 <= y < height:
                                pixels[y * width + x] = text_color

    # Simple palette: black bg, white text
    palette = [(0, 0, 0)] * 256
    palette[1] = (200, 200, 200)  # Light gray text
    palette[2] = (255, 80, 80)  # Red accent
    palette[3] = (80, 180, 255)  # Blue accent

    return create_anm([bytes(pixels)], palette, fps)


def _get_bitmap_font():
    """Return a minimal 5x7 bitmap font as {char: [row_bits...]}."""
    return {
        " ": [0b00000] * 7,
        "A": [
            0b01110, 0b10001, 0b10001, 0b11111,
            0b10001, 0b10001, 0b10001,
        ],
        "B": [
            0b11110, 0b10001, 0b10001, 0b11110,
            0b10001, 0b10001, 0b11110,
        ],
        "C": [
            0b01110, 0b10001, 0b10000, 0b10000,
            0b10000, 0b10001, 0b01110,
        ],
        "D": [
            0b11110, 0b10001, 0b10001, 0b10001,
            0b10001, 0b10001, 0b11110,
        ],
        "E": [
            0b11111, 0b10000, 0b10000, 0b11110,
            0b10000, 0b10000, 0b11111,
        ],
        "F": [
            0b11111, 0b10000, 0b10000, 0b11110,
            0b10000, 0b10000, 0b10000,
        ],
        "G": [
            0b01110, 0b10001, 0b10000, 0b10111,
            0b10001, 0b10001, 0b01110,
        ],
        "H": [
            0b10001, 0b10001, 0b10001, 0b11111,
            0b10001, 0b10001, 0b10001,
        ],
        "I": [
            0b01110, 0b00100, 0b00100, 0b00100,
            0b00100, 0b00100, 0b01110,
        ],
        "J": [
            0b00111, 0b00010, 0b00010, 0b00010,
            0b10010, 0b10010, 0b01100,
        ],
        "K": [
            0b10001, 0b10010, 0b10100, 0b11000,
            0b10100, 0b10010, 0b10001,
        ],
        "L": [
            0b10000, 0b10000, 0b10000, 0b10000,
            0b10000, 0b10000, 0b11111,
        ],
        "M": [
            0b10001, 0b11011, 0b10101, 0b10101,
            0b10001, 0b10001, 0b10001,
        ],
        "N": [
            0b10001, 0b11001, 0b10101, 0b10011,
            0b10001, 0b10001, 0b10001,
        ],
        "O": [
            0b01110, 0b10001, 0b10001, 0b10001,
            0b10001, 0b10001, 0b01110,
        ],
        "P": [
            0b11110, 0b10001, 0b10001, 0b11110,
            0b10000, 0b10000, 0b10000,
        ],
        "Q": [
            0b01110, 0b10001, 0b10001, 0b10001,
            0b10101, 0b10010, 0b01101,
        ],
        "R": [
            0b11110, 0b10001, 0b10001, 0b11110,
            0b10100, 0b10010, 0b10001,
        ],
        "S": [
            0b01110, 0b10001, 0b10000, 0b01110,
            0b00001, 0b10001, 0b01110,
        ],
        "T": [
            0b11111, 0b00100, 0b00100, 0b00100,
            0b00100, 0b00100, 0b00100,
        ],
        "U": [
            0b10001, 0b10001, 0b10001, 0b10001,
            0b10001, 0b10001, 0b01110,
        ],
        "V": [
            0b10001, 0b10001, 0b10001, 0b10001,
            0b10001, 0b01010, 0b00100,
        ],
        "W": [
            0b10001, 0b10001, 0b10001, 0b10101,
            0b10101, 0b11011, 0b10001,
        ],
        "X": [
            0b10001, 0b10001, 0b01010, 0b00100,
            0b01010, 0b10001, 0b10001,
        ],
        "Y": [
            0b10001, 0b10001, 0b01010, 0b00100,
            0b00100, 0b00100, 0b00100,
        ],
        "Z": [
            0b11111, 0b00001, 0b00010, 0b00100,
            0b01000, 0b10000, 0b11111,
        ],
        "0": [
            0b01110, 0b10001, 0b10011, 0b10101,
            0b11001, 0b10001, 0b01110,
        ],
        "1": [
            0b00100, 0b01100, 0b00100, 0b00100,
            0b00100, 0b00100, 0b01110,
        ],
        "2": [
            0b01110, 0b10001, 0b00001, 0b00110,
            0b01000, 0b10000, 0b11111,
        ],
        "3": [
            0b01110, 0b10001, 0b00001, 0b00110,
            0b00001, 0b10001, 0b01110,
        ],
        "4": [
            0b00010, 0b00110, 0b01010, 0b10010,
            0b11111, 0b00010, 0b00010,
        ],
        "5": [
            0b11111, 0b10000, 0b11110, 0b00001,
            0b00001, 0b10001, 0b01110,
        ],
        "6": [
            0b01110, 0b10000, 0b10000, 0b11110,
            0b10001, 0b10001, 0b01110,
        ],
        "7": [
            0b11111, 0b00001, 0b00010, 0b00100,
            0b01000, 0b01000, 0b01000,
        ],
        "8": [
            0b01110, 0b10001, 0b10001, 0b01110,
            0b10001, 0b10001, 0b01110,
        ],
        "9": [
            0b01110, 0b10001, 0b10001, 0b01111,
            0b00001, 0b00001, 0b01110,
        ],
        ".": [
            0b00000, 0b00000, 0b00000, 0b00000,
            0b00000, 0b00000, 0b00100,
        ],
        "-": [
            0b00000, 0b00000, 0b00000, 0b11111,
            0b00000, 0b00000, 0b00000,
        ],
        "!": [
            0b00100, 0b00100, 0b00100, 0b00100,
            0b00100, 0b00000, 0b00100,
        ],
        "'": [
            0b00100, 0b00100, 0b00000, 0b00000,
            0b00000, 0b00000, 0b00000,
        ],
    }

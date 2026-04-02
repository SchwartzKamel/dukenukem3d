"""TABLES.DAT generator for BUILD engine.

Produces the sine / cosine lookup table, radar angle table, font data
and brightness table that the engine reads at startup.
"""

import math
import struct


def create_tables_dat():
    """Generate the complete TABLES.DAT used by the BUILD engine.

    Layout:
        - 4096 bytes : sintable   (2048 signed int16)
        - 2560 bytes : radarang   (1280 signed int16  = 640 + 640 mirrored)
        - 1024 bytes : font table 1 (widths for 256 chars * 2 short each = 1024)
        - 1024 bytes : font table 2
        - 1024 bytes : britable   (16 rows * 64 entries)

    Returns:
        bytes of the complete TABLES.DAT.
    """
    # --- Sine table (2048 entries) ---
    sintable = []
    for i in range(2048):
        val = int(math.sin(i * math.pi / 1024.0) * 16383.0)
        val = max(-16384, min(16383, val))
        sintable.append(val)
    data = struct.pack("<" + "h" * 2048, *sintable)

    # --- Radar angle table (640 entries + 640 mirrored) ---
    radarang = []
    for i in range(640):
        if i == 0:
            radarang.append(0)
        else:
            radarang.append(int(math.atan(float(i) / 160.0) * (512.0 / math.pi)))
    data += struct.pack("<" + "h" * 640, *radarang)

    mirror = [-radarang[639 - i] for i in range(640)]
    data += struct.pack("<" + "h" * 640, *mirror)

    # --- Font tables ---
    data += _generate_basic_font()
    data += _generate_small_font()

    # --- Brightness table ---
    data += _generate_britable()

    return data


def _generate_basic_font():
    """Generate a basic 8x8 font table (1024 bytes).

    Each char entry is 4 bytes: xofs (short) + width (short).
    256 chars * 4 bytes = 1024 bytes.
    """
    entries = []
    for i in range(256):
        if 32 <= i < 127:
            entries.append(struct.pack("<hh", 0, 8))  # xofs=0, width=8
        else:
            entries.append(struct.pack("<hh", 0, 0))  # non-printable
    return b"".join(entries)


def _generate_small_font():
    """Generate a small 4x6 font table (1024 bytes)."""
    entries = []
    for i in range(256):
        if 32 <= i < 127:
            entries.append(struct.pack("<hh", 0, 4))
        else:
            entries.append(struct.pack("<hh", 0, 0))
    return b"".join(entries)


def _generate_britable():
    """Generate brightness table (1024 bytes = 16 * 64)."""
    data = bytearray()
    for row in range(16):
        for col in range(64):
            val = min(63, int(col * (row + 1) / 16.0))
            data.append(val)
    return bytes(data)

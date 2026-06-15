# SPDX-License-Identifier: GPL-2.0-or-later
"""ART file format for BUILD engine tile archives.

ART format (version 1):
  - uint32: artversion = 1
  - uint32: numtiles (highest tile index with nonzero size + 1)
  - uint32: localtilestart
  - uint32: localtileend
  - int16[N]: tilesizx   (width of each tile)
  - int16[N]: tilesizy   (height of each tile)
  - uint32[N]: picanm    (animation data per tile)
  - pixel data for each tile concatenated (column-major order)

Column-major means for a WxH tile the bytes are:
  col0 (H bytes), col1 (H bytes), ..., colW-1 (H bytes)
"""

import struct


def create_art_file(tiles, localtilestart=0):
    """Create a BUILD engine ART file from tile data.

    Args:
        tiles: list of (width, height, picanm, pixel_data) tuples.
            pixel_data must be bytes of length width*height in column-major order.
        localtilestart: first tile number in this ART file.

    Returns:
        bytes: Complete ART file content.
    """
    num_tiles = len(tiles)
    localtileend = localtilestart + num_tiles - 1

    # numtiles = highest tile index with nonzero size + 1 (per EDITART.C)
    numtiles_val = 0
    for i in range(num_tiles - 1, -1, -1):
        w, h = tiles[i][0], tiles[i][1]
        if w >= 2 or h >= 2:
            numtiles_val = localtilestart + i + 1
            break

    header = struct.pack("<IIII", 1, numtiles_val, localtilestart, localtileend)

    sizex_data = b""
    sizey_data = b""
    picanm_data = b""
    pixel_data = b""

    for width, height, picanm, pixels in tiles:
        sizex_data += struct.pack("<h", width)
        sizey_data += struct.pack("<h", height)
        picanm_data += struct.pack("<I", picanm)
        if len(pixels) != width * height:
            raise ValueError(
                f"Pixel data length {len(pixels)} != {width}*{height}={width * height}"
            )
        pixel_data += pixels

    return header + sizex_data + sizey_data + picanm_data + pixel_data


def read_art_file(data):
    """Parse + structurally validate a BUILD ART archive (inverse of create_art_file).

    Returns a dict {artversion, numtiles, localtilestart, localtileend, tiles} where
    `tiles` is a list of (sizx, sizy, picanm). Raises ValueError if the archive is
    structurally invalid — header truncated, implausible/negative tile count or sizes,
    or (the core g-tile-audit guard) the concatenated pixel data length != the sum of
    sizx*sizy over the tile-size arrays. A short or over-long tile means corrupt art
    the engine would mis-read, so this catches asset-gen regressions deterministically.
    """
    if len(data) < 16:
        raise ValueError(f"ART too small for the 16-byte header: {len(data)} bytes")
    artversion, numtiles, localtilestart, localtileend = struct.unpack_from("<IIII", data, 0)
    if artversion != 1:
        raise ValueError(f"unsupported artversion {artversion} (expected 1)")
    n = localtileend - localtilestart + 1
    if n < 0 or n > 1_000_000:
        raise ValueError(
            f"implausible tile count {n} (localtilestart={localtilestart}, "
            f"localtileend={localtileend})")
    header_size = 16 + 8 * n   # 16 + N*(int16 sizx + int16 sizy + uint32 picanm)
    if len(data) < header_size:
        raise ValueError(
            f"ART truncated: need {header_size} header bytes for {n} tiles, have {len(data)}")
    off = 16
    sizx = struct.unpack_from(f"<{n}h", data, off); off += 2 * n
    sizy = struct.unpack_from(f"<{n}h", data, off); off += 2 * n
    picanm = struct.unpack_from(f"<{n}I", data, off); off += 4 * n
    expected_pixels = 0
    for i in range(n):
        if sizx[i] < 0 or sizy[i] < 0:
            raise ValueError(
                f"tile {localtilestart + i}: negative size {sizx[i]}x{sizy[i]}")
        expected_pixels += sizx[i] * sizy[i]
    actual_pixels = len(data) - header_size
    if actual_pixels != expected_pixels:
        raise ValueError(
            f"pixel data size mismatch: the header implies sum(sizx*sizy)="
            f"{expected_pixels} pixel bytes, but {actual_pixels} bytes follow the header "
            f"(tiles {localtilestart}..{localtileend}); corrupt or truncated art")
    return {
        "artversion": artversion,
        "numtiles": numtiles,
        "localtilestart": localtilestart,
        "localtileend": localtileend,
        "tiles": [(sizx[i], sizy[i], picanm[i]) for i in range(n)],
    }


def rgb_to_column_major(pixels_row_major, width, height):
    """Convert row-major indexed pixel array to column-major bytes.

    Args:
        pixels_row_major: flat list/bytes in row-major order (row0, row1, ...).
        width, height: tile dimensions.

    Returns:
        bytes in column-major order for the ART file.
    """
    result = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            result[x * height + y] = pixels_row_major[y * width + x]
    return bytes(result)

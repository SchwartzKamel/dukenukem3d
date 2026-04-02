"""Palette and colour quantisation utilities for BUILD engine.

Generates a Duke3D-compatible 256-colour palette and helper functions for
converting true-colour images to paletted pixel data.
"""

import struct
import math


def _ramp(start_rgb, end_rgb, steps):
    """Linear interpolation between two RGB triples."""
    out = []
    for i in range(steps):
        t = i / max(steps - 1, 1)
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)
        out.append((r, g, b))
    return out


def build_palette():
    """Build a 256-entry RGB palette (each component 0-255).

    Returns:
        list of 256 (r, g, b) tuples with components in 0-255 range.
    """
    pal = [(0, 0, 0)] * 256

    # 0: black / transparent
    pal[0] = (0, 0, 0)

    # 1-31: grayscale ramp
    for i in range(31):
        v = int((i / 30) * 255)
        pal[1 + i] = (v, v, v)

    # 32-47: red ramp
    for c in _ramp((32, 0, 0), (255, 64, 64), 16):
        pal[32 + _ramp((32, 0, 0), (255, 64, 64), 16).index(c)] = c
    ramp = _ramp((32, 0, 0), (255, 64, 64), 16)
    for i, c in enumerate(ramp):
        pal[32 + i] = c

    # 48-63: orange / brown
    ramp = _ramp((40, 24, 0), (255, 176, 64), 16)
    for i, c in enumerate(ramp):
        pal[48 + i] = c

    # 64-79: yellow
    ramp = _ramp((40, 40, 0), (255, 255, 64), 16)
    for i, c in enumerate(ramp):
        pal[64 + i] = c

    # 80-95: green
    ramp = _ramp((0, 32, 0), (64, 255, 64), 16)
    for i, c in enumerate(ramp):
        pal[80 + i] = c

    # 96-111: cyan
    ramp = _ramp((0, 32, 32), (64, 255, 255), 16)
    for i, c in enumerate(ramp):
        pal[96 + i] = c

    # 112-127: blue
    ramp = _ramp((0, 0, 32), (64, 64, 255), 16)
    for i, c in enumerate(ramp):
        pal[112 + i] = c

    # 128-143: purple
    ramp = _ramp((32, 0, 32), (200, 64, 255), 16)
    for i, c in enumerate(ramp):
        pal[128 + i] = c

    # 144-159: skin tones
    ramp = _ramp((80, 48, 32), (255, 200, 160), 16)
    for i, c in enumerate(ramp):
        pal[144 + i] = c

    # 160-175: brown / brick
    ramp = _ramp((40, 16, 8), (180, 100, 60), 16)
    for i, c in enumerate(ramp):
        pal[160 + i] = c

    # 176-191: dark metal / gray-blue
    ramp = _ramp((24, 28, 40), (128, 140, 180), 16)
    for i, c in enumerate(ramp):
        pal[176 + i] = c

    # 192-207: tan / sand
    ramp = _ramp((80, 64, 40), (240, 220, 180), 16)
    for i, c in enumerate(ramp):
        pal[192 + i] = c

    # 208-223: dark red / maroon
    ramp = _ramp((32, 0, 0), (160, 32, 32), 16)
    for i, c in enumerate(ramp):
        pal[208 + i] = c

    # 224-239: dark green / olive
    ramp = _ramp((16, 32, 0), (100, 140, 40), 16)
    for i, c in enumerate(ramp):
        pal[224 + i] = c

    # 240-253: bright colours for HUD / effects
    brights = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
        (255, 0, 255), (0, 255, 255), (255, 128, 0), (128, 255, 0),
        (0, 128, 255), (255, 0, 128), (128, 0, 255), (0, 255, 128),
        (255, 128, 128), (128, 255, 128),
    ]
    for i, c in enumerate(brights):
        pal[240 + i] = c

    # 254: white
    pal[254] = (255, 255, 255)
    # 255: transparent key
    pal[255] = (0, 0, 0)

    return pal


def create_palette_dat(palette_rgb=None):
    """Create a PALETTE.DAT file for Duke3D.

    Layout:
        - 768 bytes: 256 * (R, G, B) in VGA 6-bit format (0-63)
        - 2 bytes : numpalookups (int16 LE)
        - numpalookups * 256 bytes: shade tables (palookup)
        - 65536 bytes: translucency table

    Returns:
        bytes of the complete PALETTE.DAT.
    """
    if palette_rgb is None:
        palette_rgb = build_palette()

    # VGA palette: 6-bit per component (0-63)
    pal_bytes = bytearray()
    for r, g, b in palette_rgb:
        pal_bytes.append(r >> 2)
        pal_bytes.append(g >> 2)
        pal_bytes.append(b >> 2)

    # Shade tables -- 32 shade levels
    numpalookups = 32
    shade_data = bytearray()
    for shade in range(numpalookups):
        shade_factor = 1.0 - (shade / (numpalookups - 1))
        for idx in range(256):
            r, g, b = palette_rgb[idx]
            sr = int(r * shade_factor)
            sg = int(g * shade_factor)
            sb = int(b * shade_factor)
            shade_data.append(_nearest_color(sr, sg, sb, palette_rgb))
        

    # Translucency table (256x256)
    trans = bytearray(65536)
    for i in range(256):
        ri, gi, bi = palette_rgb[i]
        for j in range(256):
            rj, gj, bj = palette_rgb[j]
            mr = (ri + rj) >> 1
            mg = (gi + gj) >> 1
            mb = (bi + bj) >> 1
            trans[i * 256 + j] = _nearest_color(mr, mg, mb, palette_rgb)

    data = bytes(pal_bytes)
    data += struct.pack("<h", numpalookups)
    data += bytes(shade_data)
    data += bytes(trans)
    return data


def _nearest_color(r, g, b, palette):
    """Find the nearest palette index for an RGB colour (0-255 range)."""
    best = 0
    best_dist = float("inf")
    for idx in range(256):
        pr, pg, pb = palette[idx]
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_dist:
            best_dist = d
            best = idx
            if d == 0:
                break
    return best


# Build a lookup cache once to speed up quantisation
_palette_cache = None
_palette_list = None


def _ensure_cache(palette):
    global _palette_cache, _palette_list
    if _palette_list is palette and _palette_cache is not None:
        return
    _palette_cache = {}
    _palette_list = palette


def quantize_image(pil_image, palette=None):
    """Convert a PIL RGB image to 8-bit paletted pixels using our palette.

    Args:
        pil_image: PIL Image in RGB mode.
        palette: optional list of 256 (r,g,b). Defaults to build_palette().

    Returns:
        bytes of palette indices in row-major order.
    """
    if palette is None:
        palette = build_palette()

    img = pil_image.convert("RGB")
    width, height = img.size
    pixels = img.load()

    # Build a small cache for speed
    cache = {}
    result = bytearray(width * height)

    for y in range(height):
        for x in range(width):
            rgb = pixels[x, y]
            if rgb not in cache:
                cache[rgb] = _nearest_color(rgb[0], rgb[1], rgb[2], palette)
            result[y * width + x] = cache[rgb]

    return bytes(result)

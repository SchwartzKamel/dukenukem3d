# SPDX-License-Identifier: GPL-2.0-or-later
"""Palette and colour quantisation utilities for BUILD engine.

Generates a Duke3D-compatible 256-colour palette and helper functions for
converting true-colour images to paletted pixel data.
"""

import struct
import math
import warnings
import numpy as np


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

    # 1-31: grayscale ramp (start above zero so index 1 isn't black)
    for i in range(31):
        v = int(((i + 1) / 32) * 255)
        pal[1 + i] = (v, v, v)

    # 32-47: red ramp
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


def _validate_palette_input(palette):
    """Validate palette input for create_palette_dat.

    Enforces:
      - Exactly 256 entries
      - Each entry is a tuple with exactly 3 components (R, G, B)
      - Each component is an integer in range [0, 255]
      - Warns if duplicate index 0 (reserved transparency marker) appears
        outside indices 0 and 255 (255 is also reserved for transparency)

    Args:
        palette: List/tuple of RGB tuples to validate

    Raises:
        ValueError: If palette does not meet requirements
    """
    if not isinstance(palette, (list, tuple)):
        raise ValueError(
            f"Palette must be a list or tuple, got {type(palette).__name__}"
        )

    if len(palette) != 256:
        raise ValueError(
            f"Palette must contain exactly 256 entries, got {len(palette)}"
        )

    seen_zero = False
    for idx, entry in enumerate(palette):
        if not isinstance(entry, (list, tuple)):
            raise ValueError(
                f"Palette[{idx}]: Expected RGB tuple, got {type(entry).__name__}"
            )

        if len(entry) != 3:
            raise ValueError(
                f"Palette[{idx}]: RGB tuple must have exactly 3 components, "
                f"got {len(entry)}"
            )

        for comp_idx, component in enumerate(entry):
            if not isinstance(component, int):
                raise ValueError(
                    f"Palette[{idx}][{comp_idx}]: RGB component must be int, "
                    f"got {type(component).__name__} value {component!r}"
                )

            if not (0 <= component <= 255):
                raise ValueError(
                    f"Palette[{idx}][{comp_idx}]: RGB component must be in "
                    f"range [0, 255], got {component}"
                )

        # Warn on duplicate black at indices other than 0 and 255
        if idx not in (0, 255) and entry == (0, 0, 0):
            if not seen_zero:
                warnings.warn(
                    f"Palette[{idx}] = (0, 0, 0) duplicates the transparent "
                    f"key at index 0. This may be unintended.",
                    UserWarning,
                    stacklevel=3
                )
                seen_zero = True


def create_palette_dat(palette_rgb=None):
    """Create a PALETTE.DAT file for Duke3D.

    Layout:
        - 768 bytes: 256 * (R, G, B) in VGA 6-bit format (0-63)
        - 2 bytes : numpalookups (int16 LE)
        - numpalookups * 256 bytes: shade tables (palookup)
        - 65536 bytes: translucency table

    Args:
        palette_rgb: Optional list of 256 (r, g, b) tuples with components
                     in [0, 255]. Each tuple must have exactly 3 integer
                     components. Defaults to build_palette() if not provided.
                     See _validate_palette_input for exact requirements.

    Returns:
        bytes of the complete PALETTE.DAT.

    Raises:
        ValueError: If palette_rgb does not meet input validation requirements
                    (exactly 256 entries, each with 3 integer components
                    in range [0, 255]).
    """
    if palette_rgb is None:
        palette_rgb = build_palette()
    else:
        _validate_palette_input(palette_rgb)

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
    """Find the nearest palette index for an RGB colour (0-255 range).
    
    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)
        palette: List of 256 (r,g,b) tuples
    
    Returns:
        Nearest palette index (0-255)
    
    Raises:
        ValueError: If any RGB component is out of range [0, 255]
    """
    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
        raise ValueError(f"RGB values must be in range [0, 255], got R={r}, G={g}, B={b}")
    
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
    
    # Convert image to numpy array: shape (height, width, 3), dtype uint8
    arr = np.asarray(img, dtype=np.uint8)
    
    # Reshape to flat array of pixels: (height*width, 3)
    pixels_flat = arr.reshape(-1, 3)
    
    # Convert palette to numpy array for vectorized distance computation
    palette_arr = np.array(palette, dtype=np.int32)
    
    # Compute squared Euclidean distances between each pixel and palette entry
    # Shape: (num_pixels, 256)
    # Use squared distances to avoid sqrt (argmin is identical for sqrt and squared)
    pixels_int32 = pixels_flat.astype(np.int32)
    diffs = pixels_int32[:, np.newaxis, :] - palette_arr[np.newaxis, :, :]
    dists_squared = (diffs ** 2).sum(axis=2)
    
    # Find nearest palette index for each pixel
    indices = dists_squared.argmin(axis=1).astype(np.uint8)
    
    return bytes(indices)

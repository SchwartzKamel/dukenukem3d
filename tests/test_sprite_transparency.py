"""Sprite/object transparency guard — no black boxes around in-world art.

The BUILD engine draws every sprite (enemies, bosses, NPCs, effects, props,
item pickups) with palette index 255 as the transparency key. If the asset
pipeline emits a sprite tile on an opaque black background (index 0), the engine
paints a solid black box around the actor/item in the scene — the exact "black
backgrounds around objects" regression these tests gate.

Design — "pass the pass, fail the fail":
  * Sprite-category tiles MUST have transparent (index 255) corners/border, and a
    non-empty foreground. These assertions FAIL on the pre-fix pipeline (which
    quantized a black background to opaque index 0) and PASS after it.
  * Wall/floor/sky tiles MUST stay fully opaque (0% index 255) — a guard that the
    transparency key is applied to sprites only, never to tiled world surfaces.
  * A discrimination test proves the check is non-vacuous: a black-background
    sprite run through the plain (non-keyed) quantizer does NOT key to 255, so the
    pass is earned by the transparency path, not by the assertion being trivially true.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import generate_assets as ga
from palette import build_palette, quantize_image

TRANSPARENT_KEY_INDEX = 255

# Representative tiles per in-world sprite category (name -> human label).
SPRITE_TILE_NAMES = [
    # enemies
    "LIZTROOP", "OCTABRAIN", "PIGCOP", "DRONE", "NEWBEAST", "SHARK", "COMMANDER",
    # bosses
    "BOSS1", "BOSS2", "BOSS3",
    # characters / NPCs
    "APLAYER", "HOLODUKE", "SPACEMARINE",
    # effects (explosions / blood / fire / splashes)
    "EXPLOSION2", "COOLEXPLOSION1", "BLOOD", "FIRE", "WATERSPLASH2", "SHOTSPARK1",
    # props / destructibles / pickups
    "NUKEBARREL", "EXPLODINGBARREL", "REACTOR", "VENDMACHINE",
]

# Tiled world surfaces that MUST remain fully opaque (no transparency key).
OPAQUE_TILE_NAMES = [
    "W_SCREENBREAK", "DOORTILE1", "CLOUDYSKIES", "BIGFORCE", "FLOORSLIME",
]


@pytest.fixture(scope="module")
def palette():
    return build_palette()


@pytest.fixture(scope="module")
def game_tiles(palette):
    """All NAMES.H-driven tiles produced by the real generation path."""
    return ga.generate_game_tiles(palette)


@pytest.fixture(scope="module")
def names():
    return ga.parse_names_h()


def _indices(tile):
    """Column-major palette indices for a (w, h, picanm, pixels) tile."""
    w, h, _picanm, pixels = tile
    return w, h, np.frombuffer(pixels, dtype=np.uint8)


def _corners(w, h, arr):
    """The four corner indices in BUILD column-major (index = x*h + y) layout."""
    return [int(arr[0]), int(arr[(w - 1) * h]), int(arr[h - 1]), int(arr[w * h - 1])]


def _border_fraction_transparent(w, h, arr):
    grid = arr.reshape(w, h)  # column-major: axis0 = x, axis1 = y
    border = np.concatenate([grid[0, :], grid[-1, :], grid[:, 0], grid[:, -1]])
    return float((border == TRANSPARENT_KEY_INDEX).mean())


# ---------------------------------------------------------------------------
# Sprites: transparent background, no black box (fails on the pre-fix pipeline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", SPRITE_TILE_NAMES)
def test_sprite_corners_are_transparent(name, names, game_tiles):
    """Every sprite corner is the 255 transparency key (not an opaque black box)."""
    tnum = names.get(name)
    if tnum is None or tnum not in game_tiles:
        pytest.skip(f"{name}: tile not generated in this NAMES.H")
    w, h, arr = _indices(game_tiles[tnum])
    corners = _corners(w, h, arr)
    assert corners == [TRANSPARENT_KEY_INDEX] * 4, (
        f"{name} (tile {tnum}) has a non-transparent corner {corners}; a black "
        f"background paints a box around the sprite in-world."
    )


@pytest.mark.parametrize("name", SPRITE_TILE_NAMES)
def test_sprite_border_is_transparent(name, names, game_tiles):
    """The sprite's outer border is overwhelmingly transparent background."""
    tnum = names.get(name)
    if tnum is None or tnum not in game_tiles:
        pytest.skip(f"{name}: tile not generated in this NAMES.H")
    w, h, arr = _indices(game_tiles[tnum])
    frac = _border_fraction_transparent(w, h, arr)
    assert frac > 0.95, f"{name} (tile {tnum}) border only {frac:.2%} transparent"


@pytest.mark.parametrize("name", SPRITE_TILE_NAMES)
def test_sprite_foreground_preserved(name, names, game_tiles):
    """Keying the background must not erase the sprite itself."""
    tnum = names.get(name)
    if tnum is None or tnum not in game_tiles:
        pytest.skip(f"{name}: tile not generated in this NAMES.H")
    _w, _h, arr = _indices(game_tiles[tnum])
    opaque = int((arr != TRANSPARENT_KEY_INDEX).sum())
    assert opaque > 0, f"{name} (tile {tnum}) keyed out its entire foreground"
    # Sprites are mostly background; a fully-opaque tile means the key did nothing.
    assert int((arr == TRANSPARENT_KEY_INDEX).sum()) > 0, (
        f"{name} (tile {tnum}) has no transparent pixels"
    )


def test_all_sprite_category_tiles_transparent(names, game_tiles):
    """Comprehensive sweep: EVERY tile classified into a sprite category has a
    transparent corner. Guards against a future sprite generator that forgets the
    transparency key (the "fix all things" guarantee)."""
    num_to_name = {}
    for nm, num in names.items():
        num_to_name.setdefault(num, nm)

    sprite_cats = ga._SPRITE_CATEGORIES
    offenders = []
    checked = 0
    for tnum, tile in game_tiles.items():
        nm = num_to_name.get(tnum)
        if nm is None:
            continue
        _w2, _h2, category = ga._classify_tile(nm, tnum)
        if category not in sprite_cats:
            continue
        w, h, arr = _indices(tile)
        if w == 0 or h == 0:
            continue
        checked += 1
        if _corners(w, h, arr) != [TRANSPARENT_KEY_INDEX] * 4:
            offenders.append((nm, tnum, category))

    assert checked > 20, f"expected many sprite tiles, only checked {checked}"
    assert not offenders, (
        f"{len(offenders)} sprite tile(s) have an opaque (black-box) background: "
        + ", ".join(f"{n}#{t}({c})" for n, t, c in offenders[:25])
    )


# ---------------------------------------------------------------------------
# Item / weapon pickups (SPRITE_DEFS path via proc_sprite_placeholder)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tile_num,w,h,desc", ga.SPRITE_DEFS)
def test_pickup_sprite_is_transparent(tile_num, w, h, desc, palette):
    """The SPRITE_DEFS pickup path (proc_sprite_placeholder) keys its background
    to 255 — the shipped pickups (health, ammo, armor, access chips, weapons) no
    longer render inside a black box."""
    img = ga.proc_sprite_placeholder(w, h, desc, 200 + tile_num)
    arr = np.frombuffer(ga._quantize_with_transparency(img, palette), dtype=np.uint8)
    assert int(arr[0]) == TRANSPARENT_KEY_INDEX, (
        f"pickup tile {tile_num} ({desc}) corner is opaque {int(arr[0])}"
    )
    assert int((arr == TRANSPARENT_KEY_INDEX).sum()) > 0, "no transparent background"
    assert int((arr != TRANSPARENT_KEY_INDEX).sum()) > 0, "foreground keyed away"


# ---------------------------------------------------------------------------
# World surfaces stay opaque (the key is sprite-only)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", OPAQUE_TILE_NAMES)
def test_wall_floor_tiles_stay_opaque(name, names, game_tiles):
    """Tiled wall/floor/sky surfaces must contain no transparency-key pixels."""
    tnum = names.get(name)
    if tnum is None or tnum not in game_tiles:
        pytest.skip(f"{name}: tile not generated in this NAMES.H")
    _w, _h, arr = _indices(game_tiles[tnum])
    n255 = int((arr == TRANSPARENT_KEY_INDEX).sum())
    assert n255 == 0, (
        f"{name} (tile {tnum}) has {n255} transparent pixels; a tiled surface "
        f"must be fully opaque or it punches holes in walls/floors."
    )


# ---------------------------------------------------------------------------
# Discrimination — the assertion is earned, not vacuous ("fail the fail")
# ---------------------------------------------------------------------------

def test_black_background_would_fail(palette):
    """The pre-fix behavior — a black background through the PLAIN quantizer —
    does NOT produce the 255 transparency key, so the passing tests above are
    only satisfied by the transparency path, never trivially."""
    black_bg = ga.Image.new("RGB", (32, 32), (0, 0, 0))
    arr = np.frombuffer(quantize_image(black_bg, palette), dtype=np.uint8)
    assert int(arr[0]) != TRANSPARENT_KEY_INDEX, (
        "an opaque black background must not quantize to the transparency key; "
        "if it did, these tests could not distinguish the bug from the fix."
    )


def test_magenta_key_quantizes_to_255(palette):
    """The magenta key (255,0,255) is what the transparency quantizer maps to 255."""
    keyed = ga.Image.new("RGB", (8, 8), (255, 0, 255))
    arr = np.frombuffer(ga._quantize_with_transparency(keyed, palette), dtype=np.uint8)
    assert (arr == TRANSPARENT_KEY_INDEX).all(), "magenta key did not map to index 255"

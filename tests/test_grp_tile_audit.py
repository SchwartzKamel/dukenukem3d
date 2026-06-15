"""g-tile-audit — GRP tile-integrity validator.

`art_format.read_art_file()` parses + structurally validates a BUILD ART archive: the
concatenated pixel data must equal sum(sizx*sizy) over the header's tile-size arrays.
`audit_grp_tiles.audit_grp()` runs it over every TILES*.ART in a GRP. Together they guard
against asset-gen regressions that emit a truncated/over-long tile (corrupt art the engine
would mis-read).
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from art_format import create_art_file, read_art_file
from grp_format import read_grp, create_grp


def _grp_path():
    for c in (PROJECT_ROOT / "DUKE3D.GRP", PROJECT_ROOT / "generated_assets" / "DUKE3D.GRP"):
        if c.is_file():
            return c
    return None


def test_read_art_roundtrip_valid():
    """A well-formed ART (from create_art_file) parses back to the same tile sizes."""
    tiles = [(2, 3, 0, bytes(6)), (4, 4, 0, bytes(16)), (0, 0, 0, b"")]
    info = read_art_file(create_art_file(tiles, localtilestart=10))
    assert info["localtilestart"] == 10 and info["localtileend"] == 12
    assert [(w, h) for w, h, _ in info["tiles"]] == [(2, 3), (4, 4), (0, 0)]


def test_read_art_detects_truncated_pixels():
    """Dropping pixel bytes (a short tile) must fail the sum(sizx*sizy) check."""
    good = create_art_file([(2, 3, 0, bytes(6)), (4, 4, 0, bytes(16))], localtilestart=0)
    with pytest.raises(ValueError, match="pixel data size mismatch"):
        read_art_file(good[:-4])


def test_read_art_detects_bad_version():
    """A non-1 artversion is rejected."""
    good = bytearray(create_art_file([(1, 1, 0, bytes(1))], localtilestart=0))
    struct.pack_into("<I", good, 0, 2)   # artversion 1 -> 2
    with pytest.raises(ValueError, match="artversion"):
        read_art_file(bytes(good))


def test_current_grp_tiles_valid():
    """The shipped GRP's TILES*.ART archives all validate (the live guard)."""
    grp = _grp_path()
    if grp is None:
        pytest.skip("DUKE3D.GRP not generated")
    import audit_grp_tiles
    ok, lines = audit_grp_tiles.audit_grp(grp.read_bytes())
    assert ok, "GRP tile audit failed:\n" + "\n".join(lines)
    assert any("TILES000.ART" in ln for ln in lines), f"TILES000.ART not audited: {lines}"


def test_audit_detects_corrupt_tile_in_grp():
    """Non-vacuous: truncating TILES000.ART's pixel data makes the GRP audit FAIL."""
    grp = _grp_path()
    if grp is None:
        pytest.skip("DUKE3D.GRP not generated")
    import audit_grp_tiles
    files = read_grp(grp.read_bytes())
    files["TILES000.ART"] = files["TILES000.ART"][:-16]   # drop pixel bytes from the tail
    ok, lines = audit_grp_tiles.audit_grp(create_grp(files))
    assert not ok, "corrupt (truncated) tile archive was not detected:\n" + "\n".join(lines)
    assert any("FAIL" in ln and "TILES000.ART" in ln for ln in lines), lines

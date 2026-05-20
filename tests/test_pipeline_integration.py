"""Integration test: run the full asset pipeline and verify output."""
import os
import struct
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.slow
def test_full_pipeline_no_ai(tmp_path, monkeypatch):
    """Run the full asset pipeline with --no-ai and verify outputs."""
    # Use absolute path to generate_assets.py script
    generate_script = os.path.join(PROJECT_ROOT, "tools", "generate_assets.py")
    result = subprocess.run(
        [sys.executable, generate_script, "--no-ai", "--output", str(tmp_path)],
        cwd=PROJECT_ROOT,
        capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, f"Pipeline failed:\n{result.stderr}\n{result.stdout}"
    assert "Done!" in result.stdout

    # Check GRP exists and has reasonable size in the output directory
    grp_path = tmp_path / "DUKE3D.GRP"
    assert grp_path.exists(), f"GRP not found at {grp_path}"
    grp_size = grp_path.stat().st_size
    assert grp_size > 100000, f"GRP too small: {grp_size} bytes"

    # Verify GRP magic
    with open(grp_path, "rb") as f:
        magic = f.read(12)
    assert magic == b"KenSilverman"

    # Check individual generated files
    expected_files = [
        "TILES000.ART", "PALETTE.DAT", "TABLES.DAT",
        "E1L1.MAP", "GAME.CON", "DEFS.CON", "DUKE3D.GRP"
    ]
    for fname in expected_files:
        fpath = tmp_path / fname
        assert fpath.exists(), f"Missing: {fpath}"
        assert fpath.stat().st_size > 0, f"Empty: {fpath}"


@pytest.mark.slow
def test_generated_art_is_valid(tmp_path, monkeypatch):
    """The generated TILES000.ART has valid header."""
    generate_script = os.path.join(PROJECT_ROOT, "tools", "generate_assets.py")
    art_path = tmp_path / "TILES000.ART"
    if not art_path.exists():
        # Run pipeline first
        subprocess.run(
            [sys.executable, generate_script, "--no-ai", "--output", str(tmp_path)],
            cwd=PROJECT_ROOT, capture_output=True, timeout=120
        )

    with open(art_path, "rb") as f:
        data = f.read(16)

    version, numtiles_legacy, start, end = struct.unpack("<iiii", data)
    assert version == 1
    assert numtiles_legacy > 0  # highest tile with nonzero size + 1
    assert start == 0
    tile_count = end - start + 1
    assert tile_count > 0
    assert end == tile_count - 1


@pytest.mark.slow
def test_generated_palette_is_valid(tmp_path, monkeypatch):
    """The generated PALETTE.DAT has valid VGA palette."""
    generate_script = os.path.join(PROJECT_ROOT, "tools", "generate_assets.py")
    pal_path = tmp_path / "PALETTE.DAT"
    if not pal_path.exists():
        subprocess.run(
            [sys.executable, generate_script, "--no-ai", "--output", str(tmp_path)],
            cwd=PROJECT_ROOT, capture_output=True, timeout=120
        )

    with open(pal_path, "rb") as f:
        data = f.read(768)

    # All palette values should be 0-63 (VGA 6-bit)
    for i, b in enumerate(data):
        assert 0 <= b <= 63, f"Palette byte {i} = {b} exceeds VGA range"


@pytest.mark.slow
def test_generated_map_is_valid(tmp_path, monkeypatch):
    """The generated E1L1.MAP has correct version."""
    generate_script = os.path.join(PROJECT_ROOT, "tools", "generate_assets.py")
    map_path = tmp_path / "E1L1.MAP"
    if not map_path.exists():
        subprocess.run(
            [sys.executable, generate_script, "--no-ai", "--output", str(tmp_path)],
            cwd=PROJECT_ROOT, capture_output=True, timeout=120
        )

    with open(map_path, "rb") as f:
        data = f.read(4)

    version = struct.unpack("<i", data)[0]
    assert version == 7

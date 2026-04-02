"""Integration test: run the full asset pipeline and verify output."""
import os
import struct
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_full_pipeline_no_ai():
    """Run the full asset pipeline with --no-ai and verify outputs."""
    result = subprocess.run(
        [sys.executable, "tools/generate_assets.py", "--no-ai"],
        cwd=PROJECT_ROOT,
        capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, f"Pipeline failed:\n{result.stderr}\n{result.stdout}"
    assert "Done!" in result.stdout

    # Check GRP exists and has reasonable size
    grp_path = os.path.join(PROJECT_ROOT, "DUKE3D.GRP")
    assert os.path.exists(grp_path)
    grp_size = os.path.getsize(grp_path)
    assert grp_size > 100000, f"GRP too small: {grp_size} bytes"

    # Verify GRP magic
    with open(grp_path, "rb") as f:
        magic = f.read(12)
    assert magic == b"KenSilverman"

    # Check individual generated files
    gen_dir = os.path.join(PROJECT_ROOT, "generated_assets")
    expected_files = [
        "TILES000.ART", "PALETTE.DAT", "TABLES.DAT",
        "E1L1.MAP", "GAME.CON", "DEFS.CON", "DUKE3D.GRP"
    ]
    for fname in expected_files:
        fpath = os.path.join(gen_dir, fname)
        assert os.path.exists(fpath), f"Missing: {fpath}"
        assert os.path.getsize(fpath) > 0, f"Empty: {fpath}"


def test_generated_art_is_valid():
    """The generated TILES000.ART has valid header."""
    art_path = os.path.join(PROJECT_ROOT, "generated_assets", "TILES000.ART")
    if not os.path.exists(art_path):
        # Run pipeline first
        subprocess.run(
            [sys.executable, "tools/generate_assets.py", "--no-ai"],
            cwd=PROJECT_ROOT, capture_output=True, timeout=120
        )

    with open(art_path, "rb") as f:
        data = f.read(16)

    version, numtiles_legacy, start, end = struct.unpack("<iiii", data)
    assert version == 1
    assert numtiles_legacy == 0  # legacy field
    assert start == 0
    tile_count = end - start + 1
    assert tile_count > 0
    assert end == tile_count - 1


def test_generated_palette_is_valid():
    """The generated PALETTE.DAT has valid VGA palette."""
    pal_path = os.path.join(PROJECT_ROOT, "generated_assets", "PALETTE.DAT")
    if not os.path.exists(pal_path):
        subprocess.run(
            [sys.executable, "tools/generate_assets.py", "--no-ai"],
            cwd=PROJECT_ROOT, capture_output=True, timeout=120
        )

    with open(pal_path, "rb") as f:
        data = f.read(768)

    # All palette values should be 0-63 (VGA 6-bit)
    for i, b in enumerate(data):
        assert 0 <= b <= 63, f"Palette byte {i} = {b} exceeds VGA range"


def test_generated_map_is_valid():
    """The generated E1L1.MAP has correct version."""
    map_path = os.path.join(PROJECT_ROOT, "generated_assets", "E1L1.MAP")
    if not os.path.exists(map_path):
        subprocess.run(
            [sys.executable, "tools/generate_assets.py", "--no-ai"],
            cwd=PROJECT_ROOT, capture_output=True, timeout=120
        )

    with open(map_path, "rb") as f:
        data = f.read(4)

    version = struct.unpack("<i", data)[0]
    assert version == 7

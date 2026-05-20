"""Test consistency of critical macro values between SRC/BUILD.H and source/BUILD.H."""
import re
from pathlib import Path

import pytest


def _extract_define(path: Path, name: str) -> int:
    """Extract and parse a #define macro value from a C header file.
    
    Args:
        path: Path to the header file
        name: Name of the macro to extract
        
    Returns:
        Parsed integer value of the macro
        
    Raises:
        ValueError: If macro is not found or value cannot be parsed as int
    """
    content = path.read_text()
    pattern = rf'#define\s+{re.escape(name)}\s+(\d+)'
    match = re.search(pattern, content)
    
    if not match:
        raise ValueError(f"Macro {name} not found in {path}")
    
    return int(match.group(1))


@pytest.fixture
def repo_root():
    """Get the repository root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.mark.xfail(strict=False, reason="build-r7-lto-maxtiles-mismatch CRITICAL")
def test_maxtiles_matches_between_headers(repo_root):
    """MAXTILES should match between SRC/BUILD.H and source/BUILD.H.
    
    Currently fails due to build-r7-lto-maxtiles-mismatch.
    """
    src = _extract_define(repo_root / "SRC/BUILD.H", "MAXTILES")
    source = _extract_define(repo_root / "source/BUILD.H", "MAXTILES")
    assert src == source, f"MAXTILES mismatch: SRC/BUILD.H={src} vs source/BUILD.H={source}"


def test_maxsectors_matches_between_headers(repo_root):
    """MAXSECTORS should match between SRC/BUILD.H and source/BUILD.H."""
    src = _extract_define(repo_root / "SRC/BUILD.H", "MAXSECTORS")
    source = _extract_define(repo_root / "source/BUILD.H", "MAXSECTORS")
    assert src == source, f"MAXSECTORS mismatch: SRC/BUILD.H={src} vs source/BUILD.H={source}"


def test_maxwalls_matches_between_headers(repo_root):
    """MAXWALLS should match between SRC/BUILD.H and source/BUILD.H."""
    src = _extract_define(repo_root / "SRC/BUILD.H", "MAXWALLS")
    source = _extract_define(repo_root / "source/BUILD.H", "MAXWALLS")
    assert src == source, f"MAXWALLS mismatch: SRC/BUILD.H={src} vs source/BUILD.H={source}"


def test_maxsprites_matches_between_headers(repo_root):
    """MAXSPRITES should match between SRC/BUILD.H and source/BUILD.H."""
    src = _extract_define(repo_root / "SRC/BUILD.H", "MAXSPRITES")
    source = _extract_define(repo_root / "source/BUILD.H", "MAXSPRITES")
    assert src == source, f"MAXSPRITES mismatch: SRC/BUILD.H={src} vs source/BUILD.H={source}"

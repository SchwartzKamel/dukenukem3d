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


@pytest.mark.parametrize("constant_name", [
    "MAXSECTORS",
    "MAXWALLS",
    "MAXSPRITES",
    pytest.param("MAXTILES", marks=pytest.mark.xfail(strict=False, reason="build-r7-lto-maxtiles-mismatch CRITICAL")),
    "MAXSTATUS",
    "MAXSPRITESONSCREEN",
])
def test_build_h_constants_match_between_headers(repo_root, constant_name):
    """BUILD.H constants should match between SRC/BUILD.H and source/BUILD.H.
    
    MAXTILES is expected to fail due to build-r7-lto-maxtiles-mismatch.
    All other constants should match perfectly.
    """
    src = _extract_define(repo_root / "SRC/BUILD.H", constant_name)
    source = _extract_define(repo_root / "source/BUILD.H", constant_name)
    assert src == source, f"{constant_name} mismatch: SRC/BUILD.H={src} vs source/BUILD.H={source}"

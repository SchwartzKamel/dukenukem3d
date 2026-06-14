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
    content = path.read_text(encoding="utf-8")
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
    # test-r14-xpass-maxtiles-promotion: was xfail, now pass
    # was xfail (cycle 42): build-r7-lto-maxtiles-mismatch CRITICAL — closed by cycle-42 MAXTILES abort()
    "MAXTILES",
    "MAXSTATUS",
    "MAXSPRITESONSCREEN",
])
def test_build_h_constants_match_between_headers(repo_root, constant_name):
    """BUILD.H constants should match between SRC/BUILD.H and source/BUILD.H.
    
    All constants must match perfectly, including MAXTILES (now enforced by
    cycle-42 Stage 3 abort() in the constructor).
    """
    src = _extract_define(repo_root / "SRC/BUILD.H", constant_name)
    source = _extract_define(repo_root / "source/BUILD.H", constant_name)
    assert src == source, f"{constant_name} mismatch: SRC/BUILD.H={src} vs source/BUILD.H={source}"

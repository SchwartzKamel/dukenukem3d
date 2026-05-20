"""Test link-time MAXTILES assertion mechanism.

This test suite validates that the link-time MAXTILES assertion infrastructure
is correctly in place. Stage 1 (current) will detect the mismatch and xfail
until Stage 2 unifies the headers.

See docs/audits/build-system-r12.md for the 3-stage remediation roadmap.
"""
import re
from pathlib import Path

import pytest


def _extract_maxtiles(path: Path) -> int:
    """Extract MAXTILES value from a C header file.
    
    Args:
        path: Path to the header file
        
    Returns:
        Parsed integer value of MAXTILES
        
    Raises:
        ValueError: If MAXTILES is not found or value cannot be parsed as int
    """
    content = path.read_text()
    match = re.search(r'#define\s+MAXTILES\s+(\d+)', content)
    if not match:
        raise ValueError(f"MAXTILES not found in {path}")
    return int(match.group(1))


@pytest.fixture
def repo_root():
    """Get the repository root directory."""
    return Path(__file__).resolve().parent.parent


def test_maxtiles_guard_constructor_present(repo_root):
    """Verify that the link-time assertion constructor is implemented.
    
    The constructor function check_maxtiles_assertion should be present
    in compat/maxtiles_guard.c to fire at program initialization.
    """
    guard_file = repo_root / "compat/maxtiles_guard.c"
    assert guard_file.exists(), "compat/maxtiles_guard.c does not exist"
    
    content = guard_file.read_text()
    assert "check_maxtiles_assertion" in content, \
        "Constructor function check_maxtiles_assertion not found in compat/maxtiles_guard.c"
    
    # Verify the __attribute__((constructor)) annotation is present
    assert "__attribute__((constructor))" in content, \
        "GCC constructor attribute not found in compat/maxtiles_guard.c"


def test_maxtiles_values_match_between_headers(repo_root):
    """Verify MAXTILES is identical in SRC/BUILD.H and source/BUILD.H.
    
    This test is expected to fail (xfail) under the current state where:
    - SRC/BUILD.H (engine):    MAXTILES = 9216
    - source/BUILD.H (game):   MAXTILES = 6144
    
    Stage 1 detects this mismatch via the constructor, which fires at
    program initialization. This test documents the expected failure until
    Stage 2 (header unification) resolves the conflict.
    """
    src_maxtiles = _extract_maxtiles(repo_root / "SRC/BUILD.H")
    source_maxtiles = _extract_maxtiles(repo_root / "source/BUILD.H")
    
    assert src_maxtiles == source_maxtiles, (
        f"MAXTILES mismatch: SRC/BUILD.H={src_maxtiles} vs source/BUILD.H={source_maxtiles} "
        f"(engine=9216, game=6144 per Stage 1 expectation)"
    )


def test_maxtiles_values_are_reasonable(repo_root):
    """Verify both MAXTILES values are reasonable (6144 or 9216).
    
    This guards against accidental corruption of the header files.
    Valid values are 6144 (game-centric) or 9216 (engine-centric).
    """
    src_maxtiles = _extract_maxtiles(repo_root / "SRC/BUILD.H")
    source_maxtiles = _extract_maxtiles(repo_root / "source/BUILD.H")
    
    assert src_maxtiles in [6144, 9216], \
        f"SRC/BUILD.H MAXTILES={src_maxtiles} is unexpected"
    
    assert source_maxtiles in [6144, 9216], \
        f"source/BUILD.H MAXTILES={source_maxtiles} is unexpected"

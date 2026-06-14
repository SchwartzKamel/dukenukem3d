"""Test runtime bounds checking in makepalookup() bounds guard.

Cycle 111 added static bounds guards to makepalookup() in SRC/ENGINE.C:7568:
  if (palnum < 0 || palnum >= MAXPALOOKUPS) return;

This test creates a C harness that simulates the guard logic and validates
it against negative, boundary, and overflow values of palnum.

MAXPALOOKUPS = 256 (from SRC/BUILD.H:20)

Test cases:
  - Guard must trigger (return without crashing):
    palnum = -1, -100, -128, -2147483648 (INT_MIN)
    palnum = 256, 257, 512 (>= MAXPALOOKUPS)
  
  - Guard must NOT trigger (function proceeds):
    palnum = 0, 1, 255 (MAXPALOOKUPS-1)
"""

import subprocess
import os
import tempfile
import pytest
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.slow
def test_makepalookup_bounds_guard(compiled_makepalookup_harness):
    """Run cached C harness to verify makepalookup() bounds guard.
    
    The guard at SRC/ENGINE.C:7568 checks:
      if (palnum < 0 || palnum >= MAXPALOOKUPS) return;
    
    This test verifies that the guard correctly rejects OOB values.
    
    Uses a session-scoped fixture that compiles once per pytest session,
    dramatically reducing test startup overhead.
    """
    out_file = compiled_makepalookup_harness
    
    # Run test harness
    result = subprocess.run(
        [str(out_file)],
        capture_output=True, text=True, timeout=10
    )
    
    # Print output for debugging
    print("\n--- Test Harness Output ---")
    print(result.stdout)
    if result.stderr:
        print("--- Stderr ---")
        print(result.stderr)
    print("--- End Output ---\n")
    
    # Verify successful completion
    assert result.returncode == 0, (
        f"Test harness exited with code {result.returncode}.\n"
        f"Output:\n{result.stdout}\n"
        f"Stderr:\n{result.stderr}"
    )
    
    # Verify expected output
    assert "ALL BOUNDS GUARD CHECKS PASSED" in result.stdout, (
        f"Expected success message not found in output:\n{result.stdout}"
    )


@pytest.mark.slow
def test_makepalookup_guard_location_exists():
    """Verify the bounds guard exists at SRC/ENGINE.C:7568.
    
    This is a static verification that the guard is present in the source.
    """
    engine_c = os.path.join(PROJECT_ROOT, "SRC", "ENGINE.C")
    
    if not os.path.exists(engine_c):
        pytest.skip(f"{engine_c} not found")
    
    with open(engine_c, "r", errors="replace", encoding="utf-8") as f:
        lines = f.readlines()
    
    # The guard should be in the makepalookup function
    # Check around line 7568
    guard_pattern = "if (palnum < 0 || palnum >= MAXPALOOKUPS) return;"
    
    # Look in a range around the expected line
    found = False
    for i, line in enumerate(lines):
        if guard_pattern in line:
            found = True
            print(f"Guard found at line {i + 1}: {line.rstrip()}")
            break
    
    assert found, (
        f"Bounds guard not found in {engine_c}. "
        f"Expected pattern: {guard_pattern}"
    )


@pytest.mark.slow
def test_premap_guard_location_exists():
    """Verify the bounds guard also exists in source/PREMAP.C:1230.
    
    Cycle 111 also added a similar guard to PREMAP.C.
    """
    premap_c = os.path.join(PROJECT_ROOT, "source", "PREMAP.C")
    
    if not os.path.exists(premap_c):
        pytest.skip(f"{premap_c} not found")
    
    with open(premap_c, "r", errors="replace", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Look for the guard in PREMAP.C
    guard_pattern = "if (look_pos < 0 || look_pos >= MAXPALOOKUPS) continue;"
    
    found = False
    for i, line in enumerate(lines):
        if guard_pattern in line:
            found = True
            print(f"Guard found at line {i + 1}: {line.rstrip()}")
            break
    
    assert found, (
        f"Bounds guard not found in {premap_c}. "
        f"Expected pattern: {guard_pattern}"
    )


def test_maxpalookups_value():
    """Verify MAXPALOOKUPS is defined as 256 in SRC/BUILD.H."""
    build_h = os.path.join(PROJECT_ROOT, "SRC", "BUILD.H")
    
    if not os.path.exists(build_h):
        pytest.skip(f"{build_h} not found")
    
    with open(build_h, "r", errors="replace", encoding="utf-8") as f:
        content = f.read()
    
    # Check that MAXPALOOKUPS is defined as 256
    assert "#define MAXPALOOKUPS 256" in content, (
        f"MAXPALOOKUPS not defined as 256 in {build_h}"
    )

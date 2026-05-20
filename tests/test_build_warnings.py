#!/usr/bin/env python3
"""
Build warning regression test.

Validates that the number of LTO type-mismatch warnings stays below baseline.
This test helps prevent regression of issues fixed in build-r16-lto-type-mismatch.
"""

import subprocess
import re
import sys
import os

def run_build():
    """Run a clean build and capture all output."""
    # Change to repo root
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)
    
    # Run clean build
    try:
        result = subprocess.run(
            ['bash', '-c', 'make clean && make -j$(nproc) 2>&1'],
            capture_output=True,
            text=True,
            timeout=300
        )
        output = result.stdout + result.stderr
        return output
    except subprocess.TimeoutExpired:
        raise RuntimeError("Build timed out after 5 minutes")

def count_lto_warnings(output):
    """Count LTO type-mismatch warnings in build output."""
    # Match patterns like:
    # - "warning: type of 'X' does not match original declaration [-Wlto-type-mismatch]"
    pattern = r"warning:.*type.*does not match.*\[-Wlto-type-mismatch\]"
    matches = re.findall(pattern, output, re.IGNORECASE)
    return len(matches)

def test_build_lto_warnings():
    """Test that LTO type-mismatch warnings are at or below baseline."""
    print("Running build warning regression test...")
    output = run_build()
    
    warning_count = count_lto_warnings(output)
    baseline = 0  # After fix-r16, this should be 0
    
    print(f"LTO type-mismatch warnings found: {warning_count}")
    print(f"Baseline (max allowed): {baseline}")
    
    if warning_count > baseline:
        print("\n❌ FAILURE: LTO type-mismatch warnings exceeded baseline")
        print("\nWarnings detected:")
        for line in output.split('\n'):
            if 'lto-type-mismatch' in line.lower():
                print(f"  {line}")
        sys.exit(1)
    
    print("✅ PASS: Build has no LTO type-mismatch warnings")
    assert warning_count <= baseline, f"Found {warning_count} LTO warnings, expected ≤ {baseline}"

if __name__ == '__main__':
    try:
        test_build_lto_warnings()
    except Exception as e:
        print(f"❌ Test failed with error: {e}", file=sys.stderr)
        sys.exit(1)

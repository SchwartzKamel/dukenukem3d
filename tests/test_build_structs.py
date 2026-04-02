"""Tests to verify BUILD engine struct sizes match expected binary format.

These tests compile and run a small C program that checks struct sizes,
ensuring 64-bit compatibility is maintained.
"""
import subprocess
import os
import tempfile

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_struct_sizes():
    """Compile and run a C program to verify struct sizes."""
    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <assert.h>
#include "BUILD.H"

int main() {
    printf("sizeof(sectortype) = %zu (expected 40)\n", sizeof(sectortype));
    printf("sizeof(walltype) = %zu (expected 32)\n", sizeof(walltype));
    printf("sizeof(spritetype) = %zu (expected 44)\n", sizeof(spritetype));

    assert(sizeof(sectortype) == 40);
    assert(sizeof(walltype) == 32);
    assert(sizeof(spritetype) == 44);

    printf("ALL STRUCT SIZE CHECKS PASSED\n");
    return 0;
}
"""
    c_file = os.path.join(PROJECT_ROOT, "_test_structs.c")
    out_file = os.path.join(PROJECT_ROOT, "_test_structs")
    try:
        with open(c_file, "w") as f:
            f.write(c_code)

        result = subprocess.run(
            ["gcc", "-std=gnu89", f"-I{PROJECT_ROOT}/SRC", f"-I{PROJECT_ROOT}/compat",
             "-x", "c", c_file, "-o", out_file],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        result = subprocess.run([out_file], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Struct size check failed: {result.stdout}\n{result.stderr}"
        assert "ALL STRUCT SIZE CHECKS PASSED" in result.stdout
    finally:
        if os.path.exists(c_file):
            os.unlink(c_file)
        if os.path.exists(out_file):
            os.unlink(out_file)


def test_binary_exists():
    """The duke3d binary should exist after building."""
    binary = os.path.join(PROJECT_ROOT, "duke3d")
    assert os.path.exists(binary), "duke3d binary not found — run 'make' first"


def test_binary_is_executable():
    """The duke3d binary should be executable."""
    binary = os.path.join(PROJECT_ROOT, "duke3d")
    if os.path.exists(binary):
        assert os.access(binary, os.X_OK), "duke3d is not executable"

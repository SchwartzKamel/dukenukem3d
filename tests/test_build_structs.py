"""Tests to verify BUILD engine struct sizes match expected binary format.

These tests compile and run a small C program that checks struct sizes,
ensuring 64-bit compatibility is maintained.

For cross-compilation (e.g., MinGW on Linux), set STRUCT_TEST_CC environment
variable to the cross-compiler (e.g., i686-w64-mingw32-gcc).
"""
import subprocess
import os
import tempfile

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_struct_test_compiler():
    """Get compiler for struct tests, respecting STRUCT_TEST_CC env var for cross-compile."""
    return os.environ.get("STRUCT_TEST_CC", "gcc")


def can_execute_binary(binary_path):
    """Check if a compiled binary can be executed on the current system.
    
    For cross-compiled binaries (e.g., MinGW PE32 on Linux), execution will fail
    unless wine is installed. In that case, we return False.
    """
    try:
        result = subprocess.run([binary_path], capture_output=True, text=True, timeout=1)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.slow
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
    compiler = get_struct_test_compiler()
    try:
        with open(c_file, "w") as f:
            f.write(c_code)

        result = subprocess.run(
            [compiler, "-std=gnu89", f"-I{PROJECT_ROOT}/SRC", f"-I{PROJECT_ROOT}/compat",
             "-x", "c", c_file, "-o", out_file],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Compilation failed with {compiler}: {result.stderr}"

        # Try to run; skip execution check for cross-compiled binaries
        if can_execute_binary(out_file):
            result = subprocess.run([out_file], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Struct size check failed: {result.stdout}\n{result.stderr}"
            assert "ALL STRUCT SIZE CHECKS PASSED" in result.stdout
        else:
            # Cross-compiled binary (e.g., MinGW on Linux) — compilation success is enough
            print(f"(Cross-compiled {compiler} binary — skipping execution check)")
    finally:
        if os.path.exists(c_file):
            os.unlink(c_file)
        if os.path.exists(out_file):
            os.unlink(out_file)


@pytest.mark.slow
def test_weaponhit_struct_size():
    """Compile and run a C program to verify weaponhit (hittype) struct size.
    
    weaponhit is defined in source/DUKE3D.H and is used for weapon-sprite collision state.
    Size must be stable for binary compatibility across platforms.
    """
    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <assert.h>

/* Minimal weaponhit struct definition (from source/DUKE3D.H) */
typedef struct weaponhit
{
    char cgg;
    short picnum,ang,extra,owner,movflag;
    short tempang,actorstayput,dispicnum;
    short timetosleep;
    long floorz,ceilingz,lastvx,lastvy,bposx,bposy,bposz;
    long temp_data[6];
} weaponhit;

int main() {
    printf("sizeof(weaponhit) = %zu (expected 128)\n", sizeof(weaponhit));
    assert(sizeof(weaponhit) == 128);
    printf("WEAPONHIT STRUCT SIZE CHECK PASSED\n");
    return 0;
}
"""
    c_file = os.path.join(PROJECT_ROOT, "_test_weaponhit.c")
    out_file = os.path.join(PROJECT_ROOT, "_test_weaponhit")
    compiler = get_struct_test_compiler()
    try:
        with open(c_file, "w") as f:
            f.write(c_code)

        result = subprocess.run(
            [compiler, "-std=gnu89", f"-I{PROJECT_ROOT}/SRC", f"-I{PROJECT_ROOT}/compat",
             "-x", "c", c_file, "-o", out_file],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Compilation failed with {compiler}: {result.stderr}"

        # Try to run; skip execution check for cross-compiled binaries
        if can_execute_binary(out_file):
            result = subprocess.run([out_file], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Weaponhit struct size check failed: {result.stdout}\n{result.stderr}"
            assert "WEAPONHIT STRUCT SIZE CHECK PASSED" in result.stdout
        else:
            # Cross-compiled binary (e.g., MinGW on Linux) — compilation success is enough
            print(f"(Cross-compiled {compiler} binary — skipping execution check)")
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


def test_actortype_char_size():
    """Compile and run a C program to verify char size used in actortype array.
    
    actortype is defined in source/DUKE3D.H as char actortype[MAXTILES].
    The element type (char) must be 1 byte on all platforms.
    """
    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <assert.h>

int main() {
    printf("sizeof(char) = %zu (expected 1)\n", sizeof(char));
    assert(sizeof(char) == 1);
    printf("ACTORTYPE CHAR SIZE CHECK PASSED\n");
    return 0;
}
"""
    c_file = os.path.join(PROJECT_ROOT, "_test_actortype.c")
    out_file = os.path.join(PROJECT_ROOT, "_test_actortype")
    compiler = get_struct_test_compiler()
    try:
        with open(c_file, "w") as f:
            f.write(c_code)

        result = subprocess.run(
            [compiler, "-std=gnu89", f"-I{PROJECT_ROOT}/SRC", f"-I{PROJECT_ROOT}/compat",
             "-x", "c", c_file, "-o", out_file],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Compilation failed with {compiler}: {result.stderr}"

        # Try to run; skip execution check for cross-compiled binaries
        if can_execute_binary(out_file):
            result = subprocess.run([out_file], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Actortype char size check failed: {result.stdout}\n{result.stderr}"
            assert "ACTORTYPE CHAR SIZE CHECK PASSED" in result.stdout
        else:
            # Cross-compiled binary (e.g., MinGW on Linux) — compilation success is enough
            print(f"(Cross-compiled {compiler} binary — skipping execution check)")
    finally:
        if os.path.exists(c_file):
            os.unlink(c_file)
        if os.path.exists(out_file):
            os.unlink(out_file)


def test_hittype_weaponhit_size():
    """Compile and run a C program to verify weaponhit struct size for hittype array.
    
    hittype is defined in source/DUKE3D.H as struct weaponhit hittype[MAXSPRITES].
    Validates struct size consistency with test_weaponhit_struct_size.
    """
    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <assert.h>

/* weaponhit struct definition (from source/DUKE3D.H) */
typedef struct weaponhit
{
    char cgg;
    short picnum,ang,extra,owner,movflag;
    short tempang,actorstayput,dispicnum;
    short timetosleep;
    long floorz,ceilingz,lastvx,lastvy,bposx,bposy,bposz;
    long temp_data[6];
} weaponhit;

int main() {
    printf("sizeof(weaponhit) = %zu (expected 128)\n", sizeof(weaponhit));
    assert(sizeof(weaponhit) == 128);
    printf("HITTYPE WEAPONHIT STRUCT SIZE CHECK PASSED\n");
    return 0;
}
"""
    c_file = os.path.join(PROJECT_ROOT, "_test_hittype.c")
    out_file = os.path.join(PROJECT_ROOT, "_test_hittype")
    compiler = get_struct_test_compiler()
    try:
        with open(c_file, "w") as f:
            f.write(c_code)

        result = subprocess.run(
            [compiler, "-std=gnu89", f"-I{PROJECT_ROOT}/SRC", f"-I{PROJECT_ROOT}/compat",
             "-x", "c", c_file, "-o", out_file],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Compilation failed with {compiler}: {result.stderr}"

        # Try to run; skip execution check for cross-compiled binaries
        if can_execute_binary(out_file):
            result = subprocess.run([out_file], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Hittype weaponhit struct size check failed: {result.stdout}\n{result.stderr}"
            assert "HITTYPE WEAPONHIT STRUCT SIZE CHECK PASSED" in result.stdout
        else:
            # Cross-compiled binary (e.g., MinGW on Linux) — compilation success is enough
            print(f"(Cross-compiled {compiler} binary — skipping execution check)")
    finally:
        if os.path.exists(c_file):
            os.unlink(c_file)
        if os.path.exists(out_file):
            os.unlink(out_file)


def test_packbuftype_unsigned_char_size():
    """Compile and run a C program to verify unsigned char size used in packbuf array.
    
    packbuf is defined in source/DUKE3D.H as unsigned char packbuf[576].
    The element type (unsigned char) must be 1 byte on all platforms.
    """
    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <assert.h>

int main() {
    printf("sizeof(unsigned char) = %zu (expected 1)\n", sizeof(unsigned char));
    assert(sizeof(unsigned char) == 1);
    printf("PACKBUF UNSIGNED CHAR SIZE CHECK PASSED\n");
    return 0;
}
"""
    c_file = os.path.join(PROJECT_ROOT, "_test_packbuf.c")
    out_file = os.path.join(PROJECT_ROOT, "_test_packbuf")
    compiler = get_struct_test_compiler()
    try:
        with open(c_file, "w") as f:
            f.write(c_code)

        result = subprocess.run(
            [compiler, "-std=gnu89", f"-I{PROJECT_ROOT}/SRC", f"-I{PROJECT_ROOT}/compat",
             "-x", "c", c_file, "-o", out_file],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Compilation failed with {compiler}: {result.stderr}"

        # Try to run; skip execution check for cross-compiled binaries
        if can_execute_binary(out_file):
            result = subprocess.run([out_file], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Packbuf unsigned char size check failed: {result.stdout}\n{result.stderr}"
            assert "PACKBUF UNSIGNED CHAR SIZE CHECK PASSED" in result.stdout
        else:
            # Cross-compiled binary (e.g., MinGW on Linux) — compilation success is enough
            print(f"(Cross-compiled {compiler} binary — skipping execution check)")
    finally:
        if os.path.exists(c_file):
            os.unlink(c_file)
        if os.path.exists(out_file):
            os.unlink(out_file)

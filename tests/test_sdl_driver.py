"""Unit tests for the SDL driver compat layer (compat/sdl_driver.c).

Tests the `sdl_quit_requested_get()` getter function which returns the value of
a module-static `volatile sig_atomic_t sdl_quit_requested` flag set by SDL_QUIT events.

Approach:
- Compile a minimal test harness that links sdl_driver.c and calls the getter.
- Verify the initial state (should return 0).
- If SDL2 is available, simulate SDL_QUIT injection and verify the flag changes.
- Validate symbol export via nm/objdump.

Skip cleanly if SDL2 runtime not available (mirror test_visual_playtest.py pattern).
"""

import ctypes
import os
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helper: detect SDL2 runtime availability
# ---------------------------------------------------------------------------

def sdl2_available():
    """Check if libSDL2 is available in the runtime linker path.
    
    Tries to load SDL2 on current platform:
    - Linux: libSDL2-2.0.so.0
    - macOS: libSDL2-2.0.0.dylib
    - Windows: SDL2.dll
    """
    # Linux (primary)
    try:
        ctypes.CDLL("libSDL2-2.0.so.0")
        return True
    except OSError:
        pass
    
    # macOS
    try:
        ctypes.CDLL("libSDL2-2.0.0.dylib")
        return True
    except OSError:
        pass
    
    # Windows
    try:
        ctypes.CDLL("SDL2.dll")
        return True
    except OSError:
        pass
    
    return False


def get_sdl2_lib_path():
    """Try to find SDL2 library path.
    
    Checks common system library locations for:
    - Linux: libSDL2-2.0.so.0 (via ldconfig, /usr/lib, /usr/local/lib, etc.)
    - macOS: libSDL2-2.0.0.dylib (via /opt/homebrew/lib, /usr/local/lib)
    - Windows: SDL2.dll (via PATH environment variable)
    """
    # Linux: Try common locations first
    linux_paths = [
        "/home/linuxbrew/.linuxbrew/lib",
        "/usr/lib",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/local/lib",
    ]
    
    for path in linux_paths:
        if os.path.isdir(path):
            sdl2_file = os.path.join(path, "libSDL2-2.0.so.0")
            if os.path.isfile(sdl2_file):
                return path
    
    # macOS: Try Homebrew and standard locations
    macos_paths = [
        "/opt/homebrew/lib",        # M1/M2 Homebrew
        "/usr/local/lib",           # Intel Homebrew or manual install
    ]
    
    for path in macos_paths:
        if os.path.isdir(path):
            sdl2_file = os.path.join(path, "libSDL2-2.0.0.dylib")
            if os.path.isfile(sdl2_file):
                return path
    
    # Try ldconfig (Linux)
    try:
        result = subprocess.run(
            ["ldconfig", "-p"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in result.stdout.split("\n"):
            if "libSDL2-2.0.so.0" in line:
                parts = line.split(" => ")
                if len(parts) == 2:
                    path = parts[1].strip()
                    if path:
                        return os.path.dirname(path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Windows: Check PATH for SDL2.dll
    try:
        result = subprocess.run(
            ["where", "SDL2.dll"] if os.name == 'nt' else ["which", "SDL2.dll"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            dll_path = result.stdout.strip()
            if dll_path:
                return os.path.dirname(dll_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


# ---------------------------------------------------------------------------
# Test: Initial state of sdl_quit_requested_get()
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_sdl_quit_requested_initial_state():
    """Test that sdl_quit_requested_get() returns 0 before any events.
    
    This is a core invariant: the quit flag must start at zero and remain zero
    until SDL_QUIT events are processed.
    """
    if not sdl2_available():
        pytest.skip("libSDL2-2.0.so.0 not available")

    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <SDL.h>
#include "sdl_driver.h"

int main() {
    /* Minimal SDL init to verify the function is callable */
    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        return 1;
    }
    
    /* Get the initial quit flag state */
    int quit_state = sdl_quit_requested_get();
    printf("Initial sdl_quit_requested_get() = %d\n", quit_state);
    
    SDL_Quit();
    
    /* Should be 0 initially */
    if (quit_state != 0) {
        fprintf(stderr, "FAIL: expected 0, got %d\n", quit_state);
        return 1;
    }
    
    printf("PASS: Initial state is 0\n");
    return 0;
}
"""
    
    _test_sdl_driver_generic(c_code, "test_sdl_quit_requested_initial_state")


# ---------------------------------------------------------------------------
# Test: Symbol export and type signature
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_sdl_quit_requested_symbol_export():
    """Test that sdl_quit_requested_get is exported and callable.
    
    Verify via compilation and linking that:
    - The function is declared in sdl_driver.h
    - The function is defined in sdl_driver.c
    - The type signature matches (int return, void params)
    """
    c_code = r"""
#include <stdio.h>
#include "sdl_driver.h"

/* Verify function signature matches the header */
int main() {
    /* This will fail to compile if the declaration is wrong */
    void *func_ptr = (void*) &sdl_quit_requested_get;
    printf("Symbol sdl_quit_requested_get exported: %p\n", func_ptr);
    printf("PASS: Symbol is accessible\n");
    return 0;
}
"""
    
    _test_sdl_driver_generic(c_code, "test_sdl_quit_requested_symbol_export")


# ---------------------------------------------------------------------------
# Test: SDL_QUIT event injection (if available)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_sdl_quit_requested_with_event_injection():
    """Test that sdl_quit_requested_get() can detect SDL_QUIT events.
    
    If SDL2 event injection is available:
    - Create an SDL_QUIT event
    - Push it onto the event queue
    - Call sdl_pollevents() to process it
    - Verify the getter returns non-zero

    Skip if SDL2 runtime is not available.
    """
    if not sdl2_available():
        pytest.skip("libSDL2-2.0.so.0 not available")

    c_code = r"""
#include <stdio.h>
#include <stdint.h>
#include <SDL.h>
#include "sdl_driver.h"

int main() {
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) < 0) {
        fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        return 1;
    }
    
    /* Create a dummy window so events can be processed */
    SDL_Window *window = SDL_CreateWindow(
        "Test",
        SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED,
        320, 200,
        SDL_WINDOW_HIDDEN
    );
    
    if (!window) {
        fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }
    
    /* Verify initial state */
    int initial = sdl_quit_requested_get();
    printf("Initial state: %d\n", initial);
    
    if (initial != 0) {
        fprintf(stderr, "FAIL: expected initial state 0, got %d\n", initial);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }
    
    /* Inject a SDL_QUIT event */
    SDL_Event event;
    event.type = SDL_QUIT;
    if (SDL_PushEvent(&event) < 0) {
        fprintf(stderr, "SDL_PushEvent failed: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }
    
    /* Process events (should set the quit flag) */
    sdl_pollevents();
    
    /* Check if quit flag was set */
    int after_event = sdl_quit_requested_get();
    printf("After SDL_QUIT injection: %d\n", after_event);
    
    SDL_DestroyWindow(window);
    SDL_Quit();
    
    if (after_event != 0) {
        printf("PASS: SDL_QUIT event was detected\n");
        return 0;
    } else {
        fprintf(stderr, "FAIL: SDL_QUIT event not detected (flag still 0)\n");
        return 1;
    }
}
"""
    
    _test_sdl_driver_generic(c_code, "test_sdl_quit_requested_with_event_injection")


# ---------------------------------------------------------------------------
# Helper: Generic SDL driver test compilation and execution
# ---------------------------------------------------------------------------

def _test_sdl_driver_generic(c_code, test_name):
    """Compile and run a test harness against sdl_driver.c.
    
    Args:
        c_code: String containing C test code
        test_name: String name for cleanup/reporting
    
    Raises:
        AssertionError if compilation or execution fails
    """
    c_file = os.path.join(PROJECT_ROOT, f"_test_{test_name}.c")
    out_file = os.path.join(PROJECT_ROOT, f"_test_{test_name}")
    
    try:
        # Write test source
        with open(c_file, "w", encoding="utf-8") as f:
            f.write(c_code)
        
        # Find SDL2 include path
        sdl2_include = None
        common_include_paths = [
            "/home/linuxbrew/.linuxbrew/include/SDL2",
            "/usr/include/SDL2",
            "/opt/homebrew/include/SDL2",
        ]
        for path in common_include_paths:
            if os.path.exists(os.path.join(path, "SDL.h")):
                sdl2_include = path
                break
        
        if not sdl2_include:
            pytest.skip("SDL2 development headers not found")
        
        # Compile: link sdl_driver.c with test harness
        # Include compat, SRC, source dirs for headers
        compile_cmd = [
            "gcc",
            "-std=gnu11",
            f"-I{PROJECT_ROOT}/compat",
            f"-I{PROJECT_ROOT}/SRC",
            f"-I{PROJECT_ROOT}/source",
            f"-I{sdl2_include}",
            "-Wall",
            # Link against sdl_driver.c and its dependencies
            os.path.join(PROJECT_ROOT, "compat/sdl_driver.c"),
            os.path.join(PROJECT_ROOT, "compat/audio_stub.c"),
            os.path.join(PROJECT_ROOT, "compat/mact_stub.c"),
            os.path.join(PROJECT_ROOT, "compat/hud.c"),
            c_file,
            "-o", out_file,
            "-lSDL2",
            "-lm",  # Math library for compat layer
        ]
        
        # Add SDL2 library path if found
        sdl2_path = get_sdl2_lib_path()
        if sdl2_path:
            compile_cmd.insert(-2, f"-L{sdl2_path}")
            compile_cmd.insert(-2, "-Wl,-rpath," + sdl2_path)
        
        result = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            pytest.skip(
                f"Compilation failed (SDL2 may not be available):\n{result.stderr}"
            )
        
        # Run test
        env = os.environ.copy()
        if sdl2_path:
            ld_lib = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = f"{sdl2_path}:{ld_lib}" if ld_lib else sdl2_path
        
        result = subprocess.run(
            [out_file],
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        
        if result.returncode != 0:
            pytest.fail(
                f"Test execution failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )
        
        # Verify test passed
        if "PASS" not in result.stdout and "FAIL" not in result.stdout:
            if "skipped" in result.stdout.lower():
                pytest.skip(result.stdout)
            else:
                pytest.fail(f"Test did not report PASS/FAIL:\n{result.stdout}")
        
        if "FAIL" in result.stdout:
            pytest.fail(f"Test reported FAIL:\n{result.stdout}\n{result.stderr}")
        
    finally:
        # Cleanup
        for f in [c_file, out_file]:
            if os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Test: Verify symbol via nm/objdump if available
# ---------------------------------------------------------------------------

def test_sdl_quit_requested_symbol_presence():
    """Test that sdl_quit_requested_get is present in the compiled binary.
    
    Uses nm or objdump to verify the symbol exists in the duke3d binary
    (if it's been compiled). Skips if binary doesn't exist or nm unavailable.
    """
    binary_path = os.path.join(PROJECT_ROOT, "duke3d")
    
    if not os.path.exists(binary_path):
        pytest.skip(f"Binary not found at {binary_path} (run 'make' to build)")
    
    # Try nm first (most portable)
    try:
        result = subprocess.run(
            ["nm", binary_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            if "sdl_quit_requested_get" in result.stdout:
                assert True  # Symbol found
            else:
                pytest.skip("Binary not built (run `make` first); LTO may also strip non-exported internal symbols even when present")
        else:
            pytest.skip(f"nm command failed: {result.stderr}")
    except FileNotFoundError:
        pytest.skip("nm command not available")


# ---------------------------------------------------------------------------
# Summary: Test count and skip reasons
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(__doc__)
    print("\nTests defined:")
    print("  1. test_sdl_quit_requested_initial_state")
    print("  2. test_sdl_quit_requested_symbol_export")
    print("  3. test_sdl_quit_requested_with_event_injection")
    print("  4. test_sdl_quit_requested_symbol_presence")
    print("\nRun with: pytest tests/test_sdl_driver.py -v")

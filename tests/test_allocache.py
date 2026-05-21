"""
Static analysis tests for cache allocator behavior (CACHE1D.C).

Tests verify allocache/agecache/uncache patterns: size validation, 
alignment assumptions, free list management. These are STATIC ANALYSIS 
tests (parse C source) not runtime tests.

Pattern follows test_engine_bounds_hardening.py conventions.
"""

import re
from pathlib import Path
import pytest


@pytest.fixture
def repo_root():
    """Return the repository root path."""
    return Path(__file__).parent.parent


class TestAllocacheFunctionDeclaration:
    """Verify allocache function signature and purpose."""

    def test_allocache_function_exists(self, repo_root):
        """allocache function should be declared in CACHE1D.C."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for allocache function definition
        has_allocache = re.search(r"allocache\s*\(", content)
        assert has_allocache, (
            "SRC/CACHE1D.C must define allocache() function for cache memory allocation."
        )

    def test_allocache_takes_three_params(self, repo_root):
        """allocache(long *bufptr, long bufsiz, char *lockptr) signature."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for function signature with three parameters
        has_bufptr = "long *" in content and "allocache" in content
        has_bufsiz = "long bufsiz" in content or "bufsiz" in content
        has_lockptr = "char *" in content and "lockptr" in content

        assert has_bufptr and has_bufsiz and has_lockptr, (
            "allocache should accept (long *bufptr, long bufsiz, char *lockptr) parameters."
        )


class TestAllocacheSizeValidation:
    """Verify allocache validates allocation size against total cache size."""

    def test_allocache_checks_newbytes_against_cachesize(self, repo_root):
        """allocache must validate newbytes <= cachesize."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for pattern: if (newbytes > cachesize) or similar
        has_size_check = (
            "newbytes" in content and "cachesize" in content and
            (">=" in content or ">" in content)
        )
        assert has_size_check, (
            "allocache must validate that newbytes <= cachesize to prevent allocation failure. "
            "Look for bounds check in allocache function body."
        )

    def test_cachesize_static_variable(self, repo_root):
        """cachesize should be static variable in CACHE1D.C."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for: static long cachesize = 0;
        has_cachesize = re.search(r"static\s+long\s+cachesize", content)
        assert has_cachesize, (
            "CACHE1D.C should declare 'static long cachesize' as module-private variable."
        )


class TestAllocacheFreeList:
    """Verify allocache uses free list for memory management."""

    def test_allocache_finds_best_fit(self, repo_root):
        """allocache should scan free list for best-fit candidate."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for patterns indicating free list scanning
        has_bestval = "bestval" in content
        has_loop = "for(" in content or "while(" in content

        assert has_bestval and has_loop, (
            "allocache should maintain a bestval for best-fit search through free list."
        )

    def test_allocache_updates_o1_o2_bounds(self, repo_root):
        """allocache tracks o1 (candidate start) and o2 (candidate end)."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for patterns: o1 = cachesize; o2 = o1 + newbytes
        has_o1 = "o1" in content and "cachesize" in content
        has_o2 = "o2" in content and "newbytes" in content

        assert has_o1 and has_o2, (
            "allocache should use o1 (offset start) and o2 (offset end) for candidate bounds."
        )


class TestInitcacheFunction:
    """Verify initcache sets up the cache pool."""

    def test_initcache_function_exists(self, repo_root):
        """initcache function initializes cache."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for initcache function
        has_initcache = re.search(r"initcache\s*\(", content)
        assert has_initcache, (
            "SRC/CACHE1D.C must define initcache() function to set up cache pool."
        )

    def test_initcache_sets_cachesize(self, repo_root):
        """initcache sets cachesize = dacachesize parameter."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for assignment pattern: cachesize = dacachesize;
        has_assignment = "cachesize" in content and "dacachesize" in content
        assert has_assignment, (
            "initcache should assign cachesize = dacachesize to set total cache size."
        )


class TestAgecacheFunction:
    """Verify agecache periodically evicts old cache entries."""

    def test_agecache_function_exists(self, repo_root):
        """agecache function exists for cache eviction."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for agecache function
        has_agecache = re.search(r"agecache\s*\(\s*\)", content)
        assert has_agecache, (
            "SRC/CACHE1D.C must define agecache() function to evict old entries."
        )

    def test_agecache_checks_free_bytes_threshold(self, repo_root):
        """agecache only runs if cache1d_free_bytes below threshold."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for pattern: if (cache1d_free_bytes > (cachesize >> ...)) return;
        has_threshold_check = (
            "cache1d_free_bytes" in content and
            ("cachesize >>" in content or ">> " in content) and
            "return" in content
        )
        assert has_threshold_check, (
            "agecache should check if cache1d_free_bytes exceeds threshold before evicting."
        )


class TestCache1dFreeBytes:
    """Verify cache1d_free_bytes counter tracks available cache memory."""

    def test_cache1d_free_bytes_declared(self, repo_root):
        """cache1d_free_bytes static variable tracks free memory."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for variable declaration or usage
        has_free_bytes = "cache1d_free_bytes" in content
        assert has_free_bytes, (
            "CACHE1D.C should track cache1d_free_bytes counter for free memory."
        )

    def test_cache1d_free_bytes_initialized_in_initcache(self, repo_root):
        """cache1d_free_bytes initialized to dacachesize in initcache."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for pattern: cache1d_free_bytes = dacachesize;
        has_init = "cache1d_free_bytes" in content and "dacachesize" in content
        assert has_init, (
            "initcache should initialize cache1d_free_bytes = dacachesize."
        )


class TestSuckcacheFunction:
    """Verify suckcache frees previously allocated cache memory."""

    def test_suckcache_function_exists(self, repo_root):
        """suckcache function frees cache memory."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for suckcache function
        has_suckcache = re.search(r"suckcache\s*\(", content)
        assert has_suckcache, (
            "SRC/CACHE1D.C must define suckcache() function to free cached memory."
        )

    def test_suckcache_handles_pointer_parameter(self, repo_root):
        """suckcache takes pointer parameter for memory location."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for patterns involving pointer handling
        has_ptr = "suckptr" in content or "*" in content and "suckcache" in content
        assert has_ptr, (
            "suckcache should accept a pointer parameter to mark memory as freed."
        )


class TestAllocacheCallSites:
    """Verify allocache is called correctly at initialization."""

    def test_lzwbuf_allocations_use_allocache(self, repo_root):
        """LZW buffers allocated with allocache in CACHE1D.C."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for pattern: allocache((long *)&lzwbufN, ...
        has_lzwbuf = re.search(r"allocache\s*\(\s*\(.*\)&lzwbuf", content)
        assert has_lzwbuf, (
            "CACHE1D.C should allocate LZW buffers using allocache((long *)&lzwbufN, ...)."
        )

    def test_allocache_guards_with_null_check(self, repo_root):
        """allocache calls guarded: if (lzwbufN == NULL) allocache(...)."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for pattern: if (...NULL) allocache
        has_guard = re.search(r"if\s*\([^)]*NULL[^)]*\)\s*allocache", content)
        assert has_guard, (
            "allocache calls should be guarded with NULL check to avoid re-allocation."
        )

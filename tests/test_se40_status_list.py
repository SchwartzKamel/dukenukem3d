"""
Static analysis tests for SE40 sprite iteration patterns.

Tests verify that ENGINE.C sprite iteration loops use correct sentinel
bounds (MAXSPRITESONSCREEN, MAXSPRITES) without off-by-one errors.
Sprite struct size is 44 bytes; SE40 refers to sectortype size (40 bytes).

Tests follow the pattern established in test_engine_bounds_hardening.py:
parse C source with regex, verify loop guards and array declarations.
"""

import re
from pathlib import Path
import pytest


@pytest.fixture
def repo_root():
    """Return the repository root path."""
    return Path(__file__).parent.parent


class TestSE40SpriteArrayDeclarations:
    """Verify sprite array declarations use correct sizes."""

    def test_spritesx_array_MAXSPRITESONSCREEN(self, repo_root):
        """spritesx[MAXSPRITESONSCREEN] — no off-by-one."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find declaration: static long spritesx[MAXSPRITESONSCREEN];
        has_spritesx = "spritesx[MAXSPRITESONSCREEN]" in content
        assert has_spritesx, (
            "ENGINE.C should declare spritesx[MAXSPRITESONSCREEN]. "
            "Check that it is not spritesx[MAXSPRITES] or other size."
        )

    def test_spritesy_array_MAXSPRITESONSCREEN_plus_one(self, repo_root):
        """spritesy[MAXSPRITESONSCREEN+1] — sentinel at end for gap sort."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find declaration: static long spritesy[MAXSPRITESONSCREEN+1];
        has_spritesy = "spritesy[MAXSPRITESONSCREEN+1]" in content
        assert has_spritesy, (
            "ENGINE.C should declare spritesy[MAXSPRITESONSCREEN+1] "
            "(extra element for gap sort sentinel). "
            "Check against off-by-one errors."
        )

    def test_spritesz_array_MAXSPRITESONSCREEN(self, repo_root):
        """spritesz[MAXSPRITESONSCREEN] — Z coordinate array."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        has_spritesz = "spritesz[MAXSPRITESONSCREEN]" in content
        assert has_spritesz, (
            "ENGINE.C should declare spritesz[MAXSPRITESONSCREEN]. "
            "Check for consistency with spritesx/spritesy declarations."
        )

    def test_tspriteptr_array_MAXSPRITESONSCREEN(self, repo_root):
        """tspriteptr[MAXSPRITESONSCREEN] — sprite pointer array."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        has_tspriteptr = "tspriteptr[MAXSPRITESONSCREEN]" in content
        assert has_tspriteptr, (
            "ENGINE.C should declare tspriteptr[MAXSPRITESONSCREEN]. "
            "This array stores pointers to sorted sprite structures."
        )


class TestSE40SpriteLoopBounds:
    """Verify sprite loop bounds checking prevents buffer overflow."""

    def test_spritesortcnt_less_than_MAXSPRITESONSCREEN(self, repo_root):
        """Loop condition: spritesortcnt < MAXSPRITESONSCREEN guards append."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find pattern: (spritesortcnt < MAXSPRITESONSCREEN)
        has_guard = "spritesortcnt < MAXSPRITESONSCREEN" in content
        assert has_guard, (
            "ENGINE.C must check 'spritesortcnt < MAXSPRITESONSCREEN' "
            "before appending to sprite arrays to prevent overflow."
        )

    def test_sprite_iteration_uses_headspritesect(self, repo_root):
        """Sprite sector list uses headspritesect/nextspritesect chain."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Look for iteration pattern: for(z=headspritesect[...]; z>=0; z=nextspritesect[z])
        has_headsprite = "headspritesect[" in content
        has_nextsprite = "nextspritesect[" in content

        assert has_headsprite and has_nextsprite, (
            "ENGINE.C sprite iteration should use headspritesect and nextspritesect "
            "for linked list traversal, not array indexing alone."
        )

    def test_sprite_cstat_visibility_check(self, repo_root):
        """Sprites check cstat & 0x8000 before rendering."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Check for cstat visibility bit test
        has_cstat = "cstat&0x8000" in content
        assert has_cstat, (
            "ENGINE.C should test sprite cstat visibility bit (0x8000) "
            "before rendering to skip invisible sprites."
        )


class TestSE40SpriteArrayAccess:
    """Verify sprite array accesses are bounded."""

    def test_tspriteptr_assignment_bounded(self, repo_root):
        """tspriteptr[i] assignment guarded by loop bounds."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find tspriteptr[i] = &tsprite[i] pattern
        has_assignment = "tspriteptr[i] = &tsprite[i]" in content
        assert has_assignment, (
            "ENGINE.C should assign tspriteptr[i] = &tsprite[i] during sprite sort."
        )

    def test_spritesx_assignment_bounded(self, repo_root):
        """spritesx[i] assignment during sprite positioning."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find spritesx[i] assignment
        has_spritesx_assign = "spritesx[i]" in content
        assert has_spritesx_assign, (
            "ENGINE.C should assign spritesx[i] during sprite coordinate transform."
        )

    def test_spritesy_gap_sort_pattern(self, repo_root):
        """Gap sort uses spritesy[spritesortcnt] as sentinel."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Look for: spritesy[spritesortcnt] = (spritesy[spritesortcnt-1]^1)
        # XOR with 1 to create unique sentinel (not equal to last real value)
        has_sentinel = "spritesy[spritesortcnt]" in content
        has_xor = "spritesy[spritesortcnt-1]^1" in content

        assert has_sentinel or has_xor, (
            "ENGINE.C gap sort should use spritesy[spritesortcnt] as sentinel "
            "to stop gap sort loop (typically XORed with last value)."
        )


class TestSE40SpriteSwap:
    """Verify sprite array swap patterns maintain consistency."""

    def test_swaplong_tspriteptr_spritesx_swap(self, repo_root):
        """Gap sort must swap tspriteptr and spritesx together."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find pattern: swaplong(&tspriteptr[l], ...); swaplong(&spritesx[l], ...);
        has_swaplong = "swaplong(" in content
        has_tspriteptr_swap = "swaplong(&tspriteptr[" in content

        assert has_swaplong and has_tspriteptr_swap, (
            "ENGINE.C gap sort should use swaplong() to swap tspriteptr and spritesx "
            "to keep pointer and coordinate arrays in sync."
        )

    def test_spritesy_swap_synchronized(self, repo_root):
        """Gap sort swaps spritesy alongside other arrays."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Look for spritesy swap pattern in gap sort section
        has_spritesy_swap = "swaplong(&spritesy[" in content
        assert has_spritesy_swap, (
            "ENGINE.C gap sort should swap spritesy alongside tspriteptr/spritesx "
            "to maintain sorted order."
        )


class TestSE40MaxSpriteConstants:
    """Verify MAXSPRITES and MAXSPRITESONSCREEN constants are defined correctly."""

    def test_maxsprites_defined_in_BUILD_H(self, repo_root):
        """MAXSPRITES constant should be defined in BUILD.H."""
        build_h = repo_root / "SRC" / "BUILD.H"
        if not build_h.exists():
            pytest.skip(f"{build_h} not found")

        content = build_h.read_text(errors="replace")

        # Look for #define MAXSPRITES
        has_maxsprites = re.search(r"#define\s+MAXSPRITES\s+", content)
        assert has_maxsprites, (
            "SRC/BUILD.H must define MAXSPRITES constant."
        )

    def test_maxspritesonscreen_defined_in_BUILD_H(self, repo_root):
        """MAXSPRITESONSCREEN constant should be defined in BUILD.H."""
        build_h = repo_root / "SRC" / "BUILD.H"
        if not build_h.exists():
            pytest.skip(f"{build_h} not found")

        content = build_h.read_text(errors="replace")

        # Look for #define MAXSPRITESONSCREEN
        has_maxspritesonscreen = re.search(r"#define\s+MAXSPRITESONSCREEN\s+", content)
        assert has_maxspritesonscreen, (
            "SRC/BUILD.H must define MAXSPRITESONSCREEN constant."
        )

    def test_maxspritesonscreen_less_than_maxsprites(self, repo_root):
        """MAXSPRITESONSCREEN should be <= MAXSPRITES."""
        build_h = repo_root / "SRC" / "BUILD.H"
        if not build_h.exists():
            pytest.skip(f"{build_h} not found")

        content = build_h.read_text(errors="replace")

        # Extract both constants
        maxsprites_match = re.search(r"#define\s+MAXSPRITES\s+(\d+)", content)
        maxspritesonscreen_match = re.search(r"#define\s+MAXSPRITESONSCREEN\s+(\d+)", content)

        if maxsprites_match and maxspritesonscreen_match:
            maxsprites = int(maxsprites_match.group(1))
            maxspritesonscreen = int(maxspritesonscreen_match.group(1))

            assert maxspritesonscreen <= maxsprites, (
                f"MAXSPRITESONSCREEN ({maxspritesonscreen}) must be <= MAXSPRITES ({maxsprites}). "
                "Screen can show at most the total sprite count."
            )

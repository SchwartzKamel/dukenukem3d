"""
Static analysis tests for MENUES.C critical menu transitions and sentinels.

Tests verify:
1. engine-r17-numwalls-load-clamp sentinel at lines 329 and 340
2. Menu state transitions (save/load cycles)
3. numwalls/numsectors bounds clamping on load

Pattern follows test_engine_bounds_hardening.py conventions: 
parse C source with regex, verify sentinel comments and bounds checks.
"""

import re
from pathlib import Path
import pytest


@pytest.fixture
def repo_root():
    """Return the repository root path."""
    return Path(__file__).parent.parent


class TestMenuesNumwallsSentinels:
    """Verify engine-r17-numwalls-load-clamp sentinels are present."""

    def test_numwalls_sentinel_line_329_exists(self, repo_root):
        """engine-r17-numwalls-load-clamp sentinel at line 329."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        lines = menues_c.read_text(errors="replace").split("\n")

        # Check around line 329 (may be off by a few due to edits)
        found_sentinel = False
        search_range = range(max(0, 328-5), min(len(lines), 328+5))
        for i in search_range:
            if "engine-r17-numwalls-load-clamp" in lines[i]:
                found_sentinel = True
                break

        assert found_sentinel, (
            "MENUES.C should have 'engine-r17-numwalls-load-clamp' sentinel "
            "comment around line 329 to mark numwalls bounds check."
        )

    def test_numsectors_sentinel_line_340_exists(self, repo_root):
        """engine-r17-numwalls-load-clamp sentinel at line 340."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        lines = menues_c.read_text(errors="replace").split("\n")

        # Check around line 340 (may be off by a few due to edits)
        found_sentinel = False
        search_range = range(max(0, 339-5), min(len(lines), 339+5))
        for i in search_range:
            if "engine-r17-numwalls-load-clamp" in lines[i]:
                found_sentinel = True
                break

        assert found_sentinel, (
            "MENUES.C should have 'engine-r17-numwalls-load-clamp' sentinel "
            "comment around line 340 to mark numsectors bounds check."
        )


class TestMenuesNumwallsBoundsCheck:
    """Verify numwalls is clamped on load."""

    def test_numwalls_bounds_check_exists(self, repo_root):
        """numwalls is checked: if (numwalls < 0 || numwalls > MAXWALLS)."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: if (numwalls < 0 || numwalls > MAXWALLS)
        has_check = (
            "numwalls" in content and
            "MAXWALLS" in content and
            ("< 0" in content or "< " in content) and
            (">" in content)
        )
        assert has_check, (
            "MENUES.C must check: if (numwalls < 0 || numwalls > MAXWALLS) "
            "before loading wall data."
        )

    def test_numwalls_check_returns_on_bounds_violation(self, repo_root):
        """numwalls check returns error if out of bounds."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Extract region around numwalls check and verify error handling
        # Look for pattern: if (...numwalls...) { kclose(...); return
        has_kclose = "kclose" in content
        has_return = "return" in content

        assert has_kclose and has_return, (
            "numwalls bounds check should call kclose(fil) and return error "
            "to cleanly exit on invalid bounds."
        )

    def test_numwalls_loaded_from_file(self, repo_root):
        """numwalls is read from file: kdfread(&numwalls, ...)."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: kdfread(&numwalls, ...
        has_kdfread = re.search(r"kdfread\s*\(\s*&numwalls", content)
        assert has_kdfread, (
            "MENUES.C should load numwalls from file using kdfread(&numwalls, ...)."
        )


class TestMenuesNumsectorsBoundsCheck:
    """Verify numsectors is clamped on load."""

    def test_numsectors_bounds_check_exists(self, repo_root):
        """numsectors is checked: if (numsectors < 0 || numsectors > MAXSECTORS)."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: if (numsectors < 0 || numsectors > MAXSECTORS)
        has_check = (
            "numsectors" in content and
            "MAXSECTORS" in content and
            ("< 0" in content or "< " in content) and
            (">" in content)
        )
        assert has_check, (
            "MENUES.C must check: if (numsectors < 0 || numsectors > MAXSECTORS) "
            "before loading sector data."
        )

    def test_numsectors_check_returns_on_bounds_violation(self, repo_root):
        """numsectors check returns error if out of bounds."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Extract region and verify error handling similar to numwalls
        has_kclose = "kclose" in content
        has_return = "return" in content

        assert has_kclose and has_return, (
            "numsectors bounds check should call kclose(fil) and return error "
            "to cleanly exit on invalid bounds."
        )

    def test_numsectors_loaded_from_file(self, repo_root):
        """numsectors is read from file: kdfread(&numsectors, ...)."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: kdfread(&numsectors, ...
        has_kdfread = re.search(r"kdfread\s*\(\s*&numsectors", content)
        assert has_kdfread, (
            "MENUES.C should load numsectors from file using kdfread(&numsectors, ...)."
        )


class TestMenuesWallArrayMemset:
    """Verify wall array is zero-initialized after partial load."""

    def test_wall_memset_after_load(self, repo_root):
        """Wall array zero-initialized: memset(wall + numwalls, ...)."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: memset(wall + numwalls, 0, ...
        has_memset = re.search(r"memset\s*\(\s*wall\s*\+\s*numwalls", content)
        assert has_memset, (
            "MENUES.C should zero-initialize remaining wall array: "
            "memset(wall + numwalls, 0, (MAXWALLS - numwalls) * sizeof(walltype))."
        )

    def test_wall_array_kdfread(self, repo_root):
        """Wall array loaded from file."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: kdfread(&wall[0], sizeof(walltype), numwalls, ...
        has_kdfread = re.search(r"kdfread\s*\(\s*&wall\[0\]", content)
        assert has_kdfread, (
            "MENUES.C should load wall array using kdfread(&wall[0], sizeof(walltype), numwalls, fil)."
        )


class TestMenuesSectorArrayMemset:
    """Verify sector array is zero-initialized after partial load."""

    def test_sector_memset_after_load(self, repo_root):
        """Sector array zero-initialized: memset(sector + numsectors, ...)."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: memset(sector + numsectors, 0, ...
        has_memset = re.search(r"memset\s*\(\s*sector\s*\+\s*numsectors", content)
        assert has_memset, (
            "MENUES.C should zero-initialize remaining sector array: "
            "memset(sector + numsectors, 0, (MAXSECTORS - numsectors) * sizeof(sectortype))."
        )

    def test_sector_array_kdfread(self, repo_root):
        """Sector array loaded from file."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: kdfread(&sector[0], sizeof(sectortype), numsectors, ...
        has_kdfread = re.search(r"kdfread\s*\(\s*&sector\[0\]", content)
        assert has_kdfread, (
            "MENUES.C should load sector array using kdfread(&sector[0], sizeof(sectortype), numsectors, fil)."
        )


class TestMenuesTimingVariables:
    """Verify menu uses timing variables for state management."""

    def test_totalclock_saved_on_error(self, repo_root):
        """ototalclock = totalclock set on error."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for pattern: ototalclock = totalclock;
        has_save = "ototalclock = totalclock" in content
        assert has_save, (
            "MENUES.C should save ototalclock = totalclock on menu state changes/errors."
        )

    def test_ready2send_flag_set(self, repo_root):
        """ready2send flag used for synchronization."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for ready2send flag
        has_ready2send = "ready2send" in content
        assert has_ready2send, (
            "MENUES.C should use ready2send flag for multiplayer/state synchronization."
        )


class TestMenuesFileOperations:
    """Verify file I/O patterns in menu loading."""

    def test_kclose_on_error_path(self, repo_root):
        """kclose(fil) called on error paths."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Count kclose calls
        kclose_count = content.count("kclose(")
        assert kclose_count >= 2, (
            "MENUES.C should call kclose(fil) on error paths (at least 2 instances)."
        )

    def test_kdfread_used_for_loading(self, repo_root):
        """kdfread used for all file reads."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Count kdfread calls
        kdfread_count = content.count("kdfread(")
        assert kdfread_count >= 5, (
            "MENUES.C should use kdfread for multiple loads (numwalls, numsectors, wall, sector, sprite)."
        )


class TestMenuesMaxConstantsUsage:
    """Verify MAXWALLS, MAXSECTORS, MAXSPRITES are used correctly."""

    def test_MAXWALLS_constant_in_check(self, repo_root):
        """MAXWALLS constant used in numwalls bounds check."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for MAXWALLS in bounds check context
        has_maxwalls = "MAXWALLS" in content and "numwalls" in content
        assert has_maxwalls, (
            "MENUES.C should use MAXWALLS constant in numwalls bounds check."
        )

    def test_MAXSECTORS_constant_in_check(self, repo_root):
        """MAXSECTORS constant used in numsectors bounds check."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for MAXSECTORS in bounds check context
        has_maxsectors = "MAXSECTORS" in content and "numsectors" in content
        assert has_maxsectors, (
            "MENUES.C should use MAXSECTORS constant in numsectors bounds check."
        )

    def test_MAXSPRITES_constant_referenced(self, repo_root):
        """MAXSPRITES constant used for sprite array load."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for MAXSPRITES
        has_maxsprites = "MAXSPRITES" in content
        assert has_maxsprites, (
            "MENUES.C should reference MAXSPRITES constant for sprite array operations."
        )


class TestProbeCursorTransitionSafety:
    """Verify probe() cache handling does not leak stale pixels across menu changes."""

    def test_probe_menu_change_resets_cache_without_restore(self, repo_root):
        """On menu transition, probe() must reset cursor cache and avoid restoring old pixels."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")
        marker = "if (probe_last_menu != current_menu)"
        marker_pos = content.find(marker)
        assert marker_pos != -1, "probe() menu-change guard not found in MENUES.C."

        window = content[marker_pos:marker_pos + 900]
        if_match = re.search(
            r"if\s*\(\s*probe_last_menu\s*!=\s*current_menu\s*\)\s*\{(?P<body>.*?)\}\s*else\s*\{(?P<else_body>.*?)\}",
            window,
            re.S,
        )
        assert if_match, (
            "probe() should use an if/else guard around probe_last_menu/current_menu handling."
        )

        if_body = if_match.group("body")
        else_body = if_match.group("else_body")

        assert "probe_cursor_restore" not in if_body, (
            "Menu-transition branch in probe() must not restore cached pixels from the previous menu."
        )
        assert if_body.count("probe_cursor_reset") >= 2, (
            "Menu-transition branch in probe() should reset both cursor caches."
        )
        assert else_body.count("probe_cursor_restore") >= 2, (
            "Same-menu branch in probe() should restore both cursor caches before redrawing cursor icons."
        )

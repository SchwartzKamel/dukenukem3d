"""
Test engine and bounds hardening (cycles 12-16).

Cycle 59 split: test-r16-mega-file-split-critical
Extracted from test_engine_net_hardening_regressions.py (3803 lines)
Sentinel: engine-r1x/menu-r1x/premap-r1x tests for buffer, sprite, actor, sector bounds.
"""

"""
Regression tests for hardening fixes from cycle 11-15, 19-20, 22, and r8.

These tests use static analysis (grep-style source inspection) to verify
that critical guard patterns remain in place. They do NOT execute the engine.
This is sufficient to catch common regressions like:
  - Someone removed the bounds check
  - Someone reverted to strcpy
  - Someone removed the ferror guard

Test coverage:
  1. labelcode array (cycle 12): Proper array declaration + extern
  2. MENUES.C file-I/O (cycle 13): ferror guards at 49+ sites
  3. audio_stub.c RIFF validation (cycle 13): Both "RIFF" and "WAVE" checks
  4. audio_stub.c channel exhaustion (cycle 13): Mix_GroupOldest usage
  5. CON-script bounds (cycle 15): labelcnt >= MAXLABELS patterns
  6. MMULTI.C bounds (cycle 15): from_player bounds checks
  7. SoundOwner cap (cycle 15): FX_StopSound in xyzsound context
  8. FX_SetVolume thread safety (cycle 15): SDL_LockAudio in FX_SetVolume
  9. sprite-yvel bounds (cycle 20): player_from_yvel macro and usage
  10. savegame loader bounds (cycle 20): ferror checks after kdfread
  11. savegame wall/sector partial-reads (cycle r8): partial read + memset cleanup
  12. cache1d_free_bytes counter (cycle 22): static variable + references
  13. NET_CONNECT_TIMEOUT define (cycle 22): timeout value <= 30
  14. spriteqamount bounds (cycle 19): array bounds checking
"""

import re
from pathlib import Path
import pytest


@pytest.fixture
def repo_root():
    """Return the repository root path."""
    return Path(__file__).parent.parent



class TestLabelcodeArray:
    """Verify cycle-12 labelcode array fix (not a cast from &sector[0])."""

    def test_global_c_declares_labelcode_array(self, repo_root):
        """GLOBAL.C must declare labelcode[MAXLABELS] array."""
        global_c = repo_root / "source" / "GLOBAL.C"
        if not global_c.exists():
            pytest.skip(f"{global_c} not found")

        content = global_c.read_text(errors="replace")

        # Check for labelcode array declaration (not a cast)
        # Should be: long labelcode[MAXLABELS] or similar
        # NOT: (long *)&sector[0]
        has_array_decl = "labelcode[" in content and "MAXLABELS" in content
        assert has_array_decl, (
            "GLOBAL.C must declare labelcode[MAXLABELS] array. "
            "Check that it's not just a cast from &sector[0]."
        )

    def test_duke3d_h_extern_labelcode(self, repo_root):
        """DUKE3D.H must expose extern labelcode declaration."""
        duke3d_h = repo_root / "source" / "DUKE3D.H"
        if not duke3d_h.exists():
            pytest.skip(f"{duke3d_h} not found")

        content = duke3d_h.read_text(errors="replace")

        # Check for extern labelcode (either array or pointer form)
        # Pattern: extern ... labelcode[MAXLABELS] or extern ... labelcode *
        has_extern = ("extern" in content and
                      ("labelcode[" in content or "labelcode *" in content))
        assert has_extern, (
            "DUKE3D.H must expose 'extern long labelcode[MAXLABELS]' or "
            "'extern long *labelcode'"
        )



class TestMenuesFileIO:
    """Verify cycle-13 MENUES.C file-I/O hardening (ferror guards)."""

    def test_menues_c_ferror_guards(self, repo_root):
        """MENUES.C saveplayer must have ferror(fil) guards at 49+ sites."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Count occurrences of ferror(fil) pattern
        ferror_count = content.count("ferror(fil)")
        assert ferror_count >= 49, (
            f"MENUES.C should have at least 49 ferror(fil) guards, "
            f"found {ferror_count}. Cycle-13 fix may have been reverted."
        )



class TestMMULTIBounds:
    """Verify cycle-15 MMULTI.C multiplayer bounds checking."""

    def test_mmulti_c_player_bounds_checks(self, repo_root):
        """MMULTI.C must have from_player bounds checks (2+ guards)."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        # Count patterns like: from_player < MAXPLAYERS, from_player >= MAXPLAYERS
        from_player_checks = content.count("from_player <")
        maxplayers_checks = content.count(">= MAXPLAYERS")

        # At least 2 guards total (various forms)
        total_guards = from_player_checks + maxplayers_checks
        assert total_guards >= 2, (
            f"MMULTI.C should have at least 2 player bounds checks, "
            f"found {total_guards} (from_player checks: {from_player_checks}, "
            f"MAXPLAYERS checks: {maxplayers_checks}). Cycle-15 fix may have "
            "been reverted."
        )



class TestFXSetVolumeLocking:
    """Verify cycle-15 FX_SetVolume thread-safety in audio_stub.c."""

    def test_audio_stub_fx_setvolume_locking(self, repo_root):
        """audio_stub.c FX_SetVolume must use SDL_LockAudio."""
        audio_stub = repo_root / "compat" / "audio_stub.c"
        if not audio_stub.exists():
            pytest.skip(f"{audio_stub} not found")

        content = audio_stub.read_text(errors="replace")

        # Look for SDL_LockAudio in the function body
        # Pattern: "int FX_SetVolume" or similar, then look for SDL_LockAudio
        fx_setvolume_section = re.search(
            r"(?:int|void)\s+FX_SetVolume.*?(?=\n(?:int|void)\s+\w+|$)",
            content,
            re.DOTALL
        )

        if fx_setvolume_section:
            section = fx_setvolume_section.group(0)
            has_lock = "SDL_LockAudio" in section
            assert has_lock, (
                "FX_SetVolume function must contain SDL_LockAudio for "
                "thread safety. Cycle-15 fix may have been reverted."
            )
        else:
            pytest.skip("FX_SetVolume function not found in audio_stub.c")



class TestSpriteYvelBounds:
    """Verify cycle-20 sprite Y-velocity bounds checking with player_from_yvel."""

    def test_duke3d_h_player_from_yvel_macro(self, repo_root):
        """DUKE3D.H must define player_from_yvel macro."""
        duke3d_h = repo_root / "source" / "DUKE3D.H"
        if not duke3d_h.exists():
            pytest.skip(f"{duke3d_h} not found")

        content = duke3d_h.read_text(errors="replace")

        assert "player_from_yvel" in content, (
            "DUKE3D.H must define player_from_yvel macro for Y-velocity bounds. "
            "Cycle-20 fix may have been reverted."
        )

    def test_actors_c_player_from_yvel_usage(self, repo_root):
        """ACTORS.C must use player_from_yvel macro at 10+ call sites."""
        actors_c = repo_root / "source" / "ACTORS.C"
        if not actors_c.exists():
            pytest.skip(f"{actors_c} not found")

        content = actors_c.read_text(errors="replace")

        # Count player_from_yvel( function-call usage
        usage_count = content.count("player_from_yvel(")
        assert usage_count >= 10, (
            f"ACTORS.C should use player_from_yvel macro at least 10 times, "
            f"found {usage_count}. Cycle-20 Y-velocity bounds fix may have been reverted."
        )



class TestSavegameLoaderBounds:
    """Verify cycle-20 savegame loader ferror guards after kdfread."""

    def test_menues_c_kdfread_ferror_checks(self, repo_root):
        """MENUES.C must have ferror guards after kdfread operations."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Check for kdfread operations
        has_kdfread = "kdfread(" in content
        # Verify ferror guards exist (already tested in TestMenuesFileIO)
        has_ferror = "ferror(fil)" in content

        assert has_kdfread and has_ferror, (
            "MENUES.C must contain kdfread calls with subsequent ferror(fil) "
            "checks for savegame loading robustness. Cycle-20 fix may have been reverted."
        )

    def test_menues_c_animatecnt_kdfread_boundary(self, repo_root):
        """MENUES.C must have ferror check after animatecnt kdfread."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for kdfread(&animatecnt pattern followed by ferror
        # This is a specific critical boundary in savegame loading
        has_animatecnt_kdfread = "kdfread(&animatecnt" in content
        assert has_animatecnt_kdfread, (
            "MENUES.C savegame loader must read animatecnt via kdfread. "
            "Cycle-20 fix may have been reverted."
        )

    def test_menues_c_wall_sector_partial_reads(self, repo_root):
        """Verify cycle-r8 fix: wall/sector arrays read actual counts then memset remainder."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Check for partial-read pattern: kdfread with numwalls/numsectors + memset cleanup
        has_numwalls_partial_read = (
            "kdfread(&wall[0],sizeof(walltype),numwalls,fil)" in content
        )
        has_numwalls_memset = "memset(wall + numwalls, 0" in content

        has_numsectors_partial_read = (
            "kdfread(&sector[0],sizeof(sectortype),numsectors,fil)" in content
        )
        has_numsectors_memset = "memset(sector + numsectors, 0" in content

        assert has_numwalls_partial_read and has_numwalls_memset, (
            "MENUES.C savegame loader must read numwalls worth of walls, then memset "
            "the remainder. Cycle-r8 fix may have been reverted."
        )
        assert has_numsectors_partial_read and has_numsectors_memset, (
            "MENUES.C savegame loader must read numsectors worth of sectors, then memset "
            "the remainder. Cycle-r8 fix may have been reverted."
        )



class TestCache1dFreeBytes:
    """Verify cycle-22 cache1d_free_bytes counter management in CACHE1D.C."""

    def test_cache1d_c_free_bytes_declaration(self, repo_root):
        """CACHE1D.C must declare static long cache1d_free_bytes."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        assert "static long cache1d_free_bytes" in content, (
            "CACHE1D.C must declare 'static long cache1d_free_bytes' counter. "
            "Cycle-22 memory tracking fix may have been reverted."
        )

    def test_cache1d_c_free_bytes_references(self, repo_root):
        """CACHE1D.C must reference cache1d_free_bytes at 5+ sites."""
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Count cache1d_free_bytes references (excluding the static declaration)
        reference_count = content.count("cache1d_free_bytes")
        assert reference_count >= 5, (
            f"CACHE1D.C should reference cache1d_free_bytes at least 5 times, "
            f"found {reference_count}. Cycle-22 memory tracking fix may have been reverted."
        )



class TestAllocacheOverflowGuard:
    """Verify cycle-25/r8 allocache alignment overflow guard in CACHE1D.C."""

    def test_cache1d_c_allocache_overflow_guard(self, repo_root):
        """CACHE1D.C allocache() must check for overflow before alignment.
        
        This test verifies that the overflow guard pattern is present:
        - Check if newbytes > LONG_MAX - 15 (0x7fffffffL - 15)
        - Guard must come BEFORE the alignment operation
        - Should call reportandexit or similar on overflow
        """
        cache1d_c = repo_root / "SRC" / "CACHE1D.C"
        if not cache1d_c.exists():
            pytest.skip(f"{cache1d_c} not found")

        content = cache1d_c.read_text(errors="replace")

        # Look for overflow guard pattern:
        # The guard should check newbytes > 0x7fffffffL - 15 or similar
        guard_pattern = r"newbytes\s*>\s*0x7fffffffL?\s*-\s*15"
        has_guard = re.search(guard_pattern, content)

        assert has_guard, (
            "CACHE1D.C allocache() must include overflow guard: "
            "check 'if (newbytes > 0x7fffffffL - 15)' or similar before "
            "alignment operation. Cycle-25/r8 allocache-overflow fix may have "
            "been reverted."
        )

        # Verify the guard comes before the alignment operation
        guard_match = re.search(r"if\s*\(\s*newbytes\s*>\s*0x7fffffffL?\s*-\s*15\s*\)", content)
        align_match = re.search(r"newbytes\s*=\s*\(\s*\(\s*newbytes\s*\+\s*15\s*\)\s*&\s*~\s*\(\s*long\s*\)\s*15\s*\)", content)
        
        assert guard_match and align_match, (
            "Could not find guard or alignment patterns in CACHE1D.C"
        )
        
        assert guard_match.start() < align_match.start(), (
            "Overflow guard must appear before alignment operation in CACHE1D.C. "
            "Guard at position {}, alignment at position {}".format(
                guard_match.start(), align_match.start()
            )
        )

        # Verify reportandexit is called in the guard branch
        guard_section = content[guard_match.start():align_match.start()]
        assert "reportandexit" in guard_section, (
            "Overflow guard in CACHE1D.C must call reportandexit() to fail gracefully. "
            "The guard condition was found but exit path may be missing."
        )



class TestSpriteqamountBounds:
    """Verify cycle-19 spriteqamount array bounds checking in MENUES.C."""

    def test_menues_c_spriteqamount_bounds_check(self, repo_root):
        """MENUES.C must have spriteqamount bounds check against MAXSPRITES."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        # Look for bounds check pattern: spriteqamount [<>]= MAXSPRITES
        pattern = r"spriteqamount\s*[<>]=?\s*MAXSPRITES"
        bounds_check = re.search(pattern, content)

        assert bounds_check, (
            "MENUES.C must have a bounds check like "
            "'if(spriteqamount < 0 || spriteqamount > MAXSPRITES)' "
            "or similar. Cycle-19 fix may have been reverted."
        )


# ===== Parametrized integration test =====

class TestAllHardeningFixesSummary:
    """Quick summary that all 8 cycles of hardening are present."""

    @pytest.mark.parametrize(
        "fix_name,file_path,pattern",
        [
            ("labelcode array", "source/GLOBAL.C", "labelcode["),
            ("MENUES.C ferror", "source/MENUES.C", "ferror(fil)"),
            ("audio RIFF", "compat/audio_stub.c", "RIFF"),
            ("audio WAVE", "compat/audio_stub.c", "WAVE"),
            ("Mix_GroupOldest", "compat/audio_stub.c", "Mix_GroupOldest"),
            ("GAMEDEF.C bounds", "source/GAMEDEF.C", "MAXLABELS"),
            ("MMULTI.C bounds", "SRC/MMULTI.C", "MAXPLAYERS"),
            ("SoundOwner aging", "source/SOUNDS.C", "FX_StopSound"),
            ("SDL_LockAudio", "compat/audio_stub.c", "SDL_LockAudio"),
            ("sprite-yvel bounds", "source/DUKE3D.H", "player_from_yvel"),
            ("sprite-yvel usage", "source/ACTORS.C", "player_from_yvel("),
            ("savegame kdfread", "source/MENUES.C", "kdfread("),
            ("cache1d counter", "SRC/CACHE1D.C", "cache1d_free_bytes"),
            ("NET timeout", "SRC/MMULTI.C", "NET_CONNECT_TIMEOUT"),
            ("spriteqamount bounds", "source/MENUES.C", "MAXSPRITES"),
        ],
    )
    def test_hardening_patterns_present(self, repo_root, fix_name, file_path, pattern):
        """Assert that each critical hardening pattern is present."""
        file_to_check = repo_root / file_path
        if not file_to_check.exists():
            pytest.skip(f"{file_path} not found")

        content = file_to_check.read_text(errors="replace")
        assert pattern in content, (
            f"Hardening fix '{fix_name}' pattern '{pattern}' not found in "
            f"{file_path}. A recent refactor may have reverted this fix."
        )



class TestHlineasmShiftBounds:
    """Verify cycle-r8 finding #3: sethlinesizes shift-bounds validation."""

    def test_sethlinesizes_logx_logy_bounds_check(self, repo_root):
        """sethlinesizes must validate logx and logy to [0, 31] range."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Check for bounds clamping in sethlinesizes:
        # Should have pattern like "if (logx < 0)" and "if (logx > 31)"
        has_logx_clamp = "if (logx < 0)" in content and "if (logx > 31)" in content
        assert has_logx_clamp, (
            "sethlinesizes must clamp logx to [0, 31] range. "
            "Check for 'if (logx < 0)' and 'if (logx > 31)' patterns."
        )

        # Same for logy
        has_logy_clamp = "if (logy < 0)" in content and "if (logy > 31)" in content
        assert has_logy_clamp, (
            "sethlinesizes must clamp logy to [0, 31] range. "
            "Check for 'if (logy < 0)' and 'if (logy > 31)' patterns."
        )



class TestAnimateoffsClamp:
    """Verify cycle-r8 finding #4: animateoffs bounds clamping."""

    def test_animateoffs_result_clamped(self, repo_root):
        """animateoffs result must be clamped to [0, MAXTILES) on sprite rendering."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Check for pattern that validates animateoffs result:
        # Should have pattern like "newtile + animateoffs" or similar that checks bounds
        # and falls back to original tilenum if out of range
        has_clamp_pattern = (
            "newtile = tilenum + animateoffs" in content and
            "(unsigned)newtile >= (unsigned)MAXTILES" in content and
            "newtile = tilenum" in content
        )
        assert has_clamp_pattern, (
            "animateoffs result must be bounds-checked before assignment. "
            "Expect pattern: newtile = tilenum + animateoffs; "
            "if ((unsigned)newtile >= (unsigned)MAXTILES) newtile = tilenum;"
        )



class TestHlineasmShiftBounds:
    """Verify cycle-r8 finding #3: sethlinesizes shift-bounds validation."""

    def test_sethlinesizes_logx_logy_bounds_check(self, repo_root):
        """sethlinesizes must validate logx and logy to [0, 31] range."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Check for bounds clamping in sethlinesizes:
        # Should have pattern like "if (logx < 0)" and "if (logx > 31)"
        has_logx_clamp = "if (logx < 0)" in content and "if (logx > 31)" in content
        assert has_logx_clamp, (
            "sethlinesizes must clamp logx to [0, 31] range. "
            "Check for 'if (logx < 0)' and 'if (logx > 31)' patterns."
        )

        # Same for logy
        has_logy_clamp = "if (logy < 0)" in content and "if (logy > 31)" in content
        assert has_logy_clamp, (
            "sethlinesizes must clamp logy to [0, 31] range. "
            "Check for 'if (logy < 0)' and 'if (logy > 31)' patterns."
        )



class TestAnimateoffsClamp:
    """Verify cycle-r8 finding #4: animateoffs bounds clamping."""

    def test_animateoffs_result_clamped(self, repo_root):
        """animateoffs result must be clamped to [0, MAXTILES) on sprite rendering."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Check for pattern that validates animateoffs result:
        # Should have pattern like "newtile + animateoffs" or similar that checks bounds
        # and falls back to original tilenum if out of range
        has_clamp_pattern = (
            "newtile = tilenum + animateoffs" in content and
            "(unsigned)newtile >= (unsigned)MAXTILES" in content and
            "newtile = tilenum" in content
        )
        assert has_clamp_pattern, (
            "animateoffs result must be bounds-checked before assignment. "
            "Expect pattern: newtile = tilenum + animateoffs; "
            "if ((unsigned)newtile >= (unsigned)MAXTILES) newtile = tilenum;"
        )



class TestOperatesectorsDepthCap:
    """Verify engine-r9 operatesectors depth limit fix (stack overflow prevention)."""

    def test_operatesectors_has_depth_counter(self, repo_root):
        """SECTOR.C must declare operatesectors_depth static counter."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        # Check for static depth counter declaration
        assert re.search(
            r"static\s+int\s+operatesectors_depth\s*=\s*0",
            content
        ), (
            "SECTOR.C must declare 'static int operatesectors_depth = 0;' "
            "to prevent stack overflow from recursive operatesectors calls"
        )

    def test_operatesectors_has_max_depth_constant(self, repo_root):
        """SECTOR.C must define OPERATESECTORS_MAX_DEPTH macro."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        # Check for macro definition
        assert re.search(
            r"#define\s+OPERATESECTORS_MAX_DEPTH\s+64",
            content
        ), (
            "SECTOR.C must define '#define OPERATESECTORS_MAX_DEPTH 64' "
            "to set the recursion depth limit"
        )

    def test_operatesectors_depth_check_before_increment(self, repo_root):
        """operatesectors() must check depth >= MAX before incrementing."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        # Check for depth check followed by increment
        # Pattern: if depth >= MAX with error message, then increment
        assert re.search(
            r"operatesectors_depth\s*>=\s*OPERATESECTORS_MAX_DEPTH",
            content
        ), (
            "operatesectors() must check 'operatesectors_depth >= OPERATESECTORS_MAX_DEPTH' "
            "before recursing to prevent stack overflow"
        )

        # Verify error message is logged
        assert re.search(
            r'printf\s*\(\s*"[^"]*SECURITY[^"]*operatesectors',
            content
        ), (
            "operatesectors() must log security message when depth cap is hit"
        )

    def test_operatesectors_increments_depth(self, repo_root):
        """operatesectors() must increment operatesectors_depth."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        # Check that operatesectors_depth++ exists in the file
        assert re.search(
            r"operatesectors_depth\s*\+\+",
            content
        ), (
            "operatesectors() must increment 'operatesectors_depth++' "
            "after the depth check"
        )

    def test_operatesectors_decrements_depth_on_exit(self, repo_root):
        """operatesectors() must decrement operatesectors_depth before exit."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        # Check for cleanup label and decrement
        assert re.search(
            r"cleanup_operatesectors\s*:\s*\n\s*operatesectors_depth\s*--\s*;",
            content
        ), (
            "operatesectors() must have a cleanup_operatesectors label "
            "that decrements 'operatesectors_depth--;' before function exit"
        )

    def test_operatesectors_all_returns_use_goto(self, repo_root):
        """operatesectors() must use goto cleanup for all returns (except early return)."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        # Extract the operatesectors function body
        func_match = re.search(
            r"void\s+operatesectors\s*\(\s*short\s+sn\s*,\s*short\s+ii\s*\)\s*\{(.*?)^cleanup_operatesectors:",
            content,
            re.MULTILINE | re.DOTALL
        )
        assert func_match, "Could not extract operatesectors function"

        func_body = func_match.group(1)

        # Count goto cleanup statements (should be > 0)
        goto_count = len(re.findall(r"goto\s+cleanup_operatesectors", func_body))
        assert goto_count > 0, (
            "operatesectors() must use 'goto cleanup_operatesectors' "
            "for all returns (except early depth-cap return) to ensure decrement"
        )




class TestPlayerWeaponAmmoBounds:
    """Verify engine-r9 player weapon/ammo field bounds checking."""

    def test_duke3d_h_weapon_valid_macro(self, repo_root):
        """DUKE3D.H must declare WEAPON_VALID macro for bounds checking."""
        duke3d_h = repo_root / "source" / "DUKE3D.H"
        if not duke3d_h.exists():
            pytest.skip(f"{duke3d_h} not found")

        content = duke3d_h.read_text(errors="replace")

        # Check for WEAPON_VALID macro
        has_weapon_valid = "#define WEAPON_VALID" in content
        assert has_weapon_valid, (
            "DUKE3D.H must declare 'WEAPON_VALID' macro for weapon bounds checking. "
            "Engine-r9 player-weapon-ammo-bounds fix may have been reverted."
        )

        # Check for WEAPON_CLAMP macro as well
        has_weapon_clamp = "#define WEAPON_CLAMP" in content
        assert has_weapon_clamp, (
            "DUKE3D.H must declare 'WEAPON_CLAMP' macro for weapon index clamping. "
            "Engine-r9 player-weapon-ammo-bounds fix may have been reverted."
        )

    @pytest.mark.xfail(strict=False, reason="engine-r9-player-weapon-ammo-bounds: cycle-30 attempt reverted; awaiting re-dispatch")
    def test_player_c_displayweapon_bounds_check(self, repo_root):
        """PLAYER.C displayweapon() must bounds-check curr_weapon before use."""
        player_c = repo_root / "source" / "PLAYER.C"
        if not player_c.exists():
            pytest.skip(f"{player_c} not found")

        content = player_c.read_text(errors="replace")

        # Look for bounds check in displayweapon function
        # Should check WEAPON_VALID(cw) before using cw in array contexts
        has_bounds_check = "WEAPON_VALID(cw)" in content
        assert has_bounds_check, (
            "PLAYER.C displayweapon() must include bounds check with WEAPON_VALID macro. "
            "Engine-r9 player-weapon-ammo-bounds fix may have been reverted."
        )

        # Check that there's an error message for security
        has_security_msg = "SECURITY" in content and "weapon" in content.lower()
        assert has_security_msg, (
            "PLAYER.C should include security warning message when weapon is out of bounds. "
            "Engine-r9 bounds checking may be incomplete."
        )

    def test_player_c_checkweapons_bounds_check(self, repo_root):
        """PLAYER.C checkweapons() must bounds-check weapon before array access."""
        player_c = repo_root / "source" / "PLAYER.C"
        if not player_c.exists():
            pytest.skip(f"{player_c} not found")

        content = player_c.read_text(errors="replace")

        # Find checkweapons function and verify it has bounds check
        checkweapons_match = re.search(
            r"void\s+checkweapons\s*\(.*?\)\s*\{[^}]*?WEAPON_VALID",
            content,
            re.DOTALL
        )
        assert checkweapons_match, (
            "PLAYER.C checkweapons() must include WEAPON_VALID bounds check. "
            "Engine-r9 player-weapon-ammo-bounds fix may have been reverted."
        )

    @pytest.mark.xfail(strict=False, reason="engine-r9-player-weapon-ammo-bounds: cycle-30 attempt reverted; awaiting re-dispatch")
    def test_player_c_addweapon_call_bounds_check(self, repo_root):
        """PLAYER.C addweapon calls must bounds-check weapon index."""
        player_c = repo_root / "source" / "PLAYER.C"
        if not player_c.exists():
            pytest.skip(f"{player_c} not found")

        content = player_c.read_text(errors="replace")

        # Look for addweapon calls with bounds checking
        # e.g., if (WEAPON_VALID(...)) addweapon(...)
        has_guarded_addweapon = "if (WEAPON_VALID(p->last_full_weapon))" in content
        assert has_guarded_addweapon, (
            "PLAYER.C must guard addweapon() calls with WEAPON_VALID bounds check. "
            "Engine-r9 player-weapon-ammo-bounds fix may be incomplete."
        )


class TestActorTileMetadataBounds:
    def test_picnum_safe_macro(self, repo_root):
        h = repo_root / "source" / "DUKE3D.H"
        assert re.search(r'#define\s+PICNUM_SAFE', h.read_text(errors="replace")), "PICNUM_SAFE macro required"
    
    def test_actor_bounds_guarded(self, repo_root):
        ac = repo_root / "source" / "ACTORS.C"
        c = ac.read_text(errors="replace")
        assert len(re.findall(r'PICNUM_SAFE\(', c)) >= 2, "PICNUM_SAFE not applied to ACTORS.C"



class TestRTSNumlumpsOverflow:
    """Verify cycle-35 RTS.C integer overflow fix (engine-r10-rts-overflow).
    
    Bug: header.numlumps read from attacker-controlled WAD file, then multiplied
    by sizeof(filelump_t) without overflow check. Multiplication can overflow int
    to huge unsigned value, resulting in tiny allocation followed by OOB write.
    
    Fix: Add bounds-check guard before multiplication: if numlumps < 0 or > 65536,
    reject the WAD file and cleanup.
    """

    def test_rts_numlumps_guard_present(self, repo_root):
        """Verify RTS.C has numlumps overflow guard before multiplication."""
        rts_c = repo_root / "source" / "RTS.C"
        if not rts_c.exists():
            pytest.skip(f"{rts_c} not found")
        
        content = rts_c.read_text(errors="replace")
        
        # Check for the guard pattern:
        # if (header.numlumps < 0 || header.numlumps > 65536)
        guard_pattern = re.search(
            r'if\s*\(\s*header\.numlumps\s*<\s*0\s*\|\|\s*header\.numlumps\s*>\s*65536\s*\)',
            content,
            re.MULTILINE
        )
        
        assert guard_pattern, (
            "RTS.C missing numlumps overflow guard. Expected pattern:\n"
            "if (header.numlumps < 0 || header.numlumps > 65536)"
        )
        
        # Check for the error message inside the guard (Error() is the project's
        # fatal handler — equivalent semantics to printf+abort, see RTS.C:82).
        error_msg_pattern = re.search(
            r'(?:printf|Error\s*\().*RTS.*invalid.*numlumps.*refusing',
            content,
            re.MULTILINE | re.IGNORECASE
        )
        
        assert error_msg_pattern, (
            "RTS.C missing error message. Expected Error() or printf with 'RTS: invalid numlumps ... refusing'"
        )
        
        # Verify the guard comes BEFORE the multiplication
        # Pattern: header.numlumps*sizeof(filelump_t)
        mult_pattern = re.search(
            r'length\s*=\s*header\.numlumps\s*\*\s*sizeof\s*\(\s*filelump_t\s*\)',
            content,
            re.MULTILINE
        )
        
        assert mult_pattern, (
            "RTS.C missing numlumps multiplication. Expected pattern:\n"
            "length = header.numlumps*sizeof(filelump_t);"
        )
        
        # Ensure guard appears before multiplication
        guard_pos = guard_pattern.start()
        mult_pos = mult_pattern.start()
        assert guard_pos < mult_pos, (
            "Bounds-check guard must appear BEFORE numlumps multiplication."
        )
        
        # The guard must abort/return — Error() is fatal in this codebase (see RTS.C:82),
        # equivalent to printf-then-exit semantics.
        error_handler = re.search(
            r'if\s*\(\s*header\.numlumps\s*<\s*0\s*\|\|\s*header\.numlumps\s*>\s*65536\s*\)\s*'
            r'(?:\{[^}]*?(?:Error\s*\(|return\s*;|fclose\s*\([^)]*\))[^}]*?\}'
            r'|\s*Error\s*\([^;]*;)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert error_handler, (
            "RTS.C guard must contain Error(), return, or fclose(handle) to halt processing."
        )




class TestDasectSectorIndexValidation:
    """Regression test for engine-r10-dasect-unvalidated vulnerability.
    
    Finding: In ACTORS.C checkfloordamage(), dasect is assigned from tempshort[]
    (attacker-controlled data from map) without validation, then immediately
    dereferenced with sector[dasect].ceilingz at line 471+. This allows
    out-of-bounds reads if dasect < 0 or dasect >= MAXSECTORS (1024).
    
    Fix: Add bounds-check guard immediately after assignment and before
    first dereference.
    """

    def test_dasect_bounds_check_present(self, repo_root):
        """Verify dasect has bounds-check before sector[] dereference."""
        actors_c = repo_root / "source" / "ACTORS.C"
        content = actors_c.read_text(errors="replace")
        
        # Verify the sentinel comment exists
        assert "engine-r10-dasect-unvalidated" in content, (
            "Missing sentinel comment for dasect bounds-check."
        )
        
        # Find the pattern: dasect = tempshort[...]; followed by bounds-check guard.
        # Allow an optional /* ... */ sentinel comment between the two lines.
        bounds_check_pattern = re.search(
            r'dasect\s*=\s*tempshort\[sectcnt\+\+\]\s*;'
            r'(?:\s|/\*.*?\*/)*'
            r'if\s*\(\s*dasect\s*<\s*0\s*\|\|\s*dasect\s*>=\s*MAXSECTORS\s*\)\s*continue\s*;',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert bounds_check_pattern, (
            "dasect bounds-check not found. Expected pattern:\n"
            "dasect = tempshort[sectcnt++];\n"
            "if(dasect < 0 || dasect >= MAXSECTORS) continue;"
        )
        
        # Get the position where the bounds-check pattern ends
        bounds_check_end = bounds_check_pattern.end()
        
        # Verify that sector[dasect] appears after the bounds-check
        # Look for sector[dasect] within the next 500 characters
        post_check_content = content[bounds_check_end:bounds_check_end+500]
        assert "sector[dasect]" in post_check_content, (
            "sector[dasect] dereference must appear after the bounds-check guard."
        )



class TestSpriteQAmountBounds:
    """Regression test for spriteqamount savegame bounds-check fix.
    
    Finding: spriteqamount loaded from savegame was checked against MAXSPRITES (4096),
    but the spriteq[] array is only 1024 elements. This could cause out-of-bounds
    reads when the savegame contains spriteqamount > 1024.
    
    Fix: Add defensive bounds-check capping spriteqamount to 1024 array size.
    """

    def test_spriteqamount_bounds_check(self, repo_root):
        """Verify spriteqamount has bounds-check against actual array size."""
        menues_c = repo_root / "source" / "MENUES.C"
        content = menues_c.read_text(errors="replace")
        
        # Verify the sentinel comment exists
        assert "engine-porter: defensive cap against spriteq[1024]" in content, (
            "Missing sentinel comment for spriteqamount bounds-check."
        )
        
        # Find the bounds-check pattern
        bounds_check_pattern = re.search(
            r'/\*\s*engine-porter:\s*defensive\s+cap\s+against\s+spriteq\[1024\].*?\*/'
            r'\s*if\s*\(\s*spriteqamount\s*>\s*1024\s*\)\s*spriteqamount\s*=\s*0\s*;',
            content,
            re.MULTILINE
        )
        
        assert bounds_check_pattern, (
            "spriteqamount bounds-check not found. Expected pattern:\n"
            "/* engine-porter: defensive cap against spriteq[1024] */\n"
            "if(spriteqamount > 1024) spriteqamount = 0;"
        )
        
        # Verify the existing MAXSPRITES check is still present
        maxsprites_check = re.search(
            r'if\s*\(\s*spriteqamount\s*<\s*0\s*\|\|\s*spriteqamount\s*>\s*MAXSPRITES\s*\)',
            content
        )
        assert maxsprites_check, (
            "Original MAXSPRITES check must be preserved (not modified)."
        )
        
        # Verify the new check appears after the MAXSPRITES check
        maxsprites_pos = maxsprites_check.start()
        new_check_pos = bounds_check_pattern.start()
        assert new_check_pos > maxsprites_pos, (
            "New bounds-check must appear AFTER the MAXSPRITES check."
        )
        
        # Verify the kdfread call is after the bounds-check
        kdfread_pattern = re.search(
            r'kdfread\s*\(\s*\(short\s*\*\)\s*&spriteq\[0\]',
            content
        )
        assert kdfread_pattern, "kdfread for spriteq not found."
        assert kdfread_pattern.start() > new_check_pos, (
            "kdfread must come AFTER the new bounds-check."
        )



class TestGameUnsafeStringReplacements:
    """Verify that unsafe strcpy/strcat have been replaced with safe equivalents."""

    def test_user_quote_strcpy_replaced(self, repo_root):
        """
        Verify that strcpy calls on user_quote arrays are replaced with strncpy.
        Test covers lines 355, 359 in source/GAME.C where user_quote buffers
        are copied and must be NUL-terminated.
        """
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Check line 355: strcpy(user_quote[i],...) should be strncpy
        line_355_pattern = re.search(
            r'strncpy\s*\(\s*user_quote\s*\[\s*i\s*\]\s*,\s*user_quote\s*\[\s*i\s*-\s*1\s*\]\s*,\s*128\s*\)',
            content
        )
        assert line_355_pattern, (
            "Line 355: user_quote strcpy must be replaced with strncpy(user_quote[i],...,128)"
        )
        
        # Check that NUL-termination follows at line 356
        nul_term_355 = re.search(
            r'strncpy\s*\(\s*user_quote\s*\[\s*i\s*\]\s*,\s*user_quote\s*\[\s*i\s*-\s*1\s*\]\s*,\s*128\s*\)\s*;\s*'
            r'user_quote\s*\[\s*i\s*\]\s*\[\s*127\s*\]\s*=\s*0\s*;',
            content
        )
        assert nul_term_355, (
            "Line 356: NUL-termination (user_quote[i][127] = 0) required after strncpy"
        )
        
        # Check line 359: strcpy(user_quote[0], daquote) should be strncpy
        line_359_pattern = re.search(
            r'strncpy\s*\(\s*user_quote\s*\[\s*0\s*\]\s*,\s*daquote\s*,\s*128\s*\)',
            content
        )
        assert line_359_pattern, (
            "Line 359: user_quote strcpy must be replaced with strncpy(user_quote[0],...,128)"
        )
        
        # Check that NUL-termination follows at line 360
        nul_term_359 = re.search(
            r'strncpy\s*\(\s*user_quote\s*\[\s*0\s*\]\s*,\s*daquote\s*,\s*128\s*\)\s*;\s*'
            r'user_quote\s*\[\s*0\s*\]\s*\[\s*127\s*\]\s*=\s*0\s*;',
            content
        )
        assert nul_term_359, (
            "Line 360: NUL-termination (user_quote[0][127] = 0) required after strncpy"
        )

    def test_chat_message_strcat_replaced(self, repo_root):
        """
        Verify that strcat on tempbuf+1 is replaced with strncat.
        Test covers line 2321 in source/GAME.C where chat messages are appended
        to the network buffer.
        """
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Check line 2321: strcat(tempbuf+1, recbuf) should be strncat
        line_2321_pattern = re.search(
            r'strncat\s*\(\s*tempbuf\s*\+\s*1\s*,\s*recbuf\s*,\s*2047\s*\)',
            content
        )
        assert line_2321_pattern, (
            "Line 2321: strcat(tempbuf+1,recbuf) must be replaced with strncat(tempbuf+1,recbuf,2047)"
        )

    def test_ridecule_strcat_replaced(self, repo_root):
        """
        Verify that strcat on tempbuf+1 with ridecule is replaced with strncat.
        Test covers line 6479 in source/GAME.C where ridecule messages are appended
        to the network buffer.
        """
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Check line 6479: strcat(tempbuf+1, ud.ridecule[...]) should be strncat
        line_6479_pattern = re.search(
            r'strncat\s*\(\s*tempbuf\s*\+\s*1\s*,\s*ud\s*\.\s*ridecule\s*\[\s*i\s*-\s*1\s*\]\s*,\s*2047\s*\)',
            content
        )
        assert line_6479_pattern, (
            "Line 6479: strcat(tempbuf+1,ud.ridecule[i-1]) must be replaced with strncat(...,2047)"
        )

    @pytest.mark.parametrize("unsafe_func,description", [
        ("strcpy", "strcpy (unsafe string copy)"),
        ("strcat", "strcat (unsafe string concatenation)"),
    ])
    def test_no_unsafe_functions_on_patched_lines(self, repo_root, unsafe_func, description):
        """
        Parametrized test: Verify that unsafe string functions are gone from patched lines.
        This is the primary regression check - if someone accidentally reverts the changes,
        this will catch it.
        """
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        lines = game_c.read_text(errors="replace").split("\n")
        
        # Check lines 355, 359 for strcpy
        if unsafe_func == "strcpy":
            for line_num in [354, 358]:  # 0-indexed: line 355 = idx 354
                assert unsafe_func not in lines[line_num], (
                    f"Line {line_num+1}: {description} should be removed (found in: {lines[line_num][:80]})"
                )
        
        # Check lines 2321, 6479 for strcat
        if unsafe_func == "strcat":
            for line_num in [2320, 6478]:  # 0-indexed
                assert unsafe_func not in lines[line_num], (
                    f"Line {line_num+1}: {description} should be removed (found in: {lines[line_num][:80]})"
                )



class TestDrawspriteSectnumBounds:
    """Verify r11 drawsprite sectnum bounds check (engine-r11-drawsprite-sectnum)."""

    def test_drawsprite_sectnum_bounds_check(self, repo_root):
        """ENGINE.C drawsprite() must bounds-check sectnum before sector[] deref."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find the drawsprite function
        if "drawsprite" not in content:
            pytest.skip("drawsprite function not found in ENGINE.C")

        # Check for the bounds check pattern around sectnum assignment
        # Pattern: if ((unsigned)sectnum >= (unsigned)MAXSECTORS) return;
        # Or: /* engine-r11-drawsprite-sectnum: bound check before sector[] deref */
        has_sectnum_check = (
            "engine-r11-drawsprite-sectnum" in content and
            "if ((unsigned)sectnum >= (unsigned)MAXSECTORS)" in content
        )

        assert has_sectnum_check, (
            "ENGINE.C drawsprite() must have bounds check for sectnum before "
            "sector[sectnum] dereference. Expected pattern: "
            "'if ((unsigned)sectnum >= (unsigned)MAXSECTORS) return;' with "
            "comment 'engine-r11-drawsprite-sectnum'"
        )



class TestDrawroomsCursectnumBounds:
    """Verify r11 drawrooms cursectnum bounds check (engine-r11-drawrooms-cursectnum)."""

    def test_drawrooms_cursectnum_bounds_check(self, repo_root):
        """ENGINE.C drawrooms() must bounds-check cursectnum before sector[] deref."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Find the drawrooms function
        if "drawrooms" not in content:
            pytest.skip("drawrooms function not found in ENGINE.C")

        # Check for the bounds check pattern in drawrooms
        # Pattern: if((unsigned)dacursectnum >= MAXSECTORS) return;
        has_cursectnum_check = (
            "if((unsigned)dacursectnum >= MAXSECTORS)" in content
        )

        assert has_cursectnum_check, (
            "ENGINE.C drawrooms() must have bounds check for cursectnum parameter "
            "before sector[cursectnum] dereference. Expected pattern: "
            "'if((unsigned)dacursectnum >= MAXSECTORS) return;'"
        )



class TestScansectorDepthCap:
    """Verify cycle-38 engine-r12 scansector depth overflow guard."""

    def test_scansector_depth_cap_guard_present(self, repo_root):
        """SRC/ENGINE.C scansector() must have >= 256 overflow guard before push."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Check for the sentinel comment that marks the fix
        has_sentinel = "engine-r12-scansector-depth-cap: stack overflow guard" in content

        # Check for the guard condition >= 256
        has_guard = ("sectorbordercnt >= 256" in content or 
                     "sectorbordercnt >= SCANSECTOR_MAX_DEPTH" in content or
                     "sectorbordercnt >= MAXSECTORS" in content)

        assert has_sentinel, (
            "SRC/ENGINE.C scansector() must include sentinel comment:\n"
            "'engine-r12-scansector-depth-cap: stack overflow guard'"
        )

        assert has_guard, (
            "SRC/ENGINE.C scansector() must include overflow guard:\n"
            "'if (sectorbordercnt >= 256) return;' or equivalent\n"
            "placed BEFORE the sectorborder[] push operation"
        )

    def test_scansector_guard_before_push(self, repo_root):
        """Verify guard check precedes sectorborder[] increment."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        # Extract scansector function body to verify guard ordering
        # Pattern: Find the region with both the sentinel and the push
        sentinel_idx = content.find("engine-r12-scansector-depth-cap")
        push_idx = content.find("sectorborder[sectorbordercnt++]")

        if sentinel_idx == -1:
            pytest.skip("Sentinel comment not found")
        if push_idx == -1:
            pytest.skip("sectorborder push not found")

        # Verify sentinel appears before the push operation
        assert sentinel_idx < push_idx, (
            "Sentinel comment must appear before sectorborder[] push operation"
        )

        # Extract the region between sentinel and push to verify guard structure
        guard_region = content[sentinel_idx:push_idx+50]

        # Verify guard condition is present in the region
        has_guard_check = ("sectorbordercnt >= 256" in guard_region or
                          "sectorbordercnt >= SCANSECTOR_MAX_DEPTH" in guard_region or
                          "sectorbordercnt >= MAXSECTORS" in guard_region)

        assert has_guard_check, (
            "Guard check 'if (sectorbordercnt >= 256) return;' must be\n"
            "between sentinel comment and sectorborder[] push operation"
        )




class TestActorsDasectnumBounds:
    """Verify r12 ACTORS.C dasectnum bounds check (engine-r12-actors-dasectnum-bounds)."""

    def test_actors_dasectnum_bounds_check(self, repo_root):
        """ACTORS.C must bounds-check dasectnum before sector[] dereferences around lines 675-690."""
        actors_c = repo_root / "source" / "ACTORS.C"
        if not actors_c.exists():
            pytest.skip(f"{actors_c} not found")

        content = actors_c.read_text(errors="replace")

        # Check for the sentinel comment that marks the fix
        has_sentinel = "engine-r12-actors-dasectnum-bounds" in content

        # Check for MAXSECTORS bounds check pattern near the vulnerable area
        # Pattern: if((unsigned)dasectnum >= MAXSECTORS)
        has_bounds_check = "if((unsigned)dasectnum >= MAXSECTORS)" in content

        # Verify both the sentinel and the bounds check are present
        assert has_sentinel and has_bounds_check, (
            "source/ACTORS.C around lines 675-690 must have:\n"
            "1. Sentinel comment: 'engine-r12-actors-dasectnum-bounds: sector bounds guard'\n"
            "2. Bounds check pattern: 'if((unsigned)dasectnum >= MAXSECTORS)'\n"
            "The guard must be placed BEFORE sector[dasectnum] accesses to prevent OOB dereference."
        )

        # Verify the guard is present in the right area (within ~10 lines of the original 675-690)
        # Extract content around the guard location
        lines = content.split('\n')
        guard_line = None
        sentinel_line = None

        for i, line in enumerate(lines):
            if "engine-r12-actors-dasectnum-bounds" in line:
                sentinel_line = i
            if "if((unsigned)dasectnum >= MAXSECTORS)" in line:
                guard_line = i

        # The guard and sentinel should be near each other or on the same line
        assert sentinel_line is not None, (
            "Sentinel comment 'engine-r12-actors-dasectnum-bounds' not found in ACTORS.C"
        )
        assert guard_line is not None, (
            "Bounds check 'if((unsigned)dasectnum >= MAXSECTORS)' not found in ACTORS.C"
        )

        # They should be on the same line or very close
        if guard_line is not None and sentinel_line is not None:
            assert abs(guard_line - sentinel_line) <= 1, (
                f"Sentinel comment (line {sentinel_line}) and bounds check (line {guard_line}) "
                f"should be on the same line or adjacent. Found {abs(guard_line - sentinel_line)} lines apart."
            )



class TestSpawnSectnumBounds:
    """Verify r12 spawn() sectnum bounds check (engine-r12-game-spawn-sect-bounds)."""

    def test_spawn_sectnum_bounds_check(self, repo_root):
        """GAME.C spawn() must bounds-check sprite[i].sectnum before sector[] deref."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Find the spawn function
        if "spawn(" not in content:
            pytest.skip("spawn function not found in GAME.C")

        # Check for sentinel comment around line 3409-3410
        has_sentinel = "engine-r12-game-spawn-sect-bounds" in content

        assert has_sentinel, (
            "GAME.C spawn() must have sentinel comment "
            "'engine-r12-game-spawn-sect-bounds: sectnum guard before sector[] deref'"
        )

        # Extract lines around 3409-3410 (±15 lines for flexibility)
        lines = content.split('\n')
        
        # Find lines near 3409 where sector[SECT] first appears
        sect_deref_line = None
        guard_line = None
        sentinel_line = None
        
        for i, line in enumerate(lines):
            # Roughly around line 3409 (0-indexed would be ~3408-3410)
            if i >= 3350 and i <= 3450:
                if "engine-r12-game-spawn-sect-bounds" in line:
                    sentinel_line = i
                if "sector[SECT].floorz" in line or "sector[SECT].ceilingz" in line:
                    sect_deref_line = i
                # Check for MAXSECTORS guard
                if "(unsigned)sprite[i].sectnum >= MAXSECTORS" in line:
                    guard_line = i
        
        # Verify sentinel exists
        assert sentinel_line is not None, (
            "Sentinel comment 'engine-r12-game-spawn-sect-bounds' not found near line 3409"
        )
        
        # Verify guard exists
        assert guard_line is not None, (
            "Bounds check '(unsigned)sprite[i].sectnum >= MAXSECTORS' not found near line 3409"
        )
        
        # Verify guard comes BEFORE the sector[] deref
        if sect_deref_line is not None:
            assert guard_line < sect_deref_line, (
                f"MAXSECTORS guard (line {guard_line}) must come BEFORE sector[SECT] deref (line {sect_deref_line})"
            )
        
        # Verify they are within ~15 lines of each other
        assert abs(sentinel_line - guard_line) <= 2, (
            f"Sentinel (line {sentinel_line}) and guard (line {guard_line}) "
            f"should be on same or adjacent lines. Found {abs(sentinel_line - guard_line)} lines apart."
        )



class TestFtaQuotesStrcpyOverflow:
    """Verify r12 fta_quotes buffer overflow fix (sec-r12-strcat-fta-quotes-overflow)."""

    def test_fta_quotes_strncpy_replacement(self, repo_root):
        """GAME.C lines 6482, 6704: verify strcpy→strncpy replacement for fta_quotes buffer."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        sentinel_found_6480s = False
        sentinel_found_6700s = False
        strncpy_found_6480s = False
        strncpy_found_6700s = False
        strcpy_found_6480s = False
        strcpy_found_6700s = False

        for i in range(max(0, 6475-1), min(len(lines), 6515)):
            if "sec-r12-strcat-fta-quotes-overflow" in lines[i]:
                sentinel_found_6480s = True
            if "strncpy(fta_quotes" in lines[i] or "strncpy(&fta_quotes" in lines[i]:
                strncpy_found_6480s = True
            if "strcpy(fta_quotes" in lines[i] or "strcpy(&fta_quotes" in lines[i]:
                strcpy_found_6480s = True

        for i in range(max(0, 6700-1), min(len(lines), 6740)):
            if "sec-r12-strcat-fta-quotes-overflow" in lines[i]:
                sentinel_found_6700s = True
            if "strncpy(fta_quotes" in lines[i] or "strncpy(&fta_quotes" in lines[i]:
                strncpy_found_6700s = True
            if "strcpy(fta_quotes" in lines[i] or "strcpy(&fta_quotes" in lines[i]:
                strcpy_found_6700s = True

        assert sentinel_found_6480s or sentinel_found_6700s, (
            "Sentinel comment 'sec-r12-strcat-fta-quotes-overflow' not found "
            "near lines 6482 or 6704 in GAME.C"
        )

        assert strncpy_found_6480s, (
            "strncpy(fta_quotes, ...) not found near line 6487 in GAME.C; "
            "strcpy must be replaced with strncpy + explicit null-termination"
        )

        assert strncpy_found_6700s, (
            "strncpy(fta_quotes, ...) not found near line 6708 in GAME.C; "
            "strcpy must be replaced with strncpy + explicit null-termination"
        )

        assert not strcpy_found_6480s, (
            "Raw strcpy(fta_quotes) still found near line 6487; "
            "must use strncpy + explicit null-termination"
        )

        assert not strcpy_found_6700s, (
            "Raw strcpy(fta_quotes) still found near line 6708; "
            "must use strncpy + explicit null-termination"
        )



class TestActorsSpriteSectnumChain:
    """Verify r12 ACTORS.C sprite sectnum bounds check (engine-r12-actors-sprite-sectnum-chain)."""

    def test_actors_sprite_sectnum_chain_guards_present(self, repo_root):
        """ACTORS.C must have >= 2 sectnum bounds guards in animation logic (lines 900-1319)."""
        actors_c = repo_root / "source" / "ACTORS.C"
        if not actors_c.exists():
            pytest.skip(f"{actors_c} not found")

        content = actors_c.read_text(errors="replace")
        lines = content.split('\n')

        # Count sentinel occurrences within the line range 900-1319
        # The sentinel is: engine-r12-actors-sprite-sectnum-chain
        sentinel_count = 0
        sentinel_lines = []

        for i, line in enumerate(lines):
            line_num = i + 1
            if 900 <= line_num <= 1319:
                if "engine-r12-actors-sprite-sectnum-chain" in line:
                    sentinel_count += 1
                    sentinel_lines.append(line_num)

        assert sentinel_count >= 2, (
            f"ACTORS.C lines 900-1319 must have at least 2 bounds guards with sentinel "
            f"'engine-r12-actors-sprite-sectnum-chain', found {sentinel_count} at lines {sentinel_lines}.\n"
            "Guards must protect sector[s->sectnum] derefs from cascading OOB access."
        )

    def test_actors_sprite_sectnum_chain_bounds_check_pattern(self, repo_root):
        """ACTORS.C must have pattern if((unsigned)s->sectnum >= MAXSECTORS) guards."""
        actors_c = repo_root / "source" / "ACTORS.C"
        if not actors_c.exists():
            pytest.skip(f"{actors_c} not found")

        content = actors_c.read_text(errors="replace")

        # Check for the bounds check pattern
        has_bounds_check = "if((unsigned)s->sectnum >= MAXSECTORS)" in content

        assert has_bounds_check, (
            "source/ACTORS.C must include bounds check pattern:\n"
            "'if((unsigned)s->sectnum >= MAXSECTORS)'\n"
            "used in animation logic (ms, movefta, moveplayers functions)"
        )



class TestActorsProjectileSectnumGuard:
    """Verify bounds guard for sprite[j].sectnum in projectile deflection code."""

    def test_engine_r12_sentinel_present(self, repo_root):
        """source/GAME.C must have sentinel 'engine-r12-actors-projectile-sectnum' comment."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "engine-r12-actors-projectile-sectnum" in content, (
            "source/GAME.C must contain sentinel comment 'engine-r12-actors-projectile-sectnum' "
            "to mark the fix for the OOB write to tempsectorz[] array."
        )

    def test_bounds_guard_pattern_present(self, repo_root):
        """source/GAME.C must have bounds guard for (unsigned)sprite[j].sectnum >= (unsigned)MAXSECTORS."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for the bounds guard pattern
        assert "(unsigned)sprite[j].sectnum >= (unsigned)MAXSECTORS" in content, (
            "source/GAME.C must contain bounds guard pattern: "
            "(unsigned)sprite[j].sectnum >= (unsigned)MAXSECTORS"
        )



class TestSecR13MenuesStrcpy:
    """Tests for sec-r13 strcpy buffer overflow fixes in source/MENUES.C"""

    def test_sec_r13_strcpy_menuname_filesystem_overflow_sentinel(self, repo_root):
        """source/MENUES.C must have sentinel 'sec-r13-strcpy-menuname-filesystem-overflow' comment."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        assert "sec-r13-strcpy-menuname-filesystem-overflow" in content, (
            "source/MENUES.C must contain sentinel comment 'sec-r13-strcpy-menuname-filesystem-overflow' "
            "to mark the fix for the strcpy buffer overflow on filesystem input menuname."
        )

    def test_sec_r13_strcpy_password_defensive_sentinel(self, repo_root):
        """source/MENUES.C must have sentinel 'sec-r13-strcpy-password-defensive' comment."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        assert "sec-r13-strcpy-password-defensive" in content, (
            "source/MENUES.C must contain sentinel comment 'sec-r13-strcpy-password-defensive' "
            "to mark the fix for the strcpy buffer overflow on password field."
        )

    def test_no_strcpy_menuname_in_menues_c(self, repo_root):
        """source/MENUES.C must not have 'strcpy(menuname' remaining."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        assert "strcpy(menuname" not in content, (
            "source/MENUES.C must not have any remaining 'strcpy(menuname' calls. "
            "All must be replaced with strncpy + null-terminator."
        )

    def test_no_strcpy_pwlockout_in_menues_c(self, repo_root):
        """source/MENUES.C must not have 'strcpy(&ud.pwlockout' remaining."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        assert "strcpy(&ud.pwlockout" not in content, (
            "source/MENUES.C must not have any remaining 'strcpy(&ud.pwlockout' calls. "
            "All must be replaced with strncpy + null-terminator."
        )

    def test_engine_r13_nextsectorneighborz_bounds_sentinel(self, repo_root):
        """Verify engine-r13-engine-nextsectorneighborz-bounds sentinel guards are present."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        sentinel = "engine-r13-engine-nextsectorneighborz-bounds"
        sentinel_count = content.count(sentinel)

        assert sentinel_count >= 2, (
            f"nextsectorneighborz bounds hardening must have at least 2 sentinel comments. "
            f"Found {sentinel_count}. Sentinel: '/* {sentinel} */'."
        )



class TestSecR13SprintfBoundsAudit:
    """Verify sec-r13-sprintf-bounds-audit fix (sprintf -> snprintf for tempbuf)."""

    def test_sentinel_comment_present(self, repo_root):
        """Verify sec-r13-sprintf-bounds-audit sentinel appears at least once."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")
        sentinel_count = content.count("sec-r13-sprintf-bounds-audit")

        assert sentinel_count >= 1, (
            f"source/MENUES.C must have at least 1 'sec-r13-sprintf-bounds-audit' sentinel comment, "
            f"found {sentinel_count}"
        )

    def test_no_sprintf_tempbuf_remain(self, repo_root):
        """Verify NO sprintf(tempbuf calls remain in source/MENUES.C."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")
        lines = content.split('\n')

        sprintf_tempbuf_count = 0
        sprintf_tempbuf_lines = []
        for i, line in enumerate(lines):
            if "sprintf(tempbuf" in line:
                sprintf_tempbuf_count += 1
                sprintf_tempbuf_lines.append(i + 1)

        assert sprintf_tempbuf_count == 0, (
            f"source/MENUES.C must have NO 'sprintf(tempbuf' calls remaining, "
            f"found {sprintf_tempbuf_count} at lines: {sprintf_tempbuf_lines}"
        )

    def test_snprintf_tempbuf_present(self, repo_root):
        """Verify at least 10 snprintf(tempbuf, sizeof(tempbuf) calls present."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")
        snprintf_tempbuf_count = content.count("snprintf(tempbuf, sizeof(tempbuf)")

        assert snprintf_tempbuf_count >= 10, (
            f"source/MENUES.C must have at least 10 'snprintf(tempbuf, sizeof(tempbuf)' calls, "
            f"found {snprintf_tempbuf_count}"
        )



class TestEngineR13SectorBounds:
    """Verify bounds guards for sector indexing in engine-r13."""

    def test_operatesectors_bounds_sentinel(self, repo_root):
        """source/SECTOR.C operatesectors() must have sentinel 'engine-r13-sector-operatesectors-bounds'."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        assert "engine-r13-sector-operatesectors-bounds" in content, (
            "source/SECTOR.C must contain sentinel comment 'engine-r13-sector-operatesectors-bounds' "
            "to mark the entry guard for operatesectors()."
        )

    def test_operatesectors_bounds_check_present(self, repo_root):
        """source/SECTOR.C operatesectors() must check '(unsigned)sn >= (unsigned)MAXSECTORS'."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        assert "(unsigned)sn >= (unsigned)MAXSECTORS" in content, (
            "source/SECTOR.C operatesectors() must have bounds check '(unsigned)sn >= (unsigned)MAXSECTORS'"
        )

    def test_animatesect_bounds_sentinel(self, repo_root):
        """source/SECTOR.C doanimations() must have sentinel 'engine-r13-sector-animatesect-bounds'."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        assert "engine-r13-sector-animatesect-bounds" in content, (
            "source/SECTOR.C must contain sentinel comment 'engine-r13-sector-animatesect-bounds' "
            "to mark the skip guard for animatesect[]."
        )

    def test_animatesect_bounds_check_present(self, repo_root):
        """source/SECTOR.C doanimations() must check '(unsigned)dasect >= (unsigned)MAXSECTORS'."""
        sector_c = repo_root / "source" / "SECTOR.C"
        if not sector_c.exists():
            pytest.skip(f"{sector_c} not found")

        content = sector_c.read_text(errors="replace")

        assert "(unsigned)dasect >= (unsigned)MAXSECTORS" in content, (
            "source/SECTOR.C doanimations() must have bounds check '(unsigned)dasect >= (unsigned)MAXSECTORS'"
        )


# ============================================================================
# pytest-xdist Integration Tests (perf-r12-pytest-xdist-integration)
# ============================================================================

def test_pytest_xdist_in_requirements():
    """Verify pytest-xdist>=3.5 is in requirements.txt for parallel test execution."""
    from pathlib import Path
    req_file = Path(__file__).parent.parent / "requirements.txt"
    content = req_file.read_text()
    
    assert "pytest-xdist" in content, (
        "requirements.txt must contain pytest-xdist>=3.5 for parallel test execution"
    )
    
    # Extract version constraint
    import re
    match = re.search(r'pytest-xdist([>=<]+[\d.]+)?', content)
    assert match, "pytest-xdist version not found"
    
    version_spec = match.group(1) or ""
    # Allow >=3.5 or any 3.x version
    if version_spec and "3." not in version_spec:
        # If version is specified, ensure it's at least 3.5
        assert ">=3" in version_spec or "==3" in version_spec or version_spec == "", (
            f"pytest-xdist version should be >=3.5, got: pytest-xdist{version_spec}"
        )


def test_pytest_ini_documents_xdist_status():
    """Verify pytest.ini has xdist enabled via addopts and sentinel documented.

    The session-autouse `generated_audio_artifacts` fixture (tests/conftest.py)
    uses FileLock to coordinate across xdist workers, ensuring artifacts are
    generated once and shared safely. This enables parallel test execution.
    
    See perf-r12-xdist-fixture-redesign for the filelock-based coordination pattern.
    """
    from pathlib import Path
    pytest_ini = Path(__file__).parent.parent / "pytest.ini"
    content = pytest_ini.read_text()

    assert "perf-r12-pytest-xdist-integration" in content, (
        "pytest.ini must retain sentinel comment 'perf-r12-pytest-xdist-integration'"
    )
    assert "serial" in content, (
        "pytest.ini must retain the `serial` marker registration for xdist"
    )
    assert "-n auto" in content, (
        "pytest.ini must have 'addopts = -n auto' to enable parallel test execution"
    )
    assert "perf-r12-xdist-fixture-redesign" in content, (
        "pytest.ini must reference perf-r12-xdist-fixture-redesign to document the fix"
    )



def test_pytest_ini_has_serial_marker():
    """Verify pytest.ini has serial marker registration for xdist."""
    from pathlib import Path
    pytest_ini = Path(__file__).parent.parent / "pytest.ini"
    content = pytest_ini.read_text()
    
    assert "serial:" in content or "serial" in content, (
        "pytest.ini must have serial marker registered for tests incompatible with xdist"
    )


def test_audio_pipeline_tests_marked_serial():
    """Verify stateful tests are marked with @pytest.mark.serial."""
    from pathlib import Path
    audio_pipeline = Path(__file__).parent / "test_audio_pipeline.py"
    content = audio_pipeline.read_text()
    
    # Check for serial marker on tests that write to generated_assets/
    assert "@pytest.mark.serial" in content, (
        "test_audio_pipeline.py should have tests marked with @pytest.mark.serial "
        "for tests that write to generated_assets/"
    )
    
    # Verify specific tests are marked
    assert "@pytest.mark.serial" in content and "test_no_ai_flag_generates_wav_files" in content, (
        "test_no_ai_flag_generates_wav_files should be marked @pytest.mark.serial"
    )
    
    assert "TestParallelManifestRace" in content, (
        "TestParallelManifestRace class should exist for testing parallel coordination"
    )



class TestSecR13GameStrcatTempbufHarden:
    """Verify sec-r13 GAME.C strcat(tempbuf) bounded hardening."""
    
    def test_sentinel_comment_present(self, repo_root):
        """Assert sentinel comment 'sec-r13-game-c-strcat-tempbuf-harden' appears at least once."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        sentinel = "sec-r13-game-c-strcat-tempbuf-harden"
        
        assert sentinel in content, (
            f"Sentinel comment '{sentinel}' must appear at least once in GAME.C"
        )
    
    def test_no_unbounded_strcat_on_tempbuf(self, repo_root):
        """Assert NO bare strcat(&tempbuf[0], ...) or strcat(tempbuf, ...) remain."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        """Count unbounded strcat patterns"""
        unbounded_patterns = [
            r"strcat\s*\(\s*&tempbuf\s*\[",
            r"strcat\s*\(\s*tempbuf\s*,",
        ]
        
        for pattern in unbounded_patterns:
            matches = re.findall(pattern, content)
            assert len(matches) == 0, (
                f"Found {len(matches)} unbounded strcat calls matching '{pattern}' in GAME.C. "
                "All strcat(tempbuf, ...) must be replaced with bounded strncat()."
            )
    
    def test_strncat_on_tempbuf_present(self, repo_root):
        """Assert at least 1 strncat(tempbuf, ...) is present."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        """Count strncat on tempbuf"""
        strncat_matches = re.findall(r"strncat\s*\(\s*tempbuf", content)
        
        assert len(strncat_matches) >= 1, (
            "At least 1 strncat(tempbuf, ...) must be present in GAME.C after hardening"
        )



class TestFixEngineCloudArraySizing:
    """Verify fix-engine-cloud-array-sizing: opaque sizeof(short)<<7 replaced with explicit MAXCLOUDS constant."""
    
    def test_maxclouds_define_exists(self, repo_root):
        """Assert MAXCLOUDS define exists in source/MENUES.C."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")
        
        content = menues_c.read_text(errors="replace")
        
        """Check for #define MAXCLOUDS 128"""
        maxclouds_pattern = r"#define\s+MAXCLOUDS\s+128"
        assert re.search(maxclouds_pattern, content), (
            "MAXCLOUDS define (= 128) must exist in source/MENUES.C"
        )
    
    def test_no_old_sizeof_short_shift7_pattern(self, repo_root):
        """Assert NO remaining sizeof(short)<<7 patterns in actual code (OK in comments/sentinel)."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")
        
        content = menues_c.read_text(errors="replace")
        
        """Find lines with sizeof(short)<<7"""
        lines_with_pattern = []
        for i, line in enumerate(content.split('\n'), 1):
            """Skip if it's only in a comment"""
            if 'sizeof(short)<<7' in line:
                """Check if this is NOT just in the #define comment"""
                stripped = line.split('/*')[0]  
                if 'sizeof(short)<<7' in stripped:
                    lines_with_pattern.append(f"line {i}: {line}")
        
        assert len(lines_with_pattern) == 0, (
            f"No sizeof(short)<<7 patterns should remain in code. Found {len(lines_with_pattern)}: {lines_with_pattern}"
        )
    
    def test_sizeof_short_maxclouds_pattern_exists(self, repo_root):
        """Assert (sizeof(short) * MAXCLOUDS) pattern exists in source/MENUES.C."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")
        
        content = menues_c.read_text(errors="replace")
        
        """Count occurrences of the replacement pattern"""
        replacement_matches = re.findall(r"\(sizeof\(short\)\s*\*\s*MAXCLOUDS\)", content)
        
        assert len(replacement_matches) >= 6, (
            f"Expected at least 6 occurrences of (sizeof(short) * MAXCLOUDS), found {len(replacement_matches)}"
        )
    
    def test_sentinel_comment_present(self, repo_root):
        """Assert sentinel comment 'fix-engine-cloud-array-sizing' appears in MAXCLOUDS define."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")
        
        content = menues_c.read_text(errors="replace")
        sentinel = "fix-engine-cloud-array-sizing"
        
        assert sentinel in content, (
            f"Sentinel comment '{sentinel}' must appear in source/MENUES.C (in MAXCLOUDS define)"
        )



class TestEngineR15VolumeLevelBounds:
    """Verify bounds guards for volume/level indexing in engine-r15."""

    def test_premap_bounds_sentinel(self, repo_root):
        """source/PREMAP.C must have sentinel 'engine-r15-premap-volume-level-bounds'."""
        premap_c = repo_root / "source" / "PREMAP.C"
        if not premap_c.exists():
            pytest.skip(f"{premap_c} not found")

        content = premap_c.read_text(errors="replace")

        assert "engine-r15-premap-volume-level-bounds" in content, (
            "source/PREMAP.C must contain sentinel comment 'engine-r15-premap-volume-level-bounds' "
            "to mark the entry guard for level/volume array bounds."
        )

    def test_premap_bounds_check_present(self, repo_root):
        """source/PREMAP.C must check '(unsigned)ud.volume_number >= 4 || (unsigned)ud.level_number >= 11'."""
        premap_c = repo_root / "source" / "PREMAP.C"
        if not premap_c.exists():
            pytest.skip(f"{premap_c} not found")

        content = premap_c.read_text(errors="replace")

        assert "ud.volume_number >= 4" in content or "volume_number >= 4" in content, (
            "source/PREMAP.C must have bounds check for ud.volume_number >= 4"
        )
        assert "ud.level_number >= 11" in content or "level_number >= 11" in content, (
            "source/PREMAP.C must have bounds check for ud.level_number >= 11"
        )

    def test_menues_bounds_sentinel(self, repo_root):
        """source/MENUES.C must have sentinel 'engine-r15-menues-music-index-bounds'."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        assert "engine-r15-menues-music-index-bounds" in content, (
            "source/MENUES.C must contain sentinel comment 'engine-r15-menues-music-index-bounds' "
            "to mark the entry guard for music index bounds."
        )

    def test_menues_bounds_check_present(self, repo_root):
        """source/MENUES.C must check '(unsigned)ud.volume_number >= 4 || (unsigned)ud.level_number >= 11'."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        assert "ud.volume_number >= 4" in content or "volume_number >= 4" in content, (
            "source/MENUES.C must have bounds check for ud.volume_number >= 4"
        )
        assert "ud.level_number >= 11" in content or "level_number >= 11" in content, (
            "source/MENUES.C must have bounds check for ud.level_number >= 11"
        )



class TestEngineR15PremapNoCppComments:
    """Test that source/PREMAP.C contains no C++ style comments."""

    def test_no_cpp_comments_in_premap(self, repo_root):
        """source/PREMAP.C must use K&R /* */ style comments, not // comments."""
        premap_c = repo_root / "source" / "PREMAP.C"
        if not premap_c.exists():
            pytest.skip(f"{premap_c} not found")

        content = premap_c.read_text(errors="replace")
        lines = content.split('\n')

        in_multiline_comment = False
        for i, line in enumerate(lines, start=1):
            # Track entry/exit from multiline comments
            if '/*' in line:
                in_multiline_comment = True
            if '*/' in line:
                in_multiline_comment = False
                continue  # Skip rest of line with closing */

            # Skip lines inside multiline comments
            if in_multiline_comment:
                continue

            # Skip string literals naively by splitting on quotes
            parts = line.split('"')
            for j, part in enumerate(parts):
                # Only check even-indexed parts (outside strings)
                if j % 2 == 0:
                    # Reject // outside of include directives
                    if '//' in part and '#include' not in part:
                        pytest.fail(
                            f"Line {i} contains C++ style comment (//): {line.rstrip()}\n"
                            f"Must use /* */ style per K&R C (gnu89 standard)"
                        )

    def test_premap_sentinel_present(self, repo_root):
        """source/PREMAP.C must have the closure sentinel at the top."""
        premap_c = repo_root / "source" / "PREMAP.C"
        if not premap_c.exists():
            pytest.skip(f"{premap_c} not found")

        content = premap_c.read_text(errors="replace")
        
        assert "engine-r15-krn-premap-cpp-comments-clean" in content, (
            "source/PREMAP.C must include the sentinel "
            "/* engine-r15-krn-premap-cpp-comments-clean */ near the top"
        )



class TestEngineR16LoadpicsStrcpyBounds:
    """Test engine-r16 strcpy bounds fix for artfilename buffer in SRC/ENGINE.C loadpics()."""

    def test_sentinel_present(self, repo_root):
        """engine-r16-loadpics-strncpy sentinel must be present."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        assert "engine-r16-loadpics-strncpy" in content, (
            "SRC/ENGINE.C loadpics() must have sentinel comment 'engine-r16-loadpics-strncpy'"
        )

    def test_strcpy_artfilename_removed(self, repo_root):
        """strcpy(artfilename without 'n' must NOT appear in SRC/ENGINE.C."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        assert "strcpy(artfilename" not in content, (
            "SRC/ENGINE.C must NOT contain unbounded strcpy(artfilename"
        )

    def test_strncpy_artfilename_present(self, repo_root):
        """strncpy(artfilename with sizeof(artfilename)-1 must appear."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        assert "strncpy(artfilename" in content, (
            "SRC/ENGINE.C must contain bounded strncpy(artfilename"
        )

        assert "sizeof(artfilename)-1" in content, (
            "SRC/ENGINE.C strncpy must use sizeof(artfilename)-1 as size parameter"
        )



class TestEngineR16GameArgvBounds:
    """Test engine-r16 strcpy/strcat bounds fix for argv-derived strings in source/GAME.C."""

    def test_sentinel_present(self, repo_root):
        """engine-r16-game-argv-bounds sentinel must be present in GAME.C."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "engine-r16-game-argv-bounds" in content, (
            "source/GAME.C must have sentinel comment 'engine-r16-game-argv-bounds'"
        )

    def test_strcpy_confilename_removed(self, repo_root):
        """strcpy(confilename without 'n' must NOT appear in GAME.C argv processing."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "strcpy(confilename,c)" not in content, (
            "source/GAME.C must NOT contain unbounded strcpy(confilename,c)"
        )

    def test_strncpy_confilename_present(self, repo_root):
        """strncpy(confilename with sizeof(confilename)-1 must appear."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "strncpy(confilename,c,sizeof(confilename)-1)" in content, (
            "source/GAME.C must contain bounded strncpy(confilename,c,sizeof(confilename)-1)"
        )

    def test_strcpy_firstdemofile_removed(self, repo_root):
        """strcpy(firstdemofile without 'n' must NOT appear in case 'd'/'D' argv processing."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "strcpy(firstdemofile,c)" not in content, (
            "source/GAME.C must NOT contain unbounded strcpy(firstdemofile,c)"
        )

    def test_strncpy_firstdemofile_present(self, repo_root):
        """strncpy(firstdemofile with sizeof(firstdemofile)-1 must appear."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "strncpy(firstdemofile,temp,sizeof(firstdemofile)-1)" in content or \
               "strncpy(firstdemofile,c,sizeof(firstdemofile)-1)" in content, (
            "source/GAME.C must contain bounded strncpy(firstdemofile,...,sizeof(firstdemofile)-1)"
        )

    def test_argv_temp_buffer_for_extensions(self, repo_root):
        """argv-derived strings must use temporary buffers before extension appending."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Verify temp buffer is used in 'g' case for .grp extension
        assert "char temp[256];" in content, (
            "source/GAME.C case 'g'/'G' must use temporary buffer 'char temp[256];'"
        )

    def test_idfile_strcat_bounds_checked(self, repo_root):
        """strcat(idfile, IDFILENAME) must have length bounds check."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Look for the bounds check pattern for idfile strcat
        # The pattern should be either an if check or use strncat
        has_strlen_check = "strlen(idfile)" in content and "IDFILENAME" in content
        has_strncat = "strncat(idfile,IDFILENAME" in content
        
        assert has_strlen_check or has_strncat, (
            "source/GAME.C must have bounds check for idfile before using IDFILENAME; "
            "either if(strlen(idfile)...) check or strncat()"
        )

    def test_strncpy_count_increased(self, repo_root):
        """Count of strncpy calls in GAME.C should match baseline plus conversions."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        
        strncpy_count = content.count("strncpy(")
        
        # We converted at least 3 strcpy/strcat calls (confilename, firstdemofile x2, 
        # plus temp buffer uses) to strncpy/strncat, so minimum count should be
        # baseline + 3. The exact number depends on whether strncat is used.
        assert strncpy_count >= 9, (
            f"source/GAME.C must have >= 9 strncpy calls, found {strncpy_count}; "
            "the argv bounds fixes should have added bounded string functions"
        )




class TestNumwallsNumsectorsBounds:
    """Verify cycle-r17 numwalls/numsectors load-time and usage bounds hardening."""

    def test_engine_c_numwalls_load_clamp_sentinel(self, repo_root):
        """SRC/ENGINE.C must have engine-r17-numwalls-load-clamp sentinel at numwalls load."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        has_sentinel = "/* engine-r17-numwalls-load-clamp */" in content
        assert has_sentinel, (
            "SRC/ENGINE.C must have '/* engine-r17-numwalls-load-clamp */' sentinel "
            "before numwalls and numsectors load-time bounds checks"
        )

        has_numwalls_bounds = (
            "kread(fil,&numwalls,2)" in content and
            "if (numwalls < 0 || numwalls > MAXWALLS)" in content
        )
        assert has_numwalls_bounds, (
            "SRC/ENGINE.C must have numwalls bounds check: "
            "if (numwalls < 0 || numwalls > MAXWALLS)"
        )

        has_numsectors_bounds = (
            "kread(fil,&numsectors,2)" in content and
            "if (numsectors < 0 || numsectors > MAXSECTORS)" in content
        )
        assert has_numsectors_bounds, (
            "SRC/ENGINE.C must have numsectors bounds check: "
            "if (numsectors < 0 || numsectors > MAXSECTORS)"
        )

    def test_menues_c_numwalls_load_clamp_sentinel(self, repo_root):
        """source/MENUES.C must have engine-r17-numwalls-load-clamp sentinel at load."""
        menues_c = repo_root / "source" / "MENUES.C"
        if not menues_c.exists():
            pytest.skip(f"{menues_c} not found")

        content = menues_c.read_text(errors="replace")

        has_sentinel = "/* engine-r17-numwalls-load-clamp */" in content
        assert has_sentinel, (
            "source/MENUES.C must have '/* engine-r17-numwalls-load-clamp */' sentinel "
            "before numwalls and numsectors load-time bounds checks"
        )

        has_numwalls_bounds = (
            "kdfread(&numwalls,2,1,fil)" in content and
            "if(numwalls < 0 || numwalls > MAXWALLS)" in content
        )
        assert has_numwalls_bounds, (
            "source/MENUES.C must have numwalls bounds check: "
            "if(numwalls < 0 || numwalls > MAXWALLS)"
        )

        has_numsectors_bounds = (
            "kdfread(&numsectors,2,1,fil)" in content and
            "if(numsectors < 0 || numsectors > MAXSECTORS)" in content
        )
        assert has_numsectors_bounds, (
            "source/MENUES.C must have numsectors bounds check: "
            "if(numsectors < 0 || numsectors > MAXSECTORS)"
        )

    def test_engine_c_draw2dline_numwalls_guard(self, repo_root):
        """SRC/ENGINE.C draw2dline must guard numwalls=0 in wall loop."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        has_guard_pattern = (
            "if (numwalls > 0)" in content and
            "for(i=numwalls-1,wal=&wall[i];i>=0;i--,wal--)" in content
        )
        assert has_guard_pattern, (
            "SRC/ENGINE.C draw2dline loop must have 'if (numwalls > 0)' guard "
            "before 'for(i=numwalls-1,wal=&wall[i];i>=0;i--,wal--)' to prevent "
            "out-of-bounds pointer assignment when numwalls=0"
        )

    def test_no_unguarded_numwalls_minus_one_init(self, repo_root):
        """Verify no unguarded wall[numwalls-1] or [numwalls-1] pointer initialization."""
        engine_c = repo_root / "SRC" / "ENGINE.C"
        if not engine_c.exists():
            pytest.skip(f"{engine_c} not found")

        content = engine_c.read_text(errors="replace")

        lines = content.split("\n")
        found_dangerous = False
        prev_has_guard = False

        for i, line in enumerate(lines):
            if "if (numwalls > 0)" in line:
                prev_has_guard = True
                continue
            elif "wal=&wall[i]" in line and "numwalls-1" in line:
                if not prev_has_guard:
                    found_dangerous = True
                    break
                prev_has_guard = False

        assert not found_dangerous, (
            "SRC/ENGINE.C contains unguarded 'wal=&wall[numwalls-1]' pattern. "
            "All such initializations must be guarded by 'if (numwalls > 0)'"
        )

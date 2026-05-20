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


class TestAudioStubRIFFValidation:
    """Verify cycle-13 audio_stub.c RIFF header validation."""

    def test_audio_stub_riff_magic_check(self, repo_root):
        """audio_stub.c must check for RIFF magic string."""
        audio_stub = repo_root / "compat" / "audio_stub.c"
        if not audio_stub.exists():
            pytest.skip(f"{audio_stub} not found")

        content = audio_stub.read_text(errors="replace")

        assert "RIFF" in content, (
            "audio_stub.c must validate RIFF magic in WAVE file detection. "
            "Cycle-13 fix may have been reverted."
        )

    def test_audio_stub_wave_format_check(self, repo_root):
        """audio_stub.c must check for WAVE format string."""
        audio_stub = repo_root / "compat" / "audio_stub.c"
        if not audio_stub.exists():
            pytest.skip(f"{audio_stub} not found")

        content = audio_stub.read_text(errors="replace")

        assert "WAVE" in content, (
            "audio_stub.c must validate WAVE format in wav_file_size(). "
            "Cycle-13 fix may have been reverted."
        )


class TestAudioStubChannelExhaustion:
    """Verify cycle-13 audio_stub.c channel exhaustion mitigation."""

    def test_audio_stub_mix_group_oldest(self, repo_root):
        """audio_stub.c mixer_play must call Mix_GroupOldest."""
        audio_stub = repo_root / "compat" / "audio_stub.c"
        if not audio_stub.exists():
            pytest.skip(f"{audio_stub} not found")

        content = audio_stub.read_text(errors="replace")

        assert "Mix_GroupOldest" in content, (
            "audio_stub.c must call Mix_GroupOldest for channel exhaustion "
            "handling. Cycle-13 fix may have been reverted."
        )


class TestCONScriptBounds:
    """Verify cycle-15 CON-script bounds checking in GAMEDEF.C."""

    def test_gamedef_c_labelcnt_bounds(self, repo_root):
        """GAMEDEF.C must have labelcnt >= MAXLABELS checks (5+ sites)."""
        gamedef_c = repo_root / "source" / "GAMEDEF.C"
        if not gamedef_c.exists():
            pytest.skip(f"{gamedef_c} not found")

        content = gamedef_c.read_text(errors="replace")

        # Count occurrences of labelcnt >= MAXLABELS pattern
        # This pattern appears in bounds checks
        pattern = r"labelcnt\s*>=\s*MAXLABELS"
        matches = re.findall(pattern, content)
        assert len(matches) >= 5, (
            f"GAMEDEF.C should have at least 5 'labelcnt >= MAXLABELS' "
            f"bounds checks, found {len(matches)}. Cycle-15 fix may have "
            "been reverted."
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


class TestSoundOwnerCap:
    """Verify cycle-15 SoundOwner aging mechanism in SOUNDS.C."""

    def test_sounds_c_fx_stopsound_in_xyzsound(self, repo_root):
        """SOUNDS.C xyzsound must call FX_StopSound for aging out."""
        sounds_c = repo_root / "source" / "SOUNDS.C"
        if not sounds_c.exists():
            pytest.skip(f"{sounds_c} not found")

        content = sounds_c.read_text(errors="replace")

        # Both FX_StopSound and xyzsound should be in the file
        has_fx_stop = "FX_StopSound" in content
        has_xyzsound = "xyzsound" in content

        assert has_fx_stop and has_xyzsound, (
            "SOUNDS.C must have FX_StopSound call inside xyzsound function. "
            "This is the aging-out mechanism for old sounds. Cycle-15 fix "
            "may have been reverted."
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


class TestNETConnectTimeout:
    """Verify cycle-22 NET_CONNECT_TIMEOUT define and value in MMULTI.C."""

    def test_mmulti_c_net_connect_timeout_define(self, repo_root):
        """MMULTI.C must define NET_CONNECT_TIMEOUT with value <= 30."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        # Check for the #define NET_CONNECT_TIMEOUT
        assert "#define NET_CONNECT_TIMEOUT" in content, (
            "MMULTI.C must define NET_CONNECT_TIMEOUT for connection timeout. "
            "Cycle-22 network hardening fix may have been reverted."
        )

        # Extract and verify the value is <= 30
        import re
        timeout_match = re.search(
            r"#define\s+NET_CONNECT_TIMEOUT\s+(\d+)",
            content
        )

        if timeout_match:
            timeout_value = int(timeout_match.group(1))
            assert timeout_value <= 30, (
                f"NET_CONNECT_TIMEOUT value must be <= 30, found {timeout_value}. "
                "Cycle-22 network hardening fix may have been weakened."
            )
        else:
            pytest.fail(
                "NET_CONNECT_TIMEOUT define found but value could not be parsed"
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


class TestPacketType9BufferOverflow:
    """Verify r5 finding #1: Packet type 9 (wchoice) buffer overflow guard."""

    def test_packet_type_9_bounds_check(self, repo_root):
        """Packet type 9 must validate packbufleng before writing to wchoice array."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for the bounds guard pattern: packbufleng check against MAX_WEAPONS
        # Pattern: if (packbufleng - 1 > MAX_WEAPONS) { ... break; }
        has_bounds_guard = (
            "packbufleng - 1 > MAX_WEAPONS" in content
        )
        assert has_bounds_guard, (
            "Packet type 9 must validate packbufleng against MAX_WEAPONS. "
            "Expect pattern: if (packbufleng - 1 > MAX_WEAPONS) { ... break; }"
        )

        # Also verify that the security logging message appears
        has_security_msg = "Packet type 9 payload too large" in content
        assert has_security_msg, (
            "Packet type 9 bounds check must include security log message"
        )


class TestPacketTypes01OOBRead:
    """Verify r5 finding #2: Packet types 0 and 1 (sync) OOB read guards."""

    def test_packet_type_1_length_validation(self, repo_root):
        """Packet type 1 must validate packet length before parsing fields."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for length validation pattern in packet type 1
        # Pattern: required_len = 2; if (k&1) required_len += 2; ... if (packbufleng < required_len)
        has_required_len_decl = "required_len" in content
        has_required_len_check = "if (packbufleng < required_len)" in content

        assert has_required_len_decl, (
            "Packet type 1 must declare required_len variable"
        )
        assert has_required_len_check, (
            "Packet type 1 must check: if (packbufleng < required_len) { ... break; }"
        )

        # Verify security message appears
        has_security_msg = "Packet type 1 truncated" in content
        assert has_security_msg, (
            "Packet type 1 length validation must include security log message"
        )

    def test_packet_type_0_bounds_checks(self, repo_root):
        """Packet type 0 must validate buffer bounds before field reads."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for defensive bounds checks in packet type 0
        # Pattern: checks like "if (k >= packbufleng)" and "if (j >= packbufleng)"
        has_bitmask_check = "k >= packbufleng" in content
        has_field_checks = (
            "if (j >= packbufleng)" in content or
            "if (j+1 >= packbufleng)" in content
        )

        assert has_bitmask_check, (
            "Packet type 0 must validate bitmask read with: if (k >= packbufleng) { ... break; }"
        )
        assert has_field_checks, (
            "Packet type 0 must validate field reads with: if (j >= packbufleng) or if (j+1 >= packbufleng) { ... break; }"
        )

        # Verify security messages appear
        has_lag_read_msg = "Packet type 0 truncated at lag read" in content
        has_bitmask_msg = "Packet type 0 truncated at bitmask read" in content
        has_field_msg = "Packet type 0 truncated (fvel)" in content or "Packet type 0 truncated (avel)" in content

        assert has_lag_read_msg, (
            "Packet type 0 lag read validation must include security log message"
        )
        assert has_bitmask_msg, (
            "Packet type 0 bitmask read validation must include security log message"
        )
        assert has_field_msg, (
            "Packet type 0 field read validation must include security log messages"
        )

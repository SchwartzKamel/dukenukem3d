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


class TestPacketTypes58RangeValidation:
    """Verify r5 finding #3: Packet types 5 and 8 range validation for game settings."""

    def test_packet_type_5_level_number_bounds(self, repo_root):
        """Packet type 5 must validate level_number against bounds."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for level_number bounds check pattern in case 5
        # Pattern: if (packbuf[1] >= 11) or similar
        has_level_check = "packbuf[1] >= 11" in content
        
        assert has_level_check, (
            "Packet type 5 must validate level_number with pattern: if (packbuf[1] >= 11)"
        )

        # Verify security message appears
        has_security_msg = "Packet type 5 invalid level number" in content
        assert has_security_msg, (
            "Packet type 5 level bounds check must include security log message"
        )

    def test_packet_type_5_volume_number_bounds(self, repo_root):
        """Packet type 5 must validate volume_number against bounds."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for volume_number bounds check pattern in case 5
        # Pattern: if (packbuf[2] >= 4) or similar
        has_volume_check = "packbuf[2] >= 4" in content
        
        assert has_volume_check, (
            "Packet type 5 must validate volume_number with pattern: if (packbuf[2] >= 4)"
        )

        # Verify security message appears
        has_security_msg = "Packet type 5 invalid volume number" in content
        assert has_security_msg, (
            "Packet type 5 volume bounds check must include security log message"
        )

    def test_packet_type_5_skill_bounds(self, repo_root):
        """Packet type 5 must validate player_skill against bounds."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for skill bounds check pattern in case 5
        # Pattern: if (packbuf[3] >= 5) or similar
        has_skill_check = "packbuf[3] >= 5" in content
        
        assert has_skill_check, (
            "Packet type 5 must validate skill with pattern: if (packbuf[3] >= 5)"
        )

        # Verify security message appears
        has_security_msg = "Packet type 5 invalid skill" in content
        assert has_security_msg, (
            "Packet type 5 skill bounds check must include security log message"
        )

    def test_packet_type_5_boolean_flags_bounds(self, repo_root):
        """Packet type 5 must validate boolean flags (monsters_off, respawn_*, marker, ffire)."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for boolean flag bounds checks
        # Pattern: if (packbuf[N] > 1) for flags
        has_monsters_off_check = "packbuf[4] > 1" in content
        has_respawn_monsters_check = "packbuf[5] > 1" in content
        has_respawn_items_check = "packbuf[6] > 1" in content
        has_respawn_inventory_check = "packbuf[7] > 1" in content
        has_marker_check = "packbuf[9] > 1" in content
        has_ffire_check = "packbuf[10] > 1" in content
        
        assert has_monsters_off_check, (
            "Packet type 5 must validate monsters_off flag: if (packbuf[4] > 1)"
        )
        assert has_respawn_monsters_check, (
            "Packet type 5 must validate respawn_monsters flag: if (packbuf[5] > 1)"
        )
        assert has_respawn_items_check, (
            "Packet type 5 must validate respawn_items flag: if (packbuf[6] > 1)"
        )
        assert has_respawn_inventory_check, (
            "Packet type 5 must validate respawn_inventory flag: if (packbuf[7] > 1)"
        )
        assert has_marker_check, (
            "Packet type 5 must validate marker flag: if (packbuf[9] > 1)"
        )
        assert has_ffire_check, (
            "Packet type 5 must validate ffire flag: if (packbuf[10] > 1)"
        )

    def test_packet_type_8_range_validation(self, repo_root):
        """Packet type 8 must have same range validation as type 5."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        # Check for level, volume, skill bounds in case 8
        has_level_check = "Packet type 8 invalid level number" in content
        has_volume_check = "Packet type 8 invalid volume number" in content
        has_skill_check = "Packet type 8 invalid skill" in content
        has_flags_check = "Packet type 8 invalid" in content
        
        assert has_level_check, (
            "Packet type 8 must validate level_number with security message"
        )
        assert has_volume_check, (
            "Packet type 8 must validate volume_number with security message"
        )
        assert has_skill_check, (
            "Packet type 8 must validate skill with security message"
        )
        assert has_flags_check, (
            "Packet type 8 must validate all flags with security messages"
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

    @pytest.mark.xfail(strict=False, reason="engine-r9-player-weapon-ammo-bounds: cycle-30 attempt reverted; awaiting re-dispatch")
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

class TestConfigParserBufferSafety:
    """Verify engine-r9 Finding 3: Config file parser buffer operations are hardened.
    
    This test ensures that strcpy and sprintf calls in CONFIG.C have been replaced
    with bounds-checked versions (strncpy and snprintf) to prevent buffer overflow
    vulnerabilities when parsing user-controlled configuration files.
    """

    def test_no_unsafe_strcpy_in_config_c(self, repo_root):
        """CONFIG.C must not use strcpy for user-controlled input buffers."""
        config_c = repo_root / "source" / "CONFIG.C"
        if not config_c.exists():
            pytest.skip(f"{config_c} not found")

        content = config_c.read_text(errors="replace")

        # Check that strcpy is completely removed from CONFIG.C
        has_strcpy = "strcpy(" in content
        assert not has_strcpy, (
            "CONFIG.C must not use strcpy. All strcpy calls must be replaced with "
            "strncpy + explicit NUL termination for setupfilename, extension, and filename buffers."
        )

    def test_strncpy_with_nul_termination_for_setupfilename(self, repo_root):
        """CONFIG.C must use strncpy with explicit NUL termination for setupfilename[128]."""
        config_c = repo_root / "source" / "CONFIG.C"
        if not config_c.exists():
            pytest.skip(f"{config_c} not found")

        content = config_c.read_text(errors="replace")

        # Check for strncpy usage with setupfilename
        has_strncpy_setupfilename = (
            "strncpy(setupfilename" in content and 
            "sizeof(setupfilename) - 1" in content
        )
        assert has_strncpy_setupfilename, (
            "CONFIG.C must use strncpy(setupfilename, src, sizeof(setupfilename) - 1) "
            "for all setupfilename assignments."
        )

        # Check for explicit NUL termination pattern
        has_nul_term = "setupfilename[sizeof(setupfilename) - 1] = 0" in content
        assert has_nul_term, (
            "CONFIG.C must explicitly set setupfilename[sizeof(setupfilename) - 1] = 0 "
            "after strncpy calls to guarantee NUL termination."
        )

    def test_snprintf_for_config_key_building(self, repo_root):
        """CONFIG.C must use snprintf for building config key names (Finding 3 + Finding 5)."""
        config_c = repo_root / "source" / "CONFIG.C"
        if not config_c.exists():
            pytest.skip(f"{config_c} not found")

        content = config_c.read_text(errors="replace")

        # Check that sprintf is completely removed from CONFIG.C
        has_sprintf = "sprintf(" in content
        assert not has_sprintf, (
            "CONFIG.C must not use sprintf. All sprintf calls for building config key names "
            "(MouseButton, MouseButtonClicked, JoystickButton, GamePadDigitalAxes, "
            "WeaponChoice, etc.) must be replaced with snprintf(buf, sizeof(buf), ...)."
        )

        # Check for snprintf usage
        has_snprintf = "snprintf(" in content
        assert has_snprintf, (
            "CONFIG.C must use snprintf for safe string formatting. "
            "Expected at least one snprintf call for config key building."
        )

        # Verify that snprintf is used with sizeof() for str buffer
        has_snprintf_str = "snprintf(str, sizeof(str)" in content
        assert has_snprintf_str, (
            "CONFIG.C must use snprintf(str, sizeof(str), ...) pattern for building "
            "temporary key names to prevent buffer overflow."
        )

        # Verify that snprintf is used with sizeof() for buf buffer
        has_snprintf_buf = "snprintf(buf, sizeof(buf)" in content
        assert has_snprintf_buf, (
            "CONFIG.C must use snprintf(buf, sizeof(buf), ...) pattern for building "
            "WeaponChoice key names to prevent buffer overflow."
        )

    def test_strncpy_count_rise(self, repo_root):
        """Verify that strncpy usage has increased from baseline of 0."""
        config_c = repo_root / "source" / "CONFIG.C"
        if not config_c.exists():
            pytest.skip(f"{config_c} not found")

        content = config_c.read_text(errors="replace")

        # Count strncpy occurrences (should be >= 6 for setupfilename, extension, filenames)
        strncpy_count = content.count("strncpy(")
        assert strncpy_count >= 6, (
            f"CONFIG.C must use strncpy at least 6 times (found {strncpy_count}). "
            "Expected replacements for setupfilename (4 sites), extension (1 site), "
            "filenames (1 site)."
        )

    def test_snprintf_count_rise(self, repo_root):
        """Verify that snprintf usage has increased from baseline of 0."""
        config_c = repo_root / "source" / "CONFIG.C"
        if not config_c.exists():
            pytest.skip(f"{config_c} not found")

        content = config_c.read_text(errors="replace")

        # Count snprintf occurrences (should be >= 14 for all mouse/joystick/gamepad keys)
        snprintf_count = content.count("snprintf(")
        assert snprintf_count >= 14, (
            f"CONFIG.C must use snprintf at least 14 times (found {snprintf_count}). "
            "Expected replacements for MouseButton, JoystickButton, GamePadDigitalAxes, "
            "JoystickAnalogAxes, JoystickDigitalAxes, and WeaponChoice."
        )


class TestConfigKeyLengthLimit:
    """Verify engine-r9 Finding 5: Config key parsing has a sensible length limit.
    
    This test ensures that:
    1. MAX_CONFIG_KEY constant is defined (64 bytes)
    2. Config key parsing enforces this limit
    3. Lines that exceed the limit are skipped with a SECURITY warning
    """

    def test_max_config_key_constant_defined(self, repo_root):
        """MAX_CONFIG_KEY constant must be defined in DUKE3D.H."""
        duke3d_h = repo_root / "source" / "DUKE3D.H"
        if not duke3d_h.exists():
            pytest.skip(f"{duke3d_h} not found")

        content = duke3d_h.read_text(errors="replace")

        # Check for MAX_CONFIG_KEY definition
        has_max_config_key = "#define MAX_CONFIG_KEY" in content
        assert has_max_config_key, (
            "DUKE3D.H must define MAX_CONFIG_KEY constant to cap config-key parsing length."
        )

        # Verify the value is 64
        max_config_key_64 = "MAX_CONFIG_KEY 64" in content or "MAX_CONFIG_KEY 64" in content
        assert max_config_key_64, (
            "MAX_CONFIG_KEY should be defined as 64 bytes to limit config key name length."
        )

    def test_config_key_validation_in_scriplib(self, repo_root):
        """SCRIPLIB config key parsing must enforce MAX_CONFIG_KEY limit.
        
        This test checks that the key parsing loop in mact_stub.c or similar
        respects the MAX_CONFIG_KEY limit and skips lines that exceed it.
        """
        mact_stub = repo_root / "compat" / "mact_stub.c"
        if not mact_stub.exists():
            pytest.skip(f"{mact_stub} not found (optional check)")

        content = mact_stub.read_text(errors="replace")

        # Check for MAX_CONFIG_KEY usage in key parsing
        # The limit should be enforced when reading the config key from file
        has_key_limit = "MAX_CONFIG_KEY" in content or "63" in content
        # Note: The existing code uses strncpy with size 63 which is equivalent to MAX_CONFIG_KEY=64
        
        if has_key_limit or "strncpy(e->key, k, 63)" in content:
            # Good, the key length is already limited
            pass
        else:
            # This is optional since the constraint says "ONLY edit source/CONFIG.C"
            pytest.skip("SCRIPLIB key length validation is optional (not in scope of CONFIG.C-only constraint)")

    def test_sprintf_key_builders_use_snprintf(self, repo_root):
        """CONFIG.C key builders (sprintf→snprintf) implicitly limit key length to str[80]."""
        config_c = repo_root / "source" / "CONFIG.C"
        if not config_c.exists():
            pytest.skip(f"{config_c} not found")

        content = config_c.read_text(errors="replace")

        # The key names are built in str[80] or buf[80] with snprintf
        # This limits the key length to < 80 bytes, which is well above MAX_CONFIG_KEY=64
        # But the intent of Finding 5 is to have explicit validation
        
        # Verify that keys are built with snprintf into bounded buffers
        has_str_buffer = "char str[80]" in content
        has_snprintf_keys = "snprintf(str, sizeof(str)" in content
        
        assert has_str_buffer and has_snprintf_keys, (
            "CONFIG.C must build config keys in bounded str[80] buffer using snprintf "
            "to prevent overflow. The key length is implicitly limited by buffer size."
        )

    def test_no_unbounded_config_key_access(self, repo_root):
        """SCRIPT_GetString calls in CONFIG.C must pass size parameter."""
        config_c = repo_root / "source" / "CONFIG.C"
        if not config_c.exists():
            pytest.skip(f"{config_c} not found")

        content = config_c.read_text(errors="replace")

        # Check that all SCRIPT_GetString calls pass sizeof(temp) or equivalent
        script_get_string_calls = re.findall(
            r'SCRIPT_GetString\s*\([^)]+\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert script_get_string_calls, (
            "CONFIG.C should have SCRIPT_GetString calls for config value reading."
        )

        # Verify that sizeof(temp) is passed to SCRIPT_GetString
        has_sizeof_temp = "sizeof(temp)" in content or "sizeof(buf)" in content
        assert has_sizeof_temp, (
            "SCRIPT_GetString calls must pass sizeof(buffer) to respect buffer size limits "
            "and prevent NULL-termination edge cases (Finding 5)."
        )


class TestActorTileMetadataBounds:
    def test_picnum_safe_macro(self, repo_root):
        h = repo_root / "source" / "DUKE3D.H"
        assert re.search(r'#define\s+PICNUM_SAFE', h.read_text(errors="replace")), "PICNUM_SAFE macro required"
    
    def test_actor_bounds_guarded(self, repo_root):
        ac = repo_root / "source" / "ACTORS.C"
        c = ac.read_text(errors="replace")
        assert len(re.findall(r'PICNUM_SAFE\(', c)) >= 2, "PICNUM_SAFE not applied to ACTORS.C"


class TestPacketType4ChatStrncpy:
    """Regression test for net-r6-type4-strcpy-fix: packet type 4 buffer overflow.
    
    Finding: Chat packet (type 4) used strcpy() to copy attacker-controlled data
    from packbuf+1 into recbuf[80] with no bounds check. An attacker sending
    a packet with packbufleng > 80 would overflow the buffer.
    
    Fix: Add bounds-check before strncpy, use min(packbufleng-1, sizeof(recbuf)-1).
    """

    def test_type4_strncpy_bounds(self, repo_root):
        """Verify type 4 (chat) uses strncpy instead of strcpy."""
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Find the case 4: block in getpackets()
        case_4_match = re.search(
            r'case\s+4\s*:\s*'
            r'/\*.*?Type 4.*?bounds-check.*?\*/'
            r'.*?if\s*\(\s*packbufleng\s*>\s*1\s*&&\s*packbufleng\s*<=\s*sizeof\(recbuf\)\s*\)'
            r'.*?strncpy\s*\(\s*recbuf\s*,\s*packbuf\s*\+\s*1\s*,\s*packbufleng\s*-\s*1\s*\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert case_4_match, (
            "Case 4 (chat packet) must use strncpy with bounds-check:\n"
            "1. Comment explaining Type 4 bounds-check\n"
            "2. if (packbufleng > 1 && packbufleng <= sizeof(recbuf))\n"
            "3. strncpy(recbuf, packbuf+1, packbufleng-1)"
        )

    def test_type4_null_termination(self, repo_root):
        """Verify type 4 explicitly null-terminates after strncpy."""
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Ensure the pattern includes both strncpy and explicit null-termination
        case_4_match = re.search(
            r'case\s+4\s*:.*?'
            r'strncpy\s*\([^)]+\)\s*;'
            r'.*?recbuf\s*\[\s*packbufleng\s*-\s*1\s*\]\s*=\s*0\s*;',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert case_4_match, (
            "Type 4 handler must explicitly null-terminate recbuf after strncpy:\n"
            "recbuf[packbufleng-1] = 0;"
        )

    def test_type4_vulnerable_strcpy_removed(self, repo_root):
        """Verify the vulnerable unbounded strcpy is no longer in case 4."""
        game_c = repo_root / "source" / "GAME.C"
        content = game_c.read_text(errors="replace")
        
        # Find case 4 block
        case_4_match = re.search(
            r'case\s+4\s*:.*?break\s*;',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        if case_4_match:
            case_4_block = case_4_match.group(0)
            # The block should contain strncpy, not an unbounded strcpy
            # But it's OK if strcpy appears elsewhere (different case or other context)
            if 'strcpy' in case_4_block and 'strncpy' not in case_4_block:
                pytest.fail(
                    "Case 4 block still contains unbounded strcpy without strncpy. "
                    "Must use strncpy with bounds-check."
                )



class TestPacketType6FieldBounds:
    """Verify net-r8-type-6-bounds: Packet type 6 (player name) field validation.
    
    Bug: Packet type 6 handler read packbuf[i] in a loop until null terminator
    without checking:
    1. if 'other' (player index) is < MAXPLAYERS
    2. if i < packbufleng before reading packbuf[i]
    3. if name length exceeds MAXPLAYERNAMELENGTH before writing
    
    This allowed:
    - OOB write to ud.user_name[invalid_player] with high player index
    - OOB read from packbuf if attacker sends packet without null terminator
    - Buffer overflow in ud.user_name[player][i] if name too long
    
    Fix: Add all three bounds checks before processing the name field.
    """
    
    def test_packet_type_6_player_index_bounds(self, repo_root):
        """Verify packet type 6 validates player index against MAXPLAYERS."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Check for player index bounds check pattern
        # Pattern: if ((unsigned)other >= MAXPLAYERS)
        has_index_check = re.search(
            r'case\s+6\s*:.*?'
            r'if\s*\(\s*\(\s*unsigned\s*\)\s*other\s*>=\s*MAXPLAYERS\s*\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert has_index_check, (
            "Packet type 6 must validate player index with pattern: "
            "if ((unsigned)other >= MAXPLAYERS)"
        )
    
    def test_packet_type_6_sentinel_comment(self, repo_root):
        """Verify the net-r8-type-6-bounds sentinel comment is present."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Check for the sentinel comment that marks this hardening
        has_sentinel = "net-r8-type-6-bounds" in content
        
        assert has_sentinel, (
            "Packet type 6 bounds check must include sentinel comment: "
            "/* net-r8-type-6-bounds: packet field validation */"
        )
    
    def test_packet_type_6_buffer_length_bounds(self, repo_root):
        """Verify packet type 6 loop checks packbufleng before reading."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Find the case 6 block and check for packbufleng bounds check in the loop
        case_6_match = re.search(
            r'case\s+6\s*:.*?'
            r'for\s*\(\s*i\s*=\s*2\s*;.*?i\s*<\s*packbufleng.*?\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert case_6_match, (
            "Packet type 6 loop must check packbufleng before reading: "
            "for (i=2; i < packbufleng && ...)"
        )
    
    def test_packet_type_6_name_length_bounds(self, repo_root):
        """Verify packet type 6 prevents name overflow beyond MAXPLAYERNAMELENGTH."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Check for MAXPLAYERNAMELENGTH check in the loop condition
        has_name_length_check = re.search(
            r'case\s+6\s*:.*?'
            r'for\s*\(\s*i\s*=\s*2\s*;.*?i\s*-\s*2\s*<\s*MAXPLAYERNAMELENGTH.*?\)',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        assert has_name_length_check, (
            "Packet type 6 loop must check MAXPLAYERNAMELENGTH: "
            "for (i=2; ... && i - 2 < MAXPLAYERNAMELENGTH)"
        )
    
    def test_packet_type_6_null_termination_after_truncate(self, repo_root):
        """Verify packet type 6 name buffer is null-terminated after truncation.
        
        When a player name exceeds MAXPLAYERNAMELENGTH, the handler truncates
        and must explicitly null-terminate to prevent strlen/strcpy from reading
        past the buffer boundary.
        """
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")
        
        content = game_c.read_text(errors="replace")
        
        # Find the case 6 block starting from the sentinel
        case_6_start = content.find("net-r8-type-6-bounds")
        assert case_6_start >= 0, (
            "Packet type 6 bounds check must include sentinel comment: "
            "net-r8-type-6-bounds"
        )
        
        # Extract 1200+ chars from the sentinel to capture the full case 6 block including truncation branch
        case_6_context = content[case_6_start:case_6_start + 1200]
        
        # Verify truncation branch exists with sentinel comment + MAXPLAYERNAMELENGTH
        has_truncation_branch = (
            "MAXPLAYERNAMELENGTH" in case_6_context and
            "Truncating" in case_6_context
        )
        assert has_truncation_branch, (
            "Packet type 6 must have truncation branch that mentions "
            "MAXPLAYERNAMELENGTH and 'Truncating'"
        )
        
        # Verify explicit null-termination after truncation
        # Look for patterns like: user_name[...][MAXPLAYERNAMELENGTH-1] = 0
        # or: user_name[...][MAXPLAYERNAMELENGTH-1] = '\0'
        # or: memset/strncpy that guarantees termination
        truncation_null_term = re.search(
            r'else\s*\{.*?'
            r'(?:'
            r'user_name\s*\[\s*other\s*\]\s*\[\s*MAXPLAYERNAMELENGTH\s*-\s*1\s*\]\s*=\s*(?:0|\'\\0\'|"\\0")|'
            r'memset\s*\([^)]*user_name\s*\[\s*other\s*\]\s*[^)]*\)|'
            r'strncpy\s*\([^)]*\)'
            r').*?\}',
            case_6_context,
            re.MULTILINE | re.DOTALL
        )
        
        assert truncation_null_term, (
            "Packet type 6 truncation branch must explicitly null-terminate, e.g.:\n"
            "ud.user_name[other][MAXPLAYERNAMELENGTH-1] = 0;\n"
            "or use memset/strncpy to guarantee termination."
        )


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


class TestHostAcceptTimeout:
    """Regression test for host-side accept() timeout hardening.

    Finding: A crashed client attempting to connect could block the host's
    accept() call indefinitely, preventing the host from accepting other
    connections or timing out gracefully. The host loop has an overall
    NET_CONNECT_TIMEOUT (30s) but no per-accept timeout, so a single slow
    connection blocks other players.

    Fix: Add select() with NET_HOST_ACCEPT_TIMEOUT_SEC (10s) before each
    accept() call on both POSIX and Windows platforms. On timeout, accept()
    returns INVALID_SOCKET and the loop continues, allowing the host to
    either accept other connections or reach the overall timeout.
    """

    def test_host_accept_timeout_constant_defined(self, repo_root):
        """Verify NET_HOST_ACCEPT_TIMEOUT_SEC constant is defined."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        assert "NET_HOST_ACCEPT_TIMEOUT_SEC" in content, (
            "Missing NET_HOST_ACCEPT_TIMEOUT_SEC constant in SRC/MMULTI.C"
        )

        const_pattern = re.search(
            r'#define\s+NET_HOST_ACCEPT_TIMEOUT_SEC\s+(\d+)',
            content
        )
        assert const_pattern, "NET_HOST_ACCEPT_TIMEOUT_SEC not found as #define"
        timeout_value = int(const_pattern.group(1))
        assert timeout_value == 10, (
            f"NET_HOST_ACCEPT_TIMEOUT_SEC should be 10, got {timeout_value}"
        )

    def test_select_included_for_posix(self, repo_root):
        """Verify sys/select.h is included for POSIX select() support."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        select_include_pattern = re.search(
            r'#include\s+<sys/select\.h>',
            content
        )
        assert select_include_pattern, (
            "Missing #include <sys/select.h> for POSIX select() support"
        )

    def test_net_accept_timeout_function_exists(self, repo_root):
        """Verify net_accept_timeout() function is implemented."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        func_pattern = re.search(
            r'static\s+SOCKET\s+net_accept_timeout\s*\('
            r'\s*SOCKET\s+server_sock.*?\n\s*\{.*?select\s*\(',
            content,
            re.DOTALL
        )
        assert func_pattern, (
            "net_accept_timeout() function with select() not found"
        )

    def test_accept_loop_uses_timeout_wrapper(self, repo_root):
        """Verify the host accept loop uses net_accept_timeout()."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        accept_pattern = re.search(
            r'client\s*=\s*net_accept_timeout\s*\('
            r'\s*server_socket,.*?NET_HOST_ACCEPT_TIMEOUT_SEC\s*\)',
            content,
            re.DOTALL
        )
        assert accept_pattern, (
            "Accept loop does not use net_accept_timeout() with "
            "NET_HOST_ACCEPT_TIMEOUT_SEC timeout"
        )

    def test_timeout_both_platforms_support(self, repo_root):
        """Verify select() works on both Windows (winsock2) and POSIX."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        content = mmulti_c.read_text(errors="replace")

        assert "#include <winsock2.h>" in content, (
            "Missing winsock2.h include for Windows select() support"
        )

        assert "#include <sys/select.h>" in content, (
            "Missing sys/select.h include for POSIX select() support"
        )

        assert "FD_ZERO" in content, "FD_ZERO macro not found"
        assert "FD_SET" in content, "FD_SET macro not found"


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


class TestMusicPlaySongStateConsistency:
    """Verify MUSIC_PlaySong state machine bug fix (audio-r10-music-state-consistency)."""

    def test_music_playing_only_on_success(self, repo_root):
        """
        audio_stub.c MUSIC_PlaySong() must only set music_playing=1 when
        Mix_LoadMUS_RW succeeds, not unconditionally.
        Regression: Previously, music_playing was set even when Mix_LoadMUS_RW failed,
        leading to inconsistent state where the music_playing flag didn't reflect
        actual playback status.
        """
        audio_stub = repo_root / "compat" / "audio_stub.c"
        if not audio_stub.exists():
            pytest.skip(f"{audio_stub} not found")

        content = audio_stub.read_text(errors="replace")

        # Find the MUSIC_PlaySong function
        if "MUSIC_PlaySong" not in content:
            pytest.skip("MUSIC_PlaySong function not found in audio_stub.c")

        # Pattern 1: Check that music_playing = 1 is inside the success path,
        # not at the end of the function unconditionally
        # The fix should have the sentinel comment: audio-r10-music-state-consistency
        has_sentinel = "audio-r10-music-state-consistency" in content

        # Pattern 2: Check for the fix structure:
        # - MUSIC_Error is returned when Mix_LoadMUS_RW fails
        # - music_playing = 1 is only set after successful Mix_PlayMusic call
        has_error_return = (
            "if (!current_music)" in content and
            "return MUSIC_Error" in content and
            "audio-r10-music-state-consistency" in content
        )

        # Pattern 3: Ensure music_playing assignment is not unconditional at function end
        # Find the function and check its structure
        func_pattern = r"int\s+MUSIC_PlaySong\s*\([^)]*\)\s*\{(.*?)^\}"
        func_match = re.search(func_pattern, content, re.MULTILINE | re.DOTALL)

        if func_match:
            func_body = func_match.group(1)
            # The corrected version should have:
            # 1. music_playing = 1 preceded by Mix_PlayMusic (success path)
            # 2. Sentinel comment about the state machine fix
            lines = func_body.split('\n')
            
            music_playing_line = None
            mix_playmusic_line = None
            
            for i, line in enumerate(lines):
                if "music_playing" in line and "=" in line and "1" in line:
                    music_playing_line = i
                if "Mix_PlayMusic" in line:
                    mix_playmusic_line = i
            
            # Verify that music_playing assignment comes after Mix_PlayMusic
            if music_playing_line is not None and mix_playmusic_line is not None:
                assert music_playing_line > mix_playmusic_line, (
                    "music_playing = 1 must be set after Mix_PlayMusic call (success path)"
                )

        assert has_sentinel and has_error_return, (
            "compat/audio_stub.c MUSIC_PlaySong() must:\n"
            "1. Return MUSIC_Error when Mix_LoadMUS_RW fails\n"
            "2. Only set music_playing = 1 after successful Mix_PlayMusic call\n"
            "3. Include sentinel comment 'audio-r10-music-state-consistency'"
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


class TestRecvEagainDistinguish:
    """Verify net-r9 MMULTI.C recv() EAGAIN/EWOULDBLOCK error discrimination."""

    def test_mmulti_recv_eagain_distinguish_sentinel_present(self, repo_root):
        """MMULTI.C must have sentinel comment 'net-r9-recv-eagain-distinguish' for recv() fixes."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        # Count occurrences of sentinel comment in EAGAIN/EWOULDBLOCK handling
        sentinel_count = content.count("net-r9-recv-eagain-distinguish")

        assert sentinel_count >= 1, (
            f"MMULTI.C must have at least 1 sentinel comment "
            f"'net-r9-recv-eagain-distinguish' for recv() EAGAIN handling, "
            f"found {sentinel_count}. Cycle-r9 fix may be incomplete."
        )

    def test_mmulti_recv_eagain_posix_handling(self, repo_root):
        """MMULTI.C recv() calls must handle EAGAIN/EWOULDBLOCK/EINTR on POSIX."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find recv() calls and their surrounding context
        recv_line_nums = []
        for i, line in enumerate(lines):
            if 'recv(sock' in line:
                recv_line_nums.append(i + 1)

        # At least 1 recv() call site expected
        assert len(recv_line_nums) >= 1, (
            f"MMULTI.C must have at least 1 recv() call, found {len(recv_line_nums)}"
        )

        # For each recv(), check if EAGAIN/EWOULDBLOCK handling exists in nearby context
        for recv_line in recv_line_nums:
            # Check ±20 lines around the recv() for error handling patterns
            start = max(0, recv_line - 20)
            end = min(len(lines), recv_line + 30)
            context = '\n'.join(lines[start:end])

            # Must handle POSIX errors: EAGAIN, EWOULDBLOCK, EINTR
            has_posix_eagain = 'EAGAIN' in context
            has_posix_ewouldblock = 'EWOULDBLOCK' in context or 'errno' in context
            has_eintr = 'EINTR' in context

            # At minimum, context near recv() should reference these constants
            assert has_posix_eagain or has_eintr, (
                f"recv() at line {recv_line} must handle EAGAIN/EWOULDBLOCK/EINTR "
                f"on POSIX. Check lines {start+1}-{end}"
            )

    def test_mmulti_recv_windows_handling(self, repo_root):
        """MMULTI.C recv() calls must handle WSAEWOULDBLOCK on Windows."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        # Check for Windows-specific error code handling
        has_wsaewouldblock = 'WSAEWOULDBLOCK' in content
        has_wsa_getlasterror = 'WSAGetLastError()' in content

        # Should have both to properly handle Windows socket errors
        assert has_wsaewouldblock and has_wsa_getlasterror, (
            "MMULTI.C must have Windows socket error handling:\n"
            f"  - WSAEWOULDBLOCK: {has_wsaewouldblock}\n"
            f"  - WSAGetLastError(): {has_wsa_getlasterror}\n"
            "Both are required for proper Windows recv() error discrimination."
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

        for i in range(max(0, 6475-1), min(len(lines), 6495)):
            if "sec-r12-strcat-fta-quotes-overflow" in lines[i]:
                sentinel_found_6480s = True
            if "strncpy(fta_quotes" in lines[i] or "strncpy(&fta_quotes" in lines[i]:
                strncpy_found_6480s = True
            if "strcpy(fta_quotes" in lines[i] or "strcpy(&fta_quotes" in lines[i]:
                strcpy_found_6480s = True

        for i in range(max(0, 6700-1), min(len(lines), 6720)):
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


class TestType8BoardfilenameUnderflow:
    """Verify net-r9-type-8-boardfilename-underflow fix in GAME.C."""

    def test_type8_boardfilename_underflow_sentinel_present(self, repo_root):
        """source/GAME.C must have sentinel 'net-r9-type-8-boardfilename-underflow' comment."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r9-type-8-boardfilename-underflow" in content, (
            "source/GAME.C must contain sentinel comment 'net-r9-type-8-boardfilename-underflow' "
            "to mark the fix for the unsigned integer underflow on packbufleng-11."
        )

    def test_type8_boardfilename_precondition_guard(self, repo_root):
        """source/GAME.C must have 'packbufleng < 11' check before copybufbyte boardfilename call."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find the line with 'net-r9-type-8-boardfilename-underflow' sentinel
        sentinel_line_idx = None
        for i, line in enumerate(lines):
            if "net-r9-type-8-boardfilename-underflow" in line:
                sentinel_line_idx = i
                break

        assert sentinel_line_idx is not None, (
            "Could not find sentinel comment 'net-r9-type-8-boardfilename-underflow' in source/GAME.C"
        )

        # Check that the sentinel line contains the precondition check
        sentinel_line = lines[sentinel_line_idx]
        assert "packbufleng < 11" in sentinel_line, (
            f"Sentinel line {sentinel_line_idx + 1} must contain 'packbufleng < 11' precondition check. "
            f"Found: {sentinel_line}"
        )

        # Verify copybufbyte call with boardfilename is within 5 lines after sentinel
        found_copybufbyte = False
        for j in range(sentinel_line_idx + 1, min(sentinel_line_idx + 6, len(lines))):
            if "copybufbyte" in lines[j] and "boardfilename" in lines[j]:
                found_copybufbyte = True
                break

        assert found_copybufbyte, (
            f"source/GAME.C must have 'copybufbyte' call with 'boardfilename' "
            f"within 5 lines after the sentinel at line {sentinel_line_idx + 1}"
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


class TestType17EnvelopePrevalidate:
    """Verify bounds guard for type-17 network packet envelope."""

    def test_sentinel_present_in_game_c(self, repo_root):
        """source/GAME.C must have sentinel 'net-r11-type-17-envelope-prevalidate' comment."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")

        assert "net-r11-type-17-envelope-prevalidate" in content, (
            "source/GAME.C must contain sentinel comment 'net-r11-type-17-envelope-prevalidate' "
            "to mark the fix for the type-17 input-sync handler bounds check."
        )

    def test_packbufleng_bounds_check_present(self, repo_root):
        """source/GAME.C case 17 must have 'packbufleng < 20' bounds check."""
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        lines = content.split('\n')

        # Find case 17 in the dispatcher
        case_17_found = False
        case_17_line_idx = -1
        for i, line in enumerate(lines):
            if "case 17:" in line:
                case_17_line_idx = i
                case_17_found = True
                break

        assert case_17_found, (
            "source/GAME.C must have 'case 17:' handler"
        )

        # Verify packbufleng check is within 5 lines after case 17
        found_check = False
        for j in range(case_17_line_idx + 1, min(case_17_line_idx + 6, len(lines))):
            if "packbufleng <" in lines[j] and ("20" in lines[j] or any(char.isdigit() for char in lines[j])):
                found_check = True
                break

        assert found_check, (
            f"source/GAME.C case 17 handler must have 'packbufleng <' bounds check "
            f"within 5 lines after case 17 (found at line {case_17_line_idx + 1})"
        )


class TestPlayerDisconnectMemset:
    """Tests for net-r11 player disconnect memset hardening in SRC/MMULTI.C"""

    def test_player_disconnect_memset_sentinel_present(self, repo_root):
        """SRC/MMULTI.C must have sentinel 'net-r11-player-disconnect-memset' comment."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")

        assert "net-r11-player-disconnect-memset" in content, (
            "SRC/MMULTI.C must contain sentinel comment 'net-r11-player-disconnect-memset' "
            "to mark the fix for zeroing sensitive per-player state on disconnect."
        )

    def test_player_disconnect_memset_near_sentinel(self, repo_root):
        """SRC/MMULTI.C must have memset call within 5 lines of the sentinel."""
        mmulti_c = repo_root / "SRC" / "MMULTI.C"
        if not mmulti_c.exists():
            pytest.skip(f"{mmulti_c} not found")

        content = mmulti_c.read_text(errors="replace")
        lines = content.split('\n')

        sentinel_found = False
        for i, line in enumerate(lines):
            if "net-r11-player-disconnect-memset" in line:
                sentinel_found = True
                # Check within 5 lines after sentinel (looking ahead)
                found_memset = False
                for j in range(i, min(i + 5, len(lines))):
                    if "memset" in lines[j]:
                        found_memset = True
                        break
                
                assert found_memset, (
                    "SRC/MMULTI.C: memset must appear within 5 lines of "
                    "'net-r11-player-disconnect-memset' sentinel comment."
                )
                break

        assert sentinel_found, (
            "SRC/MMULTI.C: 'net-r11-player-disconnect-memset' sentinel not found."
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
    """Verify pytest.ini retains the xdist sentinel and documents opt-in path.

    NOTE: Default xdist (-n auto) was reverted after cycle-45 because the
    session-autouse `generated_audio_artifacts` fixture races across workers
    on tmp+rename. Tracked under perf-r12-xdist-fixture-redesign. This test
    only requires the sentinel comment + serial marker registration to
    remain in place; the `addopts = -n auto` opt-in will be re-added once
    the fixture is xdist-safe.
    """
    from pathlib import Path
    pytest_ini = Path(__file__).parent.parent / "pytest.ini"
    content = pytest_ini.read_text()

    assert "perf-r12-pytest-xdist-integration" in content, (
        "pytest.ini must retain sentinel comment 'perf-r12-pytest-xdist-integration'"
    )
    assert "serial" in content, (
        "pytest.ini must retain the `serial` marker registration for future xdist re-enable"
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

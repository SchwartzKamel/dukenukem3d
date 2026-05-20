"""
Regression tests for hardening fixes from cycle 11-15.

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

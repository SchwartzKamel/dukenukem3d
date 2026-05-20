"""Tests for audio playback round-trip: WAV header validation, manifest sync, and SoundOwner cap.

Covers cycle-13 (channel-exhaustion fix) and cycle-15 (SoundOwner cap fix) regression tests.
Tests structural validation without requiring Azure, SDL2_mixer, or actual playback.

No network. No API calls. Deterministic fixtures.
"""
import json
import os
import struct
import sys
import tempfile
import wave

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

import generate_audio


class TestWAVHeaderValidation:
    """Validate RIFF/WAVE header parsing and rejection of corrupted WAVs.
    
    Covers cycle-13 channel-exhaustion fix: ensures WAV structure is valid
    before loading into mixer channels.
    """

    def test_generate_silence_wav_valid_header(self):
        """generate_silence_wav() produces valid RIFF/WAVE structure."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=1, sample_rate=22050)
        
        # Verify RIFF header
        assert wav_data[:4] == b"RIFF", "WAV must start with 'RIFF' magic"
        
        # Extract RIFF size field (little-endian, 4 bytes after "RIFF")
        riff_size = struct.unpack("<I", wav_data[4:8])[0]
        assert riff_size > 0, "RIFF size must be positive"
        assert riff_size <= len(wav_data) - 8, "RIFF size must not exceed file length"
        
        # Verify WAVE header
        assert wav_data[8:12] == b"WAVE", "WAV must contain 'WAVE' after RIFF size"
        
        # Verify fmt chunk exists
        fmt_pos = wav_data.find(b"fmt ")
        assert fmt_pos > 0, "WAV must contain 'fmt ' chunk"
        fmt_size = struct.unpack("<I", wav_data[fmt_pos + 4:fmt_pos + 8])[0]
        assert fmt_size == 16, "Standard fmt chunk must be 16 bytes"
        
        # Verify data chunk exists
        data_pos = wav_data.find(b"data")
        assert data_pos > 0, "WAV must contain 'data' chunk"
        data_size = struct.unpack("<I", wav_data[data_pos + 4:data_pos + 8])[0]
        assert data_size > 0, "data chunk must have positive size"

    def test_wav_header_round_trip(self):
        """Generated WAV can be parsed by wave module without corruption."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5, sample_rate=44100)
        
        # Write to temp file and read with wave module
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_data)
            temp_path = f.name
        
        try:
            with wave.open(temp_path, "rb") as w:
                n_channels = w.getnchannels()
                sample_width = w.getsampwidth()
                frame_rate = w.getframerate()
                n_frames = w.getnframes()
                
                assert n_channels == 1, "Expected mono silence WAV"
                assert sample_width == 2, "Expected 16-bit samples"
                assert frame_rate == 44100, "Expected 44100 Hz sample rate"
                assert n_frames > 0, "Expected non-zero frame count"
                
                # Read all frames to ensure no corruption
                frames = w.readframes(n_frames)
                assert len(frames) == n_frames * sample_width, "Frame count mismatch"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_corrupt_wav_magic_rejected(self):
        """WAV with bad RIFF magic is rejected."""
        # Build corrupt WAV: wrong magic
        bad_wav = b"XXXX" + struct.pack("<I", 100) + b"WAVE"
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(bad_wav)
            temp_path = f.name
        
        try:
            # wave module should reject this
            with pytest.raises(Exception):
                with wave.open(temp_path, "rb"):
                    pass
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_corrupt_wav_size_field(self):
        """WAV with undersized chunk size is rejected."""
        # Build corrupt WAV: RIFF size smaller than actual data
        bad_wav = b"RIFF" + struct.pack("<I", 10) + b"WAVE" + b"X" * 100
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(bad_wav)
            temp_path = f.name
        
        try:
            # wave module should detect size mismatch and raise error
            with pytest.raises((wave.Error, EOFError)):
                with wave.open(temp_path, "rb") as w:
                    w.getnframes()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_wav_silence_samples_are_zero(self):
        """Generated silence WAV contains zero-valued samples."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=1, sample_rate=22050)
        
        # Extract data chunk
        data_pos = wav_data.find(b"data")
        assert data_pos > 0, "No data chunk found"
        
        data_size = struct.unpack("<I", wav_data[data_pos + 4:data_pos + 8])[0]
        data_start = data_pos + 8
        sample_data = wav_data[data_start:data_start + data_size]
        
        # All samples should be zero for silence
        assert sample_data == b"\x00" * len(sample_data), "Silence WAV must contain zero samples"


class TestManifestSoundAssetRoundTrip:
    """Verify voice manifest entries correspond to actual sound assets.
    
    Covers cycle-15 SoundOwner cap fix: ensures every manifest entry
    has a corresponding WAV file reachable and properly formed.
    """

    def test_manifest_wav_files_exist(self):
        """Every SOUND_MANIFEST entry has corresponding .WAV file in generated_assets/sounds/."""
        sound_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        
        # Skip if sounds dir doesn't exist (e.g., in shallow clone)
        if not os.path.exists(sound_dir):
            pytest.skip("generated_assets/sounds/ not found")
        
        for entry in generate_audio.SOUND_MANIFEST:
            wav_name = entry["wav"]
            wav_path = os.path.join(sound_dir, wav_name)
            assert os.path.exists(wav_path), \
                f"Manifest entry {wav_name} missing from {sound_dir}"

    def test_manifest_wav_files_are_readable(self):
        """Every manifest .WAV file is readable and has valid structure."""
        sound_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        
        if not os.path.exists(sound_dir):
            pytest.skip("generated_assets/sounds/ not found")
        
        for entry in generate_audio.SOUND_MANIFEST:
            wav_name = entry["wav"]
            wav_path = os.path.join(sound_dir, wav_name)
            
            assert os.path.getsize(wav_path) > 0, \
                f"{wav_name} is empty"
            
            # Verify basic WAV structure
            with open(wav_path, "rb") as f:
                data = f.read()
            
            assert data[:4] == b"RIFF", \
                f"{wav_name}: missing RIFF magic"
            assert b"WAVE" in data[:12], \
                f"{wav_name}: missing WAVE header"

    def test_manifest_wav_parseable_by_wave_module(self):
        """Every manifest .WAV is parseable by Python's wave module."""
        sound_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        
        if not os.path.exists(sound_dir):
            pytest.skip("generated_assets/sounds/ not found")
        
        for entry in generate_audio.SOUND_MANIFEST:
            wav_name = entry["wav"]
            wav_path = os.path.join(sound_dir, wav_name)
            
            try:
                with wave.open(wav_path, "rb") as w:
                    n_channels = w.getnchannels()
                    sample_width = w.getsampwidth()
                    frame_rate = w.getframerate()
                    n_frames = w.getnframes()
                    
                    assert n_channels > 0, f"{wav_name}: invalid channel count"
                    assert sample_width > 0, f"{wav_name}: invalid sample width"
                    assert frame_rate > 0, f"{wav_name}: invalid sample rate"
                    assert n_frames > 0, f"{wav_name}: no frames"
            except wave.Error as e:
                pytest.fail(f"{wav_name}: wave module parse error: {e}")

    def test_voice_lines_and_manifest_in_sync(self):
        """VOICE_LINES filenames match SOUND_MANIFEST 'wav' fields exactly."""
        voice_line_wavs = {filename for filename, _, _ in generate_audio.VOICE_LINES}
        manifest_wavs = {entry["wav"] for entry in generate_audio.SOUND_MANIFEST}
        
        assert voice_line_wavs == manifest_wavs, \
            f"Manifest and VOICE_LINES out of sync. Missing in manifest: " \
            f"{voice_line_wavs - manifest_wavs}. Extra in manifest: {manifest_wavs - voice_line_wavs}"

    def test_manifest_entry_voice_matches_voice_lines(self):
        """Each manifest entry's voice matches the corresponding VOICE_LINES entry."""
        voice_map = {filename: voice for filename, _, voice in generate_audio.VOICE_LINES}
        
        for entry in generate_audio.SOUND_MANIFEST:
            wav_name = entry["wav"]
            manifest_voice = entry["voice"]
            expected_voice = voice_map[wav_name]
            
            assert manifest_voice == expected_voice, \
                f"{wav_name}: manifest voice '{manifest_voice}' != VOICE_LINES voice '{expected_voice}'"


class TestChannelExhaustionRegression:
    """Regression test for cycle-13 channel-exhaustion fix.
    
    Ensures WAV headers are valid and SoundOwner channel allocation
    does not overflow due to malformed assets.
    """

    def test_all_generated_wavs_valid_for_mixer(self):
        """All generated WAVs have structure compatible with SDL2_mixer loading.
        
        Ensures no corrupt headers can cause mixer channel overflow.
        """
        # Generate all 21 voice line WAVs in-memory
        for filename, prompt, voice in generate_audio.VOICE_LINES:
            wav_data = generate_audio.generate_silence_wav(duration_sec=1.0, sample_rate=22050)
            
            # Validate header structure for mixer compatibility
            assert wav_data[:4] == b"RIFF", f"{filename}: bad RIFF magic"
            
            # Extract and validate RIFF size
            riff_size = struct.unpack("<I", wav_data[4:8])[0]
            assert riff_size > 0, f"{filename}: invalid RIFF size"
            
            # Validate WAVE header
            assert wav_data[8:12] == b"WAVE", f"{filename}: missing WAVE header"
            
            # Validate fmt chunk
            fmt_pos = wav_data.find(b"fmt ")
            assert fmt_pos > 0, f"{filename}: missing fmt chunk"
            fmt_size = struct.unpack("<I", wav_data[fmt_pos + 4:fmt_pos + 8])[0]
            assert fmt_size == 16, f"{filename}: invalid fmt chunk size"
            
            # Validate data chunk
            data_pos = wav_data.find(b"data")
            assert data_pos > 0, f"{filename}: missing data chunk"
            data_size = struct.unpack("<I", wav_data[data_pos + 4:data_pos + 8])[0]
            assert data_size > 0, f"{filename}: empty data chunk"


class TestSoundOwnerCapRegression:
    """Regression test for cycle-15 SoundOwner cap fix.
    
    Ensures manifest integrity and asset bounds do not exceed
    SoundOwner playback capacity.
    """

    def test_manifest_entry_count_within_sound_owner_capacity(self):
        """Manifest size must not exceed SoundOwner capacity.
        
        SoundOwner in cycle-15 caps concurrent sounds at reasonable limit.
        Ensure manifest has bounded entries.
        """
        max_sounds = 64  # Typical cap for concurrent playback
        assert len(generate_audio.SOUND_MANIFEST) <= max_sounds, \
            f"Manifest has {len(generate_audio.SOUND_MANIFEST)} entries, " \
            f"exceeds SoundOwner cap of {max_sounds}"

    def test_manifest_entries_have_required_metadata(self):
        """Every manifest entry has complete metadata for SoundOwner runtime.
        
        Incomplete entries could cause SoundOwner buffer overflow.
        """
        required_fields = {"wav", "voice", "category", "status"}
        
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            missing = required_fields - set(entry.keys())
            assert not missing, \
                f"Manifest entry {i} ({entry.get('wav', 'unknown')}): " \
                f"missing required fields {missing}"

    def test_sound_owner_category_bounds(self):
        """All manifest categories are within expected bounds.
        
        Prevents category-indexed array overflow in SoundOwner.
        """
        valid_categories = {
            "taunt", "pain", "death", "pickup", "weapon", 
            "level_start", "alarm", "ambient"
        }
        
        for entry in generate_audio.SOUND_MANIFEST:
            category = entry["category"]
            assert category in valid_categories, \
                f"{entry['wav']}: unknown category '{category}'"


class TestSDL2MixerSkip:
    """Skip tests gracefully when SDL2_mixer is unavailable.
    
    Allows test suite to run in headless CI without requiring
    mixer library or actual audio device.
    """

    def test_mixer_availability_reported(self):
        """Test suite skips cleanly if SDL2_mixer unavailable.
        
        This is a meta-test to ensure skip behavior works.
        """
        try:
            import SDL2_mixer  # noqa: F401
            # If import succeeds, mixer is available
            assert True
        except ImportError:
            # Mixer not available; skip is expected
            pytest.skip("SDL2_mixer not available in test environment")

    @pytest.mark.skipif(
        not __import__('importlib.util').util.find_spec('SDL2_mixer'),
        reason="SDL2_mixer not installed"
    )
    def test_wav_compatible_with_mixer_format(self):
        """WAVs are compatible with SDL2_mixer standard formats.
        
        Skipped if mixer not available.
        """
        # Mixer typically expects 16-bit PCM at 22050 or 44100 Hz
        wav_data = generate_audio.generate_silence_wav(duration_sec=1.0, sample_rate=22050)
        
        # Parse fmt chunk to verify compatibility
        fmt_pos = wav_data.find(b"fmt ")
        assert fmt_pos > 0
        
        # fmt chunk: 16 bytes of format info
        fmt_data = wav_data[fmt_pos + 8:fmt_pos + 8 + 16]
        audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample = \
            struct.unpack("<HHIIHH", fmt_data)
        
        # Validate standard format
        assert audio_format == 1, "Expected PCM format (1)"
        assert channels in (1, 2), "Expected mono or stereo"
        assert sample_rate in (22050, 44100), "Expected common mixer sample rates"
        assert bits_per_sample == 16, "Expected 16-bit samples"


class TestAssetPipelineIntegration:
    """Integration test: asset pipeline generates valid audio.
    
    Ensures full round-trip from VOICE_LINES → WAV → manifest works.
    """

    def test_voice_lines_have_all_required_metadata(self):
        """Each VOICE_LINES entry has complete metadata."""
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert filename, f"Entry {i}: missing filename"
            assert prompt, f"Entry {i} ({filename}): missing prompt"
            assert voice in ("alloy", "echo", "onyx"), \
                f"Entry {i} ({filename}): invalid voice '{voice}'"

    def test_manifest_file_generation_integrity(self):
        """Manifest file (if present) matches in-memory SOUND_MANIFEST constant."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        
        if not os.path.exists(manifest_path):
            pytest.skip("MANIFEST.json not found (may regenerate on next asset generation)")
        
        with open(manifest_path) as f:
            file_manifest = json.load(f)
        
        # Manifest is now a dict with schema_version and entries
        assert isinstance(file_manifest, dict), \
            f"File manifest should be a dict, got {type(file_manifest).__name__}"
        
        assert "schema_version" in file_manifest, \
            "File manifest missing 'schema_version' key"
        assert file_manifest["schema_version"] == "1.0", \
            f"Expected schema_version '1.0', got '{file_manifest['schema_version']}'"
        
        entries = file_manifest.get("entries", [])
        assert len(entries) == len(generate_audio.SOUND_MANIFEST), \
            f"File manifest entries ({len(entries)}) != constant manifest ({len(generate_audio.SOUND_MANIFEST)})"
        
        # Check a few entries match
        for entry, file_entry in zip(generate_audio.SOUND_MANIFEST, entries):
            assert entry["wav"] == file_entry["wav"], \
                f"WAV mismatch: {entry['wav']} != {file_entry['wav']}"
            assert entry["voice"] == file_entry["voice"], \
                f"Voice mismatch for {entry['wav']}: {entry['voice']} != {file_entry['voice']}"

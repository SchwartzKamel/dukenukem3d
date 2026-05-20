"""Tests for audio asset generation pipeline (tools/generate_audio.py).

Covers VOICE_LINES schema, voice-mapping conventions, WAV generation without API,
and secret leak prevention.
"""
import os
import re
import struct
import subprocess
import sys
import tempfile
import wave

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

# Import the audio generation module
import generate_audio


class TestVoiceLinesSchema:
    """Validate VOICE_LINES catalog structure and content."""

    def test_voice_lines_count(self):
        """VOICE_LINES must contain exactly 21 entries."""
        assert len(generate_audio.VOICE_LINES) == 21, \
            f"Expected 21 voice lines, got {len(generate_audio.VOICE_LINES)}"

    def test_voice_lines_tuple_structure(self):
        """Each entry in VOICE_LINES must be a 3-tuple (filename, prompt, voice)."""
        for i, entry in enumerate(generate_audio.VOICE_LINES):
            assert isinstance(entry, tuple), \
                f"Entry {i} is not a tuple: {type(entry)}"
            assert len(entry) == 3, \
                f"Entry {i} is not a 3-tuple: {len(entry)}"
            filename, prompt, voice = entry
            assert isinstance(filename, str), \
                f"Entry {i}: filename is not str: {type(filename)}"
            assert isinstance(prompt, str), \
                f"Entry {i}: prompt is not str: {type(prompt)}"
            assert isinstance(voice, str), \
                f"Entry {i}: voice is not str: {type(voice)}"

    def test_voice_lines_voice_values(self):
        """Each entry's voice must be one of {'alloy', 'echo', 'onyx'}."""
        valid_voices = {"alloy", "echo", "onyx"}
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert voice in valid_voices, \
                f"Entry {i} ({filename}): invalid voice '{voice}' (must be in {valid_voices})"

    def test_voice_lines_filenames_wav_format(self):
        """Each filename must be uppercase 8.3 format ending in .WAV."""
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert filename.endswith(".WAV"), \
                f"Entry {i}: filename must end with .WAV: {filename}"
            assert filename == filename.upper(), \
                f"Entry {i}: filename must be uppercase: {filename}"
            # 8.3 format: max 8 chars before dot, 3 after
            name_part = filename[:-4]  # Remove .WAV
            assert len(name_part) <= 8, \
                f"Entry {i}: filename base must be ≤8 chars: {filename}"

    def test_voice_lines_filenames_expected_catalog(self):
        """Filenames must match the expected catalog patterns."""
        expected_patterns = {
            "TAUNT01", "TAUNT02", "TAUNT03", "TAUNT04", "TAUNT05",
            "PAIN01", "PAIN02", "PAIN03",
            "DEATH01", "DEATH02",
            "PICKUP01", "PICKUP02", "PICKUP03", "PICKUP04",
            "WEAPON01", "WEAPON02", "WEAPON03",
            "LEVEL01", "LEVEL02",
            "ALARM01",
            "COMP01",
        }
        filenames = [f[:-4] for f, p, v in generate_audio.VOICE_LINES]
        assert set(filenames) == expected_patterns, \
            f"Filename mismatch. Got: {set(filenames)}, Expected: {expected_patterns}"

    def test_voice_lines_not_empty_prompts(self):
        """Each prompt must be non-empty."""
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert len(prompt.strip()) > 0, \
                f"Entry {i} ({filename}): prompt is empty"


class TestVoiceMappingConvention:
    """Verify voice-mapping conventions from audio-engineer persona."""

    @pytest.mark.parametrize("filename,expected_voice", [
        ("TAUNT01.WAV", "alloy"),
        ("TAUNT02.WAV", "alloy"),
        ("TAUNT03.WAV", "alloy"),
        ("TAUNT04.WAV", "alloy"),
        ("TAUNT05.WAV", "alloy"),
        ("PAIN01.WAV", "onyx"),
        ("PAIN02.WAV", "onyx"),
        ("PAIN03.WAV", "onyx"),
        ("DEATH01.WAV", "onyx"),
        ("DEATH02.WAV", "alloy"),  # Dying gasp is alloy
        ("PICKUP01.WAV", "echo"),
        ("PICKUP02.WAV", "echo"),
        ("PICKUP03.WAV", "echo"),
        ("PICKUP04.WAV", "echo"),
        ("WEAPON01.WAV", "echo"),
        ("WEAPON02.WAV", "echo"),
        ("WEAPON03.WAV", "echo"),
        ("LEVEL01.WAV", "alloy"),
        ("LEVEL02.WAV", "alloy"),
        ("ALARM01.WAV", "echo"),
        ("COMP01.WAV", "echo"),
    ])
    def test_voice_mapping_convention(self, filename, expected_voice):
        """Voice assignments must follow the cyberpunk mercenary aesthetic.
        
        Mapping convention (from audio-engineer persona):
        - alloy: taunts, combat lines, level starts, dying gasps
        - echo: HUD notifications, weapon announcements, alarms, computer messages
        - onyx: pain grunts, death screams
        """
        voice_map = {f: v for f, p, v in generate_audio.VOICE_LINES}
        assert voice_map[filename] == expected_voice, \
            f"Expected {filename} → {expected_voice}, got {voice_map[filename]}"


class TestSilencePlaceholderGeneration:
    """Test WAV generation in --no-ai mode via subprocess."""

    def test_no_ai_flag_generates_wav_files(self, tmp_path):
        """Invoking generate_audio.py --no-ai should produce 21 WAV files."""
        # Note: generate_audio.py uses PROJECT_ROOT internally to determine output path,
        # so we run it from the project root and check generated_assets/sounds/ there.
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, \
            f"generate_audio.py --no-ai failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        
        # Check that 21 WAV files were created in generated_assets/sounds/
        expected_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        assert os.path.exists(expected_dir), f"Output directory not created: {expected_dir}"
        
        wav_files = sorted([f for f in os.listdir(expected_dir) if f.endswith(".WAV")])
        assert len(wav_files) == 21, \
            f"Expected 21 WAV files, got {len(wav_files)}: {wav_files}"

    def test_wav_files_have_valid_riff_header(self):
        """Each generated WAV file must have valid RIFF/WAVE headers."""
        # First ensure WAV files are generated
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        expected_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        wav_files = sorted([os.path.join(expected_dir, f) for f in os.listdir(expected_dir) 
                           if f.endswith(".WAV")])
        
        for wav_file in wav_files:
            with open(wav_file, "rb") as f:
                # Read RIFF header: 4 bytes "RIFF", 4 bytes size, 4 bytes "WAVE"
                header = f.read(12)
                assert len(header) >= 12, \
                    f"{os.path.basename(wav_file)}: file too small to contain RIFF header"
                
                riff_sig, size_bytes, wave_sig = header[:4], header[4:8], header[8:12]
                
                assert riff_sig == b"RIFF", \
                    f"{os.path.basename(wav_file)}: RIFF signature not found, got {riff_sig}"
                assert wave_sig == b"WAVE", \
                    f"{os.path.basename(wav_file)}: WAVE signature not found, got {wave_sig}"
                
                # size_bytes is little-endian uint32
                size = struct.unpack("<I", size_bytes)[0]
                assert size > 0, \
                    f"{os.path.basename(wav_file)}: RIFF size is 0"

    def test_wav_files_are_valid_wave_format(self):
        """Each WAV file must be readable by Python wave module with sane parameters."""
        # First ensure WAV files are generated
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        expected_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        wav_files = sorted([os.path.join(expected_dir, f) for f in os.listdir(expected_dir) 
                           if f.endswith(".WAV")])
        
        for wav_file in wav_files:
            try:
                with wave.open(wav_file, "rb") as wav:
                    channels = wav.getnchannels()
                    sample_width = wav.getsampwidth()
                    framerate = wav.getframerate()
                    
                    # Validate audio parameters
                    assert channels in {1, 2}, \
                        f"{os.path.basename(wav_file)}: channels={channels}, expected 1 or 2"
                    assert sample_width in {1, 2}, \
                        f"{os.path.basename(wav_file)}: sample_width={sample_width}, expected 1 or 2"
                    assert framerate > 0, \
                        f"{os.path.basename(wav_file)}: framerate={framerate}, must be > 0"
            except wave.Error as e:
                pytest.fail(f"{os.path.basename(wav_file)}: invalid WAV format: {e}")


class TestNoSecretLeak:
    """Verify generate_audio.py contains no hardcoded API keys."""

    def test_no_hardcoded_audio_api_key(self):
        """generate_audio.py must not contain hardcoded AUDIO_API_KEY."""
        source_file = os.path.join(PROJECT_ROOT, "tools", "generate_audio.py")
        with open(source_file, "r") as f:
            content = f.read()
        
        # Pattern: AUDIO_API_KEY= followed by non-whitespace (hardcoded key)
        # Allow only env var lookups like os.environ.get or os.getenv
        hardcoded_pattern = r'AUDIO_API_KEY\s*=\s*["\']'
        assert not re.search(hardcoded_pattern, content), \
            "Found hardcoded AUDIO_API_KEY in generate_audio.py (should use os.environ.get)"

    def test_no_hardcoded_flux_api_key(self):
        """generate_audio.py must not contain hardcoded FLUX_API_KEY."""
        source_file = os.path.join(PROJECT_ROOT, "tools", "generate_audio.py")
        with open(source_file, "r") as f:
            content = f.read()
        
        hardcoded_pattern = r'FLUX_API_KEY\s*=\s*["\']'
        assert not re.search(hardcoded_pattern, content), \
            "Found hardcoded FLUX_API_KEY in generate_audio.py (should use os.environ.get)"

    def test_env_lookup_for_api_keys(self):
        """generate_audio.py must use safe methods to retrieve API keys.
        
        Safe methods include:
        - .get() on a dict with a default value
        - os.environ.get() with a default
        - os.getenv() with a default
        
        Unsafe methods:
        - Direct dict access without fallback (os.environ["KEY"] can KeyError)
        """
        source_file = os.path.join(PROJECT_ROOT, "tools", "generate_audio.py")
        with open(source_file, "r") as f:
            content = f.read()
        
        # Check for any unsafe direct environment variable access without try/except
        # Pattern: os.environ["AUDIO_API_KEY"] or os.environ["FLUX_API_KEY"]
        unsafe_pattern = r'os\.environ\s*\[\s*["\'](?:AUDIO_API_KEY|FLUX_API_KEY)'
        assert not re.search(unsafe_pattern, content), \
            "Found unsafe os.environ[\"KEY\"] access (should use .get() with default)"
        
        # Should use safe methods like env.get() or os.environ.get() or os.getenv()
        has_safe_lookup = (
            re.search(r'\.get\s*\(\s*["\']AUDIO_API_KEY', content) or
            re.search(r'\.get\s*\(\s*["\']AUDIO_ENDPOINT', content) or
            re.search(r'os\.environ\.get\s*\(', content) or
            re.search(r'os\.getenv\s*\(', content)
        )
        assert has_safe_lookup, \
            "generate_audio.py must use safe methods (.get() with defaults) for credentials"

    def test_no_uncaught_keyerror_on_missing_env(self):
        """generate_audio.py must handle missing env vars gracefully (no KeyError crash)."""
        source_file = os.path.join(PROJECT_ROOT, "tools", "generate_audio.py")
        with open(source_file, "r") as f:
            content = f.read()
        
        # Check that the module doesn't do direct dict access like os.environ["KEY"]
        # without a fallback (which would KeyError if missing)
        unsafe_pattern = r'os\.environ\s*\[\s*["\']AUDIO_API_KEY'
        assert not re.search(unsafe_pattern, content), \
            "Found unsafe os.environ[\"AUDIO_API_KEY\"] access (use .get() for defaults)"

"""Tests for audio generation (tools/generate_audio.py).

Covers --no-ai code path, WAV format validation, VOICE_LINES catalog,
CLI argparse, and no credential leaks.
"""
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import wave

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

import generate_audio


class TestVoiceLinesStructure:
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
                f"Entry {i}: filename is not str"
            assert isinstance(prompt, str), \
                f"Entry {i}: prompt is not str"
            assert isinstance(voice, str), \
                f"Entry {i}: voice is not str"

    def test_voice_lines_valid_voices(self):
        """Each entry's voice must be one of {'alloy', 'echo', 'onyx'}."""
        valid_voices = {"alloy", "echo", "onyx"}
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert voice in valid_voices, \
                f"Entry {i} ({filename}): invalid voice '{voice}'"

    def test_voice_lines_filenames_wav_format(self):
        """Each filename must be uppercase 8.3 format ending in .WAV."""
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert filename.endswith(".WAV"), \
                f"Entry {i}: filename must end with .WAV: {filename}"
            assert filename == filename.upper(), \
                f"Entry {i}: filename must be uppercase: {filename}"
            name_part = filename[:-4]  # Remove .WAV
            assert len(name_part) <= 8, \
                f"Entry {i}: filename base must be ≤8 chars: {filename}"

    def test_voice_lines_non_empty_prompts(self):
        """Each prompt must be non-empty."""
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert len(prompt.strip()) > 0, \
                f"Entry {i} ({filename}): prompt is empty"

    def test_voice_lines_expected_filenames(self):
        """Filenames must match expected catalog patterns."""
        expected = {
            "TAUNT01", "TAUNT02", "TAUNT03", "TAUNT04", "TAUNT05",
            "PAIN01", "PAIN02", "PAIN03",
            "DEATH01", "DEATH02",
            "PICKUP01", "PICKUP02", "PICKUP03", "PICKUP04",
            "WEAPON01", "WEAPON02", "WEAPON03",
            "LEVEL01", "LEVEL02",
            "ALARM01",
            "COMP01",
        }
        filenames = {f[:-4] for f, p, v in generate_audio.VOICE_LINES}
        assert filenames == expected, \
            f"Filename mismatch. Got: {filenames}, Expected: {expected}"


class TestVoiceMappingConventions:
    """Verify voice-mapping conventions per audio-engineer persona."""

    @pytest.mark.parametrize("filename,expected_voice", [
        # Taunts: alloy (gruff mercenary)
        ("TAUNT01.WAV", "alloy"),
        ("TAUNT02.WAV", "alloy"),
        ("TAUNT03.WAV", "alloy"),
        ("TAUNT04.WAV", "alloy"),
        ("TAUNT05.WAV", "alloy"),
        # Pain: onyx (deep, authoritative)
        ("PAIN01.WAV", "onyx"),
        ("PAIN02.WAV", "onyx"),
        ("PAIN03.WAV", "onyx"),
        # Death: onyx (scream) and alloy (dying gasp)
        ("DEATH01.WAV", "onyx"),
        ("DEATH02.WAV", "alloy"),
        # Pickups: echo (electronic, synthetic)
        ("PICKUP01.WAV", "echo"),
        ("PICKUP02.WAV", "echo"),
        ("PICKUP03.WAV", "echo"),
        ("PICKUP04.WAV", "echo"),
        # Weapons: echo (electronic notifications)
        ("WEAPON01.WAV", "echo"),
        ("WEAPON02.WAV", "echo"),
        ("WEAPON03.WAV", "echo"),
        # Level start: alloy (gruff merc)
        ("LEVEL01.WAV", "alloy"),
        ("LEVEL02.WAV", "alloy"),
        # Environmental: echo (robotic/electronic)
        ("ALARM01.WAV", "echo"),
        ("COMP01.WAV", "echo"),
    ])
    def test_voice_mapping(self, filename, expected_voice):
        """Voice assignments must follow cyberpunk mercenary aesthetic."""
        voice_map = {f: v for f, p, v in generate_audio.VOICE_LINES}
        assert voice_map[filename] == expected_voice, \
            f"Expected {filename} → {expected_voice}, got {voice_map[filename]}"


class TestSilenceWavGeneration:
    """Test generate_silence_wav() function for WAV structure."""

    def test_generate_silence_wav_default_params(self):
        """generate_silence_wav() must produce valid WAV data."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        assert isinstance(wav_data, bytes), "WAV data must be bytes"
        assert len(wav_data) > 44, "WAV data must be at least 44 bytes"

    def test_generate_silence_wav_riff_header(self):
        """WAV data must have RIFF/WAVE header."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        riff_sig = wav_data[:4]
        assert riff_sig == b"RIFF", f"Expected RIFF signature, got {riff_sig}"
        
        wave_sig = wav_data[8:12]
        assert wave_sig == b"WAVE", f"Expected WAVE signature, got {wave_sig}"

    def test_generate_silence_wav_size_field(self):
        """WAV RIFF size field must be valid."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        size_bytes = wav_data[4:8]
        size = struct.unpack("<I", size_bytes)[0]
        assert size > 0, "RIFF size must be > 0"
        assert size <= len(wav_data) - 8, "RIFF size must fit in file"

    def test_generate_silence_wav_fmt_chunk(self):
        """WAV must contain fmt chunk with valid audio parameters."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        fmt_pos = wav_data.find(b"fmt ")
        assert fmt_pos > 0, "WAV must contain fmt chunk"
        
        # fmt chunk structure: tag(4) + size(4) + format_data
        fmt_size = struct.unpack("<I", wav_data[fmt_pos+4:fmt_pos+8])[0]
        assert fmt_size >= 16, "fmt chunk must be at least 16 bytes"

    def test_generate_silence_wav_pcm_format(self):
        """WAV fmt chunk must specify PCM format (1)."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        fmt_pos = wav_data.find(b"fmt ")
        fmt_data_start = fmt_pos + 8
        
        audio_format = struct.unpack("<H", wav_data[fmt_data_start:fmt_data_start+2])[0]
        assert audio_format == 1, f"Expected PCM format (1), got {audio_format}"

    def test_generate_silence_wav_channels(self):
        """WAV must have mono (1) channels."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        fmt_pos = wav_data.find(b"fmt ")
        fmt_data_start = fmt_pos + 8
        
        channels = struct.unpack("<H", wav_data[fmt_data_start+2:fmt_data_start+4])[0]
        assert channels == 1, f"Expected mono (1 channel), got {channels}"

    def test_generate_silence_wav_sample_rate(self):
        """WAV must have 22050 Hz sample rate."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        fmt_pos = wav_data.find(b"fmt ")
        fmt_data_start = fmt_pos + 8
        
        sample_rate = struct.unpack("<I", wav_data[fmt_data_start+4:fmt_data_start+8])[0]
        assert sample_rate == 22050, f"Expected 22050 Hz, got {sample_rate}"

    def test_generate_silence_wav_bit_depth(self):
        """WAV must be 16-bit PCM."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        fmt_pos = wav_data.find(b"fmt ")
        fmt_data_start = fmt_pos + 8
        
        bits_per_sample = struct.unpack("<H", wav_data[fmt_data_start+14:fmt_data_start+16])[0]
        assert bits_per_sample == 16, f"Expected 16-bit, got {bits_per_sample}"

    def test_generate_silence_wav_data_chunk(self):
        """WAV must contain data chunk."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        data_pos = wav_data.find(b"data")
        assert data_pos > 0, "WAV must contain data chunk"

    def test_generate_silence_wav_data_size(self):
        """WAV data chunk size must match duration."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        data_pos = wav_data.find(b"data")
        data_size = struct.unpack("<I", wav_data[data_pos+4:data_pos+8])[0]
        
        expected_samples = int(22050 * 0.5)
        expected_bytes = expected_samples * 2  # 16-bit mono = 2 bytes per sample
        assert data_size == expected_bytes, \
            f"Expected {expected_bytes} bytes, got {data_size}"

    def test_generate_silence_wav_readable_by_wave_module(self):
        """WAV data must be readable by Python wave module."""
        wav_data = generate_audio.generate_silence_wav(duration_sec=0.5)
        
        with io.BytesIO(wav_data) as f:
            try:
                with wave.open(f, "rb") as wav:
                    channels = wav.getnchannels()
                    sample_width = wav.getsampwidth()
                    framerate = wav.getframerate()
                    
                    assert channels == 1, f"Expected 1 channel, got {channels}"
                    assert sample_width == 2, f"Expected 2 bytes per sample, got {sample_width}"
                    assert framerate == 22050, f"Expected 22050 Hz, got {framerate}"
            except wave.Error as e:
                pytest.fail(f"WAV file not readable: {e}")

    def test_generate_silence_wav_custom_duration(self):
        """generate_silence_wav() must scale size with duration."""
        wav_short = generate_audio.generate_silence_wav(duration_sec=0.25)
        wav_long = generate_audio.generate_silence_wav(duration_sec=1.0)
        
        assert len(wav_long) > len(wav_short), \
            "Longer duration should produce larger WAV data"


class TestNoAiCodePath:
    """Test the --no-ai code path end-to-end via subprocess."""

    @pytest.mark.slow
    def test_no_ai_flag_generates_wav_files(self):
        """Invoking generate_audio.py --no-ai should produce 21 WAV files."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, \
            f"generate_audio.py --no-ai failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        
        output_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        assert os.path.exists(output_dir), f"Output directory not created: {output_dir}"
        
        wav_files = sorted([f for f in os.listdir(output_dir) if f.endswith(".WAV")])
        assert len(wav_files) == 21, \
            f"Expected 21 WAV files, got {len(wav_files)}"

    @pytest.mark.slow
    def test_no_ai_generates_valid_wav_files(self):
        """All generated WAV files must be valid and readable."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        output_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        wav_files = sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) 
                           if f.endswith(".WAV")])
        
        for wav_file in wav_files:
            try:
                with wave.open(wav_file, "rb") as wav:
                    channels = wav.getnchannels()
                    sample_width = wav.getsampwidth()
                    framerate = wav.getframerate()
                    
                    assert channels == 1, \
                        f"{os.path.basename(wav_file)}: expected 1 channel, got {channels}"
                    assert sample_width == 2, \
                        f"{os.path.basename(wav_file)}: expected 2 bytes/sample, got {sample_width}"
                    assert framerate == 22050, \
                        f"{os.path.basename(wav_file)}: expected 22050 Hz, got {framerate}"
            except wave.Error as e:
                pytest.fail(f"{os.path.basename(wav_file)}: invalid WAV: {e}")

    @pytest.mark.slow
    def test_no_ai_generates_manifest_json(self):
        """--no-ai must generate MANIFEST.json with SOUND_MANIFEST data."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        assert os.path.exists(manifest_path), f"MANIFEST.json not created: {manifest_path}"
        
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        
        # Cycle 75-76: manifest schema evolved from list to dict with
        # schema_version, entries, manifest_checksum. Accept both shapes
        # for legacy compatibility but assert the new fields when present.
        if isinstance(manifest, dict):
            assert manifest.get("schema_version") == "1.0", \
                f"MANIFEST schema_version must be '1.0', got {manifest.get('schema_version')!r}"
            assert "entries" in manifest and isinstance(manifest["entries"], list), \
                "MANIFEST dict must contain an 'entries' list"
            assert len(manifest["entries"]) > 0, "MANIFEST entries must not be empty"
            assert "manifest_checksum" in manifest, \
                "MANIFEST dict must contain 'manifest_checksum'"
        else:
            assert isinstance(manifest, list), "MANIFEST must be JSON list or dict"
            assert len(manifest) > 0, "MANIFEST must not be empty"

    @pytest.mark.slow
    def test_no_ai_mode_no_api_calls(self):
        """--no-ai mode must not attempt API calls (no network required)."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "AUDIO_API_KEY": ""}  # Ensure no API key available
        )
        
        assert result.returncode == 0, \
            f"--no-ai should not fail without API key:\n{result.stderr}"
        assert "[Silence placeholder]" in result.stdout or "placeholder" in result.stdout or "[" in result.stdout, \
            "--no-ai mode should indicate silence generation"


class TestSoundManifestValidation:
    """Validate SOUND_MANIFEST structure."""

    def test_sound_manifest_is_list(self):
        """SOUND_MANIFEST must be a list."""
        assert isinstance(generate_audio.SOUND_MANIFEST, list), \
            f"SOUND_MANIFEST must be a list, got {type(generate_audio.SOUND_MANIFEST)}"

    def test_sound_manifest_has_entries(self):
        """SOUND_MANIFEST must have entries for each VOICE_LINES."""
        assert len(generate_audio.SOUND_MANIFEST) >= len(generate_audio.VOICE_LINES), \
            f"SOUND_MANIFEST has {len(generate_audio.SOUND_MANIFEST)} entries, " \
            f"expected at least {len(generate_audio.VOICE_LINES)}"

    def test_sound_manifest_entry_structure(self):
        """Each SOUND_MANIFEST entry must be a dict with required keys."""
        required_keys = {"wav", "voice", "category"}
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            assert isinstance(entry, dict), \
                f"Entry {i} is not a dict: {type(entry)}"
            for key in required_keys:
                assert key in entry, \
                    f"Entry {i}: missing required key '{key}'"

    def test_sound_manifest_voice_names(self):
        """Voice names in SOUND_MANIFEST must be valid."""
        valid_voices = {"alloy", "echo", "onyx"}
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            voice = entry.get("voice")
            assert voice in valid_voices, \
                f"Entry {i}: invalid voice '{voice}'"

    def test_sound_manifest_wav_filenames(self):
        """WAV filenames in SOUND_MANIFEST must end with .WAV."""
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            wav = entry.get("wav")
            assert wav and wav.endswith(".WAV"), \
                f"Entry {i}: invalid WAV filename '{wav}'"

    def test_voice_lines_have_manifest_entries(self, generated_audio_artifacts):
        """Every VOICE_LINES entry must have a corresponding MANIFEST entry with valid WAV."""
        manifest = generated_audio_artifacts["manifest"]
        entries = manifest.get("entries", []) if isinstance(manifest, dict) else manifest
        manifest_filenames = {entry.get("wav") for entry in entries}
        
        for i, (filename, prompt, voice) in enumerate(generate_audio.VOICE_LINES):
            assert filename in manifest_filenames, \
                f"VOICE_LINES entry {i} ({filename}) has no corresponding MANIFEST entry"
            
            # Find the manifest entry for this file
            manifest_entry = next(
                (entry for entry in entries if entry.get("wav") == filename),
                None
            )
            assert manifest_entry is not None, f"Could not find manifest entry for {filename}"
            assert manifest_entry.get("voice") == voice, \
                f"{filename}: manifest voice '{manifest_entry.get('voice')}' != VOICE_LINES voice '{voice}'"

    def test_manifest_wav_files_exist_and_valid(self, generated_audio_artifacts):
        """Every MANIFEST entry must reference an existing WAV file with valid format."""
        import wave
        
        manifest = generated_audio_artifacts["manifest"]
        entries = manifest.get("entries", []) if isinstance(manifest, dict) else manifest
        sounds_dir = generated_audio_artifacts["sounds_dir"]
        
        for i, entry in enumerate(entries):
            wav_filename = entry.get("wav")
            wav_path = sounds_dir / wav_filename
            
            assert wav_path.exists(), \
                f"Manifest entry {i}: WAV file not found: {wav_path}"
            
            # Verify WAV is readable and has valid properties
            with wave.open(str(wav_path), "rb") as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                framerate = wav.getframerate()
                nframes = wav.getnframes()
                
                assert channels > 0, \
                    f"{wav_filename}: invalid channel count {channels}"
                assert sample_width > 0, \
                    f"{wav_filename}: invalid sample width {sample_width}"
                assert framerate > 0, \
                    f"{wav_filename}: invalid sample rate {framerate}"
                assert nframes > 0, \
                    f"{wav_filename}: no audio frames (duration = 0)"


class TestLoadEnv:
    """Test load_env() function for .env file handling."""

    def test_load_env_nonexistent_file(self):
        """load_env() must handle missing .env file gracefully."""
        nonexistent = "/nonexistent/path/.env"
        result = generate_audio.load_env(nonexistent)
        assert isinstance(result, dict), "load_env must return a dict"
        assert len(result) == 0, "load_env must return empty dict for missing file"

    def test_load_env_parses_key_value_pairs(self, tmp_path):
        """load_env() must parse key=value lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")
        
        result = generate_audio.load_env(str(env_file))
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"

    def test_load_env_ignores_comments(self, tmp_path):
        """load_env() must ignore comment lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("# Comment\nKEY=value\n# Another comment\n")
        
        result = generate_audio.load_env(str(env_file))
        assert "KEY" in result
        assert result["KEY"] == "value"
        assert len(result) == 1

    def test_load_env_ignores_empty_lines(self, tmp_path):
        """load_env() must ignore empty lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\n\n\nKEY2=value2\n")
        
        result = generate_audio.load_env(str(env_file))
        assert len(result) == 2
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"


class TestCliArgparse:
    """Test CLI argument parsing via subprocess."""

    @pytest.mark.slow
    def test_no_ai_flag_parsed(self):
        """--no-ai flag must be recognized and work."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, \
            f"--no-ai flag failed: {result.stderr}"

    @pytest.mark.slow
    def test_help_flag_works(self):
        """--help flag must work."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0, \
            f"--help flag failed: {result.stderr}"
        assert "help" in result.stdout.lower(), \
            "--help output must contain help text"

    @pytest.mark.slow
    def test_unknown_flag_fails(self):
        """Unknown flags must cause argparse to fail."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--invalid-flag"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode != 0, \
            "Unknown flag should fail, but subprocess succeeded"


class TestNoSecretLeak:
    """Verify no hardcoded API keys in generate_audio.py."""

    def test_no_hardcoded_audio_api_key(self):
        """generate_audio.py must not contain hardcoded AUDIO_API_KEY."""
        import re
        source_file = os.path.join(PROJECT_ROOT, "tools", "generate_audio.py")
        with open(source_file, "r") as f:
            content = f.read()
        
        hardcoded_pattern = r'AUDIO_API_KEY\s*=\s*["\']'
        assert not re.search(hardcoded_pattern, content), \
            "Found hardcoded AUDIO_API_KEY"

    def test_no_hardcoded_audio_endpoint(self):
        """generate_audio.py must not contain hardcoded AUDIO_ENDPOINT."""
        import re
        source_file = os.path.join(PROJECT_ROOT, "tools", "generate_audio.py")
        with open(source_file, "r") as f:
            content = f.read()
        
        hardcoded_pattern = r'AUDIO_ENDPOINT\s*=\s*["\']https?'
        assert not re.search(hardcoded_pattern, content), \
            "Found hardcoded AUDIO_ENDPOINT"

    def test_uses_safe_env_lookup(self):
        """generate_audio.py must use safe env lookup methods."""
        import re
        source_file = os.path.join(PROJECT_ROOT, "tools", "generate_audio.py")
        with open(source_file, "r") as f:
            content = f.read()
        
        unsafe_pattern = r'os\.environ\s*\[\s*["\'](?:AUDIO_API_KEY|AUDIO_ENDPOINT)'
        assert not re.search(unsafe_pattern, content), \
            "Found unsafe os.environ[\"KEY\"] access without .get()"


class TestAsyncTimeoutRegression:
    """Regression tests for audio-engineer-r3 findings (semaphore timeout + manifest sync)."""

    @pytest.mark.slow
    def test_async_main_accepts_timeout_parameter(self):
        """Verify that _generate_audio_async_main accepts acquire_timeout_sec parameter.
        
        Regression test for Issue #1 in audio-engineer-r3:
        The --acquire-timeout-sec parameter was parsed but not wired to the async function.
        """
        import inspect
        
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))
        import generate_audio
        
        sig = inspect.signature(generate_audio._generate_audio_async_main)
        assert "acquire_timeout_sec" in sig.parameters, \
            "_generate_audio_async_main must accept acquire_timeout_sec parameter"
        assert sig.parameters["acquire_timeout_sec"].default == 30.0

    @pytest.mark.slow
    def test_async_parallel_api_passes_timeout(self):
        """Verify that _generate_audio_parallel_api passes timeout to async main."""
        import inspect
        
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))
        import generate_audio
        
        sig = inspect.signature(generate_audio._generate_audio_parallel_api)
        assert "acquire_timeout_sec" in sig.parameters, \
            "_generate_audio_parallel_api must accept acquire_timeout_sec parameter"

    def test_manifest_fields_in_generated_artifacts(self, generated_audio_artifacts):
        """Verify manifest has status and generated_at fields."""
        manifest = generated_audio_artifacts["manifest"]
        entries = manifest.get("entries", []) if isinstance(manifest, dict) else manifest
        
        for i, entry in enumerate(entries):
            assert "status" in entry, f"Entry {i}: missing 'status' field"
            assert entry["status"] in ["generated", "fallback", "failed"]
            assert "generated_at" in entry, f"Entry {i}: missing 'generated_at' field"

    @pytest.mark.slow
    def test_no_ai_manifest_consistency(self):
        """Verify --no-ai path properly updates manifest."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"--no-ai failed: {result.stderr}"
        
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        entries = manifest.get("entries", []) if isinstance(manifest, dict) else manifest
        for entry in entries:
            assert "status" in entry, f"Missing status in {entry.get('wav')}"
            assert "generated_at" in entry, f"Missing generated_at in {entry.get('wav')}"


class TestManifestFreshnessSidecar:
    """Tests for audio-r5-manifest-freshness-tracking: freshness sidecar file."""

    def test_freshness_sidecar_created(self):
        """Verify that --no-ai generates freshness sidecar alongside manifest."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"--no-ai failed: {result.stderr}"
        
        sidecar_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "audio_manifest.freshness.json")
        assert os.path.exists(sidecar_path), \
            f"Freshness sidecar not created at {sidecar_path}"

    def test_freshness_sidecar_structure(self):
        """Verify sidecar JSON has required fields: generated_at, manifest_checksum."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"--no-ai failed: {result.stderr}"
        
        sidecar_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "audio_manifest.freshness.json")
        with open(sidecar_path) as f:
            freshness_data = json.load(f)
        
        assert "generated_at" in freshness_data, "Freshness sidecar missing 'generated_at' field"
        assert "manifest_checksum" in freshness_data, "Freshness sidecar missing 'manifest_checksum' field"

    def test_freshness_sidecar_iso8601_timestamp(self):
        """Verify generated_at field is valid ISO8601 format."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"--no-ai failed: {result.stderr}"
        
        sidecar_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "audio_manifest.freshness.json")
        with open(sidecar_path) as f:
            freshness_data = json.load(f)
        
        generated_at = freshness_data["generated_at"]
        # ISO8601 format: should be parseable and contain 'T' separator
        assert "T" in generated_at, f"generated_at not ISO8601: {generated_at}"
        assert "Z" in generated_at or "+" in generated_at or "-" in generated_at[-6:], \
            f"generated_at missing timezone: {generated_at}"

    def test_manifest_determinism_preserved(self):
        """Verify manifest contains hardcoded 1970-01-01 epoch (determinism preserved)."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"--no-ai failed: {result.stderr}"
        
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        entries = manifest.get("entries", []) if isinstance(manifest, dict) else manifest
        for entry in entries:
            # Manifest should still have deterministic 1970 timestamp
            assert entry["generated_at"] == "1970-01-01T00:00:00Z", \
                f"Manifest entry {entry.get('wav')} not deterministic: {entry['generated_at']}"

    def test_sidecar_checksum_matches_manifest(self):
        """Verify sidecar's manifest_checksum matches the manifest's checksum."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"--no-ai failed: {result.stderr}"
        
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        sidecar_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "audio_manifest.freshness.json")
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        with open(sidecar_path) as f:
            freshness_data = json.load(f)
        
        manifest_checksum = manifest.get("manifest_checksum")
        sidecar_checksum = freshness_data.get("manifest_checksum")
        
        assert manifest_checksum is not None, "Manifest missing manifest_checksum"
        assert sidecar_checksum is not None, "Sidecar missing manifest_checksum"
        assert sidecar_checksum == manifest_checksum, \
            f"Checksum mismatch: manifest={manifest_checksum}, sidecar={sidecar_checksum}"

    def test_sidecar_is_separate_file(self):
        """Verify sidecar is a distinct file, not embedded in manifest."""
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"--no-ai failed: {result.stderr}"
        
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        sidecar_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "audio_manifest.freshness.json")
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Manifest should NOT have a "freshness" key at top level
        assert "freshness" not in manifest, "Freshness data embedded in manifest (should be sidecar)"
        assert "generated_at" not in manifest or manifest.get("generated_at") == "1970-01-01T00:00:00Z", \
            "Manifest should not have actual generated_at timestamp"
        
        # Sidecar must exist as separate file
        assert os.path.exists(sidecar_path), f"Sidecar not found at {sidecar_path}"

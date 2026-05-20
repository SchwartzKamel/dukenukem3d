"""Tests for sound-ID manifest bridge (generated_assets/sounds/MANIFEST.json).

Validates the mapping between AI-generated WAVs and engine sound IDs for SDL2_mixer
runtime integration.
"""
import json
import os
import re
import struct
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# Pydantic-inspired validator for sound manifest entries
# ============================================================================

class SoundManifestEntry:
    """Lightweight validator for sound manifest entries (non-pydantic)."""
    
    def __init__(self, **kwargs):
        """Validate sound manifest entry fields."""
        self.wav = kwargs.get('wav')
        self.engine_sound_id = kwargs.get('engine_sound_id')
        self.engine_sound_id_int = kwargs.get('engine_sound_id_int')
        self.voice = kwargs.get('voice')
        self.category = kwargs.get('category')
        self.prompt_summary = kwargs.get('prompt_summary')
        self.status = kwargs.get('status', 'generated')
        self.generated_at = kwargs.get('generated_at')
        self.notes = kwargs.get('notes')
        
        # Validate sound_id matches C identifier pattern
        if self.engine_sound_id is not None:
            if not isinstance(self.engine_sound_id, str):
                raise ValueError(f"engine_sound_id must be str or None, got {type(self.engine_sound_id)}")
            if not re.match(r'^[A-Z_][A-Z0-9_]*$', self.engine_sound_id):
                raise ValueError(f"engine_sound_id '{self.engine_sound_id}' does not match pattern ^[A-Z_][A-Z0-9_]*$")
        
        # Validate voice
        valid_voices = {'alloy', 'echo', 'onyx'}
        if self.voice not in valid_voices:
            raise ValueError(f"voice '{self.voice}' not in {valid_voices}")
        
        # Validate wav path
        if not (self.wav.endswith('.wav') or self.wav.endswith('.WAV')):
            raise ValueError(f"wav '{self.wav}' does not end with .wav or .WAV")

sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

# Import the audio generation module to get VOICE_LINES and SOUND_MANIFEST
import generate_audio


class TestSoundManifestStructure:
    """Validate MANIFEST.json structure and required fields."""

    def test_manifest_entry_count(self):
        """Manifest must have exactly 21 entries (matching VOICE_LINES)."""
        assert len(generate_audio.SOUND_MANIFEST) == 21, \
            f"Expected 21 manifest entries, got {len(generate_audio.SOUND_MANIFEST)}"

    def test_manifest_wav_files_exist_in_voice_lines(self):
        """Every manifest entry's 'wav' must correspond to a VOICE_LINES filename."""
        voice_line_wavs = {filename for filename, _, _ in generate_audio.VOICE_LINES}
        manifest_wavs = {entry["wav"] for entry in generate_audio.SOUND_MANIFEST}
        
        assert manifest_wavs == voice_line_wavs, \
            f"Manifest WAVs do not match VOICE_LINES. Missing: {voice_line_wavs - manifest_wavs}, Extra: {manifest_wavs - voice_line_wavs}"

    def test_manifest_required_fields(self):
        """Each manifest entry must have required fields."""
        required_fields = {"wav", "engine_sound_id", "engine_sound_id_int", "voice", "category", "prompt_summary"}
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            assert isinstance(entry, dict), f"Entry {i} is not a dict: {type(entry)}"
            missing = required_fields - set(entry.keys())
            assert not missing, f"Entry {i} ({entry.get('wav', '?')}): missing fields {missing}"

    def test_manifest_engine_sound_id_type(self):
        """engine_sound_id must be either None or a valid C identifier string."""
        c_identifier_pattern = re.compile(r'^[A-Z_][A-Z0-9_]*$')
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            sound_id = entry["engine_sound_id"]
            assert sound_id is None or isinstance(sound_id, str), \
                f"Entry {i} ({entry['wav']}): engine_sound_id is not None or str: {type(sound_id)}"
            if sound_id is not None:
                assert c_identifier_pattern.match(sound_id), \
                    f"Entry {i} ({entry['wav']}): engine_sound_id '{sound_id}' is not a valid C identifier"

    def test_manifest_engine_sound_id_int_type(self):
        """engine_sound_id_int must be either None or a non-negative int."""
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            id_int = entry["engine_sound_id_int"]
            assert id_int is None or isinstance(id_int, int), \
                f"Entry {i} ({entry['wav']}): engine_sound_id_int is not None or int: {type(id_int)}"
            if id_int is not None:
                assert id_int >= 0, \
                    f"Entry {i} ({entry['wav']}): engine_sound_id_int is negative: {id_int}"

    def test_manifest_voice_values(self):
        """Every 'voice' must be one of {'alloy', 'echo', 'onyx'}."""
        valid_voices = {"alloy", "echo", "onyx"}
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            voice = entry["voice"]
            assert voice in valid_voices, \
                f"Entry {i} ({entry['wav']}): voice '{voice}' not in {valid_voices}"

    def test_manifest_category_values(self):
        """Every 'category' must be a non-empty string."""
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            category = entry["category"]
            assert isinstance(category, str) and category, \
                f"Entry {i} ({entry['wav']}): category is not a non-empty string: {category}"

    def test_manifest_prompt_summary_type(self):
        """Every 'prompt_summary' must be a non-empty string."""
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            summary = entry["prompt_summary"]
            assert isinstance(summary, str) and summary, \
                f"Entry {i} ({entry['wav']}): prompt_summary is not a non-empty string"

    def test_manifest_optional_notes_field(self):
        """If 'notes' field is present, it must be a non-empty string."""
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            if "notes" in entry:
                notes = entry["notes"]
                assert isinstance(notes, str) and notes, \
                    f"Entry {i} ({entry['wav']}): notes is not a non-empty string"


class TestManifestConsistency:
    """Validate internal consistency and cross-field relationships."""

    def test_engine_sound_id_consistency(self):
        """If engine_sound_id is not None, engine_sound_id_int must also be set."""
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            has_id = entry["engine_sound_id"] is not None
            has_int = entry["engine_sound_id_int"] is not None
            assert has_id == has_int, \
                f"Entry {i} ({entry['wav']}): engine_sound_id and engine_sound_id_int must both be None or both set"

    def test_voice_category_alignment(self):
        """Validate voice-to-category alignment follows audio-engineer convention."""
        # alloy (gruff mercenary) → taunts, level_start, death gasps
        # echo (electronic) → pickup, weapon, alarm, ambient
        # onyx (deep authoritative) → pain, death screams
        
        alloy_categories = {"taunt", "level_start", "death"}
        echo_categories = {"pickup", "weapon", "alarm", "ambient"}
        onyx_categories = {"pain", "death"}
        
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            voice = entry["voice"]
            category = entry["category"]
            
            if voice == "alloy":
                assert category in alloy_categories, \
                    f"Entry {i} ({entry['wav']}): 'alloy' voice with unexpected category '{category}'"
            elif voice == "echo":
                assert category in echo_categories, \
                    f"Entry {i} ({entry['wav']}): 'echo' voice with unexpected category '{category}'"
            elif voice == "onyx":
                assert category in onyx_categories, \
                    f"Entry {i} ({entry['wav']}): 'onyx' voice with unexpected category '{category}'"

    def test_runtime_injection_entries_have_notes(self):
        """Entries with engine_sound_id=None should preferably have a 'notes' field explaining why."""
        no_mapping_categories = {"taunt", "pickup", "weapon", "level_start"}
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            if entry["category"] in no_mapping_categories:
                if entry["engine_sound_id"] is None:
                    # These entries should have notes explaining runtime injection
                    assert "notes" in entry, \
                        f"Entry {i} ({entry['wav']}): category '{entry['category']}' with no engine_sound_id should have 'notes' field"


class TestManifestFileGeneration:
    """Validate that MANIFEST.json is generated correctly by generate_audio.py."""

    def test_manifest_file_exists(self):
        """MANIFEST.json must be created by the audio generator."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        assert os.path.exists(manifest_path), \
            f"MANIFEST.json not found at {manifest_path}. Run: python3 tools/generate_audio.py --no-ai"

    def test_manifest_file_valid_json(self):
        """MANIFEST.json must be valid JSON with schema_version."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        try:
            with open(manifest_path) as f:
                data = json.load(f)
            assert isinstance(data, dict), f"MANIFEST.json root must be a dict, got {type(data)}"
            assert "schema_version" in data, "MANIFEST.json missing schema_version field"
            assert data["schema_version"] == "1.0", f"Expected schema_version 1.0, got {data['schema_version']}"
            assert "entries" in data, "MANIFEST.json missing entries field"
            assert isinstance(data["entries"], list), f"entries must be a list, got {type(data['entries'])}"
            assert len(data["entries"]) == 21, f"MANIFEST.json entries must have 21 items, got {len(data['entries'])}"
        except json.JSONDecodeError as e:
            pytest.fail(f"MANIFEST.json is not valid JSON: {e}")

    def test_manifest_file_matches_constant(self):
        """MANIFEST.json file content must match SOUND_MANIFEST constant."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        with open(manifest_path) as f:
            file_manifest = json.load(f)
        
        # New manifest has entries field
        entries = file_manifest.get("entries", [])
        
        # Compare entries as JSON strings to avoid comparison issues with null/None
        assert json.dumps(entries, sort_keys=True) == json.dumps(generate_audio.SOUND_MANIFEST, sort_keys=True), \
            "MANIFEST.json entries do not match SOUND_MANIFEST constant in generate_audio.py"


class TestManifestMapping:
    """Validate specific sound-ID mappings against engine constants."""

    def test_pain_mappings(self):
        """PAIN entries must map to DUKE_GRUNT, DUKE_LONGTERM_PAIN variants."""
        pain_entries = {e["wav"]: e for e in generate_audio.SOUND_MANIFEST if e["category"] == "pain"}
        assert "PAIN01.WAV" in pain_entries
        assert "PAIN02.WAV" in pain_entries
        assert "PAIN03.WAV" in pain_entries
        
        assert pain_entries["PAIN01.WAV"]["engine_sound_id"] == "DUKE_GRUNT"
        assert pain_entries["PAIN02.WAV"]["engine_sound_id"] == "DUKE_LONGTERM_PAIN"
        assert pain_entries["PAIN03.WAV"]["engine_sound_id"] == "DUKE_LONGTERM_PAIN2"

    def test_death_mappings(self):
        """DEATH entries must map to DUKE_SCREAM and DUKE_DEAD."""
        death_entries = {e["wav"]: e for e in generate_audio.SOUND_MANIFEST if e["category"] == "death"}
        assert "DEATH01.WAV" in death_entries
        assert "DEATH02.WAV" in death_entries
        
        assert death_entries["DEATH01.WAV"]["engine_sound_id"] == "DUKE_SCREAM"
        assert death_entries["DEATH02.WAV"]["engine_sound_id"] == "DUKE_DEAD"

    def test_alarm_mapping(self):
        """ALARM01 must map to engine ALARM."""
        alarm_entries = {e["wav"]: e for e in generate_audio.SOUND_MANIFEST if e["category"] == "alarm"}
        assert "ALARM01.WAV" in alarm_entries
        assert alarm_entries["ALARM01.WAV"]["engine_sound_id"] == "ALARM"
        assert alarm_entries["ALARM01.WAV"]["engine_sound_id_int"] == 357

    def test_comp_mapping(self):
        """COMP01 must map to engine COMPUTER_AMBIENCE."""
        ambient_entries = {e["wav"]: e for e in generate_audio.SOUND_MANIFEST if e["category"] == "ambient"}
        assert "COMP01.WAV" in ambient_entries
        assert ambient_entries["COMP01.WAV"]["engine_sound_id"] == "COMPUTER_AMBIENCE"
        assert ambient_entries["COMP01.WAV"]["engine_sound_id_int"] == 86

    def test_runtime_injection_categories(self):
        """TAUNT, PICKUP, WEAPON, LEVEL_START should have engine_sound_id=None."""
        injection_categories = {"taunt", "pickup", "weapon", "level_start"}
        for entry in generate_audio.SOUND_MANIFEST:
            if entry["category"] in injection_categories:
                assert entry["engine_sound_id"] is None, \
                    f"{entry['wav']} (category {entry['category']}): expected engine_sound_id=None, got {entry['engine_sound_id']}"
                assert entry["engine_sound_id_int"] is None, \
                    f"{entry['wav']} (category {entry['category']}): expected engine_sound_id_int=None, got {entry['engine_sound_id_int']}"


class TestWAVFilesExist:
    """Validate that all manifest WAV files have been generated."""

    def test_all_manifest_wav_files_exist(self):
        """Every WAV referenced in SOUND_MANIFEST must exist in generated_assets/sounds/."""
        sounds_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        missing = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if not os.path.exists(wav_file):
                missing.append(entry["wav"])
        
        assert not missing, \
            f"Missing WAV files: {missing}. Run: python3 tools/generate_audio.py --no-ai"

    def test_all_manifest_wav_files_valid_size(self):
        """Every WAV file must be non-empty (> 0 bytes)."""
        sounds_dir = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
        invalid = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if os.path.exists(wav_file):
                size = os.path.getsize(wav_file)
                if size == 0:
                    invalid.append(f"{entry['wav']} (0 bytes)")
                elif size < 44:  # Minimum WAV header size
                    invalid.append(f"{entry['wav']} ({size} bytes, too small)")
        
        assert not invalid, f"Invalid WAV files: {invalid}"


def read_wav_properties(wav_path):
    """Extract WAV file properties (sample_rate, duration, num_channels, bits_per_sample).
    
    Returns a dict with keys: sample_rate, duration, num_channels, bits_per_sample, data_size
    Raises ValueError if the WAV header is invalid.
    """
    with open(wav_path, "rb") as f:
        # Read RIFF header
        riff_header = f.read(12)
        if len(riff_header) < 12:
            raise ValueError("WAV file too small to contain RIFF header")
        
        if riff_header[0:4] != b"RIFF":
            raise ValueError(f"Invalid RIFF signature: {riff_header[0:4]}")
        if riff_header[8:12] != b"WAVE":
            raise ValueError(f"Invalid WAVE signature: {riff_header[8:12]}")
        
        # Read fmt chunk
        fmt_header = f.read(8)
        if len(fmt_header) < 8:
            raise ValueError("WAV file too small to contain fmt chunk header")
        
        if fmt_header[0:4] != b"fmt ":
            raise ValueError(f"Expected 'fmt ' chunk, got {fmt_header[0:4]}")
        
        fmt_size = struct.unpack("<I", fmt_header[4:8])[0]
        if fmt_size < 16:
            raise ValueError(f"fmt chunk size too small: {fmt_size}")
        
        # Read fmt data
        fmt_data = f.read(fmt_size)
        if len(fmt_data) < 16:
            raise ValueError("fmt chunk data too small")
        
        # Parse fmt chunk (at least 16 bytes for PCM)
        audio_format = struct.unpack_from("<H", fmt_data, 0)[0]
        num_channels = struct.unpack_from("<H", fmt_data, 2)[0]
        sample_rate = struct.unpack_from("<I", fmt_data, 4)[0]
        byte_rate = struct.unpack_from("<I", fmt_data, 8)[0]
        block_align = struct.unpack_from("<H", fmt_data, 12)[0]
        bits_per_sample = struct.unpack_from("<H", fmt_data, 14)[0]
        
        if audio_format != 1:
            raise ValueError(f"Not PCM format: {audio_format}")
        
        # Find data chunk
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                raise ValueError("No data chunk found in WAV file")
            
            chunk_id = chunk_header[0:4]
            chunk_size = struct.unpack("<I", chunk_header[4:8])[0]
            
            if chunk_id == b"data":
                # Calculate duration from data chunk size
                bytes_per_sample = bits_per_sample // 8
                if bytes_per_sample == 0:
                    raise ValueError(f"Invalid bits_per_sample: {bits_per_sample}")
                total_samples = chunk_size // (num_channels * bytes_per_sample)
                duration = total_samples / sample_rate if sample_rate > 0 else 0.0
                
                return {
                    "sample_rate": sample_rate,
                    "duration": duration,
                    "num_channels": num_channels,
                    "bits_per_sample": bits_per_sample,
                    "data_size": chunk_size,
                    "audio_format": audio_format,
                }
            else:
                # Skip non-data chunks
                f.seek(chunk_size, 1)


@pytest.fixture
def sounds_dir():
    """Fixture to get the sounds directory. Skip if it doesn't exist or is empty."""
    sounds_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
    if not os.path.isdir(sounds_path) or not os.listdir(sounds_path):
        pytest.skip("generated_assets/sounds/ not populated. Run: python3 tools/generate_audio.py --no-ai")
    return sounds_path


class TestManifestWavConsistency:
    """Validate WAV file properties and consistency with manifest entries."""
    
    def test_wav_riff_header_valid(self, sounds_dir):
        """Every WAV file must have a valid RIFF header with PCM fmt chunk."""
        invalid_wavs = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if not os.path.exists(wav_file):
                continue
            
            try:
                read_wav_properties(wav_file)
            except (ValueError, struct.error) as e:
                invalid_wavs.append(f"{entry['wav']}: {str(e)}")
        
        assert not invalid_wavs, f"Invalid WAV files: {', '.join(invalid_wavs)}"
    
    def test_wav_riff_header_size_minimum(self, sounds_dir):
        """RIFF header must be at least 44 bytes (RIFF + fmt + minimal data chunk)."""
        invalid_wavs = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if not os.path.exists(wav_file):
                continue
            
            size = os.path.getsize(wav_file)
            if size < 44:
                invalid_wavs.append(f"{entry['wav']} ({size} bytes)")
        
        assert not invalid_wavs, f"WAV files smaller than 44 bytes: {invalid_wavs}"
    
    def test_wav_sample_rate_standard(self, sounds_dir):
        """Sample rate in WAV must be 22050 or 44100 Hz."""
        invalid_wavs = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if not os.path.exists(wav_file):
                continue
            
            try:
                props = read_wav_properties(wav_file)
                sample_rate = props["sample_rate"]
                if sample_rate not in (22050, 44100):
                    invalid_wavs.append(f"{entry['wav']}: sample_rate={sample_rate} (expected 22050 or 44100)")
            except (ValueError, struct.error) as e:
                invalid_wavs.append(f"{entry['wav']}: {str(e)}")
        
        assert not invalid_wavs, f"Non-standard sample rates: {', '.join(invalid_wavs)}"
    
    def test_wav_duration_reasonable(self, sounds_dir):
        """Duration extracted from WAV file must be reasonable (0.1s to 10s)."""
        invalid_wavs = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if not os.path.exists(wav_file):
                continue
            
            try:
                props = read_wav_properties(wav_file)
                duration = props["duration"]
                if duration < 0.1 or duration > 10.0:
                    invalid_wavs.append(f"{entry['wav']}: duration={duration:.2f}s (expected 0.1-10.0s)")
            except (ValueError, struct.error) as e:
                invalid_wavs.append(f"{entry['wav']}: {str(e)}")
        
        assert not invalid_wavs, f"Unreasonable durations: {', '.join(invalid_wavs)}"
    
    def test_wav_channels_mono_or_stereo(self, sounds_dir):
        """Channels in WAV must be 1 (mono) or 2 (stereo)."""
        invalid_wavs = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if not os.path.exists(wav_file):
                continue
            
            try:
                props = read_wav_properties(wav_file)
                channels = props["num_channels"]
                if channels not in (1, 2):
                    invalid_wavs.append(f"{entry['wav']}: channels={channels} (expected 1 or 2)")
            except (ValueError, struct.error) as e:
                invalid_wavs.append(f"{entry['wav']}: {str(e)}")
        
        assert not invalid_wavs, f"Invalid channel count: {', '.join(invalid_wavs)}"
    
    def test_wav_bits_per_sample_16bit(self, sounds_dir):
        """Bits per sample in WAV must be 16."""
        invalid_wavs = []
        for entry in generate_audio.SOUND_MANIFEST:
            wav_file = os.path.join(sounds_dir, entry["wav"])
            if not os.path.exists(wav_file):
                continue
            
            try:
                props = read_wav_properties(wav_file)
                bits = props["bits_per_sample"]
                if bits != 16:
                    invalid_wavs.append(f"{entry['wav']}: bits={bits} (expected 16)")
            except (ValueError, struct.error) as e:
                invalid_wavs.append(f"{entry['wav']}: {str(e)}")
        
        assert not invalid_wavs, f"Non-16-bit WAV files: {', '.join(invalid_wavs)}"
    
    def test_engine_sound_id_int_range(self):
        """engine_sound_id_int must be either None or in range [0, 999]."""
        invalid_entries = []
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            id_int = entry["engine_sound_id_int"]
            if id_int is not None and (not isinstance(id_int, int) or id_int < 0 or id_int > 999):
                invalid_entries.append(f"{entry['wav']}: engine_sound_id_int={id_int} (expected None or 0-999)")
        
        assert not invalid_entries, f"Invalid engine_sound_id_int range: {', '.join(invalid_entries)}"
    
    def test_voice_field_valid_values(self):
        """Voice field must be one of {alloy, echo, onyx}."""
        valid_voices = {"alloy", "echo", "onyx"}
        invalid_entries = []
        for i, entry in enumerate(generate_audio.SOUND_MANIFEST):
            voice = entry.get("voice")
            if voice not in valid_voices:
                invalid_entries.append(f"{entry['wav']}: voice='{voice}' (expected one of {valid_voices})")
        
        assert not invalid_entries, f"Invalid voice values: {', '.join(invalid_entries)}"



class TestManifestJsonRoundtrip:
    """Validate JSON serialization/deserialization consistency."""

    def test_voice_category_alignment_survives_json_roundtrip(self):
        """Load MANIFEST.json, dump to JSON, reload, verify voice categories are identical."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        
        with open(manifest_path, "r") as f:
            original_manifest = json.load(f)
        
        # Extract entries from the new manifest structure
        entries = original_manifest.get("entries", [])
        
        # Extract voice-to-category mapping from original
        original_voice_categories = {}
        for entry in entries:
            key = f"{entry['wav']}::{entry['voice']}"
            original_voice_categories[key] = entry["category"]
        
        # Dump to JSON string and reload
        json_string = json.dumps(original_manifest)
        reloaded_manifest = json.loads(json_string)
        
        # Extract entries from the reloaded manifest
        reloaded_entries = reloaded_manifest.get("entries", [])
        
        # Extract voice-to-category mapping from reloaded
        reloaded_voice_categories = {}
        for entry in reloaded_entries:
            key = f"{entry['wav']}::{entry['voice']}"
            reloaded_voice_categories[key] = entry["category"]
        
        # Verify they match exactly
        assert original_voice_categories == reloaded_voice_categories, \
            "Voice-to-category alignment changed after JSON roundtrip"


class TestManifestSchemaPydantic:
    """Validate manifest entries against pydantic schema with strict validators."""

    def test_all_manifest_entries_pass_schema_validation(self):
        """Load every manifest entry and validate through SoundManifestEntry model."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        
        # Extract entries from the new manifest structure
        entries = manifest.get("entries", [])
        
        validated_entries = []
        validation_errors = []
        
        for i, entry_data in enumerate(entries):
            try:
                entry = SoundManifestEntry(**entry_data)
                validated_entries.append(entry)
            except Exception as e:
                validation_errors.append(f"Entry {i} ({entry_data.get('wav', '?')}): {str(e)}")
        
        assert not validation_errors, f"Pydantic validation errors:\n" + "\n".join(validation_errors)
        assert len(validated_entries) == len(entries), \
            f"Expected {len(entries)} validated entries, got {len(validated_entries)}"

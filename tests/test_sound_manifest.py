"""Tests for sound-ID manifest bridge (generated_assets/sounds/MANIFEST.json).

Validates the mapping between AI-generated WAVs and engine sound IDs for SDL2_mixer
runtime integration.
"""
import json
import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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
        """MANIFEST.json must be valid JSON."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        try:
            with open(manifest_path) as f:
                data = json.load(f)
            assert isinstance(data, list), f"MANIFEST.json root must be an array, got {type(data)}"
            assert len(data) == 21, f"MANIFEST.json array must have 21 entries, got {len(data)}"
        except json.JSONDecodeError as e:
            pytest.fail(f"MANIFEST.json is not valid JSON: {e}")

    def test_manifest_file_matches_constant(self):
        """MANIFEST.json file content must match SOUND_MANIFEST constant."""
        manifest_path = os.path.join(PROJECT_ROOT, "generated_assets", "sounds", "MANIFEST.json")
        with open(manifest_path) as f:
            file_manifest = json.load(f)
        
        # Compare as JSON strings to avoid comparison issues with null/None
        assert json.dumps(file_manifest, sort_keys=True) == json.dumps(generate_audio.SOUND_MANIFEST, sort_keys=True), \
            "MANIFEST.json file does not match SOUND_MANIFEST constant in generate_audio.py"


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

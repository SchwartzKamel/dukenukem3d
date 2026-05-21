#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for manifest checksum verification at LOAD time.

Tests that manifests are verified with SHA256 checksums when loaded.
Sentinel for error identification: manifest-checksum-verify-on-load
"""

import hashlib
import json
import os
import struct
import warnings
import pytest
import sys
from pathlib import Path

# Add tools to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

from manifest_verification import (
    load_and_verify_audio_manifest,
    load_and_verify_tables_manifest,
    verify_manifest_checksum,
    _sha256_of_file,
    _sha256_of_manifest,
)


class TestAudioManifestChecksum:
    """Tests for audio manifest checksum verification."""
    
    def test_audio_manifest_valid_checksums(self, tmp_path):
        """Happy path: valid audio manifest with correct checksums."""
        # Create test WAV file
        wav_file = tmp_path / "TEST01.WAV"
        wav_data = b"RIFF" + struct.pack("<I", 36) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + b"\x00" * 16
        wav_data += b"data" + struct.pack("<I", 0)
        wav_file.write_bytes(wav_data)
        
        # Compute checksum
        wav_checksum = _sha256_of_file(str(wav_file))
        
        # Create manifest
        manifest = {
            "schema_version": "1.0",
            "entries": [
                {
                    "wav": "TEST01.WAV",
                    "checksum": wav_checksum,
                    "voice": "alloy",
                    "category": "taunt",
                    "status": "generated"
                }
            ]
        }
        
        # Compute manifest checksum
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should not raise
        loaded = load_and_verify_audio_manifest(str(manifest_file), str(tmp_path))
        assert loaded == manifest
    
    def test_audio_manifest_corrupted_file(self, tmp_path):
        """Fail fast on corrupted WAV file (checksum mismatch)."""
        # Create test WAV file
        wav_file = tmp_path / "TEST01.WAV"
        wav_data = b"RIFF" + struct.pack("<I", 36) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + b"\x00" * 16
        wav_data += b"data" + struct.pack("<I", 0)
        wav_file.write_bytes(wav_data)
        
        # Use wrong checksum
        wrong_checksum = "0000000000000000000000000000000000000000000000000000000000000000"
        
        manifest = {
            "schema_version": "1.0",
            "entries": [
                {
                    "wav": "TEST01.WAV",
                    "checksum": wrong_checksum,
                    "voice": "alloy",
                    "category": "taunt",
                    "status": "generated"
                }
            ]
        }
        
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should raise with sentinel
        with pytest.raises(RuntimeError) as exc_info:
            load_and_verify_audio_manifest(str(manifest_file), str(tmp_path))
        
        assert "manifest-checksum-verify-on-load" in str(exc_info.value)
        assert "Checksum mismatch" in str(exc_info.value)
    
    def test_audio_manifest_missing_checksum_field(self, tmp_path):
        """Legacy compat: missing checksum field should warn but not fail."""
        # Create test WAV file
        wav_file = tmp_path / "TEST01.WAV"
        wav_data = b"RIFF" + struct.pack("<I", 36) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + b"\x00" * 16
        wav_data += b"data" + struct.pack("<I", 0)
        wav_file.write_bytes(wav_data)
        
        # Create manifest without checksum field
        manifest = {
            "schema_version": "1.0",
            "entries": [
                {
                    "wav": "TEST01.WAV",
                    # NO checksum field
                    "voice": "alloy",
                    "category": "taunt",
                    "status": "generated"
                }
            ]
        }
        
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should warn but not fail (legacy compat)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            loaded = load_and_verify_audio_manifest(str(manifest_file), str(tmp_path))
            assert len(w) >= 1
            assert "lacks checksum field" in str(w[0].message).lower()
        
        assert loaded == manifest
    
    def test_audio_manifest_missing_file(self, tmp_path):
        """Fail fast if WAV file referenced in manifest doesn't exist."""
        wav_checksum = "0000000000000000000000000000000000000000000000000000000000000000"
        
        manifest = {
            "schema_version": "1.0",
            "entries": [
                {
                    "wav": "NONEXISTENT.WAV",
                    "checksum": wav_checksum,
                    "voice": "alloy",
                    "category": "taunt",
                    "status": "generated"
                }
            ]
        }
        
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should raise with sentinel
        with pytest.raises(RuntimeError) as exc_info:
            load_and_verify_audio_manifest(str(manifest_file), str(tmp_path))
        
        assert "manifest-checksum-verify-on-load" in str(exc_info.value)
        assert "not found" in str(exc_info.value)


class TestTablesManifestChecksum:
    """Tests for tables manifest checksum verification."""
    
    def test_tables_manifest_valid_checksums(self, tmp_path):
        """Happy path: valid tables manifest with correct checksums."""
        # Create test TABLES.DAT file
        tables_file = tmp_path / "TABLES.DAT"
        tables_data = b"TABLES" * 100  # Dummy data
        tables_file.write_bytes(tables_data)
        
        # Compute checksum
        tables_checksum = _sha256_of_file(str(tables_file))
        
        # Create manifest
        manifest = {
            "schema_version": "1.0",
            "generated_at": "2025-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"],
            "tables_checksum": tables_checksum
        }
        
        # Compute manifest checksum
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "TABLES_MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should not raise
        loaded = load_and_verify_tables_manifest(str(manifest_file), str(tmp_path))
        assert loaded == manifest
    
    def test_tables_manifest_corrupted_tables_dat(self, tmp_path):
        """Fail fast on corrupted TABLES.DAT (checksum mismatch)."""
        # Create test TABLES.DAT file
        tables_file = tmp_path / "TABLES.DAT"
        tables_data = b"TABLES" * 100
        tables_file.write_bytes(tables_data)
        
        # Use wrong checksum
        wrong_checksum = "0000000000000000000000000000000000000000000000000000000000000000"
        
        manifest = {
            "schema_version": "1.0",
            "generated_at": "2025-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"],
            "tables_checksum": wrong_checksum
        }
        
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "TABLES_MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should raise with sentinel
        with pytest.raises(RuntimeError) as exc_info:
            load_and_verify_tables_manifest(str(manifest_file), str(tmp_path))
        
        assert "manifest-checksum-verify-on-load" in str(exc_info.value)
        assert "TABLES.DAT checksum mismatch" in str(exc_info.value)
    
    def test_tables_manifest_missing_tables_dat(self, tmp_path):
        """Fail fast if TABLES.DAT file doesn't exist."""
        wrong_checksum = "0000000000000000000000000000000000000000000000000000000000000000"
        
        manifest = {
            "schema_version": "1.0",
            "generated_at": "2025-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"],
            "tables_checksum": wrong_checksum
        }
        
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "TABLES_MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should raise with sentinel
        with pytest.raises(RuntimeError) as exc_info:
            load_and_verify_tables_manifest(str(manifest_file), str(tmp_path))
        
        assert "manifest-checksum-verify-on-load" in str(exc_info.value)
        assert "not found" in str(exc_info.value)
    
    def test_tables_manifest_missing_checksum_field(self, tmp_path):
        """Legacy compat: missing tables_checksum field should warn but not fail."""
        # Don't create TABLES.DAT file (it won't be checked anyway)
        
        # Create manifest without tables_checksum field
        manifest = {
            "schema_version": "1.0",
            "generated_at": "2025-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"]
            # NO tables_checksum field
        }
        
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        manifest_file = tmp_path / "TABLES_MANIFEST.json"
        manifest_file.write_text(json.dumps(manifest))
        
        # Should warn but not fail (legacy compat)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            loaded = load_and_verify_tables_manifest(str(manifest_file), str(tmp_path))
            assert len(w) >= 1
            assert "lacks tables_checksum field" in str(w[0].message).lower()
        
        assert loaded == manifest


class TestManifestChecksum:
    """Tests for manifest-level checksum verification."""
    
    def test_manifest_checksum_valid(self, tmp_path):
        """Happy path: valid manifest checksum."""
        manifest = {
            "schema_version": "1.0",
            "generated_at": "2025-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"]
        }
        
        manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
        
        # Should not raise
        verify_manifest_checksum(manifest)
    
    def test_manifest_checksum_corrupted(self, tmp_path):
        """Fail fast on corrupted manifest checksum."""
        manifest = {
            "schema_version": "1.0",
            "generated_at": "2025-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"],
            "manifest_checksum": "0000000000000000000000000000000000000000000000000000000000000000"
        }
        
        # Should raise with sentinel
        with pytest.raises(RuntimeError) as exc_info:
            verify_manifest_checksum(manifest)
        
        assert "manifest-checksum-verify-on-load" in str(exc_info.value)
        assert "integrity check failed" in str(exc_info.value)
    
    def test_manifest_checksum_missing_field(self, tmp_path):
        """Legacy compat: missing manifest_checksum field should warn but not fail."""
        manifest = {
            "schema_version": "1.0",
            "generated_at": "2025-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"]
            # NO manifest_checksum field
        }
        
        # Should warn but not fail (legacy compat)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            verify_manifest_checksum(manifest)
            assert len(w) >= 1
            assert "lacks manifest_checksum field" in str(w[0].message).lower()


class TestIntegrationWithRealArtifacts:
    """Integration tests with real generated artifacts."""
    
    def test_load_real_audio_manifest(self, generated_audio_artifacts):
        """Integration test: load real generated audio manifest."""
        # The fixture already uses verify on load, but let's also test it directly
        manifest_path = generated_audio_artifacts["manifest_path"]
        sounds_dir = generated_audio_artifacts["sounds_dir"]
        
        # Should not raise
        manifest = load_and_verify_audio_manifest(str(manifest_path), str(sounds_dir))
        
        # Verify it has entries
        assert "entries" in manifest
        assert len(manifest["entries"]) > 0
    
    def test_load_real_tables_manifest(self):
        """Integration test: load real generated tables manifest."""
        manifest_path = Path(PROJECT_ROOT) / "generated_assets" / "TABLES_MANIFEST.json"
        
        if not manifest_path.exists():
            pytest.skip("TABLES_MANIFEST.json not found; skipping integration test")
        
        base_dir = manifest_path.parent
        
        # Should not raise
        manifest = load_and_verify_tables_manifest(str(manifest_path), str(base_dir))
        
        # Verify schema
        assert "schema_version" in manifest
        assert "table_names" in manifest

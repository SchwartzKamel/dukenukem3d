#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for asset validation post-generation checks.

Tests the validate_generated_artifacts validator with mock present/absent files.
"""

import os
import pytest
import sys
import tempfile
from pathlib import Path

# Add tools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from validate_generated_artifacts import (
    validate_artifacts,
    ARTIFACT_SETS,
    _check_file,
)


class TestCheckFileSingle:
    """Test _check_file for single file validation."""
    
    def test_file_exists_nonzero(self, tmp_path):
        """File exists with non-zero size passes."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"x" * 100)
        
        is_valid, error = _check_file(str(test_file), "required", "Test file")
        assert is_valid
        assert error is None
    
    def test_file_missing(self, tmp_path):
        """Missing file fails."""
        test_file = tmp_path / "missing.bin"
        
        is_valid, error = _check_file(str(test_file), "required", "Test file")
        assert not is_valid
        assert error is not None
        assert "MISSING" in error
    
    def test_file_zero_byte(self, tmp_path):
        """Zero-byte file fails."""
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")
        
        is_valid, error = _check_file(str(test_file), "required", "Test file")
        assert not is_valid
        assert error is not None
        assert "ZERO-BYTE" in error


class TestValidateArtifactSets:
    """Test validate_artifacts for complete artifact sets."""
    
    def test_textures_all_present(self, tmp_path):
        """Textures validation passes when all files present."""
        # Create all required texture files
        (tmp_path / "TILES000.ART").write_bytes(b"x" * 1000)
        (tmp_path / "PALETTE.DAT").write_bytes(b"x" * 256 * 3)
        (tmp_path / "TABLES.DAT").write_bytes(b"x" * 10000)
        
        is_valid, errors = validate_artifacts("textures", base_dir=str(tmp_path))
        assert is_valid
        assert len(errors) == 0
    
    def test_textures_missing_tiles(self, tmp_path):
        """Textures validation fails when TILES000.ART missing."""
        (tmp_path / "PALETTE.DAT").write_bytes(b"x" * 256 * 3)
        (tmp_path / "TABLES.DAT").write_bytes(b"x" * 10000)
        
        is_valid, errors = validate_artifacts("textures", base_dir=str(tmp_path))
        assert not is_valid
        assert len(errors) == 1
        assert "TILES000.ART" in errors[0]
    
    def test_textures_missing_palette(self, tmp_path):
        """Textures validation fails when PALETTE.DAT missing."""
        (tmp_path / "TILES000.ART").write_bytes(b"x" * 1000)
        (tmp_path / "TABLES.DAT").write_bytes(b"x" * 10000)
        
        is_valid, errors = validate_artifacts("textures", base_dir=str(tmp_path))
        assert not is_valid
        assert len(errors) == 1
        assert "PALETTE.DAT" in errors[0]
    
    def test_textures_missing_tables(self, tmp_path):
        """Textures validation fails when TABLES.DAT missing."""
        (tmp_path / "TILES000.ART").write_bytes(b"x" * 1000)
        (tmp_path / "PALETTE.DAT").write_bytes(b"x" * 256 * 3)
        
        is_valid, errors = validate_artifacts("textures", base_dir=str(tmp_path))
        assert not is_valid
        assert len(errors) == 1
        assert "TABLES.DAT" in errors[0]
    
    def test_grp_in_base_dir(self, tmp_path):
        """GRP validation passes when DUKE3D.GRP in base dir."""
        (tmp_path / "DUKE3D.GRP").write_bytes(b"DUKE\x00\x00" + b"x" * 1000)
        
        fake_project_root = tmp_path / "project_root"
        fake_project_root.mkdir()
        
        is_valid, errors = validate_artifacts(
            "grp", base_dir=str(tmp_path), project_root=str(fake_project_root)
        )
        assert is_valid
        assert len(errors) == 0
    
    def test_grp_in_project_root(self, tmp_path):
        """GRP validation passes when DUKE3D.GRP in project root."""
        fake_project_root = tmp_path / "project_root"
        fake_project_root.mkdir()
        (fake_project_root / "DUKE3D.GRP").write_bytes(b"DUKE\x00\x00" + b"x" * 1000)
        
        fake_base_dir = tmp_path / "assets"
        fake_base_dir.mkdir()
        
        is_valid, errors = validate_artifacts(
            "grp", base_dir=str(fake_base_dir), project_root=str(fake_project_root)
        )
        assert is_valid
        assert len(errors) == 0
    
    def test_grp_missing(self, tmp_path):
        """GRP validation fails when DUKE3D.GRP missing from both locations."""
        fake_project_root = tmp_path / "project_root"
        fake_project_root.mkdir()
        
        is_valid, errors = validate_artifacts(
            "grp", base_dir=str(tmp_path), project_root=str(fake_project_root)
        )
        assert not is_valid
        assert len(errors) == 1
        assert "DUKE3D.GRP" in errors[0]
    
    def test_maps_present(self, tmp_path):
        """Maps validation passes when E1L1.MAP present."""
        (tmp_path / "E1L1.MAP").write_bytes(b"x" * 5000)
        
        is_valid, errors = validate_artifacts("maps", base_dir=str(tmp_path))
        assert is_valid
        assert len(errors) == 0
    
    def test_maps_missing(self, tmp_path):
        """Maps validation fails when E1L1.MAP missing."""
        is_valid, errors = validate_artifacts("maps", base_dir=str(tmp_path))
        assert not is_valid
        assert len(errors) == 1
        assert "E1L1.MAP" in errors[0]
    
    def test_scripts_all_present(self, tmp_path):
        """Scripts validation passes when all CON/DAT files present."""
        (tmp_path / "GAME.CON").write_bytes(b"x" * 1000)
        (tmp_path / "DEFS.CON").write_bytes(b"x" * 1000)
        (tmp_path / "USER.CON").write_bytes(b"x" * 1000)
        (tmp_path / "LOOKUP.DAT").write_bytes(b"x" * 1000)
        
        is_valid, errors = validate_artifacts("scripts", base_dir=str(tmp_path))
        assert is_valid
        assert len(errors) == 0
    
    def test_scripts_missing_game_con(self, tmp_path):
        """Scripts validation fails when GAME.CON missing."""
        (tmp_path / "DEFS.CON").write_bytes(b"x" * 1000)
        (tmp_path / "USER.CON").write_bytes(b"x" * 1000)
        (tmp_path / "LOOKUP.DAT").write_bytes(b"x" * 1000)
        
        is_valid, errors = validate_artifacts("scripts", base_dir=str(tmp_path))
        assert not is_valid
        assert len(errors) == 1
        assert "GAME.CON" in errors[0]
    
    def test_audio_manifest_present(self, tmp_path):
        """Audio validation passes when MANIFEST.json present in sounds/."""
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        (sounds_dir / "MANIFEST.json").write_bytes(b'{"version": 1}')
        
        is_valid, errors = validate_artifacts(
            "audio", base_dir=str(tmp_path), check_audio_manifest=True
        )
        assert is_valid
        assert len(errors) == 0
    
    def test_audio_manifest_missing(self, tmp_path):
        """Audio validation fails when MANIFEST.json missing."""
        is_valid, errors = validate_artifacts(
            "audio", base_dir=str(tmp_path), check_audio_manifest=True
        )
        assert not is_valid
        assert len(errors) == 1
        assert "MANIFEST.json" in errors[0]
    
    def test_audio_manifest_skipped(self, tmp_path):
        """Audio validation passes when check_audio_manifest=False."""
        is_valid, errors = validate_artifacts(
            "audio", base_dir=str(tmp_path), check_audio_manifest=False
        )
        assert is_valid
        assert len(errors) == 0
    
    def test_audio_manifest_zero_byte(self, tmp_path):
        """Audio validation fails when MANIFEST.json is empty."""
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        (sounds_dir / "MANIFEST.json").write_bytes(b"")
        
        is_valid, errors = validate_artifacts(
            "audio", base_dir=str(tmp_path), check_audio_manifest=True
        )
        assert not is_valid
        assert len(errors) == 1
        assert "ZERO-BYTE" in errors[0]


class TestValidateArtifactsMultiple:
    """Test validating multiple artifact sets together."""
    
    def test_multiple_sets_all_valid(self, tmp_path):
        """Multiple sets validation succeeds when all present."""
        # Create textures
        (tmp_path / "TILES000.ART").write_bytes(b"x" * 1000)
        (tmp_path / "PALETTE.DAT").write_bytes(b"x" * 256 * 3)
        (tmp_path / "TABLES.DAT").write_bytes(b"x" * 10000)
        
        # Create GRP
        (tmp_path / "DUKE3D.GRP").write_bytes(b"x" * 1000)
        
        # Create scripts
        (tmp_path / "GAME.CON").write_bytes(b"x" * 1000)
        (tmp_path / "DEFS.CON").write_bytes(b"x" * 1000)
        (tmp_path / "USER.CON").write_bytes(b"x" * 1000)
        (tmp_path / "LOOKUP.DAT").write_bytes(b"x" * 1000)
        
        # Create maps
        (tmp_path / "E1L1.MAP").write_bytes(b"x" * 5000)
        
        # Create audio
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        (sounds_dir / "MANIFEST.json").write_bytes(b'{"version": 1}')
        
        for artifact_set in ["textures", "grp", "scripts", "maps", "audio"]:
            is_valid, errors = validate_artifacts(
                artifact_set, base_dir=str(tmp_path), check_audio_manifest=True
            )
            assert is_valid, f"{artifact_set} should be valid: {errors}"


class TestValidateArtifactsEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_invalid_artifact_set(self, tmp_path):
        """Invalid artifact set raises ValueError."""
        with pytest.raises(ValueError, match="Unknown artifact set"):
            validate_artifacts("nonexistent", base_dir=str(tmp_path))
    
    def test_multiple_errors(self, tmp_path):
        """Multiple missing files are all reported."""
        # Create only PALETTE.DAT, miss TILES000.ART and TABLES.DAT
        (tmp_path / "PALETTE.DAT").write_bytes(b"x" * 256 * 3)
        
        is_valid, errors = validate_artifacts("textures", base_dir=str(tmp_path))
        assert not is_valid
        assert len(errors) == 2  # Missing TILES000.ART and TABLES.DAT
        assert any("TILES000.ART" in e for e in errors)
        assert any("TABLES.DAT" in e for e in errors)
    
    def test_zero_byte_multiple_files(self, tmp_path):
        """Multiple zero-byte files are all detected."""
        (tmp_path / "TILES000.ART").write_bytes(b"")
        (tmp_path / "PALETTE.DAT").write_bytes(b"")
        (tmp_path / "TABLES.DAT").write_bytes(b"x" * 100)
        
        is_valid, errors = validate_artifacts("textures", base_dir=str(tmp_path))
        assert not is_valid
        assert len(errors) == 2
        assert any("TILES000.ART" in e and "ZERO-BYTE" in e for e in errors)
        assert any("PALETTE.DAT" in e and "ZERO-BYTE" in e for e in errors)


class TestArtifactSetsDefinition:
    """Test that ARTIFACT_SETS is properly defined."""
    
    def test_artifact_sets_not_empty(self):
        """ARTIFACT_SETS should have entries."""
        assert len(ARTIFACT_SETS) > 0
    
    def test_artifact_set_keys(self):
        """ARTIFACT_SETS should have expected keys."""
        expected_keys = {"textures", "grp", "audio", "maps", "scripts"}
        assert expected_keys.issubset(ARTIFACT_SETS.keys())
    
    def test_artifact_set_structure(self):
        """Each artifact in ARTIFACT_SETS should have (name, type, description)."""
        for set_name, artifacts in ARTIFACT_SETS.items():
            assert isinstance(artifacts, list)
            for artifact_item in artifacts:
                assert len(artifact_item) == 3, f"Artifact in {set_name} has wrong structure"
                name, check_type, description = artifact_item
                assert isinstance(name, str)
                assert check_type in ("required", "optional")
                assert isinstance(description, str)
    
    def test_no_duplicate_artifacts_in_sets(self):
        """No artifact should appear multiple times in same set."""
        for set_name, artifacts in ARTIFACT_SETS.items():
            names = [a[0] for a in artifacts]
            assert len(names) == len(set(names)), f"Duplicates in {set_name}: {names}"

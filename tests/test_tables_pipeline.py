"""Regression tests for TABLES.DAT manifest generation.

Validates that the table manifest is properly emitted with schema_version,
generated_at timestamp, and table_names list, following the pattern
established by tools/generate_audio.py (cycle 34).
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

# Import from tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from generate_tables import create_manifest, validate_manifest, TABLE_NAMES
from tables import create_tables_dat


class TestManifestStructure:
    """Tests for manifest structure and validation."""

    def test_manifest_has_schema_version(self):
        """Manifest must include schema_version field."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert "schema_version" in manifest
        assert manifest["schema_version"] == "1.0"

    def test_manifest_has_generated_at(self):
        """Manifest must include generated_at timestamp."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert "generated_at" in manifest
        assert manifest["generated_at"] == "1970-01-01T00:00:00Z"

    def test_manifest_has_table_names(self):
        """Manifest must include table_names list."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert "table_names" in manifest
        assert isinstance(manifest["table_names"], list)

    def test_manifest_table_names_complete(self):
        """Manifest table_names must list all expected tables."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        expected_names = {"sine", "radar", "brightness", "fonts"}
        actual_names = set(manifest["table_names"])
        assert expected_names == actual_names

    def test_table_names_constant_matches_manifest(self):
        """TABLE_NAMES constant must match manifest entries."""
        expected = {"sine", "radar", "brightness", "fonts"}
        actual = set(TABLE_NAMES)
        assert expected == actual


class TestManifestValidation:
    """Tests for manifest validation logic."""

    def test_validate_manifest_rejects_missing_schema_version(self):
        """validate_manifest must reject manifest without schema_version."""
        invalid = {"generated_at": "1970-01-01T00:00:00Z", "table_names": ["sine"]}
        try:
            validate_manifest(invalid)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "schema_version" in str(e)

    def test_validate_manifest_rejects_missing_generated_at(self):
        """validate_manifest must reject manifest without generated_at."""
        invalid = {"schema_version": "1.0", "table_names": ["sine"]}
        try:
            validate_manifest(invalid)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "generated_at" in str(e)

    def test_validate_manifest_rejects_missing_table_names(self):
        """validate_manifest must reject manifest without table_names."""
        invalid = {"schema_version": "1.0", "generated_at": "1970-01-01T00:00:00Z"}
        try:
            validate_manifest(invalid)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "table_names" in str(e)

    def test_validate_manifest_rejects_invalid_schema_version(self):
        """validate_manifest must reject unsupported schema versions."""
        invalid = {
            "schema_version": "2.0",
            "generated_at": "1970-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"],
        }
        try:
            validate_manifest(invalid)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "schema_version" in str(e)

    def test_validate_manifest_rejects_incomplete_table_names(self):
        """validate_manifest must reject incomplete table_names list."""
        invalid = {
            "schema_version": "1.0",
            "generated_at": "1970-01-01T00:00:00Z",
            "table_names": ["sine", "radar"],  # Missing brightness, fonts
        }
        try:
            validate_manifest(invalid)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "table_names" in str(e) or "mismatch" in str(e)

    def test_validate_manifest_accepts_valid_manifest(self):
        """validate_manifest must accept valid manifest without raising."""
        valid = {
            "schema_version": "1.0",
            "generated_at": "1970-01-01T00:00:00Z",
            "table_names": ["sine", "radar", "brightness", "fonts"],
        }
        # Should not raise
        validate_manifest(valid)


class TestManifestGeneration:
    """Tests for manifest generation with various timestamps."""

    def test_create_manifest_deterministic(self):
        """create_manifest with deterministic timestamp."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert manifest["generated_at"] == "1970-01-01T00:00:00Z"
        validate_manifest(manifest)

    def test_create_manifest_custom_timestamp(self):
        """create_manifest accepts custom ISO 8601 timestamp."""
        custom_ts = "2025-01-15T14:30:00Z"
        manifest = create_manifest(custom_ts)
        assert manifest["generated_at"] == custom_ts
        validate_manifest(manifest)

    def test_create_manifest_auto_timestamp(self):
        """create_manifest generates current timestamp if not provided."""
        manifest = create_manifest()
        # Should have generated_at in ISO format
        assert "generated_at" in manifest
        assert "T" in manifest["generated_at"]  # ISO format contains T
        # Validate it passes validation
        validate_manifest(manifest)


class TestManifestIntegration:
    """Integration tests for manifest with actual table data."""

    def test_manifest_json_serializable(self):
        """Manifest must be JSON serializable."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        json_str = json.dumps(manifest, indent=2, sort_keys=True)
        assert json_str
        # Verify round-trip
        deserialized = json.loads(json_str)
        assert deserialized == manifest

    def test_tables_dat_generation_unchanged(self):
        """Existing create_tables_dat() must continue to work unchanged."""
        data = create_tables_dat()
        # Original size: 8448 bytes
        assert len(data) == 8448

    def test_manifest_and_tables_dat_both_valid(self):
        """Both manifest and TABLES.DAT should be valid independently."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        tables_dat = create_tables_dat()
        
        # Manifest is valid
        validate_manifest(manifest)
        
        # TABLES.DAT has expected size
        assert len(tables_dat) == 8448
        
        # Both should coexist
        assert manifest["schema_version"] == "1.0"
        assert len(tables_dat) > 0


class TestManifestSchema:
    """Tests for manifest schema compliance."""

    def test_schema_version_is_string(self):
        """schema_version must be a string."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert isinstance(manifest["schema_version"], str)

    def test_generated_at_is_string(self):
        """generated_at must be a string in ISO 8601 format."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert isinstance(manifest["generated_at"], str)
        # Basic ISO 8601 check
        assert "T" in manifest["generated_at"]

    def test_table_names_is_list(self):
        """table_names must be a list."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert isinstance(manifest["table_names"], list)

    def test_table_names_all_strings(self):
        """All table_names entries must be strings."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        for name in manifest["table_names"]:
            assert isinstance(name, str)

    def test_manifest_only_expected_keys(self):
        """Manifest should only contain expected keys (for schema strictness)."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        # When tables_path is not provided, only these keys should be present
        expected_keys = {"schema_version", "generated_at", "table_names", "manifest_checksum"}
        actual_keys = set(manifest.keys())
        assert expected_keys == actual_keys


class TestManifestChecksums:  # asset-r13-manifest-checksums: SHA256 integrity
    """Tests for manifest checksum generation and validation."""

    def test_manifest_has_manifest_checksum_field(self):
        """Manifest must have manifest_checksum field."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        assert "manifest_checksum" in manifest
        assert isinstance(manifest["manifest_checksum"], str)
        assert len(manifest["manifest_checksum"]) == 64  # SHA256 hex

    def test_manifest_has_tables_checksum_field(self):
        """Manifest must have tables_checksum field when tables_path is provided."""
        # Create a temporary tables file
        import tempfile
        tables_dat = create_tables_dat()
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(tables_dat)
            tmp_path = tmp.name
        
        try:
            manifest = create_manifest("1970-01-01T00:00:00Z", tmp_path)
            assert "tables_checksum" in manifest
            assert isinstance(manifest["tables_checksum"], str)
            assert len(manifest["tables_checksum"]) == 64  # SHA256 hex
        finally:
            os.unlink(tmp_path)

    def test_manifest_checksum_is_valid_hex(self):
        """manifest_checksum must be a valid 64-character hex string."""
        manifest = create_manifest("1970-01-01T00:00:00Z")
        checksum = manifest["manifest_checksum"]
        
        # Should be exactly 64 hex characters
        try:
            int(checksum, 16)
        except ValueError:
            assert False, f"manifest_checksum is not a valid hex string: {checksum}"

    def test_tables_checksum_is_valid_hex(self):
        """tables_checksum must be a valid 64-character hex string."""
        import tempfile
        tables_dat = create_tables_dat()
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(tables_dat)
            tmp_path = tmp.name
        
        try:
            manifest = create_manifest("1970-01-01T00:00:00Z", tmp_path)
            checksum = manifest.get("tables_checksum")
            
            if checksum:
                # Should be exactly 64 hex characters
                try:
                    int(checksum, 16)
                except ValueError:
                    assert False, f"tables_checksum is not a valid hex string: {checksum}"
        finally:
            os.unlink(tmp_path)

    def test_manifest_checksum_matches_computed(self):
        """manifest_checksum must match the computed SHA256 of the manifest."""
        import hashlib
        
        manifest = create_manifest("1970-01-01T00:00:00Z")
        stored_checksum = manifest.get("manifest_checksum")
        
        # Compute the checksum (excluding the manifest_checksum field itself)
        manifest_copy = {k: v for k, v in sorted(manifest.items()) if k != "manifest_checksum"}
        canonical = json.dumps(manifest_copy, sort_keys=True, separators=(",", ":"))
        computed_checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        
        assert computed_checksum == stored_checksum, \
            f"manifest_checksum mismatch: stored {stored_checksum}, computed {computed_checksum}"

    def test_tables_checksum_matches_file(self):
        """tables_checksum must match the actual SHA256 of the tables file."""
        import hashlib
        import tempfile
        
        tables_dat = create_tables_dat()
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(tables_dat)
            tmp_path = tmp.name
        
        try:
            manifest = create_manifest("1970-01-01T00:00:00Z", tmp_path)
            stored_checksum = manifest.get("tables_checksum")
            
            if stored_checksum:
                # Compute the actual checksum
                h = hashlib.sha256()
                with open(tmp_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                computed_checksum = h.hexdigest()
                
                assert computed_checksum == stored_checksum, \
                    f"tables_checksum mismatch: stored {stored_checksum}, computed {computed_checksum}"
        finally:
            os.unlink(tmp_path)

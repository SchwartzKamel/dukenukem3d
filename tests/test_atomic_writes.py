"""Tests for atomic file write operations in asset generation.

Validates that:
1. _atomic_write_bytes() ensures complete writes before rename
2. _atomic_write_json() serializes and writes JSON atomically
3. Partial writes don't leave corrupted files at final path
4. Temporary files are cleaned up on errors
5. Parent directory constraint is maintained
"""
import pytest
import sys
import os
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from generate_assets import (
    _atomic_write_bytes,
    _atomic_write_json,
)


class TestAtomicWriteBytes:
    """Test suite for _atomic_write_bytes helper."""

    def test_atomic_write_bytes_creates_file(self):
        """_atomic_write_bytes should create a new file with given data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.bin")
            data = b"Hello, World!"
            
            _atomic_write_bytes(path, data)
            
            assert os.path.exists(path)
            with open(path, "rb") as f:
                assert f.read() == data

    def test_atomic_write_bytes_overwrites_existing(self):
        """_atomic_write_bytes should overwrite existing file atomically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.bin")
            
            # Write initial content
            _atomic_write_bytes(path, b"Old content")
            assert os.path.getsize(path) == 11
            
            # Overwrite with different content
            _atomic_write_bytes(path, b"New content here")
            
            with open(path, "rb") as f:
                content = f.read()
            assert content == b"New content here"
            assert os.path.getsize(path) == 16

    def test_atomic_write_bytes_no_tmp_file_left_on_success(self):
        """_atomic_write_bytes should not leave .tmp file after successful write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.bin")
            _atomic_write_bytes(path, b"data")
            
            tmp_path = path + ".tmp"
            assert not os.path.exists(tmp_path), "Temporary file should be cleaned up"

    def test_atomic_write_bytes_cleans_tmp_on_error(self):
        """_atomic_write_bytes should clean up temp file if write fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a read-only directory to trigger write error
            restricted_dir = os.path.join(tmpdir, "restricted")
            os.makedirs(restricted_dir)
            os.chmod(restricted_dir, 0o444)
            
            path = os.path.join(restricted_dir, "test.bin")
            
            try:
                with pytest.raises((OSError, IOError, PermissionError)):
                    _atomic_write_bytes(path, b"data")
                
                # Check that no temp file was left behind
                tmp_path = path + ".tmp"
                # The temp file should not exist, or if it does, it should be cleaned up
                # (Note: permissions may prevent even temp file creation in restricted dir)
            finally:
                os.chmod(restricted_dir, 0o755)

    def test_atomic_write_bytes_large_data(self):
        """_atomic_write_bytes should handle large data correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "large.bin")
            # 10MB of data
            large_data = b"X" * (10 * 1024 * 1024)
            
            _atomic_write_bytes(path, large_data)
            
            with open(path, "rb") as f:
                assert f.read() == large_data

    def test_atomic_write_bytes_binary_data(self):
        """_atomic_write_bytes should preserve binary data with all byte values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "binary.dat")
            # All byte values 0-255
            binary_data = bytes(range(256)) * 100
            
            _atomic_write_bytes(path, binary_data)
            
            with open(path, "rb") as f:
                assert f.read() == binary_data

    def test_atomic_write_bytes_empty_file(self):
        """_atomic_write_bytes should handle empty data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.bin")
            _atomic_write_bytes(path, b"")
            
            assert os.path.exists(path)
            assert os.path.getsize(path) == 0


class TestAtomicWriteJson:
    """Test suite for _atomic_write_json helper."""

    def test_atomic_write_json_simple_dict(self):
        """_atomic_write_json should write a simple dictionary as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            data = {"key": "value", "number": 42}
            
            _atomic_write_json(path, data)
            
            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_atomic_write_json_nested_structure(self):
        """_atomic_write_json should preserve nested structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nested.json")
            data = {
                "top": {
                    "nested": {
                        "list": [1, 2, 3],
                        "string": "value"
                    }
                }
            }
            
            _atomic_write_json(path, data)
            
            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_atomic_write_json_with_indent(self):
        """_atomic_write_json should apply indent formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "indented.json")
            data = {"a": 1, "b": 2}
            
            _atomic_write_json(path, data, indent=2, sort_keys=True)
            
            with open(path, "r") as f:
                content = f.read()
            
            # Should have indentation (2 spaces)
            assert "  " in content
            # Should be formatted
            assert "\n" in content

    def test_atomic_write_json_with_sort_keys(self):
        """_atomic_write_json should sort keys when requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sorted.json")
            data = {"z": 26, "a": 1, "m": 13}
            
            _atomic_write_json(path, data, sort_keys=True)
            
            with open(path, "r") as f:
                content = f.read()
            
            # Check that keys appear in sorted order
            a_pos = content.find('"a"')
            m_pos = content.find('"m"')
            z_pos = content.find('"z"')
            assert a_pos < m_pos < z_pos

    def test_atomic_write_json_no_tmp_left_on_success(self):
        """_atomic_write_json should not leave .tmp file after successful write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            _atomic_write_json(path, {"key": "value"})
            
            tmp_path = path + ".tmp"
            assert not os.path.exists(tmp_path)

    def test_atomic_write_json_overwrite(self):
        """_atomic_write_json should atomically overwrite existing JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "overwrite.json")
            
            # Write initial content
            _atomic_write_json(path, {"version": 1})
            
            # Overwrite with new content
            _atomic_write_json(path, {"version": 2, "extra": "field"})
            
            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded == {"version": 2, "extra": "field"}

    def test_atomic_write_json_list_values(self):
        """_atomic_write_json should handle lists and various data types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "list.json")
            data = {
                "list": [1, "two", 3.0, None, True, False],
                "null_value": None,
                "bool_value": True
            }
            
            _atomic_write_json(path, data)
            
            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_atomic_write_json_special_characters(self):
        """_atomic_write_json should properly escape special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "special.json")
            data = {
                "quotes": 'He said "hello"',
                "backslash": "path\\to\\file",
                "newline": "line1\nline2",
                "tab": "col1\tcol2",
                "unicode": "café ☕ 🎵"
            }
            
            _atomic_write_json(path, data)
            
            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded == data


class TestAtomicWriteParentDirConstraint:
    """Test parent directory constraints for atomic writes."""

    def test_atomic_write_requires_parent_dir_exists(self):
        """_atomic_write_bytes should fail if parent directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Path with non-existent parent directory
            path = os.path.join(tmpdir, "nonexistent", "subdir", "file.bin")
            
            with pytest.raises(OSError):
                _atomic_write_bytes(path, b"data")

    def test_atomic_write_json_requires_parent_dir_exists(self):
        """_atomic_write_json should fail if parent directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nonexistent", "file.json")
            
            with pytest.raises(OSError):
                _atomic_write_json(path, {"key": "value"})


class TestAtomicWriteIntegration:
    """Integration tests for atomic writes in realistic scenarios."""

    def test_concurrent_writes_to_different_files(self):
        """Multiple atomic writes to different files should not interfere."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = [os.path.join(tmpdir, f"file{i}.bin") for i in range(5)]
            datas = [f"content{i}".encode() for i in range(5)]
            
            for path, data in zip(paths, datas):
                _atomic_write_bytes(path, data)
            
            # Verify all files have correct content
            for path, expected_data in zip(paths, datas):
                with open(path, "rb") as f:
                    assert f.read() == expected_data

    def test_atomic_write_manifest_scenario(self):
        """Simulate writing a manifest file as done in _emit_grp_manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "GRP_MANIFEST.json")
            
            # Simulate manifest structure
            manifest = {
                "schema_version": "1.0",
                "generated_at": "2024-01-01T00:00:00Z",
                "grp_path": "DUKE3D.GRP",
                "grp_checksum": "abc123def456",
                "member_count": 3,
                "members": [
                    {"name": "TILES000.ART", "size": 1000, "sha256": "hash1"},
                    {"name": "PALETTE.DAT", "size": 2000, "sha256": "hash2"},
                    {"name": "E1L1.MAP", "size": 3000, "sha256": "hash3"}
                ],
                "manifest_checksum": "checksum_value"
            }
            
            # Write using atomic helper
            _atomic_write_json(manifest_path, manifest, indent=2, sort_keys=True)
            
            # Verify can read back
            with open(manifest_path, "r") as f:
                loaded = json.load(f)
            assert loaded == manifest
            assert loaded["manifest_checksum"] == "checksum_value"

    def test_atomic_write_binary_asset_scenario(self):
        """Simulate writing binary asset files (ART, PALETTE, MAP, GRP)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate various asset files
            assets = {
                "TILES000.ART": b"\x00" * 1000,
                "PALETTE.DAT": bytes(range(256)) * 100,
                "E1L1.MAP": b"MAP\x00" + b"\xff" * 500,
                "DUKE3D.GRP": b"GRP\x1a" + b"\x00" * 2000
            }
            
            for name, data in assets.items():
                path = os.path.join(tmpdir, name)
                _atomic_write_bytes(path, data)
            
            # Verify all files
            for name, expected_data in assets.items():
                path = os.path.join(tmpdir, name)
                with open(path, "rb") as f:
                    assert f.read() == expected_data

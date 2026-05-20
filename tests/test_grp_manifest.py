#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for GRP manifest emission and verification.

Tests verify:
- GRP manifest JSON structure (schema_version, generated_at, checksums, members)
- SHA256 checksum computation for GRP file and member files
- Manifest checksum validation (verify-on-load)
- Sentinel: asset-r16-grp-manifest-emit
"""

import json
import os
import sys
import tempfile
import unittest

# Add tools directory to path
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "tools")
sys.path.insert(0, TOOLS_DIR)

from generate_assets import _emit_grp_manifest, _sha256_of_data, _sha256_of_manifest
from manifest_verification import load_and_verify_grp_manifest, verify_manifest_checksum


class TestGrpManifestEmission(unittest.TestCase):
    """Test GRP manifest generation."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_emit_grp_manifest_creates_file(self):
        """Test that _emit_grp_manifest creates GRP_MANIFEST.json."""
        # Create a mock GRP file
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"KenSilverman" + b"\x02\x00\x00\x00"  # 2 files
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        # Create mock GRP contents
        grp_contents = {
            "FILE1.DAT": b"content1",
            "FILE2.DAT": b"content2"
        }

        # Emit manifest
        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Verify manifest file exists
        self.assertTrue(os.path.exists(manifest_path), "Manifest file not created")

    def test_emit_grp_manifest_structure(self):
        """Test that emitted manifest has correct structure."""
        # Create a mock GRP file
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"KenSilverman"
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {"TEST.DAT": b"test"}

        # Emit manifest
        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Read and validate structure
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        # Check required fields
        self.assertIn("schema_version", manifest)
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertIn("generated_at", manifest)
        self.assertIn("grp_checksum", manifest)
        self.assertIn("grp_path", manifest)
        self.assertIn("member_count", manifest)
        self.assertIn("members", manifest)
        self.assertIn("manifest_checksum", manifest)

    def test_emit_grp_manifest_member_list(self):
        """Test that manifest includes correct member listing."""
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"test"
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {
            "FILE1.DAT": b"content1",
            "FILE2.DAT": b"content2"
        }

        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        # Verify members
        self.assertEqual(manifest["member_count"], 2)
        self.assertEqual(len(manifest["members"]), 2)

        # Check first member (sorted alphabetically)
        member1 = manifest["members"][0]
        self.assertEqual(member1["name"], "FILE1.DAT")
        self.assertEqual(member1["size"], 8)
        self.assertEqual(member1["sha256"], _sha256_of_data(b"content1"))

    def test_sentinel_in_source(self):
        """Test that sentinel 'asset-r16-grp-manifest-emit' exists in source."""
        # sentinel: asset-r16-grp-manifest-emit
        with open(os.path.join(TOOLS_DIR, "generate_assets.py"), "r") as f:
            source = f.read()
        self.assertIn("asset-r16-grp-manifest-emit", source,
                      "Sentinel 'asset-r16-grp-manifest-emit' not found in generate_assets.py")

    def test_manifest_checksum_validation(self):
        """Test that manifest checksum is correctly computed and validated."""
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"test"
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {"TEST.DAT": b"test"}

        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Load manifest
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        # Verify manifest checksum validation
        verify_manifest_checksum(manifest)  # Should not raise


class TestGrpManifestVerification(unittest.TestCase):
    """Test GRP manifest verification."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_and_verify_grp_manifest(self):
        """Test loading and verifying a GRP manifest."""
        # Create a mock GRP file
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"test"
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {"TEST.DAT": b"test"}

        # Emit manifest
        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Load and verify
        manifest = load_and_verify_grp_manifest(manifest_path, self.temp_dir)
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["schema_version"], "1.0")

    def test_verify_grp_manifest_file_not_found(self):
        """Test that verification fails when manifest file not found."""
        manifest_path = os.path.join(self.temp_dir, "nonexistent.json")
        with self.assertRaises(IOError):
            load_and_verify_grp_manifest(manifest_path)

    def test_verify_grp_checksum_failure(self):
        """Test that verification fails when GRP checksum mismatches."""
        # Create initial GRP file
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"original"
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {"TEST.DAT": b"test"}

        # Emit manifest
        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Modify the GRP file (simulate corruption)
        with open(grp_path, "wb") as f:
            f.write(b"modified")

        # Verification should fail
        with self.assertRaises(RuntimeError) as ctx:
            load_and_verify_grp_manifest(manifest_path, self.temp_dir)
        self.assertIn("manifest-checksum-verify-on-load", str(ctx.exception))

    def test_verify_grp_file_missing(self):
        """Test that verification fails when GRP file is missing."""
        # Create manifest without corresponding GRP file
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"test"
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {"TEST.DAT": b"test"}

        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Delete the GRP file
        os.remove(grp_path)

        # Verification should fail
        with self.assertRaises(RuntimeError) as ctx:
            load_and_verify_grp_manifest(manifest_path, self.temp_dir)
        self.assertIn("manifest-checksum-verify-on-load", str(ctx.exception))

    def test_manifest_checksum_tampering(self):
        """Test that tampered manifest_checksum is detected."""
        # Create a mock GRP file
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"test"
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {"TEST.DAT": b"test"}

        # Emit manifest
        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Tamper with manifest checksum
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        manifest["manifest_checksum"] = "badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb"

        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        # Verification should fail
        with self.assertRaises(RuntimeError) as ctx:
            load_and_verify_grp_manifest(manifest_path, self.temp_dir)
        self.assertIn("manifest-checksum-verify-on-load", str(ctx.exception))

    def test_happy_path_integration(self):
        """Integration test: emit manifest and verify it without corruption."""
        # Create multiple GRP members
        grp_path = os.path.join(self.temp_dir, "DUKE3D.GRP")
        grp_data = b"KenSilverman" + (b"test" * 100)
        with open(grp_path, "wb") as f:
            f.write(grp_data)

        grp_contents = {
            "TILES000.ART": b"tile_data" * 10,
            "PALETTE.DAT": b"palette" * 5,
            "TABLES.DAT": b"tables" * 3,
            "E1L1.MAP": b"map_data" * 7
        }

        # Emit manifest
        manifest_path = os.path.join(self.temp_dir, "GRP_MANIFEST.json")
        _emit_grp_manifest(grp_path, grp_contents, manifest_path)

        # Verify manifest loads without errors
        manifest = load_and_verify_grp_manifest(manifest_path, self.temp_dir)
        self.assertIsNotNone(manifest)

        # Verify manifest structure
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["member_count"], 4)
        self.assertEqual(len(manifest["members"]), 4)


if __name__ == "__main__":
    unittest.main()

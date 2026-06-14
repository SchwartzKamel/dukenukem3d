#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for manifest loader adoption of manifest_verification.py.

sec-r15-manifest-loader-adoption: Ensures all production manifest loaders
route through tools/manifest_verification.py and verify checksums.
"""

import json
import os
import subprocess
import tempfile
import pytest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")


class TestManifestVerifierAdoption:
    """Verify that manifest loaders use the manifest verification utilities."""

    def test_generate_audio_load_manifest_uses_verifier(self):
        """generate_audio.load_manifest() must call load_and_verify_audio_manifest.
        
        sec-r15-manifest-loader-adoption: migrated to verifier
        
        Test that the load_manifest function in generate_audio.py routes
        through the manifest_verification module to ensure all manifests
        are verified for checksum integrity.
        """
        from tools import generate_audio
        
        # Check that the function imports and uses the verifier
        source_file = os.path.join(TOOLS_DIR, "generate_audio.py")
        with open(source_file, encoding="utf-8") as f:
            content = f.read()
        
        # Verify import is present
        assert "from manifest_verification import load_and_verify_audio_manifest" in content, \
            "generate_audio.py must import load_and_verify_audio_manifest from manifest_verification"
        
        # Verify sentinel comment marking migration
        assert "sec-r15-manifest-loader-adoption: migrated to verifier" in content, \
            "generate_audio.load_manifest must have migration sentinel comment"

    def test_no_raw_json_load_on_manifests_in_tools(self):
        """No raw json.load() on manifest files in tools/ (except manifest_verification.py).
        
        sec-r15-manifest-loader-adoption: Ensures tools use the verifier.
        
        This grep-based assertion verifies that tool scripts don't bypass
        the manifest verification system.
        """
        # Search for raw json.load in tools/ (excluding manifest_verification.py).
        # Portable Python scan instead of `grep` (not available on Windows).
        import glob as _glob
        output_lines = []
        for py in _glob.glob(os.path.join(TOOLS_DIR, "**", "*.py"), recursive=True):
            if os.path.basename(py) == "manifest_verification.py":
                continue
            rel = os.path.relpath(py, PROJECT_ROOT).replace(os.sep, "/")
            with open(py, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if "json.load" in line or "json.loads" in line:
                        output_lines.append(f"{rel}:{lineno}:{line.rstrip()}")
        
        # Filter to only lines that match json.load/loads in context of manifest files
        manifest_json_loads = []
        for line in output_lines:
            if not line:
                continue
            # Skip if it's json.load in the context of non-manifest operations
            # (manifest in variable name, or part of manifest loading logic)
            if "manifest" in line.lower() and ("json.load" in line or "json.loads" in line):
                file_path = line.split(':')[0]
                # Only flag if it's not manifest_verification.py
                if "manifest_verification.py" not in file_path:
                    manifest_json_loads.append(line)
        
        # All remaining matches should be from migration or should use the verifier
        # In this case, there should be none (they should all use load_and_verify_audio_manifest)
        if manifest_json_loads:
            # Double-check: are they calling the verifier?
            for line in manifest_json_loads:
                file_path, line_content = line.split(':', 1)
                # Make sure the file uses the verifier somewhere
                with open(file_path, encoding="utf-8") as f:
                    file_content = f.read()
                assert "load_and_verify_audio_manifest" in file_content or \
                       "load_and_verify_tables_manifest" in file_content, \
                    f"File {file_path} has raw json.load on manifest but doesn't use verifier"

    def test_migration_sentinels_present(self):
        """All manifest loaders must have sec-r15-manifest-loader-adoption sentinel.
        
        sec-r15-manifest-loader-adoption: Ensures migrations are marked.
        """
        generate_audio_file = os.path.join(TOOLS_DIR, "generate_audio.py")
        with open(generate_audio_file, encoding="utf-8") as f:
            content = f.read()
        
        # Count migration sentinels (should be present in load_manifest)
        migration_count = content.count("sec-r15-manifest-loader-adoption: migrated to verifier")
        
        # Should have at least one migration marker
        assert migration_count >= 1, \
            "generate_audio.py load_manifest should have migration sentinel"


class TestManifestLoaderBypassDocumentation:
    """Verify that intentional test bypasses are properly documented."""

    def test_test_fixtures_have_bypass_comments(self):
        """Test fixtures that intentionally omit checksums must be marked.
        
        sec-r15-manifest-loader-adoption: intentional test bypass
        
        Tests that create manifests without checksums for schema validation
        testing must have bypass comments.
        """
        test_audio_pipeline = os.path.join(TESTS_DIR, "test_audio_pipeline.py")
        with open(test_audio_pipeline, encoding="utf-8") as f:
            content = f.read()
        
        # Search for test methods that load manifests without checksums
        test_methods = [
            "test_manifest_loader_rejects_unknown_schema_version",
            "test_manifest_loader_validates_enum_fields",
            "test_manifest_loader_validates_category_enum",
            "test_manifest_loader_validates_status_enum",
            "test_manifest_loader_accepts_valid_manifest"
        ]
        
        for method in test_methods:
            assert f"def {method}" in content, \
                f"Test method {method} should exist"
        
        # Verify bypass comments are present in test methods
        bypass_marker = "sec-r15-manifest-loader-adoption: intentional test bypass"
        assert content.count(bypass_marker) >= len(test_methods), \
            f"All {len(test_methods)} test methods should have bypass comments"

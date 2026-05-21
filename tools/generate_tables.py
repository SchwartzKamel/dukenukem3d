#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate TABLES.DAT and manifest for Duke3D: Neon Noir.

Wraps the tables output (sine, radar, brightness, fonts) in a manifest
dict with schema_version, generated_at timestamp, and table_names list.
Mirrors the pattern established by tools/generate_audio.py (cycle 34).
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from tables import create_tables_dat
from manifest_verification import load_and_verify_tables_manifest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "generated_assets")

# Table names in the manifest (deterministic order)
TABLE_NAMES = ["sine", "radar", "brightness", "fonts"]


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Write bytes to a file atomically using tmp+rename pattern.
    
    This ensures that if the process is killed or hits an error mid-write,
    the original file (if it exists) is left untouched rather than corrupted.
    Uses POSIX atomic rename within the same filesystem.
    Includes fsync() for extra durability against power loss / process kill.
    
    # asset-r19-atomic-write-tables-dat: fsync for power-loss protection
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except OSError:
        # Clean up temp file on error to avoid leaving stray .tmp files
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _atomic_write_json(path: str, obj: dict, **json_kwargs) -> None:
    """Write a dict to JSON file atomically.
    
    Serializes obj to JSON and writes atomically using tmp+rename pattern
    with fsync for durability. Any keyword arguments (indent, sort_keys, etc.)
    are passed to json.dumps().
    
    # asset-r19-atomic-write-tables-dat: atomic JSON writes
    """
    json_str = json.dumps(obj, **json_kwargs)
    _atomic_write_bytes(path, json_str.encode("utf-8"))


def _sha256_of_file(path):  # asset-r13-manifest-checksums: per-file checksum
    """Compute SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_of_manifest(manifest_dict):  # asset-r13-manifest-checksums: top-level checksum
    """Compute SHA256 checksum of manifest, excluding the manifest_checksum field itself."""
    canonical = json.dumps(
        {k: v for k, v in sorted(manifest_dict.items()) if k != "manifest_checksum"},
        sort_keys=True,
        separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_manifest(manifest):
    """Validate manifest structure and content.
    
    Args:
        manifest: Dictionary containing schema_version, generated_at, table_names.
    
    Raises:
        ValueError: If manifest is invalid.
    """
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a dictionary")
    
    if "schema_version" not in manifest:
        raise ValueError("Manifest must include schema_version")
    
    if manifest["schema_version"] != "1.0":
        raise ValueError(f"Unsupported schema_version: {manifest['schema_version']}")
    
    if "generated_at" not in manifest:
        raise ValueError("Manifest must include generated_at timestamp")
    
    if "table_names" not in manifest:
        raise ValueError("Manifest must include table_names list")
    
    expected_tables = set(TABLE_NAMES)
    actual_tables = set(manifest["table_names"])
    if expected_tables != actual_tables:
        raise ValueError(
            f"table_names mismatch. Expected {expected_tables}, got {actual_tables}"
        )


def create_manifest(generated_at=None, tables_path=None):
    """Create the manifest dict wrapping TABLES.DAT metadata.
    
    Args:
        generated_at: ISO 8601 timestamp string. If None, uses current UTC time.
                       For determinism (e.g., CI), pass "1970-01-01T00:00:00Z".
        tables_path: Path to TABLES.DAT file for checksum computation.
    
    Returns:
        Dictionary with schema_version, generated_at, table_names, per-file checksums, and manifest_checksum.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()
    
    manifest = {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "table_names": TABLE_NAMES,
    }
    
    # asset-r13-manifest-checksums: SHA256 integrity
    # Add per-file checksum if tables_path is provided
    if tables_path and os.path.exists(tables_path):
        manifest["tables_checksum"] = _sha256_of_file(tables_path)
    
    # Compute and add top-level manifest checksum
    manifest["manifest_checksum"] = _sha256_of_manifest(manifest)
    
    validate_manifest(manifest)
    return manifest


def load_tables_manifest(manifest_path):
    """Load and verify TABLES manifest with SHA256 checksum validation.
    
    # manifest-checksum-verify-on-load: Verify at load time
    Performs SHA256 verification of both manifest integrity and tables_checksum.
    
    Args:
        manifest_path: Path to TABLES_MANIFEST.json file
    
    Returns:
        Validated manifest dict
    
    Raises:
        IOError: If file not found
        ValueError: If validation fails
        RuntimeError: If checksum verification fails (sentinel: manifest-checksum-verify-on-load)
    """
    # manifest-checksum-verify-on-load: Use shared verification function
    return load_and_verify_tables_manifest(manifest_path)


def main():
    parser = argparse.ArgumentParser(description="Generate TABLES.DAT and manifest")
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Use deterministic timestamp (1970-01-01T00:00:00Z) for CI",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Generating TABLES.DAT ===")
    
    # Generate the binary tables
    tables_dat = create_tables_dat()
    print(f"  TABLES.DAT: {len(tables_dat)} bytes")
    
    # Write TABLES.DAT
    tables_path = os.path.join(OUTPUT_DIR, "TABLES.DAT")
    try:
        _atomic_write_bytes(tables_path, tables_dat)
        print(f"  Written to {tables_path}")
    except OSError as exc:
        print(f"[ERROR] Failed to write TABLES.DAT: {exc}", file=sys.stderr)
        return 1

    # Create and write manifest
    generated_at = "1970-01-01T00:00:00Z" if args.deterministic else None
    manifest = create_manifest(generated_at, tables_path)
    
    manifest_path = os.path.join(OUTPUT_DIR, "TABLES_MANIFEST.json")
    try:
        _atomic_write_json(manifest_path, manifest, indent=2, sort_keys=True)
        print(f"\n=== Manifest written to {manifest_path} ===")
        print(f"  schema_version: {manifest['schema_version']}")
        print(f"  generated_at: {manifest['generated_at']}")
        print(f"  table_names: {', '.join(manifest['table_names'])}")
    except OSError as exc:
        print(f"[ERROR] Failed to write manifest: {exc}", file=sys.stderr)
        return 1

    print("\n=== Done! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

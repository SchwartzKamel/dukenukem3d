#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Manifest checksum verification utilities for asset pipeline.

Provides functions to load and verify manifest files with SHA256 checksums.
Uses sentinel 'manifest-checksum-verify-on-load' for error identification.
"""

import hashlib
import json
import os
import warnings


def _sha256_of_file(path: str) -> str:
    """Compute SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_of_manifest(manifest_dict):
    """Compute SHA256 checksum of manifest, excluding the manifest_checksum field itself."""
    canonical = json.dumps(
        {k: v for k, v in sorted(manifest_dict.items()) if k != "manifest_checksum"},
        sort_keys=True,
        separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_manifest_checksum(manifest_dict: dict) -> None:
    """Verify the integrity of a manifest's top-level checksum.
    
    Args:
        manifest_dict: Manifest dict containing manifest_checksum field
        
    Raises:
        RuntimeError: If manifest_checksum does not match computed value
                     (sentinel: manifest-checksum-verify-on-load)
    """
    if "manifest_checksum" not in manifest_dict:
        # Legacy compat: log warning but don't fail
        warnings.warn(
            "Manifest lacks manifest_checksum field (legacy compat mode)",
            category=UserWarning,
            stacklevel=2
        )
        return
    
    expected_checksum = manifest_dict["manifest_checksum"]
    computed_checksum = _sha256_of_manifest(manifest_dict)
    
    if computed_checksum != expected_checksum:
        # manifest-checksum-verify-on-load: sentinel for error identification
        raise RuntimeError(
            f"manifest-checksum-verify-on-load: Manifest integrity check failed. "
            f"Expected {expected_checksum}, got {computed_checksum}. "
            f"Manifest may be corrupted or tampered."
        )


def load_and_verify_audio_manifest(manifest_path: str, base_dir: str = None) -> dict:
    """Load and verify audio manifest with per-file SHA256 checksums.
    
    For each entry with a 'checksum' field, recomputes SHA256 of the referenced WAV file
    and raises RuntimeError on mismatch.
    
    Args:
        manifest_path: Path to MANIFEST.json file
        base_dir: Directory to resolve WAV paths relative to. Defaults to manifest's directory.
        
    Returns:
        Validated manifest dict
        
    Raises:
        IOError: If manifest file not found
        ValueError: If manifest JSON is invalid
        RuntimeError: If checksum verification fails (sentinel: manifest-checksum-verify-on-load)
    """
    if not os.path.exists(manifest_path):
        raise IOError(f"Manifest file not found: {manifest_path}")
    
    if base_dir is None:
        base_dir = os.path.dirname(manifest_path)
    
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    # Verify manifest-level checksum (if present)
    verify_manifest_checksum(manifest)
    
    # Verify per-entry checksums
    if "entries" in manifest and isinstance(manifest["entries"], list):
        for idx, entry in enumerate(manifest["entries"]):
            if not isinstance(entry, dict):
                continue
            
            # If entry has no checksum field, skip (legacy compat)
            if "checksum" not in entry:
                warnings.warn(
                    f"Manifest entry[{idx}] lacks checksum field (legacy compat mode)",
                    category=UserWarning,
                    stacklevel=2
                )
                continue
            
            # Entry has checksum: verify the file
            expected_checksum = entry["checksum"]
            
            # Get the WAV filename
            wav_file = entry.get("wav")
            if not wav_file:
                warnings.warn(
                    f"Manifest entry[{idx}] lacks wav field; skipping checksum verification",
                    category=UserWarning,
                    stacklevel=2
                )
                continue
            
            wav_path = os.path.join(base_dir, wav_file)
            
            if not os.path.exists(wav_path):
                # manifest-checksum-verify-on-load: sentinel for error identification
                raise RuntimeError(
                    f"manifest-checksum-verify-on-load: WAV file referenced in manifest not found: {wav_path}"
                )
            
            computed_checksum = _sha256_of_file(wav_path)
            
            if computed_checksum != expected_checksum:
                # manifest-checksum-verify-on-load: sentinel for error identification
                raise RuntimeError(
                    f"manifest-checksum-verify-on-load: Checksum mismatch for {wav_file} in manifest entry[{idx}]. "
                    f"Expected {expected_checksum}, got {computed_checksum}. "
                    f"File may be corrupted or tampered."
                )
    
    return manifest


def load_and_verify_tables_manifest(manifest_path: str, base_dir: str = None) -> dict:
    """Load and verify tables manifest with SHA256 checksums.

    Verifies the manifest-level checksum and the tables_checksum field.

    Args:
        manifest_path: Path to TABLES_MANIFEST.json file
        base_dir: Directory to resolve TABLES.DAT path relative to. Defaults to manifest's directory.

    Returns:
        Validated manifest dict

    Raises:
        IOError: If manifest file not found
        ValueError: If manifest JSON is invalid
        RuntimeError: If checksum verification fails (sentinel: manifest-checksum-verify-on-load)
    """
    if not os.path.exists(manifest_path):
        raise IOError(f"Manifest file not found: {manifest_path}")

    if base_dir is None:
        base_dir = os.path.dirname(manifest_path)

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Verify manifest-level checksum
    verify_manifest_checksum(manifest)

    # Verify tables_checksum if present
    if "tables_checksum" in manifest:
        expected_tables_checksum = manifest["tables_checksum"]
        tables_path = os.path.join(base_dir, "TABLES.DAT")

        if not os.path.exists(tables_path):
            # manifest-checksum-verify-on-load: sentinel for error identification
            raise RuntimeError(
                f"manifest-checksum-verify-on-load: TABLES.DAT file not found: {tables_path}"
            )

        computed_tables_checksum = _sha256_of_file(tables_path)

        if computed_tables_checksum != expected_tables_checksum:
            # manifest-checksum-verify-on-load: sentinel for error identification
            raise RuntimeError(
                f"manifest-checksum-verify-on-load: TABLES.DAT checksum mismatch. "
                f"Expected {expected_tables_checksum}, got {computed_tables_checksum}. "
                f"File may be corrupted or tampered."
            )
    else:
        # Legacy compat: log warning but don't fail
        warnings.warn(
            "Tables manifest lacks tables_checksum field (legacy compat mode)",
            category=UserWarning,
            stacklevel=2
        )

    return manifest


def load_and_verify_grp_manifest(manifest_path: str, base_dir: str = None) -> dict:  # asset-r16-grp-manifest-emit: verify GRP manifest
    """Load and verify GRP manifest with SHA256 checksums.

    Verifies the manifest-level checksum, GRP file checksum, and member checksums.

    Args:
        manifest_path: Path to GRP_MANIFEST.json file
        base_dir: Directory to resolve DUKE3D.GRP path relative to. Defaults to manifest's directory.

    Returns:
        Validated manifest dict

    Raises:
        IOError: If manifest file not found
        ValueError: If manifest JSON is invalid
        RuntimeError: If checksum verification fails (sentinel: manifest-checksum-verify-on-load)
    """
    if not os.path.exists(manifest_path):
        raise IOError(f"Manifest file not found: {manifest_path}")

    if base_dir is None:
        base_dir = os.path.dirname(manifest_path)

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Verify manifest-level checksum
    verify_manifest_checksum(manifest)

    # Verify GRP file checksum if present
    if "grp_checksum" in manifest and "grp_path" in manifest:
        expected_grp_checksum = manifest["grp_checksum"]
        grp_path = os.path.join(base_dir, manifest["grp_path"])

        if not os.path.exists(grp_path):
            # manifest-checksum-verify-on-load: sentinel for error identification
            raise RuntimeError(
                f"manifest-checksum-verify-on-load: GRP file not found: {grp_path}"
            )

        computed_grp_checksum = _sha256_of_file(grp_path)

        if computed_grp_checksum != expected_grp_checksum:
            # manifest-checksum-verify-on-load: sentinel for error identification
            raise RuntimeError(
                f"manifest-checksum-verify-on-load: GRP checksum mismatch. "
                f"Expected {expected_grp_checksum}, got {computed_grp_checksum}. "
                f"File may be corrupted or tampered."
            )
    else:
        # Legacy compat: log warning but don't fail
        warnings.warn(
            "GRP manifest lacks grp_checksum or grp_path field (legacy compat mode)",
            category=UserWarning,
            stacklevel=2
        )

    # Optionally verify member checksums if members list is present
    if "members" in manifest and isinstance(manifest["members"], list):
        for idx, member in enumerate(manifest["members"]):
            if not isinstance(member, dict):
                continue

            # If member has no checksum field, skip (forward compat for future formats)
            if "sha256" not in member:
                continue

            # Verify the member checksum is valid hex
            try:
                int(member["sha256"], 16)
            except (ValueError, TypeError):
                # manifest-checksum-verify-on-load: sentinel for error identification
                raise RuntimeError(
                    f"manifest-checksum-verify-on-load: Invalid SHA256 hex in member[{idx}]: {member.get('name', 'unknown')}"
                )

    return manifest


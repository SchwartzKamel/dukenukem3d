#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate that all expected generated artifacts exist and have non-zero size.

This post-generation validator checks for:
1. Existence of each required artifact
2. Non-zero file size (catch zero-byte stubs)

Exit codes:
    0: All artifacts present and valid
    1: One or more artifacts missing or invalid
    2: Invalid arguments or environment
"""

import argparse
import os
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATED_ASSETS_DIR = os.path.join(PROJECT_ROOT, "generated_assets")
SOUNDS_DIR = os.path.join(GENERATED_ASSETS_DIR, "sounds")


# Expected artifacts by artifact set.
# Each set is (artifact_name, check_type, description)
# check_type: "required" (file must exist and be non-zero) or "optional" (warn if missing)
ARTIFACT_SETS = {
    "textures": [
        ("TILES000.ART", "required", "BUILD engine tile archive"),
        ("PALETTE.DAT", "required", "256-color palette + shade tables"),
        ("TABLES.DAT", "required", "Sine, radar, font, brightness lookup tables"),
    ],
    "grp": [
        ("DUKE3D.GRP", "required", "Final KenSilverman GRP archive (project root or generated_assets/)"),
    ],
    "audio": [
        ("sounds/MANIFEST.json", "required", "Audio manifest with checksums"),
    ],
    "maps": [
        ("E1L1.MAP", "required", "Episode 1, Level 1 geometry"),
    ],
    "scripts": [
        ("GAME.CON", "required", "Game CON script"),
        ("DEFS.CON", "required", "Definitions CON script"),
        ("USER.CON", "required", "User CON script"),
        ("LOOKUP.DAT", "required", "Lookup table"),
    ],
}


def _check_file(artifact_path, check_type, description):
    """Check if a file exists and has non-zero size.
    
    Returns: (is_valid, error_message or None)
    """
    if not os.path.exists(artifact_path):
        msg = f"{description}: MISSING ({artifact_path})"
        return False, msg
    
    try:
        size = os.path.getsize(artifact_path)
    except OSError as e:
        msg = f"{description}: ERROR reading size ({artifact_path}): {e}"
        return False, msg
    
    if size == 0:
        msg = f"{description}: ZERO-BYTE STUB ({artifact_path})"
        return False, msg
    
    return True, None


def validate_artifacts(artifact_set, base_dir=None, check_audio_manifest=True, project_root=None):
    """Validate a set of generated artifacts.
    
    Args:
        artifact_set: Key from ARTIFACT_SETS dict ("textures", "grp", "audio", etc.)
        base_dir: Base directory for artifact paths (default: generated_assets/)
        check_audio_manifest: If False, skip audio manifest validation
        project_root: Project root for DUKE3D.GRP fallback (default: PROJECT_ROOT)
    
    Returns:
        (is_valid, errors_list)
        - is_valid: True if all required artifacts are present and valid
        - errors_list: List of error messages (empty if is_valid=True)
    """
    if base_dir is None:
        base_dir = GENERATED_ASSETS_DIR
    if project_root is None:
        project_root = PROJECT_ROOT
    
    if artifact_set not in ARTIFACT_SETS:
        raise ValueError(f"Unknown artifact set: {artifact_set}")
    
    errors = []
    artifacts = ARTIFACT_SETS[artifact_set]
    
    for artifact_name, check_type, description in artifacts:
        # Special case: DUKE3D.GRP can exist in project root OR generated_assets/
        if artifact_name == "DUKE3D.GRP":
            grp_in_generated = os.path.join(base_dir, artifact_name)
            grp_in_root = os.path.join(project_root, artifact_name)
            
            is_valid_gen = os.path.exists(grp_in_generated) and os.path.getsize(grp_in_generated) > 0
            is_valid_root = os.path.exists(grp_in_root) and os.path.getsize(grp_in_root) > 0
            
            if is_valid_gen or is_valid_root:
                continue
            
            msg = f"{description}: MISSING (checked {grp_in_generated} and {grp_in_root})"
            if check_type == "required":
                errors.append(msg)
            else:
                print(f"[WARN] {msg}", file=sys.stderr)
            continue
        
        # Special case: audio manifest is in sounds/ subdirectory
        if artifact_name == "sounds/MANIFEST.json":
            if not check_audio_manifest:
                continue
            artifact_path = os.path.join(base_dir, artifact_name)
        else:
            artifact_path = os.path.join(base_dir, artifact_name)
        
        is_valid, error_msg = _check_file(artifact_path, check_type, description)
        if not is_valid:
            if check_type == "required":
                errors.append(error_msg)
            else:
                print(f"[WARN] {error_msg}", file=sys.stderr)
    
    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate generated assets exist and have non-zero size",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all artifact sets
  python3 tools/validate_generated_artifacts.py

  # Validate only textures
  python3 tools/validate_generated_artifacts.py --sets textures

  # Validate textures and grp
  python3 tools/validate_generated_artifacts.py --sets textures grp

  # Skip audio manifest validation (for CI workflows that don't run audio generation)
  python3 tools/validate_generated_artifacts.py --no-audio-manifest

  # Check in custom directory
  python3 tools/validate_generated_artifacts.py --base-dir /tmp/assets
        """)
    
    parser.add_argument(
        "--sets",
        nargs="*",
        choices=list(ARTIFACT_SETS.keys()),
        default=None,
        help="Artifact sets to validate (default: all)")
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help=f"Base directory for artifacts (default: {GENERATED_ASSETS_DIR})")
    parser.add_argument(
        "--no-audio-manifest",
        action="store_true",
        help="Skip audio manifest validation")
    
    args = parser.parse_args()
    
    # Determine which sets to validate
    if args.sets is None:
        sets_to_validate = list(ARTIFACT_SETS.keys())
    else:
        sets_to_validate = args.sets if args.sets else list(ARTIFACT_SETS.keys())
    
    base_dir = args.base_dir or GENERATED_ASSETS_DIR
    all_valid = True
    all_errors = []
    
    for artifact_set in sets_to_validate:
        is_valid, errors = validate_artifacts(
            artifact_set,
            base_dir=base_dir,
            check_audio_manifest=not args.no_audio_manifest
        )
        if not is_valid:
            all_valid = False
            all_errors.extend(errors)
    
    if all_errors:
        print("[ERROR] Validation failed:", file=sys.stderr)
        for error_msg in all_errors:
            print(f"  - {error_msg}", file=sys.stderr)
        return 1
    
    if sets_to_validate:
        print(f"[OK] All artifacts valid ({', '.join(sets_to_validate)})")
        return 0
    
    print("[ERROR] No artifact sets specified", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

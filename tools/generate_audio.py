#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate audio assets for Duke3D: Neon Noir using GPT Audio 1.5."""

import argparse
import asyncio
import base64
import concurrent.futures
import hashlib
import json
import logging
import os
import random
import struct
import sys
import time
from datetime import datetime, timezone

import aiohttp
import requests

from manifest_verification import load_and_verify_audio_manifest
from sound_manifest import validate_sound_manifest_entries

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

# Retry constants for Azure TTS async requests
MAX_RETRIES = 3
MAX_BACKOFF = 8.0

# Configure logging for retry attempts
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.INFO)


def _redact_endpoint(url: str) -> str:
    """Redact sensitive endpoint URL for logging.

    Returns a logging-safe rendering of a connection-string URL showing
    only scheme + host's first label; drops query, path, account suffix.
    """
    if not url:
        return ""
    from urllib.parse import urlparse
    try:
        p = urlparse(url)
        host = (p.hostname or "").split(".")[0]
        return f"{p.scheme}://{host}.***"
    except Exception:
        return "***"


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Write bytes to a file atomically using tmp+rename pattern.
    
    This ensures that if the process is killed or hits an error mid-write,
    the original file (if it exists) is left untouched rather than corrupted.
    Uses POSIX atomic rename within the same filesystem.
    Includes fsync() for extra durability against power loss / process kill.
    
    # sec-r18-atomic-write-hardening: fsync for power-loss protection
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
    
    # sec-r18-atomic-write-hardening: atomic JSON writes
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


def _validate_voice_line_filename_uniqueness(voice_lines):
    """Validate that all VOICE_LINES entries have unique WAV filenames.
    
    asset-r15-sound-name-collision-detection: prevent silent WAV overwrite
    
    In parallel audio generation, duplicate WAV filenames could cause silent
    data loss if two workers write the same file concurrently. This check
    ensures all WAV filenames in VOICE_LINES are unique at module init time.
    
    Args:
        voice_lines: List of (filename, prompt, voice) tuples
        
    Raises:
        RuntimeError: If any WAV filename appears more than once
    """
    filename_to_voice_ids = {}
    
    for idx, (filename, prompt, voice) in enumerate(voice_lines):
        if filename not in filename_to_voice_ids:
            filename_to_voice_ids[filename] = []
        filename_to_voice_ids[filename].append(idx)
    
    for filename, indices in filename_to_voice_ids.items():
        if len(indices) > 1:
            voice_ids = ", ".join(str(i) for i in indices)
            raise RuntimeError(
                f"asset-r15-sound-name-collision: duplicate WAV filename '{filename}' "
                f"across voice entries {voice_ids}"
            )


# (filename, prompt, voice)
VOICE_LINES = [
    # Player taunts / one-liners
    ("TAUNT01.WAV", "Say in a gruff, sarcastic cyberpunk mercenary voice, like a jaded soldier of fortune: Welcome to the machine, punk.", "alloy"),
    ("TAUNT02.WAV", "Say in a gruff cyberpunk mercenary voice, short and brutal: Lights out, chrome-head.", "alloy"),
    ("TAUNT03.WAV", "Say in a gruff cyberpunk mercenary voice: Another day, another megacorp to burn.", "alloy"),
    ("TAUNT04.WAV", "Say in a gruff cyberpunk mercenary voice: Is that all you got? My toaster fights harder.", "alloy"),
    ("TAUNT05.WAV", "Say in a gruff cyberpunk mercenary voice, cocky: Time to take out the trash.", "alloy"),

    # Pain/damage sounds
    ("PAIN01.WAV", "Make a short grunt of pain, like getting punched. Just the grunt, no words. Male voice.", "onyx"),
    ("PAIN02.WAV", "Make a short sharp grunt of pain, like getting shot. Just the sound, no words. Male voice.", "onyx"),
    ("PAIN03.WAV", "Make a longer groan of pain, like taking heavy damage. Male voice, no words.", "onyx"),

    # Death sounds
    ("DEATH01.WAV", "Make a death scream, short and intense. Male voice dying. No words, just the scream.", "onyx"),
    ("DEATH02.WAV", "Say in a dying voice, gasping: System... failure... as if a cyberpunk soldier is shutting down.", "alloy"),

    # Pickup sounds
    ("PICKUP01.WAV", "Say very briefly and electronically: Stim acquired. Like a cyberpunk HUD notification.", "echo"),
    ("PICKUP02.WAV", "Say very briefly and electronically: Ammo loaded. Like a cyberpunk HUD notification.", "echo"),
    ("PICKUP03.WAV", "Say very briefly and electronically: Shield online. Like a cyberpunk HUD notification.", "echo"),
    ("PICKUP04.WAV", "Say very briefly and electronically: Access granted. Like a cyberpunk HUD notification.", "echo"),

    # Weapon switching
    ("WEAPON01.WAV", "Say briefly in a tech voice: Pulse pistol ready. Like a weapon system announcement.", "echo"),
    ("WEAPON02.WAV", "Say briefly in a tech voice: Scatter cannon armed. Like a weapon system announcement.", "echo"),
    ("WEAPON03.WAV", "Say briefly in a tech voice: Plasma launcher online. Like a weapon system announcement.", "echo"),

    # Level start / misc
    ("LEVEL01.WAV", "Say in a gruff cyberpunk voice: Let's get to work. Short and determined.", "alloy"),
    ("LEVEL02.WAV", "Say in a gruff cyberpunk voice: Another sector, another pile of scrap.", "alloy"),

    # Environmental
    ("ALARM01.WAV", "Say in an urgent robotic alarm voice: Warning. Intruder detected. Sector lockdown initiated.", "echo"),
    ("COMP01.WAV", "Say in a calm computer voice: Welcome to NeoTek Industries. All personnel report to decontamination.", "echo"),
]

# Sound ID manifest: bridges AI-generated WAVs to engine sound table.
# Each entry maps a WAV file to its corresponding engine sound ID (if any).
# Engine sound IDs sourced from source/SOUNDEFS.H.
SOUND_MANIFEST = [{'wav': 'TAUNT01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Welcome to the machine, punk.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'TAUNT02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Lights out, chrome-head.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'TAUNT03.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Another day, another megacorp to burn.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'TAUNT04.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Is that all you got?'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'TAUNT05.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Time to take out the trash.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'PAIN01.WAV', 'engine_sound_id': 'DUKE_GRUNT', 'engine_sound_id_int': 38, 'voice': 'onyx', 'category': 'pain', 'prompt_summary': 'short grunt of pain', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'PAIN02.WAV', 'engine_sound_id': 'DUKE_LONGTERM_PAIN', 'engine_sound_id_int': 211, 'voice': 'onyx', 'category': 'pain', 'prompt_summary': 'sharp grunt from shot', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'PAIN03.WAV', 'engine_sound_id': 'DUKE_LONGTERM_PAIN2', 'engine_sound_id_int': 274, 'voice': 'onyx', 'category': 'pain', 'prompt_summary': 'heavy damage groan', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'DEATH01.WAV', 'engine_sound_id': 'DUKE_SCREAM', 'engine_sound_id_int': 245, 'voice': 'onyx', 'category': 'death', 'prompt_summary': 'death scream', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'DEATH02.WAV', 'engine_sound_id': 'DUKE_DEAD', 'engine_sound_id_int': 41, 'voice': 'alloy', 'category': 'death', 'prompt_summary': "dying gasp: 'System... failure...'", 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'PICKUP01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Stim acquired.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'PICKUP02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Ammo loaded.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'PICKUP03.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Shield online.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'PICKUP04.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Access granted.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'WEAPON01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'weapon', 'prompt_summary': "weapon announcement: 'Pulse pistol ready.'", 'notes': 'AI-generated weapon system notification. Engine has weapon pickup sounds (DUKE_GETWEAPON*) but not weapon-ready announcements; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'WEAPON02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'weapon', 'prompt_summary': "weapon announcement: 'Scatter cannon armed.'", 'notes': 'AI-generated weapon system notification. Engine has weapon pickup sounds (DUKE_GETWEAPON*) but not weapon-ready announcements; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'WEAPON03.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'weapon', 'prompt_summary': "weapon announcement: 'Plasma launcher online.'", 'notes': 'AI-generated weapon system notification. Engine has weapon pickup sounds (DUKE_GETWEAPON*) but not weapon-ready announcements; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'LEVEL01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'level_start', 'prompt_summary': "level start: 'Let's get to work.'", 'notes': 'AI-generated level start announcement. Engine has no level-start sound hook in original code; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'LEVEL02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'level_start', 'prompt_summary': "level start: 'Another sector, another pile of scrap.'", 'notes': 'AI-generated level start announcement. Engine has no level-start sound hook in original code; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'ALARM01.WAV', 'engine_sound_id': 'ALARM', 'engine_sound_id_int': 357, 'voice': 'echo', 'category': 'alarm', 'prompt_summary': 'robotic alarm: intruder detected', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}, {'wav': 'COMP01.WAV', 'engine_sound_id': 'COMPUTER_AMBIENCE', 'engine_sound_id_int': 86, 'voice': 'echo', 'category': 'ambient', 'prompt_summary': 'computer voice announcement', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z', 'generation_method': 'ai'}]


# Validate VOICE_LINES at module import time
# asset-r15-sound-name-collision-detection: prevent silent WAV overwrite
_validate_voice_line_filename_uniqueness(VOICE_LINES)


def validate_voice_manifest_sync(voice_lines, sound_manifest):
    """Validate that VOICE_LINES and SOUND_MANIFEST are in sync.
    
    Ensures both data structures have matching entries:
    - Same filenames (no orphans in either side)
    - Same order
    - Same voice assignment for matching entries
    
    Args:
        voice_lines: List of (filename, prompt, voice) tuples
        sound_manifest: List of dicts with 'wav' and 'voice' keys
        
    Raises:
        ValueError: If any sync violations are detected, listing:
            - Orphans in VOICE_LINES (files with no SOUND_MANIFEST entry)
            - Orphans in SOUND_MANIFEST (files with no VOICE_LINES entry)
            - Order differences (if same files but different positions)
            - Voice assignment mismatches (same file, different voice)
    """
    voice_lines_filenames = [filename for filename, _, _ in voice_lines]
    voice_lines_voices = {filename: voice for filename, _, voice in voice_lines}
    
    sound_manifest_filenames = [entry['wav'] for entry in sound_manifest]
    sound_manifest_voices = {entry['wav']: entry['voice'] for entry in sound_manifest}
    
    errors = []
    
    # Check for orphans in VOICE_LINES
    orphans_in_voice = set(voice_lines_filenames) - set(sound_manifest_filenames)
    if orphans_in_voice:
        errors.append(f"Orphans in VOICE_LINES (no SOUND_MANIFEST entry): {sorted(orphans_in_voice)}")
    
    # Check for orphans in SOUND_MANIFEST
    orphans_in_manifest = set(sound_manifest_filenames) - set(voice_lines_filenames)
    if orphans_in_manifest:
        errors.append(f"Orphans in SOUND_MANIFEST (no VOICE_LINES entry): {sorted(orphans_in_manifest)}")
    
    # Check for order differences (same files, different order)
    if voice_lines_filenames != sound_manifest_filenames:
        if set(voice_lines_filenames) == set(sound_manifest_filenames):
            errors.append(f"Order mismatch: VOICE_LINES {voice_lines_filenames} != SOUND_MANIFEST {sound_manifest_filenames}")
    
    # Check for voice assignment mismatches
    common_files = set(voice_lines_filenames) & set(sound_manifest_filenames)
    for filename in common_files:
        voice_lines_voice = voice_lines_voices[filename]
        manifest_voice = sound_manifest_voices[filename]
        if voice_lines_voice != manifest_voice:
            errors.append(f"Voice mismatch for {filename}: VOICE_LINES={voice_lines_voice}, SOUND_MANIFEST={manifest_voice}")
    
    if errors:
        raise ValueError(
            f"Voice manifest sync validation failed:\n" +
            "\n".join(f"  - {error}" for error in errors)
        )


def load_env(path):
    """Load key=value pairs from a .env file."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


def validate_manifest(manifest_data, source_path):
    """Validate manifest structure, schema version, and enum fields.
    
    Args:
        manifest_data: Dict with schema_version and entries keys
        source_path: Path to manifest file (for error messages)
    
    Raises:
        ValueError: If schema_version doesn't match or validation fails
    """
    if not isinstance(manifest_data, dict):
        raise ValueError(f"{source_path}: Manifest must be a dict, got {type(manifest_data).__name__}")
    
    schema_version = manifest_data.get("schema_version")
    if schema_version != "1.0":
        raise ValueError(
            f"{source_path}: Unsupported schema_version '{schema_version}' "
            f"(expected '1.0')"
        )
    
    entries = manifest_data.get("entries")
    if not isinstance(entries, list):
        raise ValueError(
            f"{source_path}: 'entries' must be a list, got {type(entries).__name__}"
        )
    
    valid_voices = {"alloy", "echo", "onyx"}
    valid_categories = {"taunt", "pain", "death", "pickup", "weapon", "level_start", "alarm", "ambient"}
    valid_statuses = {"generated", "failed", "fallback"}
    
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{source_path}: entries[{i}] must be a dict, got {type(entry).__name__}")
        
        voice = entry.get("voice")
        if voice not in valid_voices:
            raise ValueError(
                f"{source_path}: entries[{i}] voice '{voice}' not in {valid_voices}"
            )
        
        category = entry.get("category")
        if category not in valid_categories:
            raise ValueError(
                f"{source_path}: entries[{i}] category '{category}' not in {valid_categories}"
            )
        
        status = entry.get("status")
        if status not in valid_statuses:
            raise ValueError(
                f"{source_path}: entries[{i}] status '{status}' not in {valid_statuses}"
            )


def load_manifest(manifest_path):
    """Load and verify a manifest file with SHA256 checksum validation.
    
    # manifest-checksum-verify-on-load: Verify at load time
    Performs SHA256 verification of both manifest integrity and per-file audio checksums.
    # sec-r15-manifest-loader-adoption: migrated to verifier
    
    Args:
        manifest_path: Path to manifest JSON file
    
    Returns:
        Validated manifest dict
    
    Raises:
        ValueError: If validation fails
        IOError: If file cannot be read
        RuntimeError: If checksum verification fails (sentinel: manifest-checksum-verify-on-load)
    """
    if not os.path.exists(manifest_path):
        raise IOError(f"Manifest file not found: {manifest_path}")
    
    # sec-r15-manifest-loader-adoption: migrated to verifier
    base_dir = os.path.dirname(manifest_path)
    data = load_and_verify_audio_manifest(manifest_path, base_dir)
    
    # Validate schema separately (not part of checksum verification)
    validate_manifest(data, manifest_path)
    
    return data


def generate_silence_wav(duration_sec, sample_rate=22050, bits=16):
    """Generate a silent WAV file as a placeholder."""
    num_samples = int(sample_rate * duration_sec)
    data_size = num_samples * (bits // 8)
    header = struct.pack("<4sI4s", b"RIFF", 36 + data_size, b"WAVE")
    header += struct.pack(
        "<4sIHHIIHH",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * bits // 8,
        bits // 8,
        bits,
    )
    header += struct.pack("<4sI", b"data", data_size)
    return header + b"\x00" * data_size


def generate_audio(prompt, voice, endpoint, api_key, model):
    """Call GPT Audio 1.5 to generate a WAV file (synchronous, for compatibility)."""
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{model}"
        f"/chat/completions?api-version=2025-01-01-preview"
    )

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "modalities": ["text", "audio"],
        "audio": {"voice": voice, "format": "wav"},
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            print(f"    [!] API error {resp.status_code}: {resp.text[:200]}")
            return None

        result = resp.json()
        audio_b64 = result["choices"][0]["message"]["audio"]["data"]
        return base64.b64decode(audio_b64)
    except Exception as e:
        print(f"    [!] Failed: {e}")
        return None


async def generate_audio_async(session, prompt, voice, endpoint, api_key, model):
    """Call GPT Audio 1.5 to generate a WAV file (async, for concurrent requests).
    
    Implements exponential backoff with jitter for retry logic.
    """
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{model}"
        f"/chat/completions?api-version=2025-01-01-preview"
    )

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "modalities": ["text", "audio"],
        "audio": {"voice": voice, "format": "wav"},
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
    }

    backoff = 1.0
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    error_msg = f"API error {resp.status}: {text[:200]}"
                    if attempt < MAX_RETRIES:
                        jitter = random.uniform(0, 0.5 * backoff)
                        sleep_time = backoff + jitter
                        logger.info(f"Retry attempt {attempt + 1}/{MAX_RETRIES}: {error_msg}. Sleeping {sleep_time:.2f}s")
                        await asyncio.sleep(sleep_time)
                        backoff = min(backoff * 2, MAX_BACKOFF)
                        continue
                    return None, error_msg

                result = await resp.json()
                audio_b64 = result["choices"][0]["message"]["audio"]["data"]
                return base64.b64decode(audio_b64), None
        except Exception as e:
            error_msg = f"Failed: {e}"
            if attempt < MAX_RETRIES:
                jitter = random.uniform(0, 0.5 * backoff)
                sleep_time = backoff + jitter
                logger.info(f"Retry attempt {attempt + 1}/{MAX_RETRIES}: {error_msg}. Sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue
            return None, error_msg

    return None, "Max retries exceeded"


def _add_checksums_to_manifest(manifest_dict, output_dir):  # asset-r13-manifest-checksums: SHA256 integrity
    """Add per-file checksums to manifest entries and compute manifest checksum.
    
    Args:
        manifest_dict: Dict with schema_version and entries keys
        output_dir: Directory where WAV files are stored
    
    Returns:
        Updated manifest dict with checksums
    """
    # Add per-file checksums for each entry
    for entry in manifest_dict.get("entries", []):
        wav_filename = entry.get("wav")
        if wav_filename:
            wav_path = os.path.join(output_dir, wav_filename)
            if os.path.exists(wav_path):
                entry["checksum"] = _sha256_of_file(wav_path)
    
    # Compute and add top-level manifest checksum
    manifest_dict["manifest_checksum"] = _sha256_of_manifest(manifest_dict)
    
    return manifest_dict


def _write_freshness_sidecar(manifest_dict, output_dir):
    """Write a freshness sidecar alongside the deterministic manifest.
    
    The manifest itself contains hardcoded 1970-01-01T00:00:00Z timestamps for
    determinism. This sidecar file captures actual generation time without
    breaking byte-for-byte manifest reproducibility.
    
    # audio-r5-manifest-freshness-tracking: sidecar freshness tracking
    
    The sidecar contains:
    - generated_at: ISO8601 timestamp of actual generation
    - manifest_checksum: manifest's SHA256 for audit trail correlation
    
    Args:
        manifest_dict: Dict with manifest_checksum field
        output_dir: Directory where sidecar will be written
    """
    freshness_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_checksum": manifest_dict.get("manifest_checksum", ""),
    }
    
    sidecar_path = os.path.join(output_dir, "audio_manifest.freshness.json")
    try:
        _atomic_write_json(sidecar_path, freshness_data, indent=2, sort_keys=True)
    except OSError as exc:
        print(f"[WARN] Failed to write freshness sidecar at {sidecar_path}: {exc}",
              file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Generate audio assets for Duke3D")
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip API calls (generate silence placeholders)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max concurrent API requests for async mode (default: 4, Azure limit ~8)",
    )
    parser.add_argument(
        "--acquire-timeout-sec",
        type=float,
        default=30.0,
        help="Timeout in seconds for semaphore acquire in async mode (default: 30.0)",
    )
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    endpoint = env.get("AUDIO_ENDPOINT", "")
    api_key = env.get("AUDIO_API_KEY", "")
    model = env.get("AUDIO_MODEL", "gpt-audio-1.5")
    use_ai = not args.no_ai and endpoint and api_key

    # Validate VOICE_LINES and SOUND_MANIFEST are in sync before any generation
    try:
        validate_voice_manifest_sync(VOICE_LINES, SOUND_MANIFEST)
    except ValueError as e:
        print(f"[ERROR] Voice manifest sync validation failed:\n{e}", file=sys.stderr)
        return 1
    
    # Validate SOUND_MANIFEST entries using Pydantic schema (fix-assets-sound-manifest-pydantic-schema)
    try:
        validate_sound_manifest_entries(SOUND_MANIFEST)
    except ValueError as e:
        print(f"[ERROR] Sound manifest Pydantic validation failed:\n{e}", file=sys.stderr)
        return 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Generating Audio Assets ===")
    if use_ai:
        print(f"  Using: {model} at {_redact_endpoint(endpoint)}")
        print(f"  Max concurrent requests: {args.concurrency}")
    else:
        print(f"  Mode: placeholder silence (set AUDIO_* in .env for AI generation)")
        print(f"  Workers: {args.workers}")

    start_time = time.time()
    generated = []

    if use_ai:
        # API path: use async with semaphore for rate limiting
        generated = _generate_audio_parallel_api(
            args.concurrency, endpoint, api_key, model, args.acquire_timeout_sec, args.no_ai
        )
    else:
        # Local WAV synthesis path: use ThreadPoolExecutor
        generated = _generate_audio_parallel_local(args.workers, args.no_ai)

    elapsed = time.time() - start_time

    # Write manifest (sorted for determinism)
    # Wrap SOUND_MANIFEST with schema_version for validation
    manifest_to_write = {
        "schema_version": "1.0",
        "entries": SOUND_MANIFEST
    }
    
    # Add checksums to manifest entries and manifest itself
    manifest_to_write = _add_checksums_to_manifest(manifest_to_write, OUTPUT_DIR)
    
    manifest_path = os.path.join(OUTPUT_DIR, "MANIFEST.json")
    try:
        # Write manifest atomically with fsync for durability
        # # sec-r18-atomic-write-hardening: manifest write with fsync
        _atomic_write_json(manifest_path, manifest_to_write, indent=2, sort_keys=True)
        print(f"\n=== Manifest written to {manifest_path} ===")
    except OSError as exc:
        print(f"\n[ERROR] Failed to write manifest at {manifest_path}: {exc}",
              file=sys.stderr)
        return 1
    
    # Write freshness sidecar (tracks actual generation time without breaking determinism)
    # # audio-r5-manifest-freshness-tracking: sidecar freshness tracking
    _write_freshness_sidecar(manifest_to_write, OUTPUT_DIR)

    print(f"=== Done! Generated {len(generated)} audio files in {elapsed:.2f}s ===")
    print(f"  Output: {OUTPUT_DIR}/")
    return 0


def _generate_audio_parallel_local(workers, use_deterministic):
    """Generate silence WAVs using ThreadPoolExecutor (GIL-releasing struct packing)."""
    generated = []
    
    # Determine timestamp based on determinism flag
    if use_deterministic:
        timestamp = "1970-01-01T00:00:00Z"
    else:
        timestamp = datetime.now(timezone.utc).isoformat()

    def process_voice_line(item):
        idx, (filename, prompt, voice) = item
        wav_data = generate_silence_wav(0.5)
        return idx, filename, wav_data

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {}
        for idx, (filename, prompt, voice) in enumerate(VOICE_LINES):
            print(f"  {filename}: {prompt[:60]}...")
            future = executor.submit(process_voice_line, (idx, (filename, prompt, voice)))
            future_to_idx[future] = idx

        # Collect results without mutating SOUND_MANIFEST (avoid race condition)
        results = [None] * len(VOICE_LINES)
        result_status = [None] * len(VOICE_LINES)  # Track status: "success", "failed", or None
        result_error = [None] * len(VOICE_LINES)  # Track error messages
        for future in concurrent.futures.as_completed(future_to_idx.keys()):
            idx = future_to_idx[future]
            try:
                result_idx, filename, wav_data = future.result()
                out_path = os.path.join(OUTPUT_DIR, filename)
                _atomic_write_bytes(out_path, wav_data)
                results[idx] = filename
                result_status[idx] = "success"
                print(f"    [Silence placeholder] OK")
            except Exception as e:
                # Collect error info without mutating manifest
                error_msg = f"{type(e).__name__}: {str(e)}"
                result_status[idx] = "failed"
                result_error[idx] = error_msg
                print(f"    [ERROR] {VOICE_LINES[idx][0]}: {error_msg}")

    # audio-r12-parallel-manifest-race: sequentialize manifest writes after pool exit
    # audio-r8-manifest-generation-method: track generation method for drift detection
    for idx in range(len(VOICE_LINES)):
        if result_status[idx] == "success":
            SOUND_MANIFEST[idx]["status"] = "generated"
            SOUND_MANIFEST[idx]["generation_method"] = "silence"
            SOUND_MANIFEST[idx]["generated_at"] = timestamp
        elif result_status[idx] == "failed":
            SOUND_MANIFEST[idx]["status"] = "failed"
            SOUND_MANIFEST[idx]["generation_method"] = "silence"
            SOUND_MANIFEST[idx]["error"] = result_error[idx]
            SOUND_MANIFEST[idx]["generated_at"] = timestamp

    generated = [f for f in results if f is not None]

    return generated


def _generate_audio_parallel_api(concurrency, endpoint, api_key, model, acquire_timeout_sec=30.0, use_deterministic=False):
    """Generate audio via API using asyncio + aiohttp with semaphore."""
    return asyncio.run(
        _generate_audio_async_main(concurrency, endpoint, api_key, model, acquire_timeout_sec, use_deterministic)
    )


async def _generate_audio_async_main(concurrency, endpoint, api_key, model, acquire_timeout_sec=30.0, use_deterministic=False):
    """Async generator for API calls with rate limiting and timeout."""
    # Determine timestamp based on determinism flag
    if use_deterministic:
        timestamp = "1970-01-01T00:00:00Z"
    else:
        timestamp = datetime.now(timezone.utc).isoformat()
    
    semaphore = asyncio.Semaphore(concurrency)
    generated = [None] * len(VOICE_LINES)

    async def bounded_generate(session, idx, filename, prompt, voice):
        try:
            async with asyncio.timeout(acquire_timeout_sec + 60):
                async with semaphore:
                    wav_data, error = await generate_audio_async(
                        session, prompt, voice, endpoint, api_key, model
                    )
                    return idx, filename, wav_data, error
        except asyncio.TimeoutError:
            return idx, filename, None, f"Semaphore + request timeout (>{acquire_timeout_sec}s)"

    connector = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for idx, (filename, prompt, voice) in enumerate(VOICE_LINES):
            print(f"  {filename}: {prompt[:60]}...")
            task = bounded_generate(session, idx, filename, prompt, voice)
            tasks.append(task)

        # Collect results without mutating SOUND_MANIFEST during async tasks
        results = await asyncio.gather(*tasks)
        
        # Prepare manifest updates locally first (audio-r8-manifest-generation-method)
        manifest_updates = [None] * len(VOICE_LINES)
        for idx, filename, wav_data, error in results:
            is_fallback = False
            if wav_data is None:
                wav_data = generate_silence_wav(0.5)
                is_fallback = True
                status = "fallback"
                generation_method = "fallback"
                if error:
                    print(f"    [!] {error}")
                    status = "failed"
                    generation_method = "fallback"
                    manifest_updates[idx] = ("failed", error, generation_method)
                else:
                    print(f"    [Fallback: silence] OK")
                    manifest_updates[idx] = ("fallback", None, generation_method)
            else:
                status = "generated"
                generation_method = "ai"
                print(f"    [AI] OK ({len(wav_data)} bytes)")
                manifest_updates[idx] = ("generated", None, generation_method)

            out_path = os.path.join(OUTPUT_DIR, filename)
            _atomic_write_bytes(out_path, wav_data)
            generated[idx] = filename

        # audio-r12-parallel-manifest-race: sequentialize manifest writes after async tasks complete
        for idx, update in enumerate(manifest_updates):
            if update is not None:
                status, error, generation_method = update
                SOUND_MANIFEST[idx]["status"] = status
                SOUND_MANIFEST[idx]["generation_method"] = generation_method
                SOUND_MANIFEST[idx]["generated_at"] = timestamp
                if error:
                    SOUND_MANIFEST[idx]["error"] = error

    return [f for f in generated if f is not None]


if __name__ == "__main__":
    sys.exit(main())

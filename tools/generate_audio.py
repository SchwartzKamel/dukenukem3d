#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate audio assets for Duke3D: Neon Noir using GPT Audio 1.5."""

import argparse
import asyncio
import base64
import concurrent.futures
import json
import os
import struct
import sys
import time
from datetime import datetime, timezone

import aiohttp
import requests

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Write bytes to a file atomically using tmp+rename pattern.
    
    This ensures that if the process is killed or hits an error mid-write,
    the original file (if it exists) is left untouched rather than corrupted.
    Uses POSIX atomic rename within the same filesystem.
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
    except OSError:
        # Clean up temp file on error to avoid leaving stray .tmp files
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


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
SOUND_MANIFEST = [{'wav': 'TAUNT01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Welcome to the machine, punk.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'TAUNT02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Lights out, chrome-head.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'TAUNT03.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Another day, another megacorp to burn.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'TAUNT04.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Is that all you got?'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'TAUNT05.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'taunt', 'prompt_summary': "gruff merc one-liner: 'Time to take out the trash.'", 'notes': 'AI-generated taunt. Engine has no taunt-trigger hook; runtime will inject these on player taunt events.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'PAIN01.WAV', 'engine_sound_id': 'DUKE_GRUNT', 'engine_sound_id_int': 38, 'voice': 'onyx', 'category': 'pain', 'prompt_summary': 'short grunt of pain', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'PAIN02.WAV', 'engine_sound_id': 'DUKE_LONGTERM_PAIN', 'engine_sound_id_int': 211, 'voice': 'onyx', 'category': 'pain', 'prompt_summary': 'sharp grunt from shot', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'PAIN03.WAV', 'engine_sound_id': 'DUKE_LONGTERM_PAIN2', 'engine_sound_id_int': 274, 'voice': 'onyx', 'category': 'pain', 'prompt_summary': 'heavy damage groan', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'DEATH01.WAV', 'engine_sound_id': 'DUKE_SCREAM', 'engine_sound_id_int': 245, 'voice': 'onyx', 'category': 'death', 'prompt_summary': 'death scream', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'DEATH02.WAV', 'engine_sound_id': 'DUKE_DEAD', 'engine_sound_id_int': 41, 'voice': 'alloy', 'category': 'death', 'prompt_summary': "dying gasp: 'System... failure...'", 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'PICKUP01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Stim acquired.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'PICKUP02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Ammo loaded.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'PICKUP03.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Shield online.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'PICKUP04.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'pickup', 'prompt_summary': "HUD notification: 'Access granted.'", 'notes': 'AI-generated HUD notification. Engine has no direct equivalent; runtime will inject these dynamically.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'WEAPON01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'weapon', 'prompt_summary': "weapon announcement: 'Pulse pistol ready.'", 'notes': 'AI-generated weapon system notification. Engine has weapon pickup sounds (DUKE_GETWEAPON*) but not weapon-ready announcements; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'WEAPON02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'weapon', 'prompt_summary': "weapon announcement: 'Scatter cannon armed.'", 'notes': 'AI-generated weapon system notification. Engine has weapon pickup sounds (DUKE_GETWEAPON*) but not weapon-ready announcements; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'WEAPON03.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'echo', 'category': 'weapon', 'prompt_summary': "weapon announcement: 'Plasma launcher online.'", 'notes': 'AI-generated weapon system notification. Engine has weapon pickup sounds (DUKE_GETWEAPON*) but not weapon-ready announcements; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'LEVEL01.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'level_start', 'prompt_summary': "level start: 'Let's get to work.'", 'notes': 'AI-generated level start announcement. Engine has no level-start sound hook in original code; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'LEVEL02.WAV', 'engine_sound_id': None, 'engine_sound_id_int': None, 'voice': 'alloy', 'category': 'level_start', 'prompt_summary': "level start: 'Another sector, another pile of scrap.'", 'notes': 'AI-generated level start announcement. Engine has no level-start sound hook in original code; runtime will inject these.', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'ALARM01.WAV', 'engine_sound_id': 'ALARM', 'engine_sound_id_int': 357, 'voice': 'echo', 'category': 'alarm', 'prompt_summary': 'robotic alarm: intruder detected', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}, {'wav': 'COMP01.WAV', 'engine_sound_id': 'COMPUTER_AMBIENCE', 'engine_sound_id_int': 86, 'voice': 'echo', 'category': 'ambient', 'prompt_summary': 'computer voice announcement', 'status': 'generated', 'generated_at': '1970-01-01T00:00:00Z'}]


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
    """Call GPT Audio 1.5 to generate a WAV file (async, for concurrent requests)."""
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
        async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
            if resp.status != 200:
                text = await resp.text()
                return None, f"API error {resp.status}: {text[:200]}"

            result = await resp.json()
            audio_b64 = result["choices"][0]["message"]["audio"]["data"]
            return base64.b64decode(audio_b64), None
    except Exception as e:
        return None, f"Failed: {e}"


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

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Generating Audio Assets ===")
    if use_ai:
        print(f"  Using: {model} at {endpoint[:50]}...")
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
    manifest_path = os.path.join(OUTPUT_DIR, "MANIFEST.json")
    try:
        # Write to a temp file first then rename so a partial write never
        # corrupts an existing manifest (audit-audio-manifest-write-error).
        tmp_path = manifest_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(SOUND_MANIFEST, f, indent=2, sort_keys=True)
        os.replace(tmp_path, manifest_path)
        print(f"\n=== Manifest written to {manifest_path} ===")
    except OSError as exc:
        print(f"\n[ERROR] Failed to write manifest at {manifest_path}: {exc}",
              file=sys.stderr)
        return 1

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

        # Collect results in order
        results = [None] * len(VOICE_LINES)
        for future in concurrent.futures.as_completed(future_to_idx.keys()):
            idx = future_to_idx[future]
            try:
                result_idx, filename, wav_data = future.result()
                out_path = os.path.join(OUTPUT_DIR, filename)
                _atomic_write_bytes(out_path, wav_data)
                results[idx] = filename
                # Update manifest entry with successful generation
                SOUND_MANIFEST[idx]["status"] = "generated"
                SOUND_MANIFEST[idx]["generated_at"] = timestamp
                print(f"    [Silence placeholder] OK")
            except Exception as e:
                # Handle worker failure - mark manifest entry as failed
                error_msg = f"{type(e).__name__}: {str(e)}"
                SOUND_MANIFEST[idx]["status"] = "failed"
                SOUND_MANIFEST[idx]["error"] = error_msg
                SOUND_MANIFEST[idx]["generated_at"] = timestamp
                print(f"    [ERROR] {SOUND_MANIFEST[idx]['wav']}: {error_msg}")

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

        # Collect results
        results = await asyncio.gather(*tasks)
        for idx, filename, wav_data, error in results:
            is_fallback = False
            if wav_data is None:
                wav_data = generate_silence_wav(0.5)
                is_fallback = True
                status = "fallback"
                if error:
                    print(f"    [!] {error}")
                    status = "failed"
                    SOUND_MANIFEST[idx]["error"] = error
                print(f"    [Fallback: silence] OK")
            else:
                status = "generated"
                print(f"    [AI] OK ({len(wav_data)} bytes)")

            # Update manifest entry with status and timestamp
            SOUND_MANIFEST[idx]["status"] = status
            SOUND_MANIFEST[idx]["generated_at"] = timestamp

            out_path = os.path.join(OUTPUT_DIR, filename)
            _atomic_write_bytes(out_path, wav_data)
            generated[idx] = filename

    return [f for f in generated if f is not None]


if __name__ == "__main__":
    sys.exit(main())

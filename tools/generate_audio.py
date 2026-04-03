#!/usr/bin/env python3
"""Generate audio assets for Duke3D: Neon Noir using GPT Audio 1.5."""

import argparse
import base64
import json
import os
import struct
import sys
import time

import requests

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "generated_assets", "sounds")
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

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
    """Call GPT Audio 1.5 to generate a WAV file."""
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


def main():
    parser = argparse.ArgumentParser(description="Generate audio assets for Duke3D")
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip API calls (generate silence placeholders)",
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
    else:
        print("  Mode: placeholder silence (set AUDIO_* in .env for AI generation)")

    generated = []
    for filename, prompt, voice in VOICE_LINES:
        print(f"  {filename}: {prompt[:60]}...")

        wav_data = None
        if use_ai:
            wav_data = generate_audio(prompt, voice, endpoint, api_key, model)
            if wav_data:
                print(f"    [AI] OK ({len(wav_data)} bytes)")
            time.sleep(0.5)

        if wav_data is None:
            wav_data = generate_silence_wav(0.5)
            if not use_ai:
                print(f"    [Silence placeholder] OK")
            else:
                print(f"    [Fallback: silence] OK")

        out_path = os.path.join(OUTPUT_DIR, filename)
        with open(out_path, "wb") as f:
            f.write(wav_data)
        generated.append(filename)

    print(f"\n=== Done! Generated {len(generated)} audio files ===")
    print(f"  Output: {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

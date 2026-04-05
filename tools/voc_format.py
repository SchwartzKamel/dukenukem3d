#!/usr/bin/env python3
"""Generate valid Creative Voice Files (.VOC) for Duke Nukem 3D.

Format reference: Creative Voice File specification.
- 26-byte header: magic + data offset + version + checksum
- Data blocks: type 1 = sound data (8-bit unsigned PCM)
- Terminator: type 0
"""

import hashlib
import math
import struct

SAMPLE_RATE = 11025  # Standard Duke3D VOC rate
HEADER_MAGIC = b"Creative Voice File\x1a"


def _name_hash(name):
    return int(hashlib.md5(name.encode()).hexdigest(), 16)


def _generate_tone_samples(num_samples, freq, sample_rate=SAMPLE_RATE):
    """Generate 8-bit unsigned PCM samples for a sine tone."""
    samples = bytearray(num_samples)
    for i in range(num_samples):
        t = i / sample_rate
        val = math.sin(2 * math.pi * freq * t)
        samples[i] = int((val * 0.4 + 0.5) * 255)
    return bytes(samples)


def _generate_noise_samples(num_samples, seed=0):
    """Generate 8-bit unsigned PCM white noise samples."""
    rng = seed | 1
    samples = bytearray(num_samples)
    for i in range(num_samples):
        rng = (rng * 1103515245 + 12345) & 0xFFFFFFFF
        samples[i] = (rng >> 16) & 0xFF
    return bytes(samples)


def _generate_click_samples(num_samples, seed=0):
    """Generate a short click/pop sound."""
    samples = bytearray(num_samples)
    attack = min(20, num_samples // 4)
    for i in range(attack):
        samples[i] = 128 + int(127 * (i / attack))
    for i in range(attack, min(attack * 2, num_samples)):
        frac = (i - attack) / max(1, attack)
        samples[i] = 255 - int(127 * frac)
    for i in range(attack * 2, num_samples):
        samples[i] = 128
    return bytes(samples)


def create_voc_stub(name, duration_ms=100):
    """Generate a valid Creative Voice File with a short audio burst.

    Args:
        name: Filename (used to seed deterministic audio content).
        duration_ms: Duration in milliseconds.

    Returns:
        bytes: Complete VOC file data.
    """
    h = _name_hash(name)
    num_samples = max(1, int(SAMPLE_RATE * duration_ms / 1000))

    # Choose sound type based on hash
    sound_type = h % 3
    if sound_type == 0:
        freq = 200 + (h >> 8) % 800  # 200-999 Hz tone
        audio_data = _generate_tone_samples(num_samples, freq)
    elif sound_type == 1:
        audio_data = _generate_noise_samples(num_samples, seed=h)
    else:
        audio_data = _generate_click_samples(num_samples, seed=h)

    return create_voc_from_samples(audio_data, SAMPLE_RATE)


def create_voc_from_samples(audio_data, sample_rate=SAMPLE_RATE):
    """Build a VOC file from raw 8-bit unsigned PCM samples.

    Args:
        audio_data: Raw 8-bit unsigned PCM bytes.
        sample_rate: Sample rate in Hz.

    Returns:
        bytes: Complete VOC file data.
    """
    # Header
    header_size = 26
    version = 0x010A  # Version 1.10
    checksum = 0x1234 + (~version & 0xFFFF)

    header = HEADER_MAGIC
    header += struct.pack("<H", header_size)
    header += struct.pack("<H", version)
    header += struct.pack("<H", checksum & 0xFFFF)

    # Sound data block (type 1)
    # Block format: type(1) + length(3) + sr_byte(1) + compression(1) + data
    sr_byte = 256 - (1000000 // sample_rate)
    block_payload = struct.pack("BB", sr_byte & 0xFF, 0) + audio_data
    block_len = len(block_payload)

    block = struct.pack("B", 1)  # type = sound data
    block += struct.pack("<I", block_len)[:3]  # 3-byte little-endian length
    block += block_payload

    # Terminator block (type 0)
    terminator = struct.pack("B", 0)

    return header + block + terminator

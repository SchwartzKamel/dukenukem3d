#!/usr/bin/env python3
"""Generate valid MIDI format 0 files for Duke Nukem 3D.

Each generated file contains a short melody or drone so it plays audibly
without errors in any standard MIDI player or game engine.
"""

import hashlib
import struct

# MIDI note constants
MIDDLE_C = 60
CHANNEL = 0

# Scale patterns (semitone offsets from root)
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]
BLUES_SCALE = [0, 3, 5, 6, 7, 10]
DORIAN_SCALE = [0, 2, 3, 5, 7, 9, 10]
PHRYGIAN_SCALE = [0, 1, 3, 5, 7, 8, 10]


def _variable_length(value):
    """Encode an integer as MIDI variable-length quantity."""
    if value < 0:
        raise ValueError("Negative values not allowed")
    result = []
    result.append(value & 0x7F)
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.reverse()
    return bytes(result)


def _name_hash(name):
    """Deterministic hash of a filename to seed melody generation."""
    return int(hashlib.md5(name.encode()).hexdigest(), 16)


def _pick_scale(h):
    """Choose a scale based on hash bits."""
    scales = [MINOR_SCALE, BLUES_SCALE, DORIAN_SCALE, PHRYGIAN_SCALE]
    return scales[h % len(scales)]


def _build_track(events):
    """Wrap a list of raw event bytes into an MTrk chunk."""
    body = b"".join(events)
    # End-of-track meta event
    body += b"\x00\xFF\x2F\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _note_on(delta, note, velocity=80, channel=CHANNEL):
    return _variable_length(delta) + bytes([0x90 | channel, note & 0x7F, velocity & 0x7F])


def _note_off(delta, note, velocity=0, channel=CHANNEL):
    return _variable_length(delta) + bytes([0x80 | channel, note & 0x7F, velocity & 0x7F])


def _program_change(delta, program, channel=CHANNEL):
    return _variable_length(delta) + bytes([0xC0 | channel, program & 0x7F])


def _tempo_event(bpm):
    """Set tempo meta event (delta=0)."""
    us_per_beat = int(60_000_000 / bpm)
    return b"\x00\xFF\x51\x03" + struct.pack(">I", us_per_beat)[1:]


def _track_name_event(name):
    """Track name meta event (delta=0)."""
    name_bytes = name.encode("ascii", errors="replace")[:64]
    return b"\x00\xFF\x03" + _variable_length(len(name_bytes)) + name_bytes


def create_simple_midi(name, duration_seconds=5):
    """Generate a valid MIDI format 0 file with a short melody.

    Args:
        name: Filename (used to seed deterministic melody).
        duration_seconds: Approximate duration in seconds.

    Returns:
        bytes: Complete MIDI file data.
    """
    h = _name_hash(name)
    ticks_per_quarter = 480
    bpm = 90 + (h % 60)  # 90-149 BPM range
    scale = _pick_scale(h >> 8)
    root = 48 + (h >> 16) % 12  # Root note C3-B3

    # Pick a GM instrument based on name hash
    instruments = [0, 4, 16, 24, 25, 33, 38, 48, 52, 56, 80, 88, 89, 95]
    instrument = instruments[(h >> 20) % len(instruments)]

    # Calculate ticks per beat for the target duration
    beats_total = int(bpm * duration_seconds / 60)
    ticks_per_beat = ticks_per_quarter

    events = []
    events.append(_track_name_event(name))
    events.append(_tempo_event(bpm))
    events.append(_program_change(0, instrument))

    # Generate a simple melodic sequence
    rng = h
    tick = 0
    note_durations = [ticks_per_beat // 2, ticks_per_beat, ticks_per_beat * 2]

    for i in range(beats_total):
        rng = (rng * 1103515245 + 12345) & 0xFFFFFFFF
        scale_idx = (rng >> 8) % len(scale)
        octave_offset = ((rng >> 16) % 3 - 1) * 12  # -1, 0, or +1 octave
        note = root + scale[scale_idx] + octave_offset
        note = max(36, min(96, note))  # Clamp to reasonable range

        dur_idx = (rng >> 24) % len(note_durations)
        dur = note_durations[dur_idx]
        velocity = 60 + (rng >> 4) % 40  # 60-99

        events.append(_note_on(ticks_per_beat if i > 0 else 0, note, velocity))
        events.append(_note_off(dur, note))

    track = _build_track(events)

    # MIDI header: format 0, 1 track
    header = b"MThd" + struct.pack(">IHhH", 6, 0, 1, ticks_per_quarter)
    return header + track

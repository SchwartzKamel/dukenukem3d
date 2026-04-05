"""Tests for MIDI format generator."""
import struct

from midi_format import create_simple_midi


def test_midi_magic():
    """MIDI file starts with MThd header."""
    data = create_simple_midi("test.mid")
    assert data[:4] == b"MThd"


def test_midi_format_zero():
    """Generated MIDI is format 0 with 1 track."""
    data = create_simple_midi("test.mid")
    # MThd(4) + length(4) + format(2) + ntracks(2) + division(2)
    length, fmt, ntracks = struct.unpack_from(">IHH", data, 4)
    assert length == 6
    assert fmt == 0
    assert ntracks == 1


def test_midi_has_track():
    """MIDI file contains an MTrk chunk."""
    data = create_simple_midi("test.mid")
    assert b"MTrk" in data


def test_midi_track_length():
    """MTrk chunk length field matches actual track data size."""
    data = create_simple_midi("test.mid")
    trk_offset = data.index(b"MTrk")
    trk_len = struct.unpack_from(">I", data, trk_offset + 4)[0]
    assert trk_offset + 8 + trk_len == len(data)


def test_midi_end_of_track():
    """Track ends with End-of-Track meta event (FF 2F 00)."""
    data = create_simple_midi("test.mid")
    assert data[-3:] == b"\xFF\x2F\x00"


def test_midi_deterministic():
    """Same name produces identical output."""
    a = create_simple_midi("GRABBAG.MID")
    b = create_simple_midi("GRABBAG.MID")
    assert a == b


def test_midi_different_names():
    """Different names produce different output."""
    a = create_simple_midi("GRABBAG.MID")
    b = create_simple_midi("stalker.mid")
    assert a != b


def test_midi_minimum_size():
    """MIDI file is at least header + minimal track."""
    data = create_simple_midi("test.mid", duration_seconds=1)
    # MThd(14) + MTrk(8) + at least some events
    assert len(data) > 30


def test_midi_duration_scales():
    """Longer duration produces larger file."""
    short = create_simple_midi("test.mid", duration_seconds=2)
    long = create_simple_midi("test.mid", duration_seconds=10)
    assert len(long) > len(short)


def test_midi_contains_note_events():
    """MIDI file contains note-on events (0x90)."""
    data = create_simple_midi("test.mid", duration_seconds=3)
    # Look for note-on status byte in track data
    trk_offset = data.index(b"MTrk") + 8
    track_data = data[trk_offset:]
    has_note_on = any(b == 0x90 for b in track_data)
    assert has_note_on


def test_midi_all_duke_music_files():
    """Generate MIDI for all Duke3D music filenames without error."""
    filenames = [
        "GRABBAG.MID", "BRIEFING.MID",
        "stalker.mid", "dethtoll.mid", "streets.mid", "watrwld1.mid",
        "snake1.mid", "thecall.mid", "ahgeez.mid",
        "futurmil.mid", "storm.mid", "gutwrnch.mid", "robocrep.mid",
        "stalag.mid", "pizzed.mid", "alienz.mid", "xplasma.mid",
        "alfredh.mid", "gloomy.mid", "intents.mid",
        "inhiding.mid", "FATCMDR.mid", "NAMES.MID", "subway.mid",
        "invader.mid", "gotham.mid", "233c.mid", "lordofla.mid",
        "urban.mid", "spook.mid", "whomp.mid",
        "missimp.mid", "prepd.mid", "bakedgds.mid", "cf.mid",
        "lemchill.mid", "pob.mid", "warehaus.mid", "layers.mid",
        "floghorn.mid", "depart.mid", "restrict.mid",
    ]
    for fn in filenames:
        data = create_simple_midi(fn)
        assert data[:4] == b"MThd", f"Failed for {fn}"
        assert len(data) > 30, f"Too small for {fn}"

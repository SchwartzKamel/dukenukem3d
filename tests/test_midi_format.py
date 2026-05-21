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


class TestMidiFileIO:
    """Test MIDI file I/O round-trip operations."""

    def test_midi_file_roundtrip_via_tmp_path(self, tmp_path):
        """MIDI file written and read back should match original."""
        midi_data = create_simple_midi("test.mid", duration_seconds=2)
        
        # Write to temp file
        test_file = tmp_path / "test.mid"
        test_file.write_bytes(midi_data)
        
        # Read back
        read_data = test_file.read_bytes()
        assert read_data == midi_data
        assert len(read_data) == len(midi_data)

    def test_midi_varying_duration_roundtrip(self, tmp_path):
        """Different durations should produce different files that preserve structure."""
        for duration in [1, 3, 5]:
            midi_data = create_simple_midi(f"test_{duration}.mid", duration_seconds=duration)
            
            test_file = tmp_path / f"test_{duration}.mid"
            test_file.write_bytes(midi_data)
            read_data = test_file.read_bytes()
            
            # Verify header structure
            assert read_data[:4] == b"MThd"
            assert read_data[-3:] == b"\xFF\x2F\x00"
            assert len(read_data) == len(midi_data)

    def test_midi_deterministic_generation(self, tmp_path):
        """Same name should generate identical bytes every time."""
        data1 = create_simple_midi("GRABBAG.MID", duration_seconds=2)
        data2 = create_simple_midi("GRABBAG.MID", duration_seconds=2)
        
        test_file1 = tmp_path / "grab1.mid"
        test_file2 = tmp_path / "grab2.mid"
        test_file1.write_bytes(data1)
        test_file2.write_bytes(data2)
        
        assert test_file1.read_bytes() == test_file2.read_bytes()

    def test_midi_multiple_files_different_sizes(self, tmp_path):
        """Different names and durations should produce different file sizes."""
        files = [
            ("test1.mid", 1),
            ("test2.mid", 3),
            ("different.mid", 2),
        ]
        sizes = []
        for name, duration in files:
            midi_data = create_simple_midi(name, duration_seconds=duration)
            test_file = tmp_path / name
            test_file.write_bytes(midi_data)
            sizes.append(len(test_file.read_bytes()))
        
        # At least some size variation should exist
        assert len(set(sizes)) > 1


class TestMidiValidFormat:
    """Test MIDI format validity and round-trip integrity."""

    def test_midi_header_complete(self):
        """MIDI header must have all required fields."""
        data = create_simple_midi("test.mid")
        assert data[:4] == b"MThd"
        assert len(data) >= 14  # MThd(4) + length(4) + format(2) + tracks(2) + division(2)

    def test_midi_track_marker_present(self):
        """Generated MIDI must contain MTrk marker."""
        data = create_simple_midi("test.mid", duration_seconds=2)
        assert b"MTrk" in data
        trk_pos = data.find(b"MTrk")
        assert trk_pos > 0

    def test_midi_valid_status_bytes(self):
        """MIDI note-on/off status bytes should be valid."""
        data = create_simple_midi("test.mid", duration_seconds=3)
        # Note-on is 0x90, note-off is 0x80
        track_start = data.find(b"MTrk") + 8
        # Scan for note-on (0x90 range)
        found_note_events = False
        for i in range(track_start, len(data) - 1):
            byte_val = data[i]
            if (byte_val & 0xF0) == 0x90 or (byte_val & 0xF0) == 0x80:
                found_note_events = True
                break
        assert found_note_events, "Should contain note-on/off events"

    def test_midi_no_invalid_durations(self):
        """Duration values should be reasonable."""
        sizes = []
        for duration in [0.5, 2, 5]:
            data = create_simple_midi("test.mid", duration_seconds=duration)
            assert data[:4] == b"MThd"
            assert len(data) > 30
            sizes.append(len(data))
        # Longer durations should produce larger or equal sized files
        assert sizes[1] >= sizes[0]
        assert sizes[2] >= sizes[1]


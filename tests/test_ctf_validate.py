"""Tests for tools/ctf_validate.py — the CTF map-contract validator.

Proves the validator (a) passes the real generated arena and (b) actually CATCHES
drift of the engine CTF contract (the CTF-1 bug class), so it is real backpressure
and not a rubber stamp.
"""
import os
import struct
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(PROJECT_ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import ctf_validate  # noqa: E402
from generate_ctf_map import assemble_map  # noqa: E402

# sector byte offset within the MAP: header(20) + numsectors(2); lotag is field 20
# of the 40-byte sector struct, at byte 34. (Mirrors map_format._pack_sector.)
_SECTORS_START = 22
_SECTOR_SZ = 40
_SECTOR_LOTAG_OFF = 34


def _patch_first_lotag(data, target_lotag, new_lotag):
    """Flip the first sector whose lotag == target to new_lotag (drift injection)."""
    parsed = ctf_validate.parse_map(data)
    idx = next(i for i, s in enumerate(parsed["sectors"])
               if s["lotag"] == target_lotag)
    ba = bytearray(data)
    struct.pack_into("<h", ba, _SECTORS_START + idx * _SECTOR_SZ + _SECTOR_LOTAG_OFF,
                     new_lotag)
    return bytes(ba)


def test_generated_arena_passes():
    """The real generated CTF arena satisfies the engine contract."""
    assert ctf_validate.validate_ctf_map(assemble_map()) == []


def test_missing_timer_sector_is_caught():
    """Dropping the timer-room lotag must be reported (CTF-1-class drift)."""
    broken = _patch_first_lotag(assemble_map(), ctf_validate.LOTAG_TIMER, 0)
    errors = ctf_validate.validate_ctf_map(broken)
    assert any("timer" in e for e in errors), errors


def test_ghost_centroid_drift_is_caught():
    """Re-tagging a different room as the ghost room (so the centroid is wrong)
    must be reported — exactly the CTF-1 desync."""
    # Turn the timer room into a second 'ghost' room: now there are two ghost
    # sectors (count != 1) AND, if the engine picked the wrong one, the centroid
    # would drift. Either way the validator must complain.
    broken = _patch_first_lotag(assemble_map(), ctf_validate.LOTAG_TIMER,
                                ctf_validate.LOTAG_GHOST)
    errors = ctf_validate.validate_ctf_map(broken)
    assert any("ghost" in e for e in errors), errors


def test_truncated_map_is_caught():
    """A structurally short MAP fails cleanly rather than crashing."""
    errors = ctf_validate.validate_ctf_map(assemble_map()[:50])
    assert errors and any("parse" in e.lower() or "truncat" in e.lower()
                          for e in errors), errors


def test_main_exit_codes(capsys):
    """main() returns 0 for the generator output."""
    assert ctf_validate.main([]) == 0
    out = capsys.readouterr().out
    assert "OK" in out


def test_negative_sector_count_is_caught():
    """A negative MAP count (signed-short underflow) must fail cleanly, not slip
    into an odd parse state (CTF-VALIDATE-2)."""
    ba = bytearray(assemble_map())
    struct.pack_into("<h", ba, _SECTORS_START - 2, -1)  # numsectors field at off 20
    errors = ctf_validate.validate_ctf_map(bytes(ba))
    assert errors and any("negative" in e.lower() or "parse" in e.lower()
                          for e in errors), errors


def _sprite_section_off(data):
    """Byte offset of sprite[0] in a MAP v7 buffer."""
    off = _SECTORS_START - 2  # numsectors field
    ns = struct.unpack_from("<h", data, off)[0]
    off += 2 + ns * 40
    nw = struct.unpack_from("<h", data, off)[0]
    off += 2 + nw * 32
    return off + 2  # skip numsprites field -> sprite[0]


def test_duplicate_boss_sprite_is_caught():
    """Two sprites sharing a boss hitag is drift the engine's single-actor boss
    logic can't handle — the validator must require exactly one (CTF-VALIDATE-2)."""
    ba = bytearray(assemble_map())
    # sprite hitag is at byte 40 within the 44-byte sprite struct; tag sprite[0]
    # (the player marker) with BOSS1's hitag so there are now two.
    struct.pack_into("<h", ba, _sprite_section_off(ba) + 0 * 44 + 40,
                     ctf_validate.HITAG_BOSS1)
    errors = ctf_validate.validate_ctf_map(bytes(ba))
    assert any("Meatbag" in e or "0x0CF1" in e or "found 2" in e for e in errors), errors


def test_boss_hitag_on_non_boss_picnum_is_caught():
    """A single sprite carries the boss hitag but a non-boss picnum — the engine's
    boss/flag logic targets the real actor, so the validator must reject it
    (CTF-VALIDATE-3)."""
    ba = bytearray(assemble_map())
    parsed = ctf_validate.parse_map(bytes(ba))
    idx = next(i for i, s in enumerate(parsed["sprites"])
               if s["hitag"] == ctf_validate.HITAG_BOSS1)
    # picnum is at byte 14 within the 44-byte sprite struct; blank it so the hitag
    # still matches but the picnum no longer equals BOSS1.
    struct.pack_into("<h", ba, _sprite_section_off(ba) + idx * 44 + 14, 0)
    errors = ctf_validate.validate_ctf_map(bytes(ba))
    assert any("picnum" in e for e in errors), errors

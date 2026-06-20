"""Warm-up fight — an easy first encounter before the CTF bosses.

The bosses kill too fast for a player to locate the health vars in memory, so the
spawn room (sector 0) holds a single weak grunt (LIZTROOP, TROOPSTRENGTH=30, low
damage). It lets the player take a few survivable hits to find `player_health` and
watch its own health drop to practice finding enemy health, then "roll in" east to
the bosses. The grunt carries no CTF hitag, so it does not affect the flag contract.

Two layers of backpressure:
  * a fast pure-function check on the generated map (always runs), and
  * a gated in-engine playtest that proves the grunt actually engages and its damage
    is GRADUAL/survivable (vs the boss, which one-shots) — Windows + built engine only.
"""
import re
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import generate_ctf_map as G  # noqa: E402
import ctf_validate as V  # noqa: E402

LIZTROOP = 1680
HITAG_BOSS1 = 0x0CF1
HITAG_BOSS2 = 0x0CF2
SPAWN_SECTOR = 0


def _warmup_grunts(map_bytes):
    """Every LIZTROOP sprite sitting in the spawn sector with no CTF boss hitag."""
    sprites = V.parse_map(map_bytes)["sprites"]
    return [s for s in sprites
            if s["picnum"] == LIZTROOP and s["sectnum"] == SPAWN_SECTOR
            and s["hitag"] not in (HITAG_BOSS1, HITAG_BOSS2)]


def test_canonical_map_has_one_spawn_room_warmup_grunt():
    """The default arena places exactly one weak grunt in the spawn room."""
    grunts = _warmup_grunts(G.assemble_map())
    assert len(grunts) == 1, f"expected 1 spawn-room warm-up grunt, found {len(grunts)}"
    assert grunts[0]["hitag"] == 0, "warm-up grunt must NOT carry a CTF hitag"


@pytest.mark.parametrize("seed", [1, 2, 7, 13, 99, 1234])
def test_seeded_maps_keep_the_warmup_grunt(seed):
    """Seeding only shuffles the far timer/vault slots — the spawn-room grunt stays."""
    assert len(_warmup_grunts(G.assemble_map(seed=seed))) == 1


def test_warmup_grunt_does_not_break_the_ctf_contract():
    """The grunt (no boss hitag) leaves the timer/ghost/vault + both-bosses contract intact."""
    assert V.validate_ctf_map(G.assemble_map()) == []


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_warmup_grunt_deals_gradual_survivable_damage():
    """In-engine: the spawn-room grunt engages and its damage is GRADUAL — the player
    survives many ticks through several distinct health values (time to scan), unlike
    the boss which one-shots. Held point-blank with NO retaliation the player still
    lasts seconds; in real play the pistol drops the 30-HP grunt in a few shots."""
    if sys.platform != "win32":
        pytest.skip("probe is Windows-only (Read/WriteProcessMemory)")
    try:
        import e2e_solve_flags as S
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    if S._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    if not (PROJECT_ROOT / "DUKE3D.GRP").is_file():
        pytest.skip("DUKE3D.GRP not generated")

    spawn_cx, spawn_cy = 5120, 5120
    proc = S.launch()
    try:
        mm = S.wait_memmap()
        assert mm is not None, "memory map not written (level never entered?)"
        text = S.MEMMAP_LOG.read_text(errors="replace")
        m = re.search(r"^player_health\s*=\s*(0x[0-9A-Fa-f]+)", text, re.M)
        assert m, "player_health address not published"
        hp_addr = int(m.group(1), 16)
        px, py = mm["player_posx"], mm["player_posy"]
        base, sz = mm["sprite_base"], mm["sprite_size"]
        mem = S.Mem(proc.pid)
        try:
            # the grunt is present at runtime in the spawn sector
            found = False
            deadline = time.time() + 12.0
            while time.time() < deadline and not found:
                for i in range(256):
                    a = base + i * sz
                    if mem.read_i16(a + 14) == LIZTROOP and mem.read_i16(a + 24) == 0:
                        found = True
                        break
                time.sleep(0.2)
            assert found, "no spawn-room LIZTROOP found at runtime"

            # pin the player in the spawn room and sample health
            mem.write_i16(hp_addr, 100)
            samples = []
            ticks_before_death = 0
            deadline = time.time() + 25.0
            while time.time() < deadline:
                mem.write_i32(px, spawn_cx)
                mem.write_i32(py, spawn_cy)
                hp = mem.read_i16(hp_addr)
                if hp is not None:
                    samples.append(hp)
                    if hp <= 0:
                        break
                    ticks_before_death += 1
                time.sleep(0.25)
            took_damage = any(h < 100 for h in samples)
            distinct = len(set(samples))
            assert took_damage, "grunt never damaged the player (did not engage)"
            assert ticks_before_death >= 6, (
                f"player died too fast ({ticks_before_death} ticks) — not survivable")
            assert distinct >= 5, (
                f"health barely changed ({distinct} distinct values) — not scannable")
        finally:
            mem.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

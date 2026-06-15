"""boss-dmg-tune (D3) — boss proximity damage is a survivable ramp, not an instant kill.

The two CTF bosses (boss1/Meatbag, boss2/Warden) used to do `addphealth -1000` within
`ifpdistl 1280`, instantly killing a player who walked up to them — opaque and unfair for
a hack-only game (no chance to learn "freeze your health"). This softens the proximity
aura to `addphealth -3` (~1s visible drain, still eventually fatal) WITHOUT making the boss
combat-killable (it stays regen-immortal; see test_flag_provenance.py).

Two gates:
  1. STATIC (deterministic, no engine): the authored CON drains boss1/boss2 at -3 and leaves
     the never-spawned boss3/boss4 at the stock -1000.
  2. RUNTIME (memory-hack probe): teleport the player onto boss1 with high HP and confirm HP
     declines GRADUALLY (player survives proximity contact) — under -1000 the first in-range
     tic craters HP. Proves the ramp is live in the packed GRP the engine actually loads.
"""
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_boss_con_proximity_damage_values():
    """Static contract: the four `ifpdistl 1280 { addphealth N }` proximity blocks are,
    in file order, boss1, boss2, boss3, boss4. Only the two CTF bosses are softened.

    testdata/GAME.CON is the tracked source generate_assets.py packs into the GRP and is
    always checked. generated_assets/GAME.CON (what repack_con.py swaps in) is gitignored,
    so it's only checked when present locally — but when present it must agree, else a
    surgical repack and a full regen would disagree."""
    pat = re.compile(r"ifpdistl 1280 \{ addphealth (-?\d+)")
    checked = 0
    for rel, required in (("testdata/GAME.CON", True),
                          ("generated_assets/GAME.CON", False)):
        path = PROJECT_ROOT / rel
        if not path.exists():
            assert not required, f"{rel} (tracked CON source) is missing"
            continue
        norm = re.sub(r"\s+", " ", path.read_text(errors="replace"))
        vals = [int(v) for v in pat.findall(norm)]
        assert vals == [-3, -3, -1000, -1000], (
            f"{rel}: boss proximity-damage CON drifted "
            f"(expected boss1/2 -3, boss3/4 -1000): {vals}")
        checked += 1
    assert checked >= 1, "no GAME.CON source found to validate"


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_boss_proximity_damage_is_survivable_ramp():
    """Runtime: with the ramp the player survives proximity contact and HP declines in
    small steps; under the old instant kill it would crater on the first in-range tic."""
    if sys.platform != "win32":
        pytest.skip("boss-damage probe is Windows-only (Read/WriteProcessMemory)")
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    try:
        import e2e_solve_flags as solver
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    if solver._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    if not (PROJECT_ROOT / "DUKE3D.GRP").is_file():
        pytest.skip("DUKE3D.GRP not generated")

    r = solver.probe_boss_damage_ramp(verbose=True)
    assert r.get("ok"), f"probe did not run (boss1 not reached?): {r}"
    assert r["initial_hp"] and r["initial_hp"] > 0, f"game not running / no health: {r}"
    # Survived several proximity tics with declining HP. Under -1000 the player dies on
    # the first in-range tic, so this count collapses to ~1.
    assert r["near_full_alive"] >= 3, f"player did not survive proximity contact: {r}"
    assert r["took_damage"], f"no proximity damage observed near the boss: {r}"
    # The per-tic proximity drop is the ramp (~3), NOT the old -1000 cliff.
    assert r["first_drop"] is not None and 0 < r["first_drop"] <= 20, (
        f"proximity drop is not a gradual ramp (looks like an instant kill): {r}")

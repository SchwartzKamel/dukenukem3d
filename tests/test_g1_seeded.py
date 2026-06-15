"""G1-B (rm-g1) — seeded / randomized CTF arenas.

`generate_ctf_map.assemble_map(seed=)` shuffles the TIMER and VAULT roles across the two
far connected slots (2, 3); spawn stays slot 0 and the **boss stays slot 1** (a distant
boss is culled to STAT_ZOMBIEACTOR and never runs its CTF CON, so its flags would be
unsolvable). `seed=None` is byte-identical to the canonical map. The CTF contract (one of
each lotag, both bosses, the fixed ghost centroid) is preserved (checked by ctf_validate),
the engine publishes the moved timer/vault targets (G1-A), and the harness reads them
(G1-C) — so a seeded arena is still fully solvable.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import generate_ctf_map as G
import ctf_validate as V


def test_seed_none_is_byte_identical_to_canonical():
    """seed=None must not perturb the shipped default arena."""
    assert G.assemble_map() == G.assemble_map(seed=None)


@pytest.mark.parametrize("seed", [1, 2, 7, 13, 99, 1234])
def test_seeded_map_satisfies_ctf_contract(seed):
    """Every seeded arena still passes ctf_validate (one of each lotag, both bosses, ghost)."""
    errs = V.validate_ctf_map(G.assemble_map(seed=seed))
    assert not errs, f"seed {seed} fails the CTF contract: {errs}"


def test_some_seed_changes_the_layout():
    """At least one seed produces a different arena — the shuffle is real, not a no-op."""
    default = G.assemble_map()
    assert any(G.assemble_map(seed=s) != default for s in range(1, 20)), \
        "no seed in 1..19 changed the layout"


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_seeded_arena_is_solvable():
    """A non-default seeded arena is still 6/6 solvable in-engine (G1-A publishes the moved
    targets, G1-C reads them). Swaps the seeded map into the GRP and always restores it."""
    if sys.platform != "win32":
        pytest.skip("solve harness is Windows-only (WriteProcessMemory)")
    try:
        import e2e_solve_flags as solver
        from grp_format import read_grp, create_grp
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    if solver._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    grp = PROJECT_ROOT / "DUKE3D.GRP"
    if not grp.is_file():
        pytest.skip("DUKE3D.GRP not generated")

    default = G.assemble_map()
    seed = next((s for s in range(1, 30) if G.assemble_map(seed=s) != default), None)
    assert seed is not None, "no layout-changing seed found"

    backup = grp.read_bytes()
    try:
        files = read_grp(backup)
        files["CTF1.MAP"] = G.assemble_map(seed=seed)
        grp.write_bytes(create_grp(files))
        captured = solver.solve([0, 1, 2, 3, 4, 5], verbose=False)
        assert all(captured.get(n) for n in range(6)), \
            f"seeded arena (seed {seed}) not fully solvable: {captured}"
    finally:
        grp.write_bytes(backup)   # always restore the canonical GRP

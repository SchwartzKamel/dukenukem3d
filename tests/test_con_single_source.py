"""z-con-source (finding-set Z3) — single source of truth for the packed CON/data files.

`generate_assets.py` packs the GRP's GAME.CON/DEFS.CON/USER.CON/LOOKUP.DAT from
**`engine/testdata/`** (`generate_assets.py:2844-2848`) and *also* mirrors every GRP
member into **`engine/generated_assets/`** (`generate_assets.py:2919-2923`). So the
`generated_assets/` copies are **derived** — rewritten from `testdata/` on every run —
while `testdata/` is the tracked, canonical source (`generated_assets/` is gitignored).

The trap (which this guard closes): `repack_con.py` swaps the `generated_assets/` copy
into the GRP, so a hand-edit to *one* path (e.g. only `generated_assets/GAME.CON`) is
silently reverted by the other (a full `generate_assets.py` regen, or a stale copy).
The two must never diverge — this test fails fast on any drift.
"""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files generate_assets.py loads from testdata/ and writes into BOTH the GRP and
# generated_assets/ (generate_assets.py:2844). testdata/ is canonical + tracked.
_DUAL_SOURCE = ["GAME.CON", "DEFS.CON", "USER.CON", "LOOKUP.DAT"]


def test_testdata_game_con_is_the_tracked_source():
    """The canonical source (testdata/GAME.CON) must exist — it's what the pipeline packs."""
    assert (PROJECT_ROOT / "testdata" / "GAME.CON").is_file(), (
        "testdata/GAME.CON (the canonical CON source generate_assets.py packs) is missing")


@pytest.mark.parametrize("name", _DUAL_SOURCE)
def test_generated_copy_matches_testdata_source(name):
    """generated_assets/<name> is a derived copy of testdata/<name>; when both exist they
    MUST be byte-identical, else a hand-edit to one path will be silently reverted by the
    other (the repack_con.py vs full-regen trap, finding-set Z3)."""
    src = PROJECT_ROOT / "testdata" / name
    derived = PROJECT_ROOT / "generated_assets" / name
    if not derived.exists():
        pytest.skip(f"generated_assets/{name} not present (gitignored; run generate_assets.py)")
    assert src.is_file(), (
        f"testdata/{name} is missing but generated_assets/{name} exists — the derived copy "
        f"has no tracked source (inverted/lost source of truth)")
    assert src.read_bytes() == derived.read_bytes(), (
        f"{name}: the testdata/ (canonical) and generated_assets/ (derived) copies have "
        f"DRIFTED. generate_assets.py packs testdata/ AND mirrors it into generated_assets/; "
        f"repack_con.py swaps the generated_assets/ copy into the GRP. Edit the testdata/ copy "
        f"and re-sync/regen so a one-path edit can't be silently reverted (finding-set Z3).")

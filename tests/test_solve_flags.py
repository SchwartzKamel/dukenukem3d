"""I1 — solve-each-flag E2E (all five flags).

Drives the headless game and memory-hacks the flags (the "hackable by design"
challenge), asserting each `ghvctf{}` actually emits — the project's
demo-validation backbone and the holdout for the attended intptr_t migration (E1).

Covers all five flags end-to-end: 0 & 1 (boss god-mode), 2 (frozen clock),
3 (ghost teleport, unblocked by CTF-1), and 4 (vault code + file). The harness
lives in `engine/tools/e2e_solve_flags.py`.
"""
import sys

import pytest


@pytest.mark.playtest
@pytest.mark.serial
def test_solve_all_ctf_flags():
    if sys.platform != "win32":
        pytest.skip("solve-flags harness is Windows-only (WriteProcessMemory)")
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "tools"))
    try:
        import e2e_solve_flags as solver
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")

    if solver._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")

    captured = solver.solve([0, 1, 2, 3, 4], verbose=True)
    assert captured.get(0), "Flag 0 (boss1 god-mode) was not captured"
    assert captured.get(1), "Flag 1 (boss2 god-mode) was not captured"
    assert captured.get(2), "Flag 2 (frozen clock) was not captured"
    assert captured.get(3), "Flag 3 (ghost walk) was not captured"
    assert captured.get(4), "Flag 4 (vault code) was not captured"

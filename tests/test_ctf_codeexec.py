"""G2-A (CODE_EXEC, flag 5) — control-flow hijack.

The engine publishes a NULL-by-default function-pointer slot (`ctf_codeexec_hook`) it
calls each CTF tick (`ctf_run_tick_hook`), plus a `ctf_grant_codeexec()` win function it
never calls in normal play. Capturing flag 5 requires writing the grant function's
address into the hook slot — hijacking the engine's control flow so it executes a
function the player chose. The e2e solver does exactly that; this asserts it captures.
Windows-only (WriteProcessMemory). Hack-gated by construction (the slot is NULL unless a
memory write redirects it — see test_flag_provenance.py for the fire-only=0 guard).
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_codeexec_flag_via_hook_hijack():
    if sys.platform != "win32":
        pytest.skip("solve harness is Windows-only (WriteProcessMemory)")
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    try:
        import e2e_solve_flags as solver
    except ImportError as exc:
        pytest.skip(f"harness import failed: {exc}")
    if solver._resolve_binary() is None:
        pytest.skip("duke3d.exe not built")
    if not (PROJECT_ROOT / "DUKE3D.GRP").is_file():
        pytest.skip("DUKE3D.GRP not generated")

    captured = solver.solve([5], verbose=True)
    assert captured.get(5), "Flag 5 (control-flow hijack via ctf_codeexec_hook) was not captured"

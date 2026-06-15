"""regression-guards (J-REGEX + J-SYNC): lock the 5 CTF flag strings.

Three deterministic guards against silent flag drift:
  * J-REGEX  — every emitted flag matches the DC32 platform's accept-regex
               ^ghvctf\\{[a-z0-9_]+\\}$ (backend/mist_app/flag/utils.py:199). A flag the
               platform would reject is a flag a player can never submit.
  * J-SYNC (engine ↔ harness) — the engine's ctf_emit_flag(...) strings exactly match the
               solve harness's expected set (engine/tools/e2e_solve_flags.py). Drift here means
               the e2e harness (and the player's memmap) reference a string the game never emits.
  * J-SYNC (platform, optional) — if the DC32 platform repo is reachable, the emitted flags are
               present in its flags_config.yaml. Skipped when the platform repo is absent.

Static source inspection (no engine launch) — green today; this locks it.
See docs/plans/2026-06-15_DEEP_AUDIT_HARDENING.md finding-set N (J-REGEX/J-SYNC) + N-OK.
"""
import os
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # engine/

# The platform's canonical accept-regex (backend/mist_app/flag/utils.py:199).
FLAG_RE = re.compile(r"^ghvctf\{[a-z0-9_]+\}$")


def _emit_flags_from_game_c():
    """{flag_id: string} for every ctf_emit_flag(N, "ghvctf{...}") in GAME.C."""
    src = (PROJECT_ROOT / "source" / "GAME.C").read_text(errors="replace")
    out = {}
    for m in re.finditer(r'ctf_emit_flag\(\s*(\d+)\s*,\s*"(ghvctf\{[^"]+\})"', src):
        out[int(m.group(1))] = m.group(2)
    return out


def _expected_flags_from_harness():
    """{flag_id: string} from the e2e_solve_flags.py expected dict (lines like `0: "ghvctf{...}"`)."""
    src = (PROJECT_ROOT / "tools" / "e2e_solve_flags.py").read_text(errors="replace")
    out = {}
    for m in re.finditer(r'^\s*(\d+)\s*:\s*"(ghvctf\{[^"]+\})"', src, re.M):
        out[int(m.group(1))] = m.group(2)
    return out


def test_all_flags_match_platform_accept_regex():
    """J-REGEX: every emitted flag matches the platform's accept-regex."""
    flags = _emit_flags_from_game_c()
    assert flags, "no ctf_emit_flag(...) strings found in GAME.C"
    bad = {fid: s for fid, s in flags.items() if not FLAG_RE.match(s)}
    assert not bad, f"flags fail the platform accept-regex {FLAG_RE.pattern}: {bad}"


def test_engine_emits_match_solve_harness():
    """J-SYNC: the engine emits exactly the strings the solve harness expects."""
    emit = _emit_flags_from_game_c()
    expect = _expected_flags_from_harness()
    assert expect, "no expected flags parsed from e2e_solve_flags.py"
    assert emit == expect, (
        "engine ctf_emit_flag strings drifted from the solve harness:\n"
        f"  engine : {emit}\n  harness: {expect}"
    )


def test_flags_present_in_platform_config_if_reachable():
    """J-SYNC (platform): emitted flags appear in the DC32 flags_config.yaml, when present."""
    override = os.environ.get("DC32_PLATFORM_DIR")
    candidates = []
    if override:
        candidates.append(Path(override) / "backend" / "mist_app" / "flag" / "flags_config.yaml")
    # GHV/CTF_dev/dc32-mist-store-ctf-platform is a sibling of GHV/games/.
    candidates.append(PROJECT_ROOT.parents[2] / "CTF_dev"
                      / "dc32-mist-store-ctf-platform" / "backend" / "mist_app"
                      / "flag" / "flags_config.yaml")
    cfg = next((c for c in candidates if c.is_file()), None)
    if cfg is None:
        pytest.skip("DC32 platform flags_config.yaml not reachable (set DC32_PLATFORM_DIR to enable)")
    plat = set(re.findall(r"ghvctf\{[a-z0-9_]+\}", cfg.read_text(errors="replace")))
    missing = set(_emit_flags_from_game_c().values()) - plat
    assert not missing, f"engine flags absent from platform flags_config.yaml: {missing}"

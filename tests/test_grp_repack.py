"""grp-con-repack (finding-set X): surgical CON-only GRP repack.

`read_grp` is the inverse of `create_grp` — and because `create_grp` sorts its keys
deterministically, the round trip `create_grp(read_grp(g)) == g` is byte-identical.
That invariant is what makes `replace_files` safe: it swaps named entries (e.g.
GAME.CON) while every other texture/sound entry stays byte-for-byte unchanged — the
safe build path for a CON-only edit (boss-dmg-tune) that must NOT regenerate art.
See docs/plans/2026-06-15_GRP-CON-REPACK_SPEC.md.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # engine/
TOOLS = PROJECT_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import grp_format as gf  # noqa: E402


def _real_grp():
    """A real committed GRP to exercise the round-trip against (engine or staging)."""
    for p in (PROJECT_ROOT / "DUKE3D.GRP",
              PROJECT_ROOT.parents[1] / "dist" / "staging" / "ATOMIC.GRP"):
        if p.is_file():
            return p
    return None


def _resolve_binary():
    exe = "duke3d.exe" if sys.platform == "win32" else "duke3d"
    for c in (PROJECT_ROOT / "build" / "Release" / exe, PROJECT_ROOT / "build" / exe,
              PROJECT_ROOT / exe):
        if c.is_file():
            return c
    return None


# ── pure deterministic gates ──────────────────────────────────────────────────

def test_synthetic_round_trip():
    files = {"GAME.CON": b"state foo\nenda\n", "B.DAT": b"\x00\x01\x02\x03", "A.ART": b"xyz"}
    g = gf.create_grp(files)
    back = gf.read_grp(g)
    assert back == {k.upper(): v for k, v in files.items()}
    assert gf.create_grp(back) == g            # round-trip identity


def test_read_grp_rejects_bad_magic():
    with pytest.raises(ValueError):
        gf.read_grp(b"not a grp file at all, no KenSilverman here")


def test_read_grp_rejects_truncated():
    good = gf.create_grp({"X.DAT": b"0123456789"})
    with pytest.raises(ValueError):
        gf.read_grp(good[:-3])                  # data section truncated


def test_real_grp_round_trip_identity():
    grp = _real_grp()
    if grp is None:
        pytest.skip("no DUKE3D.GRP / ATOMIC.GRP available")
    data = grp.read_bytes()
    parsed = gf.read_grp(data)
    assert "GAME.CON" in parsed
    # THE hard invariant: re-packing the parsed archive reproduces it byte-for-byte.
    assert gf.create_grp(parsed) == data


def test_replace_files_is_surgical():
    grp = _real_grp()
    if grp is None:
        pytest.skip("no DUKE3D.GRP / ATOMIC.GRP available")
    data = grp.read_bytes()
    before = gf.read_grp(data)
    new_con = before["GAME.CON"] + b"\n\n"      # safe no-op CON change (trailing blank lines)
    out = gf.replace_files(data, {"GAME.CON": new_con})
    after = gf.read_grp(out)
    assert after["GAME.CON"] == new_con          # the target changed to exactly the new bytes
    assert set(after) == set(before)             # same entry set
    for name in before:                          # every OTHER entry byte-identical
        if name != "GAME.CON":
            assert after[name] == before[name], name


def test_replace_files_rejects_unknown_name():
    grp = _real_grp()
    if grp is None:
        pytest.skip("no DUKE3D.GRP / ATOMIC.GRP available")
    with pytest.raises(KeyError):
        gf.replace_files(grp.read_bytes(), {"NOPE.XYZ": b"x"})


def test_repack_con_cli(tmp_path):
    grp = _real_grp()
    if grp is None:
        pytest.skip("no DUKE3D.GRP / ATOMIC.GRP available")
    con = tmp_path / "GAME.CON"
    con.write_bytes(gf.read_grp(grp.read_bytes())["GAME.CON"] + b"\n\n")
    out = tmp_path / "out.grp"
    r = subprocess.run([sys.executable, str(TOOLS / "repack_con.py"),
                        "--grp", str(grp), "--con", str(con), "-o", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    after = gf.read_grp(out.read_bytes())
    assert after["GAME.CON"].endswith(b"\n\n")
    # all non-GAME.CON entries identical to the source
    src = gf.read_grp(grp.read_bytes())
    for name in src:
        if name != "GAME.CON":
            assert after[name] == src[name], name


# ── engine-boot smoke (the demo path): a repacked GRP actually loads ──────────

@pytest.mark.playtest
@pytest.mark.serial
@pytest.mark.slow
def test_repacked_grp_boots(tmp_path):
    """A GRP repacked with a (trivially) changed GAME.CON still boots the engine."""
    if sys.platform != "win32":
        pytest.skip("native Windows engine launch")
    grp = _real_grp()
    binary = _resolve_binary()
    if grp is None or binary is None:
        pytest.skip("engine binary / GRP not available")

    data = grp.read_bytes()
    new_con = gf.read_grp(data)["GAME.CON"] + b"\n\n"     # safe no-op edit
    repacked = gf.replace_files(data, {"GAME.CON": new_con})
    (tmp_path / "DUKE3D.GRP").write_bytes(repacked)
    for name in ("SDL2.dll", "DUKE3D.CFG"):
        src = PROJECT_ROOT / name
        if src.is_file():
            shutil.copy(src, tmp_path / name)

    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy", "DUKE3D_HEADLESS": "1", "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_SILENT_ERRORS": "1", "DUKE3D_AUTOPLAY": "1", "DUKE3D_FRAME_LIMIT": "400",
    })
    proc = subprocess.Popen([str(binary), "/v1", "/l1", "/s2"], cwd=str(tmp_path), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=90)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

    log = tmp_path / "atomic_shell_startup.log"
    text = log.read_text(errors="replace") if log.is_file() else ""
    assert text, "engine wrote no startup log against the repacked GRP"
    assert "CRASH: Exception 0xC0000005" not in text and "CRASH: Access violation" not in text, (
        f"repacked GRP produced a crash marker:\n{text[-800:]}")
    assert "initgroupfile" in text, "engine did not load the repacked GRP"

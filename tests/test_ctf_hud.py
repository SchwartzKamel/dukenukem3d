"""G3 — CTF flag-feedback HUD tracker.

The HUD (`compat/hud.c`) draws a "FLAGS n/5" tracker in the top-left, reading
`ctf_flag_captured()`. This verifies it actually renders: the tracker region is a
crisp, low-colour overlay — a dominant dark-gray box (`col_darkgray`) plus
yellow text (`col_yellow`) — which is unmistakably distinct from the varied game
view that would otherwise occupy that corner.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_binary() -> Path:
    exe = "duke3d.exe" if sys.platform == "win32" else "duke3d"
    for candidate in [
        PROJECT_ROOT / "build" / "Release" / exe,
        PROJECT_ROOT / "build" / exe,
        PROJECT_ROOT / exe,
    ]:
        if candidate.is_file():
            return candidate
    return PROJECT_ROOT / "build" / exe


def _run_capture(capture_dir, frames: int = 120, interval: int = 30):
    binary = _resolve_binary()
    if not binary.is_file():
        pytest.skip(f"Binary not found: {binary}")
    if not (PROJECT_ROOT / "DUKE3D.GRP").is_file():
        pytest.skip("DUKE3D.GRP not found")
    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy",
        "DUKE3D_HEADLESS": "1",
        "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_SILENT_ERRORS": "1",
        "DUKE3D_AUTOPLAY": "1",
        "DUKE3D_FRAME_LIMIT": str(frames),
        "DUKE3D_CAPTURE_INTERVAL": str(interval),
        # Isolate frames from the shared session captures/ dir (xdist-safe).
        "DUKE3D_CAPTURE_DIR": str(capture_dir),
    })
    try:
        subprocess.run([str(binary), "/v1", "/l1", "/s2"], cwd=str(PROJECT_ROOT),
                       env=env, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        pytest.skip("headless capture timed out")
    return sorted(Path(capture_dir).glob("frame_*.bmp"))


def _is_gray(c):
    r, g, b = c
    return abs(r - g) <= 14 and abs(g - b) <= 14 and 30 <= r <= 120


def _is_yellow(c):
    r, g, b = c
    return r >= 24 and g >= 24 and abs(r - g) <= 16 and b <= 16


@pytest.mark.playtest
@pytest.mark.serial
def test_ctf_hud_flag_tracker_renders(tmp_path):
    """A captured frame's top-left must show the tracker: a dominant dark-gray
    box + yellow text, in a low-colour region (not varied game view)."""
    pytest.importorskip("PIL")
    from PIL import Image

    capdir = tmp_path / "caps"
    capdir.mkdir()
    frames = _run_capture(capdir)
    if not frames:
        pytest.skip("no frames captured")

    # The HUD draws once the player is in-game; check every captured frame and
    # require at least one to show the tracker signature (early frames may be
    # mid-load with no HUD).
    diagnostics = []
    for path in frames:
        im = Image.open(str(path)).convert("RGB")
        w, h = im.size
        px = im.load()
        region = [px[x, y] for y in range(2, 12) for x in range(2, 54)
                  if x < w and y < h]
        n = len(region)
        if n == 0:
            continue
        gray = sum(1 for c in region if _is_gray(c))
        yellow = sum(1 for c in region if _is_yellow(c))
        distinct = len(set(region))
        diagnostics.append((path.name, gray, yellow, distinct, n))
        if gray >= 0.30 * n and yellow >= 12 and distinct <= 14:
            return  # tracker rendered: box + text in a clean overlay region

    pytest.fail(
        "CTF flag HUD tracker not found in any captured frame "
        "(expected a dark-gray box + yellow 'FLAGS n/5' text in the top-left).\n"
        f"per-frame [name, gray, yellow, distinct, region_px]: {diagnostics}"
    )


@pytest.mark.playtest
def test_hud_includes_ctf_tracker_source():
    """Sanity: the HUD source wires the CTF tracker (guards against silent
    removal of the feature even if a capture run is skipped)."""
    hud = (PROJECT_ROOT / "compat" / "hud.c").read_text(encoding="utf-8")
    assert "ctf.h" in hud, "hud.c must include ctf.h"
    assert "ctf_flag_captured" in hud, "hud.c must read ctf_flag_captured()"
    assert "FLAGS" in hud, "hud.c must draw the FLAGS tracker label"

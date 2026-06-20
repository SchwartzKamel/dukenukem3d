"""
Static guardrails for GAME.C menu/opening stability paths.

These tests lock in:
1. Deterministic non-game menu background redraw using MENUSCREEN.
2. Demo slot 0 guard in opendemoread() to avoid accidental demo playback.
3. MENUSCREEN backdrop usage in Logo() splash screen.
"""

import re
from pathlib import Path

import pytest


@pytest.fixture
def repo_root():
    return Path(__file__).parent.parent


class TestGameMenuBackgroundStability:
    def test_drawbackground_has_non_game_menu_menuscreen_branch(self, repo_root):
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        marker = "void drawbackground(void)"
        pos = content.find(marker)
        assert pos != -1, "drawbackground() not found in GAME.C."

        window = content[pos:pos + 1600]
        assert "(ps[myconnectindex].gm&MODE_MENU)" in window, (
            "drawbackground() should check MODE_MENU state."
        )
        assert "(ps[myconnectindex].gm&MODE_GAME) == 0" in window, (
            "drawbackground() should gate the MENUSCREEN path to non-game menus."
        )
        assert "MENUSCREEN" in window and "rotatesprite(" in window, (
            "drawbackground() should render MENUSCREEN for non-game menu redraw."
        )


class TestDemoPlaybackGuard:
    def test_opendemoread_rejects_demo_zero(self, repo_root):
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        marker = "char opendemoread(char which_demo)"
        pos = content.find(marker)
        assert pos != -1, "opendemoread() not found in GAME.C."

        window = content[pos:pos + 700]
        assert "if(which_demo == 0)" in window, (
            "opendemoread() should explicitly guard demo slot 0."
        )
        assert "return(0);" in window, (
            "opendemoread() demo slot 0 guard should return 0 (no demo)."
        )


class TestLogoBackdropStability:
    def test_logo_uses_menuscreen_backdrop_for_splashes(self, repo_root):
        game_c = repo_root / "source" / "GAME.C"
        if not game_c.exists():
            pytest.skip(f"{game_c} not found")

        content = game_c.read_text(errors="replace")
        marker = "void Logo(void)"
        pos = content.find(marker)
        assert pos != -1, "Logo() not found in GAME.C."

        window = content[pos:pos + 1800]
        matches = re.findall(r"rotatesprite\([^;]*MENUSCREEN[^;]*\);", window, re.S)
        # The intro was collapsed from two identical splash screens (with a fast
        # palette fade between them, which read as a "blip in and out") into ONE
        # steady splash that draws the MENUSCREEN backdrop once and holds. So the
        # backdrop must still be present (>= 1), but a second draw is no longer
        # expected — re-introducing one would bring the blip back.
        assert len(matches) >= 1, (
            "Logo() should draw the MENUSCREEN backdrop behind the splash/title screen."
        )

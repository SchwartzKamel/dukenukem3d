"""CTF integrity: the SHIPPED credits + help screens must not hand players the answers.

The CREDITS menu (cases 990-992 in MENUES.C draw tiles 2504-2506) and the TEXTSTORY / F1HELP
screens are generated art. They previously baked in the flag token format ("FIVE GHVCTF{} FLAGS",
"GHVCTF{...}"), a per-flag solution walkthrough ("THE FIVE FLAGS" page), and a pointer to the
bundled Cheat Engine table + Python trainer ("CHEAT ENGINE TABLE + PY TRAINER",
"TRAINER + CE TABLE IN TOOLS/", "SEE TOOLS/TRAINER/ FOR HELP"). A challenge build must ship none
of those.

This test pins the redaction by scanning the credits/help art generators for any flag string or
Cheat-Engine-table / trainer-tool reference. The directional "what to do" framing (hack memory,
break the game) is intentionally KEPT -- that is the in-game hint players are meant to see.
"""
import inspect
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # engine/
sys.path.insert(0, str(PROJECT_ROOT / "tools"))


@pytest.fixture(scope="module")
def credits_help_source():
    try:
        import generate_assets as ga
    except Exception as exc:  # PIL / numpy may be absent in a minimal env
        pytest.skip(f"generate_assets import failed: {exc}")
    funcs = [ga._gen_credits_screen, ga._gen_credits_page, ga._gen_help_screen]
    return "\n".join(inspect.getsource(f) for f in funcs)


# Substrings that would spoil the CTF if rendered into the credits/help art.
FORBIDDEN = [
    "ghvctf",                  # the flag token format / any literal flag
    "cheat engine table",      # the bundled .CT answer table
    "ce table",
    "py trainer",
    "tools/trainer",
    "the five flags",          # the per-flag answer-key page heading
    "freeze hp, kill",         # flag-1 solution
    "drop the warden",         # flag-2 solution
    "freeze the ctf timer",    # flag-3 solution
    "teleport into the vault", # flag-4 solution
    "crack the 4-digit",       # flag-5 solution
]


@pytest.mark.parametrize("needle", FORBIDDEN)
def test_credits_help_art_has_no_spoiler(credits_help_source, needle):
    """No flag string, answer-key step, or Cheat-Engine-table/trainer pointer in the credits art."""
    assert needle not in credits_help_source.lower(), (
        f"credits/help art generator still references {needle!r} -- the shipped game must not "
        f"reveal flags or point players at the Cheat Engine table / trainer"
    )


def test_credits_help_art_keeps_directional_framing(credits_help_source):
    """The 'what to do' hint the user wants kept must remain: still tell players to hack/break."""
    low = credits_help_source.lower()
    assert "hack memory" in low or "hackable-by-design" in low, (
        "expected the directional 'hack the game' framing to remain in the credits/help art -- "
        "redact the answers, not the challenge framing"
    )

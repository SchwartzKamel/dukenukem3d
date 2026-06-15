"""platform-id-guard (finding-set R) — DC32 identity + manifest-schema drift guard.

Cross-checks Atomic Shell's packaging against the live `dc32-mist-store-ctf-platform`
repo on the two axes that are correct *today* but otherwise have **no** automated guard:

  * R1-R3 IDENTITY — `tools/package_for_store.py`'s GAME_ID / FOLDER_NAME / EXE_NAME must
    equal the platform `backend/games.yml` atomic_shell entry's id / folder_name / exe_name.
    A platform UUID re-roll or a folder/exe rename would silently break the client launch.
  * R5-R6 MANIFEST SCHEMA — the manifest the packager emits must carry every **non-Option**
    field of the desktop `manifest.rs` `Manifest` / `ManifestFile` structs. A new *required*
    field added platform-side would make the client reject our manifest.

Flag-string drift (R9/R10) is already covered by `test_flag_format.py`; this closes the
remaining axes. Reachable-or-skip: needs `tools/package_for_store.py` (parent repo) and the
platform repo (`DC32_PLATFORM_DIR` or the sibling `GHV/CTF_dev/dc32-mist-store-ctf-platform`);
skips cleanly when either is absent so CI stays green. See 2026-06-15_PLATFORM_COMPLIANCE_AUDIT.md.
"""
import os
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # engine/


def _packager():
    """tools/package_for_store.py in the atomic-shell parent (absent in a standalone engine checkout)."""
    p = PROJECT_ROOT.parent / "tools" / "package_for_store.py"
    return p if p.is_file() else None


def _platform_dir():
    """The DC32 platform repo: DC32_PLATFORM_DIR override, else the sibling GHV/CTF_dev path."""
    override = os.environ.get("DC32_PLATFORM_DIR")
    if override:
        return Path(override)
    cand = PROJECT_ROOT.parents[2] / "CTF_dev" / "dc32-mist-store-ctf-platform"
    return cand if cand.is_dir() else None


def _const(src, name):
    m = re.search(rf'^{name}\s*=\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else None


def test_packager_identity_matches_platform_games_yml():
    """R1-R3: package_for_store.py identity constants == the games.yml atomic_shell entry."""
    pkg = _packager()
    if pkg is None:
        pytest.skip("tools/package_for_store.py not reachable (standalone engine checkout)")
    plat = _platform_dir()
    if plat is None:
        pytest.skip("DC32 platform repo not reachable (set DC32_PLATFORM_DIR to enable)")
    games_yml = plat / "backend" / "games.yml"
    if not games_yml.is_file():
        pytest.skip(f"platform games.yml not found at {games_yml}")
    yaml = pytest.importorskip("yaml")

    src = pkg.read_text(errors="replace")
    game_id = _const(src, "GAME_ID")
    folder_name = _const(src, "FOLDER_NAME")
    exe_name = _const(src, "EXE_NAME")
    assert game_id and folder_name and exe_name, \
        "could not parse GAME_ID/FOLDER_NAME/EXE_NAME from package_for_store.py"

    games = yaml.safe_load(games_yml.read_text(errors="replace"))
    entry = next((g for g in games if str(g.get("id")) == game_id), None)
    assert entry is not None, (
        f"no games.yml entry with id == package GAME_ID {game_id} (catalog id drift / re-roll)")
    assert entry.get("folder_name") == folder_name, (
        f"folder_name drift: package {folder_name!r} vs games.yml {entry.get('folder_name')!r}")
    # EXE_NAME is the full filename (atomic_shell.exe); games.yml exe_name is the stem.
    assert entry.get("exe_name") == Path(exe_name).stem, (
        f"exe_name drift: package {exe_name!r} (stem {Path(exe_name).stem!r}) "
        f"vs games.yml {entry.get('exe_name')!r}")


def test_emitted_manifest_carries_every_required_struct_field():
    """R5-R6: package_for_store.py emits every non-Option field of manifest.rs's structs."""
    pkg = _packager()
    if pkg is None:
        pytest.skip("tools/package_for_store.py not reachable (standalone engine checkout)")
    plat = _platform_dir()
    if plat is None:
        pytest.skip("DC32 platform repo not reachable (set DC32_PLATFORM_DIR to enable)")
    manifest_rs = plat / "desktop" / "src-tauri" / "src" / "download" / "manifest.rs"
    if not manifest_rs.is_file():
        pytest.skip(f"manifest.rs not found at {manifest_rs}")

    rs = manifest_rs.read_text(errors="replace")
    required = set()
    for struct in ("Manifest", "ManifestFile"):
        m = re.search(rf"pub struct {struct}\s*\{{(.*?)\}}", rs, re.S)
        assert m, f"could not find `pub struct {struct}` in manifest.rs"
        for fm in re.finditer(r"pub\s+(\w+)\s*:\s*([^,\n]+)", m.group(1)):
            field, typ = fm.group(1), fm.group(2).strip()
            if not typ.startswith("Option"):
                required.add(field)
    # sanity: the parse must have found the known core fields (else the regex drifted)
    assert {"app_name", "app_id", "app_version", "files",
            "file_name", "file_location", "file_hash", "file_size"} <= required, (
        f"manifest.rs struct parse looks wrong (got {sorted(required)})")

    src = pkg.read_text(errors="replace")
    missing = sorted(f for f in required if f'"{f}"' not in src)
    assert not missing, (
        f"package_for_store.py omits required manifest field(s) {missing}; manifest.rs declares "
        f"them non-Option, so the desktop client would reject our manifest")

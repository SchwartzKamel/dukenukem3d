import os
import sys
import subprocess
import json
from pathlib import Path
import re

import pytest
from pydantic import BaseModel, field_validator

# Add project root and tools to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))


# ============================================================================
# Pydantic Model for Sound Manifest Entry Validation
# ============================================================================

class SoundManifestEntry(BaseModel):
    """Validates individual sound manifest entries with pydantic v2."""
    
    wav: str
    engine_sound_id: str | None = None
    engine_sound_id_int: int | None = None
    voice: str
    category: str
    prompt_summary: str
    status: str = "generated"
    generated_at: str | None = None
    notes: str | None = None
    
    @field_validator('engine_sound_id')
    @classmethod
    def validate_sound_id(cls, v):
        """Validate engine_sound_id matches C identifier pattern."""
        if v is None:
            return v
        if not re.match(r'^[A-Z_][A-Z0-9_]*$', v):
            raise ValueError(f"sound_id '{v}' does not match pattern ^[A-Z_][A-Z0-9_]*$")
        return v
    
    @field_validator('voice')
    @classmethod
    def validate_voice(cls, v):
        """Validate voice is one of known enum values."""
        valid_voices = {'alloy', 'echo', 'onyx'}
        if v not in valid_voices:
            raise ValueError(f"voice '{v}' not in {valid_voices}")
        return v
    
    @field_validator('wav')
    @classmethod
    def validate_wav_path(cls, v):
        """Validate wav_path ends with .wav or .WAV."""
        if not (v.endswith('.wav') or v.endswith('.WAV')):
            raise ValueError(f"wav_path '{v}' does not end with .wav or .WAV")
        return v


# ============================================================================
# Shared Session-Scoped Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root():
    """Return absolute path to project root (parent of tests/ directory)."""
    return Path(PROJECT_ROOT)


@pytest.fixture(scope="session")
def binary_path(project_root):
    """Return path to the duke3d binary."""
    return project_root / "duke3d"


@pytest.fixture(scope="session")
def grp_path(project_root):
    """Return path to DUKE3D.GRP file."""
    return project_root / "DUKE3D.GRP"


@pytest.fixture(scope="session")
def generated_assets_dir(project_root):
    """Return path to generated_assets directory."""
    return project_root / "generated_assets"


@pytest.fixture(scope="session", autouse=True)
def generated_audio_artifacts():
    """Run generate_audio.py --no-ai once per session and yield path to sounds directory.
    
    This fixture is autouse=True so it runs at session start, ensuring audio files
    are available for all tests that need them.
    
    NOTE: This fixture does not tear down (no cleanup code after yield). This is
    intentional because:
    - Session-scoped: generated_assets/sounds/ is part of the checked-in project state
    - Regenerating files is idempotent: running generate_audio.py --no-ai multiple
      times produces identical output (deterministic silence placeholders)
    - Tests depend on the artifacts persisting for the full session
    
    Returns a dict with:
        - sounds_dir: Path to generated_assets/sounds
        - manifest_path: Path to MANIFEST.json
        - wav_files: List of generated .WAV files
        - manifest: Parsed MANIFEST.json dict
    """
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "tools", "generate_audio.py"), "--no-ai"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30
    )
    
    assert result.returncode == 0, \
        f"generate_audio.py --no-ai failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    
    sounds_dir = Path(PROJECT_ROOT) / "generated_assets" / "sounds"
    assert sounds_dir.exists(), f"Output directory not created: {sounds_dir}"
    
    wav_files = sorted([f for f in sounds_dir.iterdir() if f.suffix == ".WAV"])
    manifest_path = sounds_dir / "MANIFEST.json"
    assert manifest_path.exists(), f"MANIFEST.json not created: {manifest_path}"
    
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    artifacts = {
        "sounds_dir": sounds_dir,
        "manifest_path": manifest_path,
        "wav_files": wav_files,
        "manifest": manifest
    }
    
    yield artifacts

def pytest_addoption(parser):
    """Add --runslow option to pytest CLI."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow tests (subprocess-heavy, C compilation); default: skip"
    )


def pytest_collection_modifyitems(config, items):
    """Skip slow tests unless --runslow is passed."""
    if config.getoption("--runslow"):
        # Run all tests
        return
    
    # Skip all tests marked as slow
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)

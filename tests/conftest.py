import os
import sys
import subprocess
import json
from pathlib import Path

import pytest

# Add project root and tools to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))


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

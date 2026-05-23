"""LLM-driven end-to-end playtest harness tests."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def llm_playtest_workspace(project_root, request, worker_id):
    """Project-local scratch directory for LLM playtest reports/copies."""
    safe_name = request.node.name.replace("/", "_").replace("[", "_").replace("]", "_")
    workspace = project_root / ".pytest_llm_playtest" / f"{worker_id}_{safe_name}"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    try:
        yield workspace
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
        parent = project_root / ".pytest_llm_playtest"
        try:
            parent.rmdir()
        except OSError:
            pass


def _write_synthetic_frames(frames_dir: Path, count: int = 3) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(count):
        image = Image.new("RGB", (64, 48), (20 + idx * 20, 30, 60))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 34, 63, 47), fill=(80, 80, 80))
        draw.rectangle((8 + idx * 6, 10, 38 + idx * 6, 32), outline=(0, 220, 255))
        draw.text((4, 36), "HUD", fill=(255, 255, 0))
        image.save(frames_dir / f"frame_{idx:03d}.bmp")


def _frames_dir_from_headless(headless_run, workspace: Path) -> Path:
    if headless_run["frame_paths"]:
        return Path(headless_run["frame_paths"][0]).parent
    frames_dir = workspace / "synthetic_captures"
    _write_synthetic_frames(frames_dir)
    return frames_dir


def _run_llm_playtest(project_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(project_root / "tools" / "llm_playtest.py"), *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _assert_report_shape(report_path: Path, expect_pass: bool) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0"
    assert report["overall_pass"] is expect_pass
    assert isinstance(report["frames"], list)
    if expect_pass:
        assert report["frames"], "expected per-frame verdicts"
        for frame in report["frames"]:
            assert {"path", "width", "height", "passes", "verdict"} <= frame.keys()
            verdict = frame["verdict"]
            assert {
                "renders_ok",
                "hud_visible",
                "geometry_coherent",
                "no_error_overlays",
                "confidence",
                "description",
            } <= verdict.keys()
    return report


@pytest.mark.playtest
@pytest.mark.slow
def test_llm_playtest_stub_passes(headless_run, project_root, llm_playtest_workspace):
    """Stub mode validates captured BMPs and emits a passing report."""
    frames_dir = _frames_dir_from_headless(headless_run, llm_playtest_workspace)
    report_path = llm_playtest_workspace / "stub_report.json"

    result = _run_llm_playtest(
        project_root,
        "--stub",
        "--frames-dir",
        str(frames_dir),
        "--report",
        str(report_path),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    report = _assert_report_shape(report_path, expect_pass=True)
    assert report["mode"] == "stub"
    assert report["passing_frames"] >= report["required_passing_frames"]


@pytest.mark.playtest
@pytest.mark.slow
def test_llm_playtest_live_passes_when_configured(
    headless_run, project_root, llm_playtest_workspace
):
    """Live mode is opt-in and requires Azure OpenAI credentials."""
    if not os.environ.get("LLM_PLAYTEST_API_KEY"):
        pytest.skip("LLM_PLAYTEST_API_KEY unset; live LLM playtest is opt-in")

    frames_dir = _frames_dir_from_headless(headless_run, llm_playtest_workspace)
    report_path = llm_playtest_workspace / "live_report.json"
    result = _run_llm_playtest(
        project_root,
        "--frames-dir",
        str(frames_dir),
        "--report",
        str(report_path),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    report = _assert_report_shape(report_path, expect_pass=True)
    assert report["mode"] == "live"


@pytest.mark.playtest
@pytest.mark.slow
def test_llm_playtest_stub_fails_gracefully_on_corrupt_bmp(
    project_root, llm_playtest_workspace
):
    """Corrupt sampled BMPs are harness errors with a JSON error report."""
    frames_dir = llm_playtest_workspace / "corrupt_captures"
    _write_synthetic_frames(frames_dir, count=1)
    (frames_dir / "frame_999.bmp").write_bytes(b"not a bmp")
    report_path = llm_playtest_workspace / "corrupt_report.json"

    result = _run_llm_playtest(
        project_root,
        "--stub",
        "--frames-dir",
        str(frames_dir),
        "--report",
        str(report_path),
    )

    assert result.returncode == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["mode"] == "error"
    assert report["overall_pass"] is False
    assert "failed to load frame" in report["error"]

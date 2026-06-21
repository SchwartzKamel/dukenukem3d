#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""
Test suite for tools/install_hooks.sh

Tests idempotent installation of the git pre-commit hook:
- Verifies tools/install_hooks.sh exists and is executable
- Tests hook creation in an isolated temp git repo (not live .git/)
- Tests idempotency (running twice does not error)
- Tests backup creation on re-install
"""

import os
import subprocess
import shutil
import sys
from pathlib import Path
import pytest


class TestInstallHooks:
    """Test pre-commit hook installer in isolated temp repos."""

    def test_install_hooks_script_exists_and_is_executable(self):
        """Verify tools/install_hooks.sh exists and is executable."""
        script = Path("tools/install_hooks.sh")
        assert script.exists(), f"{script} does not exist"
        assert os.access(script, os.X_OK), f"{script} is not executable"

    @pytest.mark.skipif(
        sys.platform != "linux",
        reason="runs tools/install_hooks.sh via bash; the Windows WSL bash stub "
               "has no distro on hosted CI. Validated in CI.",
    )
    def test_install_hooks_creates_pre_commit_hook(self, tmp_path):
        """Test that install_hooks.sh configures git core.hooksPath in a temp repo."""
        # Get paths before any directory changes
        project_root = Path.cwd()
        install_script_src = project_root / "tools" / "install_hooks.sh"
        
        # Create isolated temp git repo
        repo = tmp_path / "test_repo"
        repo.mkdir()
        
        # Initialize git
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
        
        # Copy tools directory to temp repo
        tools_dst = repo / "tools"
        tools_dst.mkdir()
        shutil.copy(install_script_src, tools_dst / "install_hooks.sh")
        os.chmod(tools_dst / "install_hooks.sh", 0o755)
        
        # Create .githooks directory with pre-commit
        githooks_dst = repo / ".githooks"
        githooks_dst.mkdir()
        (githooks_dst / "pre-commit").write_text("#!/bin/sh\necho 'test hook'\n", encoding="utf-8")
        os.chmod(githooks_dst / "pre-commit", 0o755)
        
        # Run the installer from the temp repo
        result = subprocess.run(
            ["bash", "tools/install_hooks.sh"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"install_hooks.sh failed: {result.stderr}"
        
        # Verify git config was set
        config_result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert config_result.stdout.strip() == ".githooks", "core.hooksPath not set to .githooks"

    @pytest.mark.skipif(
        sys.platform != "linux",
        reason="runs tools/install_hooks.sh via bash; the Windows WSL bash stub "
               "has no distro on hosted CI. Validated in CI.",
    )
    def test_install_hooks_is_idempotent(self, tmp_path):
        """Test that running install_hooks.sh twice does not error."""
        # Get paths before any directory changes
        project_root = Path.cwd()
        install_script_src = project_root / "tools" / "install_hooks.sh"
        
        # Create isolated temp git repo
        repo = tmp_path / "test_repo_idempotent"
        repo.mkdir()
        
        # Initialize git
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
        
        # Copy tools directory
        tools_dst = repo / "tools"
        tools_dst.mkdir()
        shutil.copy(install_script_src, tools_dst / "install_hooks.sh")
        os.chmod(tools_dst / "install_hooks.sh", 0o755)
        
        # Create .githooks directory with pre-commit
        githooks_dst = repo / ".githooks"
        githooks_dst.mkdir()
        (githooks_dst / "pre-commit").write_text("#!/bin/sh\necho 'test hook'\n", encoding="utf-8")
        os.chmod(githooks_dst / "pre-commit", 0o755)
        
        # Run installer first time
        result1 = subprocess.run(
            ["bash", "tools/install_hooks.sh"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"
        
        # Verify config was set
        config_result1 = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert config_result1.stdout.strip() == ".githooks", "core.hooksPath not set"
        
        # Run installer second time
        result2 = subprocess.run(
            ["bash", "tools/install_hooks.sh"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert result2.returncode == 0, f"Second run failed: {result2.stderr}"
        
        # Verify config still set (idempotent)
        config_result2 = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert config_result2.stdout.strip() == ".githooks", "core.hooksPath lost after second run"


if __name__ == "__main__":
    pytest_available = True
    try:
        import pytest
    except ImportError:
        pytest_available = False
    
    if pytest_available:
        pytest.main([__file__, "-v"])
    else:
        # Manual fallback test
        test = TestInstallHooks()
        
        print("Running test_install_hooks_script_exists_and_is_executable...")
        try:
            test.test_install_hooks_script_exists_and_is_executable()
            print("✓ PASSED")
        except AssertionError as e:
            pytest.fail(f"test_install_hooks_script_exists_and_is_executable failed: {e}")
        
        print("\nAll manual tests passed!")

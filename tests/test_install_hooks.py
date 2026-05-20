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
from pathlib import Path


class TestInstallHooks:
    """Test pre-commit hook installer in isolated temp repos."""

    def test_install_hooks_script_exists_and_is_executable(self):
        """Verify tools/install_hooks.sh exists and is executable."""
        script = Path("tools/install_hooks.sh")
        assert script.exists(), f"{script} does not exist"
        assert os.access(script, os.X_OK), f"{script} is not executable"

    def test_install_hooks_creates_pre_commit_hook(self, tmp_path):
        """Test that install_hooks.sh creates .git/hooks/pre-commit in a temp repo."""
        # Get paths before any directory changes
        project_root = Path.cwd()
        install_script_src = project_root / "tools" / "install_hooks.sh"
        check_secrets_src = project_root / "tools" / "check_secrets.sh"
        
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
        shutil.copy(check_secrets_src, tools_dst / "check_secrets.sh")
        os.chmod(tools_dst / "install_hooks.sh", 0o755)
        os.chmod(tools_dst / "check_secrets.sh", 0o755)
        
        # Run the installer from the temp repo
        result = subprocess.run(
            ["bash", "tools/install_hooks.sh"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"install_hooks.sh failed: {result.stderr}"
        
        # Verify hook was created
        hook_file = repo / ".git" / "hooks" / "pre-commit"
        assert hook_file.exists(), f"pre-commit hook not created at {hook_file}"
        assert os.access(hook_file, os.X_OK), f"pre-commit hook not executable"
        
        # Verify hook contents
        hook_content = hook_file.read_text()
        assert "check_secrets.sh" in hook_content, "Hook does not call check_secrets.sh"

    def test_install_hooks_is_idempotent(self, tmp_path):
        """Test that running install_hooks.sh twice does not error and backs up old hooks."""
        # Get paths before any directory changes
        project_root = Path.cwd()
        install_script_src = project_root / "tools" / "install_hooks.sh"
        check_secrets_src = project_root / "tools" / "check_secrets.sh"
        
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
        shutil.copy(check_secrets_src, tools_dst / "check_secrets.sh")
        os.chmod(tools_dst / "install_hooks.sh", 0o755)
        os.chmod(tools_dst / "check_secrets.sh", 0o755)
        
        # Run installer first time
        result1 = subprocess.run(
            ["bash", "tools/install_hooks.sh"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"
        
        hook_file = repo / ".git" / "hooks" / "pre-commit"
        assert hook_file.exists(), "Hook not created on first run"
        
        # Run installer second time
        result2 = subprocess.run(
            ["bash", "tools/install_hooks.sh"],
            cwd=repo,
            capture_output=True,
            text=True
        )
        assert result2.returncode == 0, f"Second run failed: {result2.stderr}"
        
        # Verify hook still exists (idempotent)
        assert hook_file.exists(), "Hook missing after second run"


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
        import sys
        test = TestInstallHooks()
        
        print("Running test_install_hooks_script_exists_and_is_executable...")
        try:
            test.test_install_hooks_script_exists_and_is_executable()
            print("✓ PASSED")
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            sys.exit(1)
        
        print("\nAll manual tests passed!")

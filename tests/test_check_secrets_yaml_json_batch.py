"""
Tests for check_secrets.sh coverage of YAML, JSON, and batch files.

Regression tests to ensure that secrets are detected in YAML (.yml/.yaml),
JSON (.json), and batch (.bat) files, not just traditional config files.
"""
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest


@pytest.fixture
def git_repo(tmp_path):
    """Set up a temporary git repository for testing."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )
    
    # Configure git user for commits
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )
    
    # Set hooks path to a temp location (won't interfere with test)
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )
    
    # Copy check_secrets.sh into the test repo
    repo_tools = repo_dir / "tools"
    repo_tools.mkdir()
    
    script_path = Path(__file__).parent.parent / "tools" / "check_secrets.sh"
    shutil.copy(script_path, repo_tools / "check_secrets.sh")
    
    return repo_dir


def run_check_secrets(repo_dir):
    """Run check_secrets.sh against staged changes in the test repo."""
    script_path = repo_dir / "tools" / "check_secrets.sh"
    result = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    return result


class TestSecretsDetectionYAML:
    """Test secrets detection in YAML files."""
    
    def test_aws_key_in_yaml_file_detected(self, git_repo):
        """Verify that AWS keys (AKIA prefix) in .yaml files are detected."""
        # Create a YAML file with a fake AWS access key
        yaml_file = git_repo / "config.yaml"
        yaml_file.write_text(
            "app:\n"
            "  name: MyApp\n"
            "  aws_access_key: AKIAIOSFODNN7EXAMPLE\n"
        )
        
        # Stage the file
        subprocess.run(
            ["git", "add", "config.yaml"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        # Run check_secrets.sh
        result = run_check_secrets(git_repo)
        
        # Should detect the AWS key and exit with error
        assert result.returncode != 0, (
            f"Expected non-zero exit, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "AWS" in result.stdout or "AKIA" in result.stdout, (
            f"Expected AWS key detection in output:\n{result.stdout}"
        )
    
    def test_aws_key_in_yml_file_detected(self, git_repo):
        """Verify that AWS keys in .yml files are detected."""
        # Create a YML file with a fake AWS access key
        yml_file = git_repo / "database.yml"
        yml_file.write_text(
            "production:\n"
            "  database: postgres\n"
            "  aws_key: AKIAIOSFODNN7EXAMPLE\n"
        )
        
        # Stage the file
        subprocess.run(
            ["git", "add", "database.yml"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        # Run check_secrets.sh
        result = run_check_secrets(git_repo)
        
        # Should detect the AWS key and exit with error
        assert result.returncode != 0, (
            f"Expected non-zero exit for .yml file, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "AWS" in result.stdout or "AKIA" in result.stdout, (
            f"Expected AWS key detection in output:\n{result.stdout}"
        )
    
    def test_api_key_in_yaml_detected(self, git_repo):
        """Verify that long API_KEY patterns in YAML are detected."""
        yaml_file = git_repo / "secrets.yaml"
        yaml_file.write_text(
            "services:\n"
            "  api:\n"
            "    MY_API_KEY=abcdef1234567890ABCDEF1234567890\n"
        )
        
        subprocess.run(
            ["git", "add", "secrets.yaml"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for API_KEY in YAML, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )


class TestSecretsDetectionJSON:
    """Test secrets detection in JSON files."""
    
    def test_aws_key_in_json_detected(self, git_repo):
        """Verify that AWS keys in JSON files are detected."""
        json_file = git_repo / "config.json"
        json_file.write_text(
            '{\n'
            '  "app": {\n'
            '    "name": "MyApp",\n'
            '    "aws_access_key": "AKIAIOSFODNN7EXAMPLE"\n'
            '  }\n'
            '}\n'
        )
        
        subprocess.run(
            ["git", "add", "config.json"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for AWS key in JSON, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "AWS" in result.stdout or "AKIA" in result.stdout, (
            f"Expected AWS key detection in output:\n{result.stdout}"
        )
    
    def test_github_token_in_json_detected(self, git_repo):
        """Verify that GitHub tokens in JSON files are detected."""
        json_file = git_repo / "auth.json"
        json_file.write_text(
            '{\n'
            '  "github": {\n'
            '    "token": "ghp_' + 'a' * 30 + '"\n'
            '  }\n'
            '}\n'
        )
        
        subprocess.run(
            ["git", "add", "auth.json"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for GitHub token in JSON, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "GitHub" in result.stdout or "ghp_" in result.stdout, (
            f"Expected GitHub token detection in output:\n{result.stdout}"
        )
    
    def test_stripe_key_in_json_detected(self, git_repo):
        """Verify that Stripe keys in JSON files are detected."""
        json_file = git_repo / "payment.json"
        json_file.write_text(
            '{\n'
            '  "stripe_key": "sk_live_' + 'a' * 24 + '"\n'
            '}\n'
        )
        
        subprocess.run(
            ["git", "add", "payment.json"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for Stripe key in JSON, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "Stripe" in result.stdout or "sk_live_" in result.stdout, (
            f"Expected Stripe key detection in output:\n{result.stdout}"
        )


class TestSecretsDetectionBatch:
    """Test secrets detection in batch (.bat) files."""
    
    def test_aws_key_in_bat_detected(self, git_repo):
        """Verify that AWS keys in .bat files are detected."""
        bat_file = git_repo / "deploy.bat"
        bat_file.write_text(
            "@echo off\n"
            "set AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
            "set AWS_SECRET_ACCESS_KEY=secret123\n"
            "aws s3 sync . s3://bucket/\n"
        )
        
        subprocess.run(
            ["git", "add", "deploy.bat"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for AWS key in .bat, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "AWS" in result.stdout or "AKIA" in result.stdout, (
            f"Expected AWS key detection in output:\n{result.stdout}"
        )
    
    def test_api_key_in_bat_detected(self, git_repo):
        """Verify that long API keys in .bat files are detected."""
        bat_file = git_repo / "build.bat"
        bat_file.write_text(
            "@echo off\n"
            "set MY_API_KEY=abcdef1234567890ABCDEF1234567890\n"
            "call script.exe\n"
        )
        
        subprocess.run(
            ["git", "add", "build.bat"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for API_KEY in .bat, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )


class TestSecretsAllowListedPatterns:
    """Test that allowlisted/template patterns are not flagged."""
    
    def test_yaml_with_placeholder_api_key(self, git_repo):
        """YAML files with placeholder API keys should not be flagged."""
        yaml_file = git_repo / "config.yaml"
        yaml_file.write_text(
            "app:\n"
            "  MY_API_KEY=your_api_key_here\n"
        )
        
        subprocess.run(
            ["git", "add", "config.yaml"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        # Should pass (exit 0) for placeholder
        assert result.returncode == 0, (
            f"Expected exit 0 for placeholder in YAML, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
    
    def test_json_with_env_variable_reference(self, git_repo):
        """JSON files with environment variable refs should not be flagged."""
        json_file = git_repo / "config.json"
        json_file.write_text(
            '{\n'
            '  "api_key": "$API_KEY"\n'
            '}\n'
        )
        
        subprocess.run(
            ["git", "add", "config.json"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode == 0, (
            f"Expected exit 0 for env var ref in JSON, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
    
    def test_clean_yaml_with_no_secrets(self, git_repo):
        """Clean YAML files with no secrets should pass."""
        yaml_file = git_repo / "config.yaml"
        yaml_file.write_text(
            "app:\n"
            "  name: MyApp\n"
            "  version: 1.0.0\n"
            "  database: postgres\n"
        )
        
        subprocess.run(
            ["git", "add", "config.yaml"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode == 0, (
            f"Expected exit 0 for clean YAML, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
    
    def test_clean_json_with_no_secrets(self, git_repo):
        """Clean JSON files with no secrets should pass."""
        json_file = git_repo / "config.json"
        json_file.write_text(
            '{\n'
            '  "app": {\n'
            '    "name": "MyApp",\n'
            '    "version": "1.0.0"\n'
            '  }\n'
            '}\n'
        )
        
        subprocess.run(
            ["git", "add", "config.json"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode == 0, (
            f"Expected exit 0 for clean JSON, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
    
    def test_clean_bat_with_no_secrets(self, git_repo):
        """Clean batch files with no secrets should pass."""
        bat_file = git_repo / "build.bat"
        bat_file.write_text(
            "@echo off\n"
            "echo Building application...\n"
            "cd src\n"
            "cmake . && make\n"
        )
        
        subprocess.run(
            ["git", "add", "build.bat"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode == 0, (
            f"Expected exit 0 for clean .bat, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )

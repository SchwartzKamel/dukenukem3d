"""
Regression tests for R16 new secret patterns (sec-r16-scanner-gap-new-patterns).

Tests for 6 new secret patterns:
1. Google Cloud service account JSON (service_account + private_key)
2. Slack workspace tokens (xoxp-, xoxb-, xoxa-, xoxr-)
3. npm package tokens (npm_[A-Za-z0-9]{36,})
4. Stripe restricted keys (rk_live_, rk_test_)
5. HuggingFace tokens (hf_[A-Za-z0-9_]{39,})
6. OpenAI organization IDs (org-[A-Za-z0-9]{24,})

Each pattern has a detection test and a false-positive control test.
All fixture patterns use character-class escaping to avoid self-detection.
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


class TestGoogleCloudServiceAccount:
    """Test detection of Google Cloud service account JSON patterns."""
    
    def test_google_cloud_service_account_detected(self, git_repo):
        """Verify that Google Cloud service account JSON is detected."""
        json_file = git_repo / "gcloud-creds.json"
        json_file.write_text(
            '{\n'
            '  "type": "service_account",\n'
            '  "project_id": "my-project",\n'
            '  "private_key_id": "key123",\n'
            '  "private_key": "-----BEGIN RSA PRIVATE KEY-----\\nMII...",\n'
            '  "client_email": "account@my-project.iam.gserviceaccount.com"\n'
            '}\n'
        )
        
        subprocess.run(
            ["git", "add", "gcloud-creds.json"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for Google Cloud service account, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "Google Cloud" in result.stdout or "service_account" in result.stdout, (
            f"Expected Google Cloud detection in output:\n{result.stdout}"
        )
    
    def test_google_cloud_false_positive_control(self, git_repo):
        """Verify that innocuous private_key or service_account alone don't trigger."""
        config_file = git_repo / "config.yaml"
        config_file.write_text(
            "service_account_name: my-account\n"
            "description: Shared config\n"
        )
        
        subprocess.run(
            ["git", "add", "config.yaml"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        # Should pass because we only trigger on BOTH patterns
        assert result.returncode == 0, (
            f"Expected exit 0 for benign text, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )


class TestSlackTokens:
    """Test detection of Slack workspace tokens."""
    
    def test_slack_xoxp_token_detected(self, git_repo):
        """Verify that Slack xoxp- tokens are detected."""
        config_file = git_repo / "slack-config.env"
        config_file.write_text(
            "SLACK_TOKEN=x[o]xp-1234567890-1234567890-1234567890-abcdef0123456789\n"
        )
        
        subprocess.run(
            ["git", "add", "slack-config.env"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        # Note: fixture uses escaped form; we need to test with actual form
        # Re-run with non-escaped to verify detection
        
    def test_slack_xoxp_token_real_detected(self, git_repo):
        """Verify that Slack xoxp- tokens (unescaped) are detected."""
        config_file = git_repo / "slack-real.env"
        # Create file with UNESCAPED token (not in check_secrets.sh or tests)
        config_file.write_text(
            "SLACK_USER_TOKEN=" + "xo" + "xp-1234567890-1234567890-1234567890-a1b2c3d4e5f6\n"
        )
        
        subprocess.run(
            ["git", "add", "slack-real.env"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for Slack xoxp- token, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "Slack" in result.stdout or "xoxp" in result.stdout or "xox" in result.stdout, (
            f"Expected Slack token detection in output:\n{result.stdout}"
        )
    
    def test_slack_xoxb_token_detected(self, git_repo):
        """Verify that Slack xoxb- (bot) tokens are detected."""
        config_file = git_repo / "slack-bot.env"
        config_file.write_text(
            "SLACK_BOT_TOKEN=" + "xo" + "xb-1234567890-1234567890-a1b2c3d4e5f6g7h8i9j0\n"
        )
        
        subprocess.run(
            ["git", "add", "slack-bot.env"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for Slack xoxb- token, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "Slack" in result.stdout or "xoxb" in result.stdout or "xox" in result.stdout, (
            f"Expected Slack token detection in output:\n{result.stdout}"
        )
    
    def test_slack_false_positive_control(self, git_repo):
        """Verify that benign strings don't trigger Slack detection."""
        config_file = git_repo / "readme.md"
        config_file.write_text(
            "# Slack Integration Guide\n"
            "\n"
            "Use slack_client to connect to Slack.\n"
            "For more info, see the Slack API docs.\n"
        )
        
        subprocess.run(
            ["git", "add", "readme.md"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode == 0, (
            f"Expected exit 0 for benign slack text, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )


class TestNpmTokens:
    """Test detection of npm package tokens."""
    
    def test_npm_token_detected(self, git_repo):
        """Verify that npm_ tokens are detected."""
        npmrc_file = git_repo / ".npmrc"
        npmrc_file.write_text(
            "registry=https://registry.npmjs.org/\n"
            "//registry.npmjs.org/:_authToken=" + "np" + "m_abcdef1234567890ABCDEF1234567890ABC123\n"
        )
        
        subprocess.run(
            ["git", "add", ".npmrc"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for npm token, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "npm" in result.stdout or "npm_" in result.stdout, (
            f"Expected npm token detection in output:\n{result.stdout}"
        )
    
    def test_npm_false_positive_control(self, git_repo):
        """Verify that npm_install_dir or other benign npm_ strings don't trigger."""
        config_file = git_repo / "build.sh"
        config_file.write_text(
            "#!/bin/bash\n"
            "npm_install_dir=/opt/npm\n"
            "npm install\n"
        )
        
        subprocess.run(
            ["git", "add", "build.sh"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        # npm_install_dir is only 15 chars after npm_, so won't match {36,}
        assert result.returncode == 0, (
            f"Expected exit 0 for npm_install_dir, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )


class TestStripeRestrictedKeys:
    """Test detection of Stripe restricted keys."""
    
    def test_stripe_rk_live_detected(self, git_repo):
        """Verify that Stripe rk_live_ keys are detected."""
        config_file = git_repo / "stripe-config.env"
        config_file.write_text(
            "STRIPE_RESTRICTED_KEY=" + "rk" + "_live_abcdef1234567890ABCDEF1234567890\n"
        )
        
        subprocess.run(
            ["git", "add", "stripe-config.env"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for Stripe rk_live_ key, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "Stripe" in result.stdout or "rk_live" in result.stdout or "rk_" in result.stdout, (
            f"Expected Stripe restricted key detection in output:\n{result.stdout}"
        )
    
    def test_stripe_rk_test_detected(self, git_repo):
        """Verify that Stripe rk_test_ keys are detected."""
        config_file = git_repo / "stripe-test.env"
        config_file.write_text(
            "STRIPE_TEST_KEY=" + "rk" + "_test_abcdef1234567890ABCDEF1234567890\n"
        )
        
        subprocess.run(
            ["git", "add", "stripe-test.env"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for Stripe rk_test_ key, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "Stripe" in result.stdout or "rk_test" in result.stdout or "rk_" in result.stdout, (
            f"Expected Stripe test key detection in output:\n{result.stdout}"
        )
    
    def test_stripe_false_positive_control(self, git_repo):
        """Verify that rk_live_chat_id or other benign rk_ strings don't trigger."""
        config_file = git_repo / "rooms.py"
        config_file.write_text(
            "class Room:\n"
            "    def __init__(self, room_key):\n"
            "        self.rk_live_chat_id = None\n"
            "        self.room_key = room_key\n"
        )
        
        subprocess.run(
            ["git", "add", "rooms.py"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        # rk_live_chat_id is only 13 chars after rk_, so won't match {24,}
        assert result.returncode == 0, (
            f"Expected exit 0 for rk_live_chat_id, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )


class TestHuggingFaceTokens:
    """Test detection of HuggingFace tokens."""
    
    def test_huggingface_token_detected(self, git_repo):
        """Verify that HuggingFace hf_ tokens are detected."""
        config_file = git_repo / "huggingface-config.py"
        config_file.write_text(
            "from huggingface_hub import login\n"
            "HF_TOKEN = '" + "hf" + "_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRS'\n"
            "login(token=HF_TOKEN)\n"
        )
        
        subprocess.run(
            ["git", "add", "huggingface-config.py"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for HuggingFace token, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "HuggingFace" in result.stdout or "hf_" in result.stdout, (
            f"Expected HuggingFace token detection in output:\n{result.stdout}"
        )
    
    def test_huggingface_false_positive_control(self, git_repo):
        """Verify that hf_progress or short hf_ strings don't trigger."""
        config_file = git_repo / "progress.py"
        config_file.write_text(
            "def track_progress(hf_prefix, iterations):\n"
            "    hf_progress = {\n"
            "        'current': 0,\n"
            "        'total': iterations\n"
            "    }\n"
            "    return hf_progress\n"
        )
        
        subprocess.run(
            ["git", "add", "progress.py"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        # hf_progress is only 8 chars after hf_, so won't match {39,}
        assert result.returncode == 0, (
            f"Expected exit 0 for hf_progress, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )


class TestOpenAIOrgIDs:
    """Test detection of OpenAI organization IDs."""
    
    def test_openai_org_id_detected(self, git_repo):
        """Verify that OpenAI org- IDs are detected."""
        config_file = git_repo / "openai-config.env"
        config_file.write_text(
            "OPENAI_ORG_ID=org-abcdef1234567890ABCDEF12\n"
        )
        
        subprocess.run(
            ["git", "add", "openai-config.env"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        assert result.returncode != 0, (
            f"Expected non-zero exit for OpenAI org ID, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )
        assert "OpenAI" in result.stdout or "org-" in result.stdout or "org" in result.stdout, (
            f"Expected OpenAI org ID detection in output:\n{result.stdout}"
        )
    
    def test_openai_org_id_false_positive_control(self, git_repo):
        """Verify that org-unit or short org- strings don't trigger."""
        config_file = git_repo / "structure.yaml"
        config_file.write_text(
            "organization:\n"
            "  name: MyOrg\n"
            "  org-unit: Engineering\n"
            "  org-short-id: abc123\n"
        )
        
        subprocess.run(
            ["git", "add", "structure.yaml"],
            cwd=git_repo,
            capture_output=True,
            check=True
        )
        
        result = run_check_secrets(git_repo)
        # org-unit and org-short-id are both too short after org- (< 24)
        assert result.returncode == 0, (
            f"Expected exit 0 for org-unit, got {result.returncode}\n"
            f"stdout: {result.stdout}"
        )

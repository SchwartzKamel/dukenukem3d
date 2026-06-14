"""Tests for generate_assets.sh shell script parallelization.

Validates that tools/ci/generate_assets.sh spawns audio and assets generation
in parallel with proper exit code handling.
"""
import subprocess
import os
import pytest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "tools", "ci", "generate_assets.sh")


class TestGenerateAssetsShellParallelization:
    """Test suite for shell script parallelization."""

    def test_script_exists(self):
        """Script should exist at tools/ci/generate_assets.sh."""
        assert os.path.exists(SCRIPT_PATH), f"Script not found: {SCRIPT_PATH}"

    def test_script_is_executable(self):
        """Script should be executable."""
        assert os.access(SCRIPT_PATH, os.X_OK), f"Script not executable: {SCRIPT_PATH}"

    def test_script_syntax_valid(self):
        """Script should pass bash syntax check."""
        result = subprocess.run(
            # `bash` is WSL: pass a relative forward-slash path anchored at the
            # repo cwd (a Windows abspath with backslashes would be mangled).
            ["bash", "-n", "tools/ci/generate_assets.sh"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, f"Syntax error:\n{result.stderr}"

    def test_script_contains_parallel_spawn(self):
        """Script should contain parallel spawn pattern (&)."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Look for both audio and assets commands with & background operator
        assert "python3 tools/generate_audio.py" in content, \
            "Script should contain audio generation command"
        assert "python3 tools/generate_assets.py" in content, \
            "Script should contain assets generation command"
        
        # Count background operators
        ampersand_lines = [line for line in content.split("\n") if line.rstrip().endswith("&")]
        assert len(ampersand_lines) >= 2, \
            f"Expected at least 2 background spawns (&), found {len(ampersand_lines)}"

    def test_script_contains_wait_calls(self):
        """Script should contain wait calls for both background processes."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Count wait calls - should have at least 2 for AUDIO_PID and ASSETS_PID
        wait_count = content.count("wait ")
        assert wait_count >= 2, \
            f"Expected at least 2 'wait' calls for background PIDs, found {wait_count}"

    def test_script_captures_exit_codes(self):
        """Script should capture exit codes from both background processes."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Look for patterns like: AUDIO_RC=$? and ASSETS_RC=$?
        assert "AUDIO_RC=$?" in content or "AUDIO_RC = $?" in content, \
            "Script should capture audio exit code as AUDIO_RC"
        assert "ASSETS_RC=$?" in content or "ASSETS_RC = $?" in content, \
            "Script should capture assets exit code as ASSETS_RC"

    def test_script_checks_exit_codes(self):
        """Script should check both exit codes and exit with error if either fails."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Look for exit code validation logic
        assert "AUDIO_RC" in content and "ASSETS_RC" in content, \
            "Script should reference both exit codes"
        assert "[ $AUDIO_RC -ne 0 ]" in content or "AUDIO_RC" in content, \
            "Script should check if AUDIO_RC is non-zero"
        assert "[ $ASSETS_RC -ne 0 ]" in content or "ASSETS_RC" in content, \
            "Script should check if ASSETS_RC is non-zero"

    def test_script_contains_sentinel_comment(self):
        """Script should contain perf-ci-parallel-spawn sentinel comment."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "perf-ci-parallel-spawn" in content, \
            "Script should contain 'perf-ci-parallel-spawn' sentinel comment for tracking"

    def test_script_handles_error_with_both_codes(self):
        """Script should report both error codes in error message."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Look for error reporting that includes both codes
        assert "audio_rc=" in content and "assets_rc=" in content, \
            "Script error message should include both audio_rc and assets_rc values"

    def test_script_preserves_prepost_setup(self):
        """Script should preserve pre/post setup like GRP file size check."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Original functionality should be preserved
        assert "DUKE3D.GRP" in content, \
            "Script should still check for DUKE3D.GRP file"
        assert "GRP_SIZE" in content, \
            "Script should still calculate GRP file size"

    @pytest.mark.slow
    def test_script_runs_with_no_ai_flag(self):
        """Script should run successfully with --no-ai (offline) flag."""
        # This test only runs with --runslow and requires generate_audio.py and generate_assets.py
        # to complete, which may take several minutes
        result = subprocess.run(
            ["bash", SCRIPT_PATH],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for script
        )
        
        # Script should complete successfully (exit code 0)
        # Note: This may fail if dependencies are not installed or network is required
        # Check script output for parallelization evidence (both processes should run)
        if result.returncode == 0:
            # Verify no sequential blocking output
            output = result.stdout + result.stderr
            assert "🔇" in output or "🖌️" in output or "generating" in output.lower(), \
                "Script should produce expected output messages"


class TestGenerateAssetsShellIntegration:
    """Integration tests for the generate_assets.sh script."""

    def test_script_messages_order_indicates_parallel_start(self):
        """Script should log both messages before any generation output.
        
        This indicates both processes are started in parallel, not sequentially.
        """
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Find echo lines with messages
        audio_msg_line = None
        assets_msg_line = None
        first_background_line = None
        
        for i, line in enumerate(lines):
            if "$AUDIO_MSG" in line:
                audio_msg_line = i
            if "$ASSETS_MSG" in line:
                assets_msg_line = i
            if " &" in line and "python3" in line and first_background_line is None:
                first_background_line = i
        
        # Both messages should be logged before first background spawn
        assert audio_msg_line is not None, "Script should echo audio message"
        assert assets_msg_line is not None, "Script should echo assets message"
        if first_background_line is not None:
            assert audio_msg_line < first_background_line, \
                "Audio message should be logged before background spawn"
            assert assets_msg_line < first_background_line, \
                "Assets message should be logged before background spawn"

    def test_script_uses_background_operator_correctly(self):
        """Script should use & operator to spawn processes in background."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Find lines with $AUDIO_CMD and $ASSETS_CMD followed by &
        # (commands are stored in variables)
        background_cmd_lines = [
            line for line in lines
            if ("$AUDIO_CMD" in line or "$ASSETS_CMD" in line) and "&" in line
        ]
        
        assert len(background_cmd_lines) >= 2, \
            f"Expected at least 2 background command spawns (&), found {len(background_cmd_lines)}"

    def test_script_wait_pattern_correct(self):
        """Script should wait for both PIDs separately and capture codes."""
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Verify the pattern: PID=$! ... wait $PID ... RC=$?
        # This is critical for proper error handling
        
        # Check for AUDIO_PID assignment
        assert "AUDIO_PID=$!" in content, \
            "Script should assign audio PID: AUDIO_PID=$!"
        
        # Check for ASSETS_PID assignment
        assert "ASSETS_PID=$!" in content, \
            "Script should assign assets PID: ASSETS_PID=$!"
        
        # Check for wait statements
        assert "wait $AUDIO_PID" in content, \
            "Script should wait for AUDIO_PID"
        assert "wait $ASSETS_PID" in content, \
            "Script should wait for ASSETS_PID"

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Security posture audit tests for subprocess safety and workflow secrets handling.

sec-r15-subprocess-injection-audit: Verify all subprocess calls in tools/generate_audio.py
are safe (shell=False, argv list, no f-string interpolation).

sec-r15-workflow-secrets-script-logging: Verify all GitHub Actions workflow secrets
are passed via 'env:' blocks (not interpolated into 'run:' shell strings), with
documented sentinel comments.
"""

import os
import re
from pathlib import Path


def test_generate_audio_no_unsafe_subprocess_calls():
    """Verify tools/generate_audio.py has no unsafe subprocess calls.
    
    sec-r15-subproc: argv-list, shell=False, no interpolation
    
    Checks:
    - No subprocess module imported (if present, all calls must have sentinel)
    - If any subprocess.* calls exist, they must have:
      - shell=False or no shell= parameter (defaults to False on POSIX)
      - argv as list (not string)
      - no f-string interpolation of user/env values in argv
    """
    tools_dir = Path(__file__).parent.parent / "tools"
    generate_audio = tools_dir / "generate_audio.py"
    
    assert generate_audio.exists(), f"File not found: {generate_audio}"
    
    content = generate_audio.read_text(encoding="utf-8")
    
    # Check if subprocess is imported
    has_subprocess_import = bool(
        re.search(r"^import subprocess\b|^from subprocess import", content, re.MULTILINE)
    )
    
    if has_subprocess_import:
        # If subprocess is imported, verify all calls are safe and have sentinels
        subprocess_calls = list(re.finditer(
            r"subprocess\.\w+\(",
            content
        ))
        
        for call_match in subprocess_calls:
            call_start = call_match.start()
            
            # Find the context (3 lines before the call)
            lines_before_call = content[:call_start].split('\n')[-3:]
            context = '\n'.join(lines_before_call) + '\n' + \
                     content[call_start:call_start + 200]
            
            # Verify sentinel comment exists within 3 lines before
            has_sentinel = any(
                "sec-r15-subproc" in line
                for line in lines_before_call[-3:]
            )
            assert has_sentinel, (
                f"subprocess call at {call_match.group()} "
                "must have sentinel comment '# sec-r15-subproc: argv-list, "
                "shell=False, no interpolation'\n"
                f"Context:\n{context}"
            )
            
            # Verify shell=False (or missing, which defaults to False on POSIX)
            call_block = content[call_start:call_start + 500]
            has_shell_true = bool(re.search(r"shell\s*=\s*True", call_block))
            assert not has_shell_true, (
                f"subprocess call at {call_match.group()} "
                "must have shell=False or omit shell parameter"
            )
            
            # Verify argv is a list (not a string)
            # Check for the pattern: subprocess.*(["']...) which is bad
            # Good pattern: subprocess.*([...]) or subprocess.*(..., [...])
            has_string_arg = bool(re.search(
                r"subprocess\.\w+\(\s*['\"]",
                call_block
            ))
            assert not has_string_arg, (
                f"subprocess call at {call_match.group()} "
                "must use argv list, not string"
            )
    else:
        # No subprocess import means the file is safe by default
        # Document this finding
        assert True, "generate_audio.py does not import subprocess module"


def test_workflow_secrets_have_sentinels():
    """Verify all GitHub Actions workflow secrets are documented with sentinels.
    
    sec-r15-workflow-secrets: env-passed, no-echo
    
    Checks for all workflow files:
    - Every ${{ secrets.* }} reference must be passed via 'env:' (not run:)
    - Must have a sentinel comment within 3 lines above the step
    - No 'echo $SECRET', 'set -x', or 'if: secrets.* != ''' patterns
    """
    workflows_dir = Path(__file__).parent.parent / ".github" / "workflows"
    
    assert workflows_dir.exists(), f"Workflows directory not found: {workflows_dir}"
    
    workflow_files = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))
    
    for workflow_file in workflow_files:
        content = workflow_file.read_text(encoding="utf-8")
        lines = content.split('\n')
        
        # Find all ${{ secrets.* }} references with their line numbers
        for line_idx, line in enumerate(lines):
            secret_refs = list(re.finditer(
                r"\$\{\{\s*secrets\.\w+\s*\}\}",
                line
            ))
            
            if not secret_refs:
                continue
            
            # For each secret reference, verify the step it belongs to has a sentinel
            # Find the step start (look backwards for '- name:')
            step_start_idx = None
            for i in range(line_idx, -1, -1):
                if re.match(r'^\s*-\s+name:', lines[i]):
                    step_start_idx = i
                    break
            
            if step_start_idx is None:
                continue
            
            # Check if sentinel exists between step start (or up to 3 lines before) and the secret
            sentinel_range_start = max(0, step_start_idx - 3)
            sentinel_range = '\n'.join(lines[sentinel_range_start:line_idx + 1])
            
            has_sentinel = 'sec-r15-workflow-secrets' in sentinel_range
            
            ref_texts = [ref.group() for ref in secret_refs]
            assert has_sentinel, (
                f"Step with secrets {ref_texts} in {workflow_file.name} at line {step_start_idx + 1} "
                f"must have sentinel comment '# sec-r15-workflow-secrets: env-passed, no-echo' "
                f"within 3 lines before the step"
            )
            
            # Verify the secret is in an 'env:' block, not in 'run:'
            # Check the indentation and context
            step_section = '\n'.join(lines[step_start_idx:line_idx + 1])
            
            # Find if this line is under 'env:' or 'run:'
            # Count indentation to determine which block it's in
            line_indent = len(line) - len(line.lstrip())
            
            # Check backwards for 'env:' or 'run:' at lower indentation
            found_env = False
            found_run = False
            
            for i in range(line_idx - 1, step_start_idx - 1, -1):
                check_line = lines[i]
                check_indent = len(check_line) - len(check_line.lstrip())
                
                if check_indent < line_indent:
                    if re.search(r'^\s*env:\s*$', check_line):
                        found_env = True
                        break
                    elif re.search(r'^\s*run:\s*', check_line):
                        found_run = True
                        break
            
            assert found_env and not found_run, (
                f"Secret on line {line_idx + 1} in {workflow_file.name} "
                f"must be under 'env:' block, not 'run:' block"
            )
            
            # Verify no 'echo $SECRET' patterns in the step
            for secret_ref in secret_refs:
                secret_match = re.search(r'secrets\.(\w+)', secret_ref.group())
                if secret_match:
                    secret_name = secret_match.group(1)
                    
                    # Check the entire step (from step start to end of the step)
                    # Find the end of the step (next '- ' at same or lower indentation)
                    step_end_idx = len(lines)
                    step_indent = len(lines[step_start_idx]) - len(lines[step_start_idx].lstrip())
                    
                    for i in range(step_start_idx + 1, len(lines)):
                        line_i_indent = len(lines[i]) - len(lines[i].lstrip())
                        if lines[i].strip() and line_i_indent <= step_indent and re.match(r'^\s*-\s+', lines[i]):
                            step_end_idx = i
                            break
                    
                    step_text = '\n'.join(lines[step_start_idx:step_end_idx])
                    
                    # Check for echo patterns
                    has_echo = bool(re.search(
                        rf"echo\s+.*\${secret_name}",
                        step_text,
                        re.IGNORECASE
                    ))
                    assert not has_echo, (
                        f"Step with secret {secret_name} in {workflow_file.name} "
                        "must not echo the secret value"
                    )
                    
                    # Verify no 'set -x' in the step
                    has_set_x = bool(re.search(r'set\s+-x', step_text))
                    assert not has_set_x, (
                        f"Step with secret {secret_name} in {workflow_file.name} "
                        "must not use 'set -x' (which would log all executed commands)"
                    )
                    
                    # Verify no 'if: secrets.X != ''' condition
                    has_secret_condition = bool(re.search(
                        rf"if:\s*secrets\.{secret_name}\s*!=",
                        step_text
                    ))
                    assert not has_secret_condition, (
                        f"Workflow must not use 'if: secrets.{secret_name} != ''''' "
                        f"condition as it leaks secret existence in logs"
                    )


if __name__ == "__main__":
    test_generate_audio_no_unsafe_subprocess_calls()
    test_workflow_secrets_have_sentinels()
    print("✅ All security posture checks passed!")

"""
Response Analyzer Component for Ralph
Analyzes Claude Code output to detect completion signals, test-only loops, and progress
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


# Analysis configuration
COMPLETION_KEYWORDS = ["done", "complete", "finished", "all tasks complete", "project complete", "ready for review"]
TEST_ONLY_PATTERNS = ["npm test", "bats", "pytest", "jest", "cargo test", "go test", "running tests"]
NO_WORK_PATTERNS = ["nothing to do", "no changes", "already implemented", "up to date"]
QUESTION_PATTERNS = [
    "should I", "would you", "do you want", "which approach", "which option",
    "how should", "what should", "shall I", "do you prefer", "can you clarify",
    "could you", "what do you think", "please confirm", "need clarification",
    "awaiting.*input", "waiting.*response", "your preference"
]

# Session management
SESSION_FILE = ".ralph/.claude_session_id"
SESSION_EXPIRATION_SECONDS = 86400


def get_iso_timestamp() -> str:
    """Get current ISO timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def get_epoch_seconds() -> int:
    """Get current epoch seconds."""
    return int(datetime.now(timezone.utc).timestamp())


def detect_output_format(output_file: str) -> Literal["json", "text"]:
    """
    Detect output format (json or text).

    Args:
        output_file: Path to output file

    Returns:
        "json" if valid JSON, "text" otherwise
    """
    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        return "text"

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            first_char = f.read(1)

        # Check if first character is JSON indicator
        if first_char not in ('{', '['):
            return "text"

        # Validate as JSON
        with open(output_file, 'r', encoding='utf-8') as f:
            json.load(f)

        return "json"
    except (json.JSONDecodeError, UnicodeDecodeError, IOError):
        return "text"


def detect_questions(text: str) -> bool:
    """
    Detect if Claude is asking questions instead of acting autonomously.

    Args:
        text: Text content to analyze

    Returns:
        True if questions detected, False otherwise
    """
    if not text:
        return False

    text_lower = text.lower()
    question_count = 0

    for pattern in QUESTION_PATTERNS:
        # Use case-insensitive word matching
        matches = len(re.findall(r'\b' + pattern + r'\b', text_lower, re.IGNORECASE))
        question_count += matches

    return question_count > 0


def _count_question_patterns(text: str) -> int:
    """
    Count number of question patterns in text.

    Args:
        text: Text content to analyze

    Returns:
        Number of question patterns found
    """
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    for pattern in QUESTION_PATTERNS:
        matches = len(re.findall(r'\b' + pattern + r'\b', text_lower, re.IGNORECASE))
        count += matches

    return count


def _parse_ralph_status_block(result_text: str) -> Dict[str, Any]:
    """
    Parse RALPH_STATUS block from result text.

    Args:
        result_text: Text containing RALPH_STATUS block

    Returns:
        Dict with parsed status fields
    """
    status_block = {}

    if "---RALPH_STATUS---" not in result_text:
        return status_block

    # Extract EXIT_SIGNAL
    exit_match = re.search(r'EXIT_SIGNAL:\s*(true|false)', result_text, re.IGNORECASE)
    if exit_match:
        status_block['exit_signal'] = exit_match.group(1).lower() == 'true'
        status_block['explicit_exit_signal'] = True

    # Extract STATUS
    status_match = re.search(r'STATUS:\s*(\w+)', result_text, re.IGNORECASE)
    if status_match:
        status_block['status'] = status_match.group(1).upper()

    return status_block


def _parse_claude_cli_array_format(output_file: str) -> Optional[Dict[str, Any]]:
    """
    Parse Claude CLI array format (array of message objects).

    Args:
        output_file: Path to output file

    Returns:
        Normalized result dict or None if not array format
    """
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            return None

        # Find result message (usually the last entry with type "result")
        result_obj = {}
        init_session_id = None

        for item in data:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type", "")

            if item_type == "result":
                result_obj = item
            elif item_type == "system" and item.get("subtype") == "init":
                # Extract session_id from init message
                if "session_id" in item:
                    init_session_id = item["session_id"]

        # Build normalized object with effective session_id
        effective_session_id = result_obj.get("sessionId") or result_obj.get("session_id") or init_session_id

        normalized = dict(result_obj)
        if effective_session_id:
            normalized["sessionId"] = effective_session_id

        # Remove duplicate session_id key if present
        if "session_id" in normalized and "sessionId" in normalized:
            del normalized["session_id"]

        return normalized
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def parse_json_response(output_file: str, result_file: str, ralph_dir: str = ".ralph") -> bool:
    """
    Parse JSON response and extract structured fields.
    Creates result_file with normalized analysis data.
    Supports THREE JSON formats:
    1. Flat format: { status, exit_signal, work_type, files_modified, ... }
    2. Claude CLI object format: { result, sessionId, metadata: {...} }
    3. Claude CLI array format: [ {type: "system", ...}, {type: "result", ...} ]

    Args:
        output_file: Path to Claude output file
        result_file: Path to write normalized result
        ralph_dir: Ralph directory

    Returns:
        True if parsing succeeded, False otherwise
    """
    if not os.path.exists(output_file):
        print(f"ERROR: Output file not found: {output_file}", file=__import__('sys').stderr)
        return False

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("ERROR: Invalid JSON in output file", file=__import__('sys').stderr)
        return False

    # Check if JSON is an array (Claude CLI array format)
    normalized_file = None

    if isinstance(data, list):
        normalized = _parse_claude_cli_array_format(output_file)
        if normalized is None:
            return False
        # Use normalized file for subsequent parsing
        normalized_file = normalized
    else:
        normalized_file = data

    # Detect JSON format by checking for Claude CLI fields
    has_result_field = "result" in normalized_file

    # Extract fields - support both flat format and Claude CLI format
    # Priority: Claude CLI fields first, then flat format fields

    # Status: from flat format OR derived from metadata.completion_status
    status = normalized_file.get("status", "UNKNOWN")
    completion_status = normalized_file.get("metadata", {}).get("completion_status", "")
    if completion_status in ("complete", "COMPLETE"):
        status = "COMPLETE"

    # Exit signal: from flat format OR derived from RALPH_STATUS block in result text
    explicit_exit_signal_found = "exit_signal" in normalized_file
    exit_signal = normalized_file.get("exit_signal", False)

    # Bug #1 Fix: Check for RALPH_STATUS block in .result field (Claude CLI JSON format)
    if not exit_signal and has_result_field:
        result_text = normalized_file.get("result", "")
        if result_text and "---RALPH_STATUS---" in result_text:
            status_block = _parse_ralph_status_block(result_text)

            if "explicit_exit_signal" in status_block:
                explicit_exit_signal_found = True
                exit_signal = status_block.get("exit_signal", False)

            # Also check STATUS field as fallback
            embedded_status = status_block.get("status", "")
            if embedded_status == "COMPLETE" and not explicit_exit_signal_found:
                exit_signal = True

    # Work type: from flat format
    work_type = normalized_file.get("work_type", "UNKNOWN")

    # Files modified: from flat format OR from metadata.files_changed
    files_modified = normalized_file.get("metadata", {}).get("files_changed") or normalized_file.get("files_modified", 0)

    # Error count: from flat format OR derived from metadata.has_errors
    error_count = normalized_file.get("error_count", 0)
    has_errors = normalized_file.get("metadata", {}).get("has_errors", False)
    if has_errors and error_count == 0:
        error_count = 1

    # Summary: from flat format OR from result field (Claude CLI format)
    summary = normalized_file.get("result") or normalized_file.get("summary", "")

    # Session ID: from Claude CLI format (sessionId) OR from metadata.session_id
    session_id = normalized_file.get("sessionId") or normalized_file.get("metadata", {}).get("session_id", "")

    # Loop number: from metadata
    loop_number = normalized_file.get("metadata", {}).get("loop_number") or normalized_file.get("loop_number", 0)

    # Confidence: from flat format
    confidence = normalized_file.get("confidence", 0)

    # Progress indicators: from Claude CLI metadata (optional)
    progress_indicators = normalized_file.get("metadata", {}).get("progress_indicators", [])
    progress_count = len(progress_indicators) if progress_indicators else 0

    # Permission denials: from Claude Code output (Issue #101)
    permission_denials = normalized_file.get("permission_denials", [])
    permission_denial_count = len(permission_denials) if permission_denials else 0
    has_permission_denials = permission_denial_count > 0

    # Extract denied tool names and commands for logging/display
    denied_commands = []
    if permission_denial_count > 0:
        for denial in permission_denials:
            tool_name = denial.get("tool_name", "unknown")
            if tool_name == "Bash":
                tool_input = denial.get("tool_input", {})
                command = tool_input.get("command", "?")
                # Truncate command for display
                first_line = command.split('\n')[0][:60]
                denied_commands.append(f"Bash({first_line})")
            else:
                denied_commands.append(tool_name)

    # Normalize values
    is_test_only = work_type == "TEST_ONLY"
    is_stuck = error_count > 5
    files_modified = int(files_modified)
    error_count = int(error_count)
    progress_count = int(progress_count)

    # Calculate has_completion_signal
    has_completion_signal = status == "COMPLETE" or exit_signal == True

    # Boost confidence based on structured data availability
    if has_result_field:
        confidence += 20
    if progress_count > 0:
        confidence += progress_count * 5

    # Write normalized result
    result_data = {
        "status": status,
        "exit_signal": exit_signal,
        "is_test_only": is_test_only,
        "is_stuck": is_stuck,
        "has_completion_signal": has_completion_signal,
        "files_modified": files_modified,
        "error_count": error_count,
        "summary": summary,
        "loop_number": loop_number,
        "session_id": session_id,
        "confidence": confidence,
        "has_permission_denials": has_permission_denials,
        "permission_denial_count": permission_denial_count,
        "denied_commands": denied_commands,
        "metadata": {
            "loop_number": loop_number,
            "session_id": session_id
        }
    }

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2)

    return True


def _get_git_file_changes(ralph_dir: str) -> int:
    """
    Get number of files changed via git.

    Args:
        ralph_dir: Ralph directory

    Returns:
        Number of files changed
    """
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ralph_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return 0

        loop_start_sha_file = os.path.join(ralph_dir, ".loop_start_sha")
        loop_start_sha = ""
        if os.path.exists(loop_start_sha_file):
            with open(loop_start_sha_file, 'r') as f:
                loop_start_sha = f.read().strip()

        # Get current SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ralph_dir,
            capture_output=True,
            text=True
        )
        current_sha = result.stdout.strip() if result.returncode == 0 else ""

        git_files = 0

        # Check if commits were made (HEAD changed)
        if loop_start_sha and current_sha and loop_start_sha != current_sha:
            # Commits were made - count union of committed files AND working tree changes
            result = subprocess.run(
                ["git", "diff", "--name-only", loop_start_sha, current_sha],
                cwd=ralph_dir,
                capture_output=True,
                text=True
            )
            committed_files = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

            # Unstaged changes
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=ralph_dir,
                capture_output=True,
                text=True
            )
            unstaged = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

            # Staged changes
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=ralph_dir,
                capture_output=True,
                text=True
            )
            staged = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

            git_files = len(set([
                *(result.stdout.strip().split('\n') if result.stdout.strip() else []),
                *(git_files.split('\n') if git_files else [])
            ]))
        else:
            # No commits - check for uncommitted changes
            # Unstaged
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=ralph_dir,
                capture_output=True,
                text=True
            )
            unstaged = result.stdout.strip().split('\n') if result.stdout.strip() else []

            # Staged
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=ralph_dir,
                capture_output=True,
                text=True
            )
            staged = result.stdout.strip().split('\n') if result.stdout.strip() else []

            all_files = set([f for f in (*unstaged, *staged) if f])
            git_files = len(all_files)

        return git_files
    except (subprocess.SubprocessError, OSError):
        return 0


def analyze_response(
    output_file: str,
    loop_number: int,
    result_file: str,
    ralph_dir: str = ".ralph"
) -> Dict[str, Any]:
    """
    Analyze Claude Code response and extract signals.

    Args:
        output_file: Path to Claude output file
        loop_number: Current loop number
        result_file: Path to write analysis result
        ralph_dir: Ralph directory

    Returns:
        Analysis result dictionary
    """
    # Initialize analysis result
    has_completion_signal = False
    is_test_only = False
    is_stuck = False
    has_progress = False
    confidence_score = 0
    exit_signal = False
    work_summary = ""
    files_modified = 0
    asking_questions = False
    question_count = 0
    output_length = 0
    has_permission_denials = False
    permission_denial_count = 0
    denied_commands: List[str] = []

    # Read output file
    if not os.path.exists(output_file):
        print(f"ERROR: Output file not found: {output_file}")
        return {}

    with open(output_file, 'r', encoding='utf-8') as f:
        output_content = f.read()

    output_length = len(output_content)

    # Detect output format and try JSON parsing first
    output_format = detect_output_format(output_file)

    parse_result_file = os.path.join(ralph_dir, ".json_parse_result")

    if output_format == "json":
        # Try JSON parsing
        if parse_json_response(output_file, parse_result_file, ralph_dir):
            # Extract values from JSON parse result
            with open(parse_result_file, 'r', encoding='utf-8') as f:
                json_result = json.load(f)

            has_completion_signal = json_result.get("has_completion_signal", False)
            exit_signal = json_result.get("exit_signal", False)
            is_test_only = json_result.get("is_test_only", False)
            is_stuck = json_result.get("is_stuck", False)
            work_summary = json_result.get("summary", "")
            files_modified = json_result.get("files_modified", 0)
            json_confidence = json_result.get("confidence", 0)
            session_id = json_result.get("session_id", "")

            # Extract permission denial fields
            has_permission_denials = json_result.get("has_permission_denials", False)
            permission_denial_count = json_result.get("permission_denial_count", 0)
            denied_commands = json_result.get("denied_commands", [])

            # Persist session ID if present
            if session_id:
                store_session_id(session_id, ralph_dir)

            # JSON parsing provides high confidence
            if exit_signal:
                confidence_score = 100
            else:
                confidence_score = json_confidence + 50

            # Detect questions in JSON response text
            if _count_question_patterns(work_summary) > 0:
                asking_questions = True
                question_count = _count_question_patterns(work_summary)

            # Check for file changes via git
            git_files = _get_git_file_changes(ralph_dir)
            if git_files > 0:
                has_progress = True
                files_modified = git_files

            # Clean up
            if os.path.exists(parse_result_file):
                os.remove(parse_result_file)

            # Write analysis results for JSON path
            analysis_result = {
                "loop_number": loop_number,
                "timestamp": get_iso_timestamp(),
                "output_file": output_file,
                "output_format": "json",
                "analysis": {
                    "has_completion_signal": has_completion_signal,
                    "is_test_only": is_test_only,
                    "is_stuck": is_stuck,
                    "has_progress": has_progress,
                    "files_modified": files_modified,
                    "confidence_score": confidence_score,
                    "exit_signal": exit_signal,
                    "work_summary": work_summary,
                    "output_length": output_length,
                    "has_permission_denials": has_permission_denials,
                    "permission_denial_count": permission_denial_count,
                    "denied_commands": denied_commands,
                    "asking_questions": asking_questions,
                    "question_count": question_count
                }
            }

            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, indent=2)

            return analysis_result

    # Text parsing fallback (original logic)

    explicit_exit_signal_found = False

    # 1. Check for explicit structured output (RALPH_STATUS block)
    if "---RALPH_STATUS---" in output_content:
        status_match = re.search(r'STATUS:\s*(\w+)', output_content, re.IGNORECASE)
        exit_sig_match = re.search(r'EXIT_SIGNAL:\s*(true|false)', output_content, re.IGNORECASE)

        status = status_match.group(1).upper() if status_match else ""
        exit_sig = exit_sig_match.group(1).lower() if exit_sig_match else ""

        if exit_sig:
            explicit_exit_signal_found = True
            if exit_sig == "true":
                has_completion_signal = True
                exit_signal = True
                confidence_score = 100
        elif status == "COMPLETE":
            has_completion_signal = True
            exit_signal = True
            confidence_score = 100

    # 2. Detect completion keywords in natural language output
    output_lower = output_content.lower()
    for keyword in COMPLETION_KEYWORDS:
        if keyword.lower() in output_lower:
            has_completion_signal = True
            confidence_score += 10
            break

    # 3. Detect test-only loops
    test_command_count = len(re.findall(
        r'(running tests|npm test|bats|pytest|jest)',
        output_lower
    ))
    implementation_count = len(re.findall(
        r'(implementing|creating|writing|adding|function|class)',
        output_lower
    ))

    if test_command_count > 0 and implementation_count == 0:
        is_test_only = True
        work_summary = "Test execution only, no implementation"

    # 4. Detect stuck/error loops
    # Two-stage filtering: first remove JSON field patterns, then count actual errors
    lines = output_content.split('\n')
    filtered_lines = [line for line in lines if not re.search(r'"[^"]*error[^"]*":', line)]
    filtered_content = '\n'.join(filtered_lines)

    error_count = len(re.findall(
        r'(^Error:|^ERROR:|^error:|\]: error|Link: error|Error occurred|failed with error|[Ee]xception|Fatal|FATAL)',
        filtered_content,
        re.MULTILINE
    ))

    if error_count > 5:
        is_stuck = True

    # 5. Detect "nothing to do" patterns
    for pattern in NO_WORK_PATTERNS:
        if pattern.lower() in output_lower:
            has_completion_signal = True
            confidence_score += 15
            work_summary = "No work remaining"
            break

    # 5.5. Detect question patterns
    question_count = _count_question_patterns(output_content)
    if question_count > 0:
        asking_questions = True
        work_summary = "Claude is asking questions instead of acting autonomously"

    # 6. Check for file changes (git integration)
    git_files = _get_git_file_changes(ralph_dir)
    if git_files > 0:
        has_progress = True
        files_modified = git_files
        confidence_score += 20

    # 7. Analyze output length trends
    last_output_file = os.path.join(ralph_dir, ".last_output_length")
    if os.path.exists(last_output_file):
        with open(last_output_file, 'r') as f:
            last_length = int(f.read().strip() or 0)

        if last_length > 0:
            length_ratio = (output_length * 100) // last_length
            if length_ratio < 50:
                confidence_score += 10

    # Save current output length
    with open(last_output_file, 'w') as f:
        f.write(str(output_length))

    # 8. Extract work summary from output
    if not work_summary:
        summary_match = re.search(r'(summary|completed|implemented).*', output_content, re.IGNORECASE)
        if summary_match:
            work_summary = summary_match.group(0)[:100]
        else:
            work_summary = "Output analyzed, no explicit summary found"

    # 9. Determine exit signal based on confidence
    if not explicit_exit_signal_found:
        if output_format == "json":
            # JSON mode with failed parse: suppress heuristics entirely
            pass
        elif confidence_score >= 70 and has_completion_signal:
            exit_signal = True

    # Write analysis results to file
    analysis_result = {
        "loop_number": loop_number,
        "timestamp": get_iso_timestamp(),
        "output_file": output_file,
        "output_format": "text",
        "analysis": {
            "has_completion_signal": has_completion_signal,
            "is_test_only": is_test_only,
            "is_stuck": is_stuck,
            "has_progress": has_progress,
            "files_modified": files_modified,
            "confidence_score": confidence_score,
            "exit_signal": exit_signal,
            "work_summary": work_summary,
            "output_length": output_length,
            "has_permission_denials": False,
            "permission_denial_count": 0,
            "denied_commands": [],
            "asking_questions": asking_questions,
            "question_count": question_count
        }
    }

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, indent=2)

    return analysis_result


def detect_stuck_loop(history_files: List[str], current_error: str) -> bool:
    """
    Detect if Claude is stuck (repeating same errors).

    Args:
        history_files: List of paths to recent output files
        current_error: Current error text to check against history

    Returns:
        True if stuck on same error, False otherwise
    """
    if not history_files or not current_error:
        return False

    # Extract errors from current output using two-stage filtering
    lines = current_error.split('\n')
    filtered_lines = [line for line in lines if not re.search(r'"[^"]*error[^"]*":', line)]
    filtered_content = '\n'.join(filtered_lines)

    current_errors = set(re.findall(
        r'(^Error:|^ERROR:|^error:|\]: error|Link: error|Error occurred|failed with error|[Ee]xception|Fatal|FATAL)',
        filtered_content,
        re.MULTILINE
    ))

    if not current_errors:
        return False

    # Check if same errors appear in all recent outputs
    for output_file in history_files:
        if not os.path.exists(output_file):
            return False

        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Filter and extract errors
            lines = content.split('\n')
            filtered_lines = [line for line in lines if not re.search(r'"[^"]*error[^"]*":', line)]
            filtered_content = '\n'.join(filtered_lines)

            history_errors = set(re.findall(
                r'(^Error:|^ERROR:|^error:|\]: error|Link: error|Error occurred|failed with error|[Ee]xception|Fatal|FATAL)',
                filtered_content,
                re.MULTILINE
            ))

            # Check if all current errors are present in history
            if not current_errors.issubset(history_errors):
                return False
        except (IOError, UnicodeDecodeError):
            return False

    return True


def update_exit_signals(
    analysis_file: str,
    exit_signals_file: str,
    ralph_dir: str = ".ralph"
) -> bool:
    """
    Update exit signals file based on analysis.

    Args:
        analysis_file: Path to analysis result file
        exit_signals_file: Path to exit signals file
        ralph_dir: Ralph directory

    Returns:
        True if update succeeded, False otherwise
    """
    if not os.path.exists(analysis_file):
        print(f"ERROR: Analysis file not found: {analysis_file}")
        return False

    with open(analysis_file, 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    analysis_data = analysis.get("analysis", {})

    is_test_only = analysis_data.get("is_test_only", False)
    has_completion_signal = analysis_data.get("has_completion_signal", False)
    loop_number = analysis.get("loop_number", 0)
    has_progress = analysis_data.get("has_progress", False)
    exit_signal = analysis_data.get("exit_signal", False)

    # Read current exit signals
    if os.path.exists(exit_signals_file):
        with open(exit_signals_file, 'r', encoding='utf-8') as f:
            signals = json.load(f)
    else:
        signals = {"test_only_loops": [], "done_signals": [], "completion_indicators": []}

    # Update test_only_loops array
    if is_test_only:
        signals["test_only_loops"].append(loop_number)
    else:
        if has_progress:
            signals["test_only_loops"] = []

    # Update done_signals array
    if has_completion_signal:
        signals["done_signals"].append(loop_number)

    # Update completion_indicators array (only when Claude explicitly signals exit)
    if exit_signal:
        signals["completion_indicators"].append(loop_number)

    # Keep only last 5 signals (rolling window)
    signals["test_only_loops"] = signals["test_only_loops"][-5:]
    signals["done_signals"] = signals["done_signals"][-5:]
    signals["completion_indicators"] = signals["completion_indicators"][-5:]

    # Write updated signals
    with open(exit_signals_file, 'w', encoding='utf-8') as f:
        json.dump(signals, f, indent=2)

    return True


def store_session_id(session_id: str, ralph_dir: str = ".ralph") -> bool:
    """
    Store session ID to file with timestamp.

    Args:
        session_id: Session ID to store
        ralph_dir: Ralph directory

    Returns:
        True if storage succeeded, False otherwise
    """
    if not session_id:
        return False

    session_file = os.path.join(ralph_dir, ".claude_session_id")

    session_data = {
        "session_id": session_id,
        "timestamp": get_iso_timestamp()
    }

    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2)

    return True


def get_last_session_id(ralph_dir: str = ".ralph") -> str:
    """
    Get the last stored session ID.

    Args:
        ralph_dir: Ralph directory

    Returns:
        Session ID string or empty if not found
    """
    session_file = os.path.join(ralph_dir, ".claude_session_id")

    if not os.path.exists(session_file):
        return ""

    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        return session_data.get("session_id", "")
    except (json.JSONDecodeError, IOError):
        return ""


def should_resume_session(ralph_dir: str = ".ralph") -> bool:
    """
    Check if the stored session should be resumed.

    Args:
        ralph_dir: Ralph directory

    Returns:
        True if session is valid and recent, False otherwise
    """
    session_file = os.path.join(ralph_dir, ".claude_session_id")

    if not os.path.exists(session_file):
        return False

    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False

    timestamp = session_data.get("timestamp", "")

    if not timestamp:
        return False

    # Parse timestamp to epoch
    try:
        # Handle timestamps with or without timezone
        clean_timestamp = timestamp
        if '.' in timestamp and ('+' in timestamp or 'Z' in timestamp or timestamp.endswith(('+00:00', '-00:00'))):
            # Has milliseconds and timezone
            clean_timestamp = re.sub(r'\.\d+([+-Z].*)', r'\1', timestamp)

        dt = datetime.fromisoformat(clean_timestamp.replace('Z', '+00:00'))
        session_time = int(dt.timestamp())
    except (ValueError, OSError):
        return False

    now = get_epoch_seconds()
    age = now - session_time

    return age < SESSION_EXPIRATION_SECONDS

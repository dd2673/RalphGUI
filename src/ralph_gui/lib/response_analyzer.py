#!/usr/bin/env python3
"""
Response Analyzer Component for Ralph
Analyzes Claude Code output to detect completion signals, test-only loops, and progress

Ported from bash to Python for cross-platform compatibility.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Use pathlib for path handling - Windows compatible
RALPH_DIR = Path(".ralph")

# Analysis configuration
COMPLETION_KEYWORDS = [
    "done", "complete", "finished", "all tasks complete",
    "project complete", "ready for review"
]

TEST_ONLY_PATTERNS = [
    "npm test", "bats", "pytest", "jest", "cargo test", "go test", "running tests"
]

NO_WORK_PATTERNS = [
    "nothing to do", "no changes", "already implemented", "up to date"
]

QUESTION_PATTERNS = [
    r"should I", r"would you", r"do you want", r"which approach", r"which option",
    r"how should", r"what should", r"shall I", r"do you prefer",
    r"can you clarify", r"could you", r"what do you think", r"please confirm",
    r"need clarification", r"awaiting.*input", r"waiting.*response", r"your preference"
]

# Session management
SESSION_FILE = RALPH_DIR / ".claude_session_id"
SESSION_EXPIRATION_SECONDS = 86400  # 24 hours


# =============================================================================
# DATE UTILITY FUNCTIONS
# =============================================================================

def get_iso_timestamp() -> str:
    """Get current timestamp in ISO 8601 format with seconds precision."""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def get_epoch_seconds() -> int:
    """Get current Unix epoch time in seconds."""
    return int(datetime.now(timezone.utc).timestamp())


# =============================================================================
# QUESTION DETECTION
# =============================================================================

def detect_questions(content: str) -> tuple[bool, int]:
    """
    Detect if Claude is asking questions instead of acting autonomously.

    Args:
        content: Text content to analyze

    Returns:
        Tuple of (questions_detected: bool, question_count: int)
    """
    if not content:
        return False, 0

    question_count = 0
    content_lower = content.lower()

    for pattern in QUESTION_PATTERNS:
        try:
            matches = len(re.findall(pattern, content_lower, re.IGNORECASE))
            question_count += matches
        except re.error:
            continue

    return question_count > 0, question_count


# =============================================================================
# JSON OUTPUT FORMAT DETECTION AND PARSING
# =============================================================================

def detect_output_format(output_file: Path) -> str:
    """
    Detect output format (json or text).

    Args:
        output_file: Path to output file

    Returns:
        "json" if valid JSON, "text" otherwise
    """
    if not output_file.exists() or output_file.stat().st_size == 0:
        return "text"

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            first_char = f.read(1).strip()

        if first_char not in ('{', '['):
            return "text"

        # Validate as JSON
        with open(output_file, 'r', encoding='utf-8') as f:
            json.load(f)
        return "json"
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return "text"


def parse_json_response(output_file: Path, result_file: Optional[Path] = None) -> bool:
    """
    Parse JSON response and extract structured fields.
    Creates result file with normalized analysis data.

    Supports THREE JSON formats:
    1. Flat format: { status, exit_signal, work_type, files_modified, ... }
    2. Claude CLI object format: { result, sessionId, metadata: { files_changed, has_errors, completion_status, ... } }
    3. Claude CLI array format: [ {type: "system", ...}, {type: "assistant", ...}, {type: "result", ...} ]

    Args:
        output_file: Path to JSON output file
        result_file: Path to write normalized result (defaults to .ralph/.json_parse_result)

    Returns:
        True on success, False on failure
    """
    if result_file is None:
        result_file = RALPH_DIR / ".json_parse_result"

    if not output_file.exists():
        print(f"ERROR: Output file not found: {output_file}", file=sys.stderr)
        return False

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in output file: {e}", file=sys.stderr)
        return False

    normalized_file = None

    # Check if JSON is an array (Claude CLI array format)
    if isinstance(data, list):
        normalized_file = Path(str(output_file) + ".normalized.tmp")

        # Extract the "result" type message from the array (usually the last entry)
        result_objects = [item for item in data if item.get("type") == "result"]
        result_obj = result_objects[-1] if result_objects else {}

        # Extract session_id from init message as fallback
        init_session_id = ""
        for item in data:
            if item.get("type") == "system" and item.get("subtype") == "init":
                init_session_id = item.get("session_id", "")
                break

        # Prioritize result object's own session_id, then fall back to init message
        effective_session_id = result_obj.get("sessionId") or result_obj.get("session_id") or init_session_id

        # Build normalized object merging result with effective session_id
        if effective_session_id:
            result_obj["sessionId"] = effective_session_id
        if "session_id" in result_obj:
            del result_obj["session_id"]

        # Write normalized file for subsequent parsing
        with open(normalized_file, 'w', encoding='utf-8') as f:
            json.dump(result_obj, f)

        output_file = normalized_file

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # Detect JSON format by checking for Claude CLI fields
    has_result_field = "result" in data

    # Status: from flat format OR derived from metadata.completion_status
    status = data.get("status", "UNKNOWN")
    completion_status = ""
    if isinstance(data.get("metadata"), dict):
        completion_status = data["metadata"].get("completion_status", "")
    if completion_status in ("complete", "COMPLETE"):
        status = "COMPLETE"

    # Exit signal: from flat format OR derived from completion_status
    exit_signal = data.get("exit_signal", False)
    explicit_exit_signal_found = "exit_signal" in data

    # Bug #1 Fix: If exit_signal is still false, check for RALPH_STATUS block in .result field
    if not exit_signal and has_result_field:
        result_text = data.get("result", "")
        if result_text and "---RALPH_STATUS---" in result_text:
            # Extract EXIT_SIGNAL value from RALPH_STATUS block within result text
            for line in result_text.split('\n'):
                if line.startswith("EXIT_SIGNAL:"):
                    embedded_exit_sig = line.split(":", 1)[1].strip()
                    if embedded_exit_sig:
                        explicit_exit_signal_found = True
                        exit_signal = embedded_exit_sig.lower() == "true"
                    break

            # Also check STATUS field as fallback ONLY when EXIT_SIGNAL was not specified
            if not explicit_exit_signal_found:
                for line in result_text.split('\n'):
                    if line.startswith("STATUS:"):
                        embedded_status = line.split(":", 1)[1].strip()
                        if embedded_status == "COMPLETE":
                            exit_signal = True
                        break

    # Work type: from flat format
    work_type = data.get("work_type", "UNKNOWN")

    # Files modified: from flat format OR from metadata.files_changed
    files_modified = 0
    if isinstance(data.get("metadata"), dict):
        files_modified = data["metadata"].get("files_changed", 0)
    if not files_modified:
        files_modified = data.get("files_modified", 0)
    files_modified = int(files_modified) if files_modified else 0

    # Error count: from flat format OR derived from metadata.has_errors
    error_count = int(data.get("error_count", 0))
    has_errors = False
    if isinstance(data.get("metadata"), dict):
        has_errors = data["metadata"].get("has_errors", False)
    if has_errors and error_count == 0:
        error_count = 1  # At least one error if has_errors is true

    # Summary: from flat format OR from result field (Claude CLI format)
    summary = data.get("result") or data.get("summary", "")

    # Session ID: from Claude CLI format (sessionId) OR from metadata.session_id
    session_id = data.get("sessionId", "")
    if not session_id and isinstance(data.get("metadata"), dict):
        session_id = data["metadata"].get("session_id", "")

    # Loop number: from metadata
    loop_number = 0
    if isinstance(data.get("metadata"), dict):
        loop_number = data["metadata"].get("loop_number", 0)
    if not loop_number:
        loop_number = data.get("loop_number", 0)

    # Confidence: from flat format
    confidence = int(data.get("confidence", 0))

    # Progress indicators: from Claude CLI metadata (optional)
    progress_count = 0
    if isinstance(data.get("metadata"), dict) and data["metadata"].get("progress_indicators"):
        progress_count = len(data["metadata"]["progress_indicators"])

    # Permission denials: from Claude Code output (Issue #101)
    permission_denial_count = 0
    if data.get("permission_denials"):
        permission_denial_count = len(data["permission_denials"])

    has_permission_denials = permission_denial_count > 0

    # Extract denied tool names and commands for logging/display
    denied_commands = []
    if permission_denial_count > 0:
        for denial in data["permission_denials"]:
            tool_name = denial.get("tool_name", "unknown")
            if tool_name == "Bash":
                tool_input = denial.get("tool_input", {})
                command = tool_input.get("command", "?")
                command_preview = command.split('\n')[0][:60] if command else "?"
                denied_commands.append(f"Bash({command_preview})")
            else:
                denied_commands.append(tool_name if tool_name else "unknown")

    # Normalize values
    # Convert exit_signal to boolean string
    # Only infer from status/completion_status if no explicit EXIT_SIGNAL was provided
    if explicit_exit_signal_found:
        pass  # Already set above
    elif exit_signal or status == "COMPLETE" or completion_status in ("complete", "COMPLETE"):
        exit_signal = True
    else:
        exit_signal = False

    # Determine is_test_only from work_type
    is_test_only = work_type == "TEST_ONLY"

    # Determine is_stuck from error_count (threshold >5)
    is_stuck = error_count > 5

    # Calculate has_completion_signal
    has_completion_signal = status == "COMPLETE" or exit_signal is True

    # Boost confidence based on structured data availability
    if has_result_field:
        confidence += 20  # Structured response boost
    if progress_count > 0:
        confidence += progress_count * 5  # Progress indicators boost

    # Build normalized result
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

    # Write normalized result
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False)

    # Cleanup temporary normalized file if created
    if normalized_file and normalized_file.exists():
        normalized_file.unlink()

    return True


# =============================================================================
# GIT UTILITIES
# =============================================================================

def get_git_changed_files(ralph_dir: Path) -> int:
    """
    Get count of files changed via git.

    Args:
        ralph_dir: Ralph directory path

    Returns:
        Number of changed files
    """
    try:
        # Check if git is available and we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=ralph_dir.parent
        )
        if result.returncode != 0:
            return 0

        loop_start_sha_file = ralph_dir / ".loop_start_sha"
        loop_start_sha = ""
        if loop_start_sha_file.exists():
            loop_start_sha = loop_start_sha_file.read_text().strip()

        # Get current HEAD
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ralph_dir.parent
        )
        current_sha = result.stdout.strip() if result.returncode == 0 else ""

        changed_files = set()

        # Check if commits were made (HEAD changed)
        if loop_start_sha and current_sha and loop_start_sha != current_sha:
            # Commits were made - count committed files
            result = subprocess.run(
                ["git", "diff", "--name-only", loop_start_sha, current_sha],
                capture_output=True,
                text=True,
                cwd=ralph_dir.parent
            )
            if result.returncode == 0:
                changed_files.update(f.strip() for f in result.stdout.split('\n') if f.strip())

        # Always check for uncommitted changes (staged + unstaged)
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=ralph_dir.parent
        )
        if result.returncode == 0:
            changed_files.update(f.strip() for f in result.stdout.split('\n') if f.strip())

        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            cwd=ralph_dir.parent
        )
        if result.returncode == 0:
            changed_files.update(f.strip() for f in result.stdout.split('\n') if f.strip())

        return len(changed_files)
    except (subprocess.SubprocessError, OSError):
        return 0


# =============================================================================
# TEXT PARSING
# =============================================================================

def parse_text_response(
    output_file: Path,
    output_content: str,
    loop_number: int
) -> dict:
    """
    Parse text response when JSON parsing fails or is not applicable.

    Args:
        output_file: Path to output file
        output_content: Content of the output file
        loop_number: Current loop number

    Returns:
        Analysis dictionary
    """
    has_completion_signal = False
    is_test_only = False
    is_stuck = False
    has_progress = False
    confidence_score = 0
    exit_signal = False
    work_summary = ""
    asking_questions = False
    question_count = 0

    # Track whether an explicit EXIT_SIGNAL was found in RALPH_STATUS block
    explicit_exit_signal_found = False

    # 1. Check for explicit structured output
    if "---RALPH_STATUS---" in output_content:
        for line in output_content.split('\n'):
            if line.startswith("EXIT_SIGNAL:"):
                exit_sig = line.split(":", 1)[1].strip()
                if exit_sig:
                    explicit_exit_signal_found = True
                    if exit_sig == "true":
                        has_completion_signal = True
                        exit_signal = True
                        confidence_score = 100
                    else:
                        exit_signal = False
                break
            if line.startswith("STATUS:"):
                status = line.split(":", 1)[1].strip()
                if status == "COMPLETE" and not explicit_exit_signal_found:
                    has_completion_signal = True
                    exit_signal = True
                    confidence_score = 100
                break

    # 2. Detect completion keywords in natural language output
    content_lower = output_content.lower()
    for keyword in COMPLETION_KEYWORDS:
        if keyword.lower() in content_lower:
            has_completion_signal = True
            confidence_score += 10
            break

    # 3. Detect test-only loops
    test_command_count = 0
    implementation_count = 0

    test_pattern = r"running tests|npm test|bats|pytest|jest"
    impl_pattern = r"implementing|creating|writing|adding|function|class"

    for match in re.finditer(test_pattern, content_lower, re.IGNORECASE):
        test_command_count += 1
    for match in re.finditer(impl_pattern, content_lower, re.IGNORECASE):
        implementation_count += 1

    if test_command_count > 0 and implementation_count == 0:
        is_test_only = True
        work_summary = "Test execution only, no implementation"

    # 4. Detect stuck/error loops
    error_count = 0

    # Two-stage filtering to avoid counting JSON field names as errors
    # Stage 1: Filter out JSON field patterns like "is_error": false
    lines = output_content.split('\n')
    filtered_lines = []
    for line in lines:
        # Skip JSON field patterns
        if re.match(r'^\s*"[^"]*error[^"]*":', line):
            continue
        filtered_lines.append(line)

    filtered_content = '\n'.join(filtered_lines)

    # Stage 2: Count actual error messages
    error_pattern = r'(^Error:|^ERROR:|^error:|\]: error|Link: error|Error occurred|failed with error|[Ee]xception|Fatal|FATAL)'
    for match in re.finditer(error_pattern, filtered_content, re.MULTILINE):
        error_count += 1

    if error_count > 5:
        is_stuck = True

    # 5. Detect "nothing to do" patterns
    for pattern in NO_WORK_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            has_completion_signal = True
            confidence_score += 15
            work_summary = "No work remaining"
            break

    # 5.5. Detect question patterns (Issue #190 Bug 2)
    asking_questions, question_count = detect_questions(output_content)
    if asking_questions:
        work_summary = "Claude is asking questions instead of acting autonomously"

    # 6. Check for file changes (git integration)
    git_files = get_git_changed_files(RALPH_DIR)
    if git_files > 0:
        has_progress = True
        confidence_score += 20

    # 7. Analyze output length trends
    last_output_length_file = RALPH_DIR / ".last_output_length"
    output_length = len(output_content)

    if last_output_length_file.exists():
        try:
            last_length = int(last_output_length_file.read_text().strip())
            length_ratio = (output_length * 100) / last_length if last_length > 0 else 0
            if length_ratio < 50:
                confidence_score += 10
        except (ValueError, OSError):
            pass

    # Save current output length for next iteration
    try:
        last_output_length_file.write_text(str(output_length))
    except OSError:
        pass

    # 8. Extract work summary from output
    if not work_summary:
        summary_match = re.search(r'(summary|completed|implemented).*', content_lower)
        if summary_match:
            work_summary = summary_match.group(0)[:100]
        else:
            work_summary = "Output analyzed, no explicit summary found"

    # 9. Determine exit signal based on confidence (heuristic)
    # IMPORTANT: Only apply heuristics if no explicit EXIT_SIGNAL was found
    if not explicit_exit_signal_found:
        if confidence_score >= 70 and has_completion_signal:
            exit_signal = True

    return {
        "loop_number": loop_number,
        "timestamp": get_iso_timestamp(),
        "output_file": str(output_file),
        "output_format": "text",
        "analysis": {
            "has_completion_signal": has_completion_signal,
            "is_test_only": is_test_only,
            "is_stuck": is_stuck,
            "has_progress": has_progress,
            "files_modified": git_files,
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


# =============================================================================
# MAIN RESPONSE ANALYSIS
# =============================================================================

def analyze_response(
    output_file: Path,
    loop_number: int,
    analysis_result_file: Optional[Path] = None
) -> bool:
    """
    Analyze Claude Code response and extract signals.

    Args:
        output_file: Path to output file
        loop_number: Current loop number
        analysis_result_file: Path to write analysis result (defaults to .ralph/.response_analysis)

    Returns:
        True on success, False on failure
    """
    if analysis_result_file is None:
        analysis_result_file = RALPH_DIR / ".response_analysis"

    if not output_file.exists():
        print(f"ERROR: Output file not found: {output_file}", file=sys.stderr)
        return False

    try:
        output_content = output_file.read_text(encoding='utf-8')
    except OSError as e:
        print(f"ERROR: Cannot read output file: {e}", file=sys.stderr)
        return False

    output_length = len(output_content)

    # Detect output format and try JSON parsing first
    output_format = detect_output_format(output_file)

    if output_format == "json":
        # Try JSON parsing
        if parse_json_response(output_file, RALPH_DIR / ".json_parse_result"):
            # Read parsed result
            parse_result_file = RALPH_DIR / ".json_parse_result"
            try:
                with open(parse_result_file, 'r', encoding='utf-8') as f:
                    parsed = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
            else:
                has_completion_signal = parsed.get("has_completion_signal", False)
                exit_signal = parsed.get("exit_signal", False)
                is_test_only = parsed.get("is_test_only", False)
                is_stuck = parsed.get("is_stuck", False)
                work_summary = parsed.get("summary", "")
                files_modified = parsed.get("files_modified", 0)
                json_confidence = parsed.get("confidence", 0)
                session_id = parsed.get("session_id", "")
                has_permission_denials = parsed.get("has_permission_denials", False)
                permission_denial_count = parsed.get("permission_denial_count", 0)
                denied_commands = parsed.get("denied_commands", [])

                # Persist session ID if present
                if session_id:
                    store_session_id(session_id)

                # Calculate confidence
                if exit_signal:
                    confidence_score = 100
                else:
                    confidence_score = json_confidence + 50

                # Detect questions in JSON response text
                asking_questions, question_count = detect_questions(work_summary)

                # Check for file changes via git
                has_progress = False
                git_files = get_git_changed_files(RALPH_DIR)
                if git_files > 0:
                    has_progress = True
                    files_modified = git_files

                # Build analysis result
                result = {
                    "loop_number": loop_number,
                    "timestamp": get_iso_timestamp(),
                    "output_file": str(output_file),
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

                # Write analysis results
                RALPH_DIR.mkdir(parents=True, exist_ok=True)
                with open(analysis_result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False)

                # Cleanup
                if parse_result_file.exists():
                    parse_result_file.unlink()

                return True

        # If JSON parsing failed, fall through to text parsing

    # Text parsing fallback
    result = parse_text_response(output_file, output_content, loop_number)

    # Write analysis results
    RALPH_DIR.mkdir(parents=True, exist_ok=True)
    with open(analysis_result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)

    return True


# =============================================================================
# EXIT SIGNALS MANAGEMENT
# =============================================================================

def update_exit_signals(
    analysis_file: Optional[Path] = None,
    exit_signals_file: Optional[Path] = None
) -> bool:
    """
    Update exit signals file based on analysis.

    Args:
        analysis_file: Path to analysis file (defaults to .ralph/.response_analysis)
        exit_signals_file: Path to exit signals file (defaults to .ralph/.exit_signals)

    Returns:
        True on success, False on failure
    """
    if analysis_file is None:
        analysis_file = RALPH_DIR / ".response_analysis"
    if exit_signals_file is None:
        exit_signals_file = RALPH_DIR / ".exit_signals"

    if not analysis_file.exists():
        print(f"ERROR: Analysis file not found: {analysis_file}", file=sys.stderr)
        return False

    try:
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: Cannot read analysis file: {e}", file=sys.stderr)
        return False

    is_test_only = analysis.get("analysis", {}).get("is_test_only", False)
    has_completion_signal = analysis.get("analysis", {}).get("has_completion_signal", False)
    loop_number = analysis.get("loop_number", 0)
    has_progress = analysis.get("analysis", {}).get("has_progress", False)

    # Read current exit signals
    signals = {"test_only_loops": [], "done_signals": [], "completion_indicators": []}
    if exit_signals_file.exists():
        try:
            with open(exit_signals_file, 'r', encoding='utf-8') as f:
                signals = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Update test_only_loops array
    if is_test_only:
        signals["test_only_loops"].append(loop_number)
    else:
        # Clear test_only_loops if we had implementation
        if has_progress:
            signals["test_only_loops"] = []

    # Update done_signals array
    if has_completion_signal:
        signals["done_signals"].append(loop_number)

    # Update completion_indicators array (only when Claude explicitly signals exit)
    exit_signal = analysis.get("analysis", {}).get("exit_signal", False)
    if exit_signal:
        signals["completion_indicators"].append(loop_number)

    # Keep only last 5 signals (rolling window)
    signals["test_only_loops"] = signals["test_only_loops"][-5:]
    signals["done_signals"] = signals["done_signals"][-5:]
    signals["completion_indicators"] = signals["completion_indicators"][-5:]

    # Write updated signals
    RALPH_DIR.mkdir(parents=True, exist_ok=True)
    with open(exit_signals_file, 'w', encoding='utf-8') as f:
        json.dump(signals, f, ensure_ascii=False)

    return True


# =============================================================================
# LOGGING
# =============================================================================

def log_analysis_summary(analysis_file: Optional[Path] = None) -> bool:
    """
    Log analysis results in human-readable format.

    Args:
        analysis_file: Path to analysis file (defaults to .ralph/.response_analysis)

    Returns:
        True on success, False on failure
    """
    if analysis_file is None:
        analysis_file = RALPH_DIR / ".response_analysis"

    if not analysis_file.exists():
        return False

    try:
        with open(analysis_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    loop = data.get("loop_number", 0)
    exit_sig = data.get("analysis", {}).get("exit_signal", False)
    confidence = data.get("analysis", {}).get("confidence_score", 0)
    test_only = data.get("analysis", {}).get("is_test_only", False)
    files_changed = data.get("analysis", {}).get("files_modified", 0)
    summary = data.get("analysis", {}).get("work_summary", "")

    # ANSI color codes
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'

    print(f"{BLUE}╔════════════════════════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║           Response Analysis - Loop #{loop}                 ║{NC}")
    print(f"{BLUE}╚════════════════════════════════════════════════════════════╝{NC}")
    print(f"{YELLOW}Exit Signal:{NC}      {exit_sig}")
    print(f"{YELLOW}Confidence:{NC}       {confidence}%")
    print(f"{YELLOW}Test Only:{NC}        {test_only}")
    print(f"{YELLOW}Files Changed:{NC}    {files_changed}")
    print(f"{YELLOW}Summary:{NC}          {summary}")
    print()

    return True


# =============================================================================
# STUCK LOOP DETECTION
# =============================================================================

def detect_stuck_loop(current_output: Path, history_dir: Optional[Path] = None) -> bool:
    """
    Detect if Claude is stuck (repeating same errors).

    Args:
        current_output: Path to current output file
        history_dir: Path to history directory (defaults to .ralph/logs)

    Returns:
        True if stuck on same error(s), False otherwise
    """
    if history_dir is None:
        history_dir = RALPH_DIR / "logs"

    if not history_dir.exists():
        return False

    # Get last 3 output files
    try:
        output_files = sorted(
            history_dir.glob("claude_output_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:3]
    except OSError:
        return False

    if len(output_files) < 3:
        return False

    # Extract key errors from current output using two-stage filtering
    try:
        current_content = current_output.read_text(encoding='utf-8')
    except OSError:
        return False

    # Stage 1: Filter out JSON field patterns to avoid false positives
    lines = current_content.split('\n')
    filtered_lines = []
    for line in lines:
        if re.match(r'^\s*"[^"]*error[^"]*":', line):
            continue
        filtered_lines.append(line)

    filtered_content = '\n'.join(filtered_lines)

    # Stage 2: Extract actual error messages
    error_pattern = r'(^Error:|^ERROR:|^error:|\]: error|Link: error|Error occurred|failed with error|[Ee]xception|Fatal|FATAL)'
    current_errors = set()
    for match in re.finditer(error_pattern, filtered_content, re.MULTILINE):
        current_errors.add(match.group(0))

    if not current_errors:
        return False

    # Check if same errors appear in all recent outputs
    for history_file in output_files:
        try:
            history_content = history_file.read_text(encoding='utf-8')
        except OSError:
            return False

        # Stage 1: Filter JSON field patterns
        lines = history_content.split('\n')
        filtered_lines = []
        for line in lines:
            if re.match(r'^\s*"[^"]*error[^"]*":', line):
                continue
            filtered_lines.append(line)
        filtered_content = '\n'.join(filtered_lines)

        # Check if all current errors appear in this history file
        for error in current_errors:
            if error not in filtered_content:
                return False

    return True


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

def store_session_id(session_id: str) -> bool:
    """
    Store session ID to file with timestamp.

    Args:
        session_id: Session ID to store

    Returns:
        True on success, False on failure
    """
    if not session_id:
        return False

    session_data = {
        "session_id": session_id,
        "timestamp": get_iso_timestamp()
    }

    try:
        RALPH_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False)
        return True
    except OSError:
        return False


def get_last_session_id() -> str:
    """
    Get the last stored session ID.

    Returns:
        Session ID string or empty if not found
    """
    if not SESSION_FILE.exists():
        return ""

    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("session_id", "")
    except (json.JSONDecodeError, OSError):
        return ""


def should_resume_session() -> bool:
    """
    Check if the stored session should be resumed.

    Returns:
        True if session is valid and recent, False otherwise
    """
    if not SESSION_FILE.exists():
        return False

    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    timestamp = data.get("timestamp", "")
    if not timestamp:
        return False

    # Parse ISO timestamp
    try:
        # Handle various ISO formats - Python 3.7+ handles milliseconds and timezone directly
        timestamp_clean = timestamp.replace('Z', '+00:00')
        session_dt = datetime.fromisoformat(timestamp_clean)
        session_time = int(session_dt.timestamp())
    except (ValueError, OSError):
        return False

    # Calculate age in seconds
    now = get_epoch_seconds()
    age = now - session_time

    # Check if session is still valid (less than expiration time)
    return age < SESSION_EXPIRATION_SECONDS


# =============================================================================
# EXPORTED FUNCTIONS (for backward compatibility)
# =============================================================================

__all__ = [
    'detect_questions',
    'detect_output_format',
    'parse_json_response',
    'analyze_response',
    'update_exit_signals',
    'log_analysis_summary',
    'detect_stuck_loop',
    'store_session_id',
    'get_last_session_id',
    'should_resume_session',
    'get_iso_timestamp',
    'get_epoch_seconds',
    'RALPH_DIR',
]


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description="Response Analyzer for Ralph")
    parser.add_argument("output_file", type=Path, help="Output file to analyze")
    parser.add_argument("--loop", type=int, default=1, help="Loop number")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if analyze_response(args.output_file, args.loop):
        log_analysis_summary()
    else:
        print("Analysis failed", file=sys.stderr)
        sys.exit(1)

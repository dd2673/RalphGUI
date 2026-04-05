"""
Circuit Breaker Component for Ralph
Prevents runaway token consumption by detecting stagnation
Based on Michael Nygard's "Release It!" pattern
"""

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class CircuitBreakerState(Enum):
    """Circuit Breaker States"""
    CLOSED = "CLOSED"       # Normal operation, progress detected
    HALF_OPEN = "HALF_OPEN" # Monitoring mode, checking for recovery
    OPEN = "OPEN"           # Failure detected, execution halted


# Configuration thresholds
CB_NO_PROGRESS_THRESHOLD = 3
CB_SAME_ERROR_THRESHOLD = 5
CB_OUTPUT_DECLINE_THRESHOLD = 70
CB_PERMISSION_DENIAL_THRESHOLD = 2
CB_COOLDOWN_MINUTES = 30
CB_AUTO_RESET = False


def get_iso_timestamp() -> str:
    """Get current ISO timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso_to_epoch(iso_timestamp: str) -> int:
    """Parse ISO timestamp to epoch seconds."""
    # Handle timestamps with or without timezone
    try:
        # Try parsing with timezone first
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except ValueError:
        # Fallback: try parsing without timezone (assume UTC)
        try:
            dt = datetime.fromisoformat(iso_timestamp)
            return int(dt.timestamp())
        except ValueError:
            return 0


def _get_default_state() -> dict:
    """Get default circuit breaker state structure."""
    return {
        "state": CircuitBreakerState.CLOSED.value,
        "last_change": get_iso_timestamp(),
        "consecutive_no_progress": 0,
        "consecutive_same_error": 0,
        "consecutive_permission_denials": 0,
        "last_progress_loop": 0,
        "total_opens": 0,
        "reason": "",
        "current_loop": 0
    }


def _ensure_file_exists(state_file: str) -> None:
    """Ensure state file exists with valid JSON."""
    path = Path(state_file)
    if path.exists():
        try:
            with open(path, 'r') as f:
                json.load(f)
            return
        except (json.JSONDecodeError, IOError):
            path.unlink()

    # Create default state file
    with open(path, 'w') as f:
        json.dump(_get_default_state(), f, indent=4)


def _ensure_history_file_exists(history_file: str) -> None:
    """Ensure history file exists with valid JSON array."""
    path = Path(history_file)
    if path.exists():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return
                path.unlink()
        except (json.JSONDecodeError, IOError):
            path.unlink()

    # Create empty history array
    with open(path, 'w') as f:
        json.dump([], f)


def init_circuit_breaker(state_file: str, ralph_dir: str = ".ralph") -> CircuitBreakerState:
    """
    Initialize circuit breaker state.

    Args:
        state_file: Path to circuit breaker state file
        ralph_dir: Ralph directory for history files

    Returns:
        Current circuit breaker state after initialization
    """
    # Determine history file path
    history_file = os.path.join(ralph_dir, ".circuit_breaker_history")

    # Ensure state file exists
    _ensure_file_exists(state_file)

    # Ensure history file exists
    _ensure_history_file_exists(history_file)

    # Check if OPEN state should transition
    with open(state_file, 'r') as f:
        state_data = json.load(f)

    current_state = state_data.get("state", CircuitBreakerState.CLOSED.value)

    if current_state == CircuitBreakerState.OPEN.value:
        if CB_AUTO_RESET:
            # Auto-reset: bypass cooldown, go straight to CLOSED
            new_state = _get_default_state()
            new_state["state"] = CircuitBreakerState.CLOSED.value
            new_state["total_opens"] = state_data.get("total_opens", 0)
            new_state["reason"] = "Auto-reset on startup"

            with open(state_file, 'w') as f:
                json.dump(new_state, f, indent=4)

            _log_circuit_transition(
                history_file,
                CircuitBreakerState.OPEN.value,
                CircuitBreakerState.CLOSED.value,
                "Auto-reset on startup (CB_AUTO_RESET=true)",
                state_data.get("current_loop", 0)
            )
        else:
            # Cooldown: check if enough time has elapsed
            opened_at = state_data.get("opened_at", state_data.get("last_change", ""))

            if opened_at:
                opened_epoch = parse_iso_to_epoch(opened_at)
                current_epoch = int(datetime.now(timezone.utc).timestamp())
                elapsed_minutes = (current_epoch - opened_epoch) // 60

                if elapsed_minutes >= CB_COOLDOWN_MINUTES:
                    # Transition to HALF_OPEN
                    state_data["state"] = CircuitBreakerState.HALF_OPEN.value
                    state_data["last_change"] = get_iso_timestamp()
                    state_data["reason"] = f"Cooldown recovery: {elapsed_minutes}m elapsed"

                    with open(state_file, 'w') as f:
                        json.dump(state_data, f, indent=4)

                    _log_circuit_transition(
                        history_file,
                        CircuitBreakerState.OPEN.value,
                        CircuitBreakerState.HALF_OPEN.value,
                        f"Cooldown elapsed ({elapsed_minutes}m >= {CB_COOLDOWN_MINUTES}m)",
                        state_data.get("current_loop", 0)
                    )

    return CircuitBreakerState(get_circuit_state(state_file))


def get_circuit_state(state_file: str) -> CircuitBreakerState:
    """
    Get current circuit breaker state.

    Args:
        state_file: Path to circuit breaker state file

    Returns:
        Current circuit breaker state
    """
    if not os.path.exists(state_file):
        return CircuitBreakerState.CLOSED

    try:
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        return CircuitBreakerState(state_data.get("state", CircuitBreakerState.CLOSED.value))
    except (json.JSONDecodeError, ValueError, IOError):
        return CircuitBreakerState.CLOSED


def can_execute(state_file: str) -> bool:
    """
    Check if circuit breaker allows execution.

    Args:
        state_file: Path to circuit breaker state file

    Returns:
        True if circuit allows execution, False otherwise
    """
    state = get_circuit_state(state_file)
    return state != CircuitBreakerState.OPEN


def record_loop_result(
    state_file: str,
    loop_number: int,
    files_changed: int,
    has_errors: bool,
    output_length: int,
    ralph_dir: str = ".ralph"
) -> bool:
    """
    Record loop execution result and update circuit breaker state.

    Args:
        state_file: Path to circuit breaker state file
        loop_number: Current loop number
        files_changed: Number of files changed in this loop
        has_errors: Whether errors were detected
        output_length: Length of Claude output
        ralph_dir: Ralph directory for response analysis file

    Returns:
        True if execution can continue, False if circuit opened
    """
    init_circuit_breaker(state_file, ralph_dir)

    with open(state_file, 'r') as f:
        state_data = json.load(f)

    current_state = state_data.get("state", CircuitBreakerState.CLOSED.value)
    consecutive_no_progress = int(state_data.get("consecutive_no_progress", 0))
    consecutive_same_error = int(state_data.get("consecutive_same_error", 0))
    consecutive_permission_denials = int(state_data.get("consecutive_permission_denials", 0))
    last_progress_loop = int(state_data.get("last_progress_loop", 0))

    # Check response analysis file for additional signals
    response_analysis_file = os.path.join(ralph_dir, ".response_analysis")
    has_completion_signal = False
    ralph_files_modified = 0
    has_permission_denials = False
    asking_questions = False

    if os.path.exists(response_analysis_file):
        try:
            with open(response_analysis_file, 'r') as f:
                analysis = json.load(f)

            analysis_data = analysis.get("analysis", {})

            # Check completion signal
            has_completion_signal = analysis_data.get("has_completion_signal", False)
            exit_signal = analysis_data.get("exit_signal", False)
            if exit_signal:
                has_completion_signal = True

            # Check files modified by Claude
            ralph_files_modified = int(analysis_data.get("files_modified", 0))

            # Check permission denials
            has_permission_denials = analysis_data.get("has_permission_denials", False)

            # Check if Claude is asking questions
            asking_questions = analysis_data.get("asking_questions", False)
        except (json.JSONDecodeError, IOError):
            pass

    # Track permission denials
    if has_permission_denials:
        consecutive_permission_denials += 1
    else:
        consecutive_permission_denials = 0

    # Determine if progress was made
    has_progress = False

    if files_changed > 0:
        has_progress = True
        consecutive_no_progress = 0
        last_progress_loop = loop_number
    elif has_completion_signal:
        has_progress = True
        consecutive_no_progress = 0
        last_progress_loop = loop_number
    elif ralph_files_modified > 0:
        has_progress = True
        consecutive_no_progress = 0
        last_progress_loop = loop_number
    elif asking_questions:
        # Claude asking questions - not progress but not stagnation either
        has_progress = False
    else:
        consecutive_no_progress += 1

    # Detect same error repetition
    if has_errors:
        consecutive_same_error += 1
    else:
        consecutive_same_error = 0

    # Determine new state and reason
    new_state = current_state
    reason = ""

    # State transitions
    if current_state == CircuitBreakerState.CLOSED.value:
        # Permission denials take highest priority
        if consecutive_permission_denials >= CB_PERMISSION_DENIAL_THRESHOLD:
            new_state = CircuitBreakerState.OPEN.value
            reason = f"Permission denied in {consecutive_permission_denials} consecutive loops - update ALLOWED_TOOLS in .ralphrc"
        elif consecutive_no_progress >= CB_NO_PROGRESS_THRESHOLD:
            new_state = CircuitBreakerState.OPEN.value
            reason = f"No progress detected in {consecutive_no_progress} consecutive loops"
        elif consecutive_same_error >= CB_SAME_ERROR_THRESHOLD:
            new_state = CircuitBreakerState.OPEN.value
            reason = f"Same error repeated in {consecutive_same_error} consecutive loops"
        elif consecutive_no_progress >= 2:
            new_state = CircuitBreakerState.HALF_OPEN.value
            reason = f"Monitoring: {consecutive_no_progress} loops without progress"

    elif current_state == CircuitBreakerState.HALF_OPEN.value:
        # Permission denials take highest priority
        if consecutive_permission_denials >= CB_PERMISSION_DENIAL_THRESHOLD:
            new_state = CircuitBreakerState.OPEN.value
            reason = f"Permission denied in {consecutive_permission_denials} consecutive loops - update ALLOWED_TOOLS in .ralphrc"
        elif has_progress:
            new_state = CircuitBreakerState.CLOSED.value
            reason = "Progress detected, circuit recovered"
        elif consecutive_no_progress >= CB_NO_PROGRESS_THRESHOLD:
            new_state = CircuitBreakerState.OPEN.value
            reason = f"No recovery, opening circuit after {consecutive_no_progress} loops"

    elif current_state == CircuitBreakerState.OPEN.value:
        reason = "Circuit breaker is open, execution halted"

    # Update total_opens counter
    total_opens = int(state_data.get("total_opens", 0))
    if new_state == CircuitBreakerState.OPEN.value and current_state != CircuitBreakerState.OPEN.value:
        total_opens += 1

    # Determine opened_at timestamp
    opened_at = None
    if new_state == CircuitBreakerState.OPEN.value and current_state != CircuitBreakerState.OPEN.value:
        opened_at = get_iso_timestamp()
    elif new_state == CircuitBreakerState.OPEN.value and current_state == CircuitBreakerState.OPEN.value:
        opened_at = state_data.get("opened_at", state_data.get("last_change", ""))

    # Build new state
    new_state_data = {
        "state": new_state,
        "last_change": get_iso_timestamp(),
        "consecutive_no_progress": consecutive_no_progress,
        "consecutive_same_error": consecutive_same_error,
        "consecutive_permission_denials": consecutive_permission_denials,
        "last_progress_loop": last_progress_loop,
        "total_opens": total_opens,
        "reason": reason,
        "current_loop": loop_number
    }

    if opened_at:
        new_state_data["opened_at"] = opened_at

    # Write state file
    with open(state_file, 'w') as f:
        json.dump(new_state_data, f, indent=4)

    # Log state transition
    history_file = os.path.join(ralph_dir, ".circuit_breaker_history")
    if new_state != current_state:
        _log_circuit_transition(history_file, current_state, new_state, reason, loop_number)

    # Return exit code based on new state
    return new_state != CircuitBreakerState.OPEN.value


def _log_circuit_transition(
    history_file: str,
    from_state: str,
    to_state: str,
    reason: str,
    loop_number: int
) -> None:
    """
    Log circuit breaker state transition to history file.

    Args:
        history_file: Path to history file
        from_state: Previous state
        to_state: New state
        reason: Reason for transition
        loop_number: Current loop number
    """
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
    except (json.JSONDecodeError, IOError):
        history = []

    transition = {
        "timestamp": get_iso_timestamp(),
        "loop": loop_number,
        "from_state": from_state,
        "to_state": to_state,
        "reason": reason
    }

    history.append(transition)

    with open(history_file, 'w') as f:
        json.dump(history, f, indent=4)


def should_halt_execution(state_file: str, ralph_dir: str = ".ralph") -> bool:
    """
    Check if loop should halt due to circuit breaker being open.

    Args:
        state_file: Path to circuit breaker state file
        ralph_dir: Ralph directory

    Returns:
        True if execution should halt, False otherwise
    """
    state = get_circuit_state(state_file)

    if state == CircuitBreakerState.OPEN:
        _display_circuit_status(state_file)
        return True

    return False


def _display_circuit_status(state_file: str) -> None:
    """Display circuit breaker status to console."""
    try:
        with open(state_file, 'r') as f:
            state_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        state_data = _get_default_state()

    state = state_data.get("state", CircuitBreakerState.CLOSED.value)
    reason = state_data.get("reason", "")
    no_progress = state_data.get("consecutive_no_progress", 0)
    last_progress = state_data.get("last_progress_loop", 0)
    current_loop = state_data.get("current_loop", "N/A")
    total_opens = state_data.get("total_opens", 0)

    # Color codes for console output
    if state == CircuitBreakerState.CLOSED.value:
        color = "\033[0;32m"  # Green
        icon = "✅"
    elif state == CircuitBreakerState.HALF_OPEN.value:
        color = "\033[1;33m"  # Yellow
        icon = "⚠️ "
    else:
        color = "\033[0;31m"  # Red
        icon = "🚨"

    nc = "\033[0m"

    print(f"{color}╔════════════════════════════════════════════════════════════╗{nc}")
    print(f"{color}║           Circuit Breaker Status                          ║{nc}")
    print(f"{color}╚════════════════════════════════════════════════════════════╝{nc}")
    print(f"{color}State:{nc}                 {icon} {state}")
    print(f"{color}Reason:{nc}                {reason}")
    print(f"{color}Loops since progress:{nc} {no_progress}")
    print(f"{color}Last progress:{nc}        Loop #{last_progress}")
    print(f"{color}Current loop:{nc}         #{current_loop}")
    print(f"{color}Total opens:{nc}          {total_opens}")
    print("")

    print(f"{color}╔════════════════════════════════════════════════════════════╗{nc}")
    print(f"{color}║  EXECUTION HALTED: Circuit Breaker Opened                 ║{nc}")
    print(f"{color}╚════════════════════════════════════════════════════════════╝{nc}")
    print("")
    print(f"{color}Ralph has detected that no progress is being made.{nc}")
    print("")
    print(f"{color}Possible reasons:{nc}")
    print("  • Project may be complete (check .ralph/fix_plan.md)")
    print("  • Claude may be stuck on an error")
    print("  • .ralph/PROMPT.md may need clarification")
    print("  • Manual intervention may be required")
    print("")
    print(f"{color}To continue:{nc}")
    print("  1. Review recent logs: tail -20 .ralph/logs/ralph.log")
    print("  2. Check Claude output: ls -lt .ralph/logs/claude_output_*.log | head -1")
    print("  3. Update .ralph/fix_plan.md if needed")
    print("  4. Reset circuit breaker: ralph --reset-circuit")
    print("")


def reset_circuit_breaker(state_file: str, reason: str = "Manual reset") -> None:
    """
    Reset circuit breaker to CLOSED state.

    Args:
        state_file: Path to circuit breaker state file
        reason: Reason for reset (default: "Manual reset")
    """
    state_data = _get_default_state()
    state_data["reason"] = reason

    with open(state_file, 'w') as f:
        json.dump(state_data, f, indent=4)

    print("\033[0;32m✅ Circuit breaker reset to CLOSED state\033[0m")

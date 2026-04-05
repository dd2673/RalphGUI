#!/usr/bin/env python3
"""
Ralph Loop - Claude Code Ralph Loop with Rate Limiting and Documentation
Adaptation of the Ralph technique for Claude Code with usage management

This script provides the core loop that repeatedly calls Claude Code
with rate limiting, circuit breaker, and session management.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import Ralph library components
from lib.date_utils import get_iso_timestamp, get_epoch_seconds, parse_iso_to_epoch
from lib.timeout_utils import portable_timeout, TimeoutExpired
from lib.response_analyzer import (
    analyze_response as lib_analyze_response,
    update_exit_signals as lib_update_exit_signals,
    store_session_id,
    get_last_session_id,
    should_resume_session,
)
from lib.circuit_breaker import (
    CircuitBreakerState,
    init_circuit_breaker,
    get_circuit_state,
    record_loop_result,
    should_halt_execution,
    reset_circuit_breaker,
    can_execute,
)
from lib.log_utils import rotate_logs as lib_rotate_logs
from lib.file_protection import validate_ralph_integrity, get_integrity_report

# =============================================================================
# Configuration
# =============================================================================

RALPH_DIR = ".ralph"
PROMPT_FILE = os.path.join(RALPH_DIR, "PROMPT.md")
LOG_DIR = os.path.join(RALPH_DIR, "logs")
DOCS_DIR = os.path.join(RALPH_DIR, "docs", "generated")
STATUS_FILE = os.path.join(RALPH_DIR, "status.json")
PROGRESS_FILE = os.path.join(RALPH_DIR, "progress.json")
LIVE_LOG_FILE = os.path.join(RALPH_DIR, "live.log")
CALL_COUNT_FILE = os.path.join(RALPH_DIR, ".call_count")
TOKEN_COUNT_FILE = os.path.join(RALPH_DIR, ".token_count")
TIMESTAMP_FILE = os.path.join(RALPH_DIR, ".last_reset")
CLAUDE_SESSION_FILE = os.path.join(RALPH_DIR, ".claude_session_id")
RALPH_SESSION_FILE = os.path.join(RALPH_DIR, ".ralph_session")
RALPH_SESSION_HISTORY_FILE = os.path.join(RALPH_DIR, ".ralph_session_history")
EXIT_SIGNALS_FILE = os.path.join(RALPH_DIR, ".exit_signals")
RESPONSE_ANALYSIS_FILE = os.path.join(RALPH_DIR, ".response_analysis")
CIRCUIT_BREAKER_STATE_FILE = os.path.join(RALPH_DIR, ".circuit_breaker_state")

# Defaults
DEFAULT_MAX_CALLS_PER_HOUR = 100
DEFAULT_MAX_TOKENS_PER_HOUR = 0
DEFAULT_VERBOSE = False
DEFAULT_CLAUDE_TIMEOUT_MINUTES = 15
DEFAULT_CLAUDE_OUTPUT_FORMAT = "json"
DEFAULT_CLAUDE_USE_CONTINUE = True
DEFAULT_CLAUDE_SESSION_EXPIRY_HOURS = 24
DEFAULT_CB_COOLDOWN_MINUTES = 30
DEFAULT_CB_AUTO_RESET = False
DEFAULT_CLAUDE_CODE_CMD = "claude"
DEFAULT_CLAUDE_AUTO_UPDATE = True
DEFAULT_DRY_RUN = False
DEFAULT_LIVE_OUTPUT = False

DEFAULT_ALLOWED_TOOLS = (
    "Write,Read,Edit,Bash(git add *),Bash(git commit *),Bash(git diff *),"
    "Bash(git log *),Bash(git status),Bash(git status *),Bash(git push *),"
    "Bash(git pull *),Bash(git fetch *),Bash(git checkout *),Bash(git branch *),"
    "Bash(git stash *),Bash(git merge *),Bash(git tag *),Bash(npm *),Bash(pytest)"
)

CLAUDE_MIN_VERSION = "2.0.76"

# Exit detection
MAX_CONSECUTIVE_TEST_LOOPS = 3
MAX_CONSECUTIVE_DONE_SIGNALS = 2

# Valid tool patterns
VALID_TOOL_PATTERNS = [
    "Write", "Read", "Edit", "MultiEdit", "Glob", "Grep", "Task", "TodoWrite",
    "WebFetch", "WebSearch", "Bash", "Bash(git *)", "Bash(npm *)", "Bash(bats *)",
    "Bash(python *)", "Bash(node *)", "NotebookEdit",
]

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
PURPLE = '\033[0;35m'
NC = '\033[0m'

# Global config dict
config: Dict[str, Any] = {}
loop_count = 0

# =============================================================================
# Logging
# =============================================================================

def log_status(level: str, message: str) -> None:
    """Log with timestamp and color."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    color = {"INFO": BLUE, "WARN": YELLOW, "ERROR": RED, "SUCCESS": GREEN, "LOOP": PURPLE}.get(level, "")

    try:
        print(f"{color}[{timestamp}] [{level}] {message}{NC}", file=sys.stderr)
    except Exception:
        pass

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, "ralph.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except Exception:
        pass


# =============================================================================
# Configuration Loading
# =============================================================================

def load_ralphrc() -> bool:
    """Load .ralphrc configuration file."""
    ralphrc_file = ".ralphrc"
    if not os.path.exists(ralphrc_file):
        return False

    try:
        with open(ralphrc_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return False

    rc_values: Dict[str, str] = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            rc_values[key] = value

    # Map .ralphrc to config
    mappings = {
        'ALLOWED_TOOLS': ('claude_allowed_tools', str),
        'SESSION_CONTINUITY': ('claude_use_continue', lambda v: v.lower() == 'true'),
        'SESSION_EXPIRY_HOURS': ('claude_session_expiry_hours', int),
        'RALPH_VERBOSE': ('verbose_progress', lambda v: v.lower() == 'true'),
        'CB_COOLDOWN_MINUTES': ('cb_cooldown_minutes', int),
        'CB_AUTO_RESET': ('cb_auto_reset', lambda v: v.lower() == 'true'),
        'CLAUDE_CODE_CMD': ('claude_code_cmd', str),
        'CLAUDE_AUTO_UPDATE': ('claude_auto_update', lambda v: v.lower() == 'true'),
        'CLAUDE_MODEL': ('claude_model', str),
        'CLAUDE_EFFORT': ('claude_effort', str),
        'RALPH_SHELL_INIT_FILE': ('ralph_shell_init_file', str),
        'MAX_CALLS_PER_HOUR': ('max_calls_per_hour', int),
        'MAX_TOKENS_PER_HOUR': ('max_tokens_per_hour', int),
        'CLAUDE_TIMEOUT_MINUTES': ('claude_timeout_minutes', int),
        'CLAUDE_OUTPUT_FORMAT': ('claude_output_format', str),
    }

    for key, (config_key, converter) in mappings.items():
        if key in rc_values:
            try:
                config[config_key] = converter(rc_values[key])
            except (ValueError, TypeError):
                pass

    return True


def apply_env_overrides() -> None:
    """Apply environment variable overrides to config."""
    env_mappings = {
        'MAX_CALLS_PER_HOUR': ('max_calls_per_hour', int),
        'MAX_TOKENS_PER_HOUR': ('max_tokens_per_hour', int),
        'CLAUDE_TIMEOUT_MINUTES': ('claude_timeout_minutes', int),
        'CLAUDE_OUTPUT_FORMAT': ('claude_output_format', str),
        'CLAUDE_ALLOWED_TOOLS': ('claude_allowed_tools', str),
        'CLAUDE_USE_CONTINUE': ('claude_use_continue', lambda v: v.lower() == 'true'),
        'CLAUDE_SESSION_EXPIRY_HOURS': ('claude_session_expiry_hours', int),
        'VERBOSE_PROGRESS': ('verbose_progress', lambda v: v.lower() == 'true'),
        'CB_COOLDOWN_MINUTES': ('cb_cooldown_minutes', int),
        'CB_AUTO_RESET': ('cb_auto_reset', lambda v: v.lower() == 'true'),
        'CLAUDE_CODE_CMD': ('claude_code_cmd', str),
        'CLAUDE_AUTO_UPDATE': ('claude_auto_update', lambda v: v.lower() == 'true'),
        'CLAUDE_MODEL': ('claude_model', str),
        'CLAUDE_EFFORT': ('claude_effort', str),
        'RALPH_SHELL_INIT_FILE': ('ralph_shell_init_file', str),
    }

    for env_key, (config_key, converter) in env_mappings.items():
        value = os.environ.get(env_key, '')
        if value:
            try:
                config[config_key] = converter(value)
            except (ValueError, TypeError):
                pass


# =============================================================================
# CLI Validation
# =============================================================================

def validate_claude_command() -> bool:
    """Verify Claude Code CLI is available."""
    cmd = config.get('claude_code_cmd', 'claude')

    if cmd.startswith('npx ') or cmd == 'npx':
        if not shutil.which('npx'):
            print(f"{RED}╔════════════════════════════════════════════════════════════╗{NC}")
            print(f"{RED}║  NPX NOT FOUND                                            ║{NC}")
            print(f"{RED}╚════════════════════════════════════════════════════════════╝{NC}")
            print(f"\n{YELLOW}CLAUDE_CODE_CMD is set to use npx, but npx is not installed.{NC}")
            print(f"\n{YELLOW}To fix this:{NC}")
            print("  1. Install Node.js (includes npx): https://nodejs.org")
            print("  2. Or install Claude Code globally:")
            print("     npm install -g @anthropic-ai/claude-code")
            return False
        return True

    if not shutil.which(cmd):
        print(f"{RED}╔════════════════════════════════════════════════════════════╗{NC}")
        print(f"{RED}║  CLAUDE CODE CLI NOT FOUND                                ║{NC}")
        print(f"{RED}╚════════════════════════════════════════════════════════════╝{NC}")
        print(f"\n{YELLOW}The Claude Code CLI command '{cmd}' is not available.{NC}")
        print(f"\n{YELLOW}Installation options:{NC}")
        print("  1. Install globally: npm install -g @anthropic-ai/claude-code")
        print("  2. Use npx: CLAUDE_CODE_CMD=\"npx @anthropic-ai/claude-code\"")
        return False

    return True


def validate_allowed_tools(tools_input: str) -> bool:
    """Validate allowed tools against whitelist."""
    if not tools_input:
        return True

    tools = [t.strip() for t in tools_input.split(',')]
    for tool in tools:
        if not tool:
            continue
        valid = tool in VALID_TOOL_PATTERNS or re.match(r'^Bash\(.+\)$', tool)
        if not valid:
            print(f"Error: Invalid tool: '{tool}'")
            print(f"Valid: {', '.join(VALID_TOOL_PATTERNS)}")
            return False
    return True


def check_claude_version() -> bool:
    """Check Claude CLI version."""
    cmd = config.get('claude_code_cmd', 'claude')
    try:
        result = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        match = re.search(r'(\d+\.\d+\.\d+)', output)
        if not match:
            return True
        version = match.group(1)
        if _compare_semver(version, CLAUDE_MIN_VERSION) >= 0:
            log_status("INFO", f"Claude CLI version {version} (>= {CLAUDE_MIN_VERSION})")
            return True
        else:
            log_status("WARN", f"Claude CLI version {version} < {CLAUDE_MIN_VERSION}")
            return False
    except Exception:
        return True


def _compare_semver(ver1: str, ver2: str) -> int:
    """Compare semver: returns 1 if ver1 > ver2, -1 if ver1 < ver2, 0 if equal."""
    def parse(v):
        parts = v.split('.')
        return [int(p) for p in parts[:3]] + [0] * (3 - len(parts[:3]))
    v1, v2 = parse(ver1), parse(ver2)
    for i in range(3):
        if v1[i] > v2[i]:
            return 1
        if v1[i] < v2[i]:
            return -1
    return 0


def check_claude_updates() -> None:
    """Check for Claude CLI updates."""
    if not config.get('claude_auto_update', True):
        return

    cmd = config.get('claude_code_cmd', 'claude')
    try:
        result = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=10)
        match = re.search(r'(\d+\.\d+\.\d+)', result.stdout + result.stderr)
        if not match:
            return
        installed = match.group(1)

        result = subprocess.run(["npm", "view", "@anthropic-ai/claude-code", "version"],
                               capture_output=True, text=True, timeout=10)
        latest = result.stdout.strip()
        if not latest:
            return

        if installed == latest:
            log_status("INFO", f"Claude CLI is up to date ({installed})")
            return

        if _compare_semver(installed, latest) >= 0:
            return

        log_status("INFO", f"Claude CLI update available: {installed} -> {latest}")
        try:
            subprocess.run(["npm", "update", "-g", "@anthropic-ai/claude-code"],
                          capture_output=True, timeout=120)
            log_status("SUCCESS", f"Claude CLI updated to {latest}")
        except Exception as e:
            log_status("WARN", f"Auto-update failed: {e}")
    except Exception:
        pass


# =============================================================================
# Session Management
# =============================================================================

def get_session_file_age_hours(file_path: str) -> float:
    """Get file age in hours."""
    if not os.path.exists(file_path):
        return 0.0
    try:
        mtime = os.path.getmtime(file_path)
        return (time.time() - mtime) / 3600
    except OSError:
        return -1.0


def init_claude_session() -> str:
    """Initialize or resume Claude session."""
    if os.path.exists(CLAUDE_SESSION_FILE):
        age_hours = get_session_file_age_hours(CLAUDE_SESSION_FILE)
        if age_hours < 0:
            _clear_session_files()
            return ""
        if age_hours >= config.get('claude_session_expiry_hours', 24):
            log_status("INFO", f"Session expired ({age_hours:.1f}h), starting new")
            _clear_session_files()
            return ""
        try:
            with open(CLAUDE_SESSION_FILE, 'r', encoding='utf-8') as f:
                session_id = f.read().strip()
            if session_id:
                log_status("INFO", f"Resuming session: {session_id[:20]}...")
                return session_id
        except Exception:
            pass
    log_status("INFO", "Starting new Claude session")
    return ""


def _clear_session_files() -> None:
    """Clear session files."""
    for f in [CLAUDE_SESSION_FILE]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass


def save_claude_session(output_file: str) -> None:
    """Save session ID from output."""
    if not os.path.exists(output_file):
        return
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('is_error', False):
            log_status("WARN", "Skipping session save due to is_error:true")
            return
        session_id = data.get('metadata', {}).get('session_id') or data.get('session_id') or data.get('sessionId')
        if session_id:
            with open(CLAUDE_SESSION_FILE, 'w', encoding='utf-8') as f:
                f.write(str(session_id))
            log_status("INFO", f"Saved session: {str(session_id)[:20]}...")
    except Exception:
        pass


def init_session_tracking() -> None:
    """Initialize session tracking."""
    ts = get_iso_timestamp()
    if not os.path.exists(RALPH_SESSION_FILE):
        new_id = _generate_session_id()
        session_data = {
            "session_id": new_id, "created_at": ts, "last_used": ts,
            "reset_at": "", "reset_reason": ""
        }
        _write_json(RALPH_SESSION_FILE, session_data)
        log_status("INFO", f"Initialized session tracking (session: {new_id})")
    else:
        try:
            with open(RALPH_SESSION_FILE, 'r', encoding='utf-8') as f:
                json.load(f)
        except (json.JSONDecodeError, IOError):
            log_status("WARN", "Corrupted session file, recreating...")
            new_id = _generate_session_id()
            session_data = {
                "session_id": new_id, "created_at": ts, "last_used": ts,
                "reset_at": ts, "reset_reason": "corrupted_file_recovery"
            }
            _write_json(RALPH_SESSION_FILE, session_data)


def _generate_session_id() -> str:
    """Generate unique session ID."""
    return f"ralph-{int(time.time())}-{int.from_bytes(os.urandom(4), 'big')}"


def reset_session(reason: str = "manual_reset") -> None:
    """Reset session."""
    ts = get_iso_timestamp()
    session_data = {
        "session_id": "", "created_at": "", "last_used": "",
        "reset_at": ts, "reset_reason": reason
    }
    _write_json(RALPH_SESSION_FILE, session_data)
    _clear_session_files()

    if os.path.exists(EXIT_SIGNALS_FILE):
        _write_json(EXIT_SIGNALS_FILE, {"test_only_loops": [], "done_signals": [], "completion_indicators": []})

    for f in [RESPONSE_ANALYSIS_FILE]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass

    _log_session_transition("active", "reset", reason)
    log_status("INFO", f"Session reset: {reason}")


def _log_session_transition(from_state: str, to_state: str, reason: str, loop_number: int = 0) -> None:
    """Log session transition to history."""
    ts = get_iso_timestamp()
    transition = {
        "timestamp": ts, "from_state": from_state, "to_state": to_state,
        "reason": reason, "loop_number": loop_number
    }
    history = []
    if os.path.exists(RALPH_SESSION_HISTORY_FILE):
        try:
            with open(RALPH_SESSION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        except (json.JSONDecodeError, IOError):
            history = []
    history.append(transition)
    history = history[-50:]
    _write_json(RALPH_SESSION_HISTORY_FILE, history)


def update_session_last_used() -> None:
    """Update last_used timestamp."""
    if not os.path.exists(RALPH_SESSION_FILE):
        return
    try:
        with open(RALPH_SESSION_FILE, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        session_data['last_used'] = get_iso_timestamp()
        _write_json(RALPH_SESSION_FILE, session_data)
    except Exception:
        pass


# =============================================================================
# Rate Limiting
# =============================================================================

def init_call_tracking() -> None:
    """Initialize call tracking, reset if new hour."""
    current_hour = datetime.now().strftime('%Y%m%d%H')
    last_reset = ""
    if os.path.exists(TIMESTAMP_FILE):
        try:
            with open(TIMESTAMP_FILE, 'r', encoding='utf-8') as f:
                last_reset = f.read().strip()
        except Exception:
            pass

    if current_hour != last_reset:
        for f, val in [(CALL_COUNT_FILE, "0"), (TOKEN_COUNT_FILE, "0"), (TIMESTAMP_FILE, current_hour)]:
            try:
                with open(f, 'w', encoding='utf-8') as fh:
                    fh.write(val)
            except Exception:
                pass
        log_status("INFO", f"Counters reset for new hour: {current_hour}")

    if not os.path.exists(EXIT_SIGNALS_FILE):
        _write_json(EXIT_SIGNALS_FILE, {"test_only_loops": [], "done_signals": [], "completion_indicators": []})

    init_circuit_breaker(CIRCUIT_BREAKER_STATE_FILE, RALPH_DIR)


def can_make_call() -> bool:
    """Check if we can make another call."""
    calls = _read_int(CALL_COUNT_FILE)
    if calls >= config.get('max_calls_per_hour', 100):
        return False
    if config.get('max_tokens_per_hour', 0) > 0:
        tokens = _read_int(TOKEN_COUNT_FILE)
        if tokens >= config.get('max_tokens_per_hour', 0):
            return False
    return True


def increment_call_counter() -> int:
    """Increment call counter."""
    calls = _read_int(CALL_COUNT_FILE) + 1
    try:
        with open(CALL_COUNT_FILE, 'w', encoding='utf-8') as f:
            f.write(str(calls))
    except Exception:
        pass
    return calls


def _read_int(filepath: str) -> int:
    """Read integer from file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return int(f.read().strip() or 0)
        except (ValueError, IOError):
            pass
    return 0


def extract_token_usage(output_file: str) -> int:
    """Extract token usage from output file."""
    if not os.path.exists(output_file):
        return 0
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        usage = data.get('usage') or data.get('metadata', {}).get('usage', {})
        input_t = usage.get('input_tokens', 0)
        output_t = usage.get('output_tokens', 0)
        return int(input_t) + int(output_t)
    except Exception:
        return 0


def update_token_count(output_file: str) -> None:
    """Accumulate token usage."""
    new_tokens = extract_token_usage(output_file)
    if new_tokens > 0:
        current = _read_int(TOKEN_COUNT_FILE)
        total = current + new_tokens
        try:
            with open(TOKEN_COUNT_FILE, 'w', encoding='utf-8') as f:
                f.write(str(total))
        except Exception:
            pass
        max_t = config.get('max_tokens_per_hour', 0)
        log_status("INFO", f"Tokens: {total}{'/' + str(max_t) if max_t > 0 else ''} (+{new_tokens})")


def wait_for_reset() -> None:
    """Wait for rate limit reset with countdown."""
    calls = _read_int(CALL_COUNT_FILE)
    tokens = _read_int(TOKEN_COUNT_FILE)
    max_calls = config.get('max_calls_per_hour', 100)
    max_tokens = config.get('max_tokens_per_hour', 0)

    reason = f"calls: {calls}/{max_calls}"
    if max_tokens > 0:
        reason += f", tokens: {tokens}/{max_tokens}"
    log_status("WARN", f"Rate limit reached ({reason}). Waiting for reset...")

    now = datetime.now()
    seconds = (60 - now.minute - 1) * 60 + (60 - now.second)
    log_status("INFO", f"Sleeping for {seconds} seconds...")

    while seconds > 0:
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        print(f"\r{YELLOW}Time until reset: {h:02d}:{m:02d}:{s:02d}{NC}", end='', file=sys.stderr)
        time.sleep(1)
        seconds -= 1
    print()

    for f, val in [(CALL_COUNT_FILE, "0"), (TOKEN_COUNT_FILE, "0"), (TIMESTAMP_FILE, datetime.now().strftime('%Y%m%d%H'))]:
        try:
            with open(f, 'w', encoding='utf-8') as fh:
                fh.write(val)
        except Exception:
            pass
    log_status("SUCCESS", "Rate limit reset!")


# =============================================================================
# Status and Metrics
# =============================================================================

def update_status(loop_count: int, calls_made: int, last_action: str, status: str, exit_reason: str = "") -> None:
    """Update status JSON."""
    tokens = _read_int(TOKEN_COUNT_FILE)
    now = datetime.now()
    next_reset = now.replace(minute=0, second=0, microsecond=0)
    if now.minute > 0 or now.second > 0:
        next_reset = next_reset.replace(hour=(next_reset.hour + 1) % 24)

    status_data = {
        "timestamp": get_iso_timestamp(),
        "loop_count": loop_count,
        "calls_made_this_hour": calls_made,
        "max_calls_per_hour": config.get('max_calls_per_hour', 100),
        "tokens_used_this_hour": tokens,
        "max_tokens_per_hour": config.get('max_tokens_per_hour', 0),
        "last_action": last_action,
        "status": status,
        "exit_reason": exit_reason,
        "next_reset": next_reset.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    }
    try:
        os.makedirs(RALPH_DIR, exist_ok=True)
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=4)
    except Exception:
        pass


def track_metrics(loop_num: int, duration: int, success: bool, calls: int) -> None:
    """Track metrics to JSONL."""
    os.makedirs(LOG_DIR, exist_ok=True)
    entry = {
        "timestamp": get_iso_timestamp(), "loop": loop_num,
        "duration": duration, "success": success, "calls": calls
    }
    try:
        with open(os.path.join(LOG_DIR, "metrics.jsonl"), 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def print_metrics_summary() -> None:
    """Print metrics summary."""
    metrics_file = os.path.join(LOG_DIR, "metrics.jsonl")
    if not os.path.exists(metrics_file):
        return
    try:
        total_loops = successful = total_calls = 0
        total_duration = 0
        with open(metrics_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    e = json.loads(line)
                    total_loops += 1
                    if e.get('success'):
                        successful += 1
                    total_duration += e.get('duration', 0)
                    total_calls += e.get('calls', 0)
                except json.JSONDecodeError:
                    continue
        if total_loops > 0:
            avg = total_duration / total_loops
            summary = {"total_loops": total_loops, "successful": successful, "avg_duration": avg, "total_calls": total_calls}
            log_status("INFO", f"Metrics: {summary}")
    except Exception:
        pass


# =============================================================================
# Exit Detection
# =============================================================================

def should_exit_gracefully() -> str:
    """Check if should exit gracefully."""
    if not os.path.exists(EXIT_SIGNALS_FILE):
        return ""

    try:
        with open(EXIT_SIGNALS_FILE, 'r', encoding='utf-8') as f:
            signals = json.load(f)
    except (json.JSONDecodeError, IOError):
        return ""

    test_loops = len(signals.get("test_only_loops", []))
    done_signals = len(signals.get("done_signals", []))
    completion_indicators = len(signals.get("completion_indicators", []))

    if config.get('verbose_progress'):
        log_status("DEBUG", f"Exit: test={test_loops} done={done_signals} completion={completion_indicators}")

    # Permission denials
    if os.path.exists(RESPONSE_ANALYSIS_FILE):
        try:
            with open(RESPONSE_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
            if analysis.get('analysis', {}).get('has_permission_denials'):
                denied = analysis.get('analysis', {}).get('denied_commands', [])
                log_status("WARN", f"Permission denied: {denied}")
                return "permission_denied"
        except (json.JSONDecodeError, IOError):
            pass

    # Test saturation
    if test_loops >= MAX_CONSECUTIVE_TEST_LOOPS:
        log_status("WARN", f"Exit: test saturation ({test_loops})")
        return "test_saturation"

    # Done signals
    if done_signals >= MAX_CONSECUTIVE_DONE_SIGNALS:
        log_status("WARN", f"Exit: completion signals ({done_signals})")
        return "completion_signals"

    # Safety circuit breaker
    if completion_indicators >= 5:
        log_status("WARN", f"Exit: safety circuit ({completion_indicators})")
        return "safety_circuit_breaker"

    # Strong completion with EXIT_SIGNAL
    claude_exit = False
    if os.path.exists(RESPONSE_ANALYSIS_FILE):
        try:
            with open(RESPONSE_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
            claude_exit = analysis.get('analysis', {}).get('exit_signal', False)
        except (json.JSONDecodeError, IOError):
            pass

    if completion_indicators >= 2 and claude_exit:
        log_status("WARN", f"Exit: project complete ({completion_indicators})")
        return "project_complete"

    # fix_plan.md completion
    fix_plan = os.path.join(RALPH_DIR, "fix_plan.md")
    if os.path.exists(fix_plan):
        try:
            with open(fix_plan, 'r', encoding='utf-8') as f:
                content = f.read()
            uncompleted = len(re.findall(r'^ *- *\[\s*\]', content, re.MULTILINE))
            completed = len(re.findall(r'^ *- *\[[xX]\]', content, re.MULTILINE))
            total = uncompleted + completed
            if total > 0 and completed == total:
                log_status("WARN", f"Exit: plan complete ({completed}/{total})")
                return "plan_complete"
        except Exception:
            pass

    return ""


def update_exit_signals_from_analysis() -> None:
    """Update exit signals based on response analysis."""
    if not os.path.exists(RESPONSE_ANALYSIS_FILE):
        return
    try:
        with open(RESPONSE_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    data = analysis.get("analysis", {})
    is_test_only = data.get("is_test_only", False)
    has_completion = data.get("has_completion_signal", False)
    loop_number = analysis.get("loop_number", 0)
    has_progress = data.get("has_progress", False)
    exit_signal = data.get("exit_signal", False)

    signals = {"test_only_loops": [], "done_signals": [], "completion_indicators": []}
    if os.path.exists(EXIT_SIGNALS_FILE):
        try:
            with open(EXIT_SIGNALS_FILE, 'r', encoding='utf-8') as f:
                signals = json.load(f)
        except (json.JSONDecodeError, IOError):
            signals = {"test_only_loops": [], "done_signals": [], "completion_indicators": []}

    if is_test_only:
        signals["test_only_loops"].append(loop_number)
    elif has_progress:
        signals["test_only_loops"] = []

    if has_completion:
        signals["done_signals"].append(loop_number)

    if exit_signal:
        signals["completion_indicators"].append(loop_number)

    signals["test_only_loops"] = signals["test_only_loops"][-5:]
    signals["done_signals"] = signals["done_signals"][-5:]
    signals["completion_indicators"] = signals["completion_indicators"][-5:]

    _write_json(EXIT_SIGNALS_FILE, signals)


def log_analysis_summary() -> None:
    """Log analysis summary."""
    if not os.path.exists(RESPONSE_ANALYSIS_FILE):
        return
    try:
        with open(RESPONSE_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
        data = analysis.get("analysis", {})
        summary = data.get("work_summary", "")
        files = data.get("files_modified", 0)
        exit_sig = data.get("exit_signal", False)
        if summary:
            log_status("INFO", f"Summary: {summary[:200]}")
        if files > 0:
            log_status("INFO", f"Files: {files}")
        if exit_sig:
            log_status("INFO", "EXIT_SIGNAL=true")
    except (json.JSONDecodeError, IOError):
        pass


# =============================================================================
# Claude Command Execution
# =============================================================================

def build_loop_context(loop_number: int) -> str:
    """Build loop context string."""
    context = f"Loop #{loop_number}. "

    fix_plan = os.path.join(RALPH_DIR, "fix_plan.md")
    if os.path.exists(fix_plan):
        try:
            with open(fix_plan, 'r', encoding='utf-8') as f:
                content = f.read()
            incomplete = len(re.findall(r'^ *- *\[\s*\]', content, re.MULTILINE))
            context += f"Remaining tasks: {incomplete}. "
        except Exception:
            pass

    if os.path.exists(CIRCUIT_BREAKER_STATE_FILE):
        try:
            with open(CIRCUIT_BREAKER_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f).get('state', 'CLOSED')
            if state != 'CLOSED':
                context += f"Circuit breaker: {state}. "
        except Exception:
            pass

    if os.path.exists(RESPONSE_ANALYSIS_FILE):
        try:
            with open(RESPONSE_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
            prev = analysis.get('analysis', {}).get('work_summary', '')
            if prev:
                context += f"Previous: {prev[:200]} "
        except Exception:
            pass

    if os.path.exists(RESPONSE_ANALYSIS_FILE):
        try:
            with open(RESPONSE_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
            if analysis.get('analysis', {}).get('asking_questions'):
                context += ("IMPORTANT: You asked questions last loop. "
                           "This is headless - do NOT ask questions. ")
        except Exception:
            pass

    return context[:500]


def build_claude_command(prompt_file: str, loop_context: str, session_id: str) -> List[str]:
    """Build Claude CLI command."""
    cmd = [config.get('claude_code_cmd', 'claude')]

    if not os.path.exists(prompt_file):
        log_status("ERROR", f"Prompt not found: {prompt_file}")
        return []

    if config.get('claude_model'):
        cmd.extend(["--model", config['claude_model']])
    if config.get('claude_effort'):
        cmd.extend(["--effort", config['claude_effort']])
    if config.get('claude_output_format') == "json":
        cmd.extend(["--output-format", "json"])

    if config.get('claude_allowed_tools'):
        cmd.append("--allowedTools")
        tools = [t.strip() for t in config['claude_allowed_tools'].split(',')]
        cmd.extend(tools)

    if config.get('claude_use_continue') and session_id:
        cmd.extend(["--resume", session_id])

    if loop_context:
        cmd.extend(["--append-system-prompt", loop_context])

    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        cmd.extend(["-p", prompt_content])
    except Exception:
        log_status("ERROR", "Failed to read prompt")
        return []

    return cmd


def _get_git_head() -> str:
    """Get git HEAD SHA."""
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def execute_claude_code(loop_number: int) -> int:
    """Execute Claude Code for one loop."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_file = os.path.join(LOG_DIR, f"claude_output_{timestamp}.log")

    loop_start_sha = _get_git_head()
    try:
        os.makedirs(RALPH_DIR, exist_ok=True)
        with open(os.path.join(RALPH_DIR, ".loop_start_sha"), 'w') as f:
            f.write(loop_start_sha)
    except Exception:
        pass

    if config.get('dry_run'):
        log_status("INFO", "[DRY RUN] Simulating execution")
        time.sleep(2)
        return 0

    calls_made = increment_call_counter()
    log_status("LOOP", f"Call {calls_made}/{config.get('max_calls_per_hour', 100)}")
    timeout_seconds = config.get('claude_timeout_minutes', 15) * 60
    log_status("INFO", f"Starting Claude Code (timeout: {config.get('claude_timeout_minutes', 15)}m)")

    loop_context = build_loop_context(loop_number)
    if loop_context and config.get('verbose_progress'):
        log_status("INFO", f"Context: {loop_context}")

    session_id = ""
    if config.get('claude_use_continue'):
        session_id = init_claude_session()

    claude_cmd = build_claude_command(config.get('prompt_file', PROMPT_FILE), loop_context, session_id)
    if not claude_cmd:
        return 1

    log_status("INFO", f"Mode: {config.get('claude_output_format', 'json')}")

    os.makedirs(LOG_DIR, exist_ok=True)

    try:
        if config.get('live_output'):
            exit_code = _execute_live(claude_cmd, output_file, timeout_seconds, loop_number)
        else:
            exit_code = _execute_background(claude_cmd, output_file, timeout_seconds)
    except TimeoutExpired:
        log_status("WARN", "Timeout")
        exit_code = 124
    except Exception as e:
        log_status("ERROR", f"Execute error: {e}")
        return 1

    if exit_code == 0:
        return _process_success(output_file, loop_number, calls_made)
    else:
        return _process_failure(output_file, exit_code, loop_number, calls_made)


def _execute_background(cmd: List[str], output_file: str, timeout_seconds: int) -> int:
    """Execute in background mode."""
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        result = portable_timeout(timeout_seconds, cmd,
                                 stdout=open(output_file, 'w', encoding='utf-8'),
                                 stderr=subprocess.PIPE,
                                 stdin=subprocess.DEVNULL)
        return result.returncode
    except TimeoutExpired:
        return 124
    except Exception as e:
        log_status("ERROR", f"Background exec error: {e}")
        return 1


def _execute_live(cmd: List[str], output_file: str, timeout_seconds: int, loop_number: int) -> int:
    """Execute with live output streaming - Windows compatible version."""
    live_cmd = []
    skip_next = False
    for arg in cmd:
        if skip_next:
            live_cmd.append("stream-json")
            skip_next = False
        elif arg == "--output-format":
            live_cmd.append(arg)
            skip_next = True
        else:
            live_cmd.append(arg)
    live_cmd.extend(["--verbose", "--include-partial-messages"])

    log_status("INFO", "Live streaming enabled")
    print(f"{PURPLE}━━━━━━━━━━━━━━━━ Output ━━━━━━━━━━━━━━━━{NC}", file=sys.stderr)

    os.makedirs(LOG_DIR, exist_ok=True)
    stderr_file = os.path.join(LOG_DIR, f"claude_stderr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    try:
        with open(output_file, 'w', encoding='utf-8') as out_f:
            with open(LIVE_LOG_FILE, 'a', encoding='utf-8') as live_f:
                process = subprocess.Popen(live_cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True)
                
                # 跨平台方案：使用线程读取输出
                import threading
                import queue
                
                stdout_queue = queue.Queue()
                stderr_queue = queue.Queue()
                stop_event = threading.Event()
                
                def stdout_reader():
                    try:
                        for line in iter(process.stdout.readline, ''):
                            if stop_event.is_set():
                                break
                            if line:
                                stdout_queue.put(line)
                    except Exception:
                        pass
                
                def stderr_reader():
                    try:
                        for line in iter(process.stderr.readline, ''):
                            if stop_event.is_set():
                                break
                            if line:
                                stderr_queue.put(line)
                    except Exception:
                        pass
                
                stdout_thread = threading.Thread(target=stdout_reader, daemon=True)
                stderr_thread = threading.Thread(target=stderr_reader, daemon=True)
                stdout_thread.start()
                stderr_thread.start()
                
                # 主循环：从队列读取并输出
                while process.poll() is None:
                    # 处理 stdout
                    try:
                        while True:
                            line = stdout_queue.get_nowait()
                            out_f.write(line)
                            live_f.write(line)
                            print(line, end='', file=sys.stderr)
                    except queue.Empty:
                        pass
                    
                    # 处理 stderr
                    try:
                        while True:
                            line = stderr_queue.get_nowait()
                            with open(stderr_file, 'a') as sf:
                                sf.write(line)
                    except queue.Empty:
                        pass
                    
                    time.sleep(0.1)  # 短暂休眠避免 CPU 占用过高
                
                # 进程结束，停止读取线程
                stop_event.set()
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)
                
                # 处理剩余输出
                try:
                    while True:
                        line = stdout_queue.get_nowait()
                        out_f.write(line)
                        live_f.write(line)
                        print(line, end='', file=sys.stderr)
                except queue.Empty:
                    pass
                
                try:
                    while True:
                        line = stderr_queue.get_nowait()
                        with open(stderr_file, 'a') as sf:
                            sf.write(line)
                except queue.Empty:
                    pass
                
                exit_code = process.returncode
    except Exception as e:
        log_status("ERROR", f"Live exec error: {e}")
        return 1

    print(f"\n{PURPLE}━━━━━━━━━━━━━━━━ End ━━━━━━━━━━━━━━━━━{NC}", file=sys.stderr)

    if config.get('claude_use_continue') and os.path.exists(output_file):
        _extract_session_from_stream(output_file)

    return exit_code


def _extract_session_from_stream(output_file: str) -> None:
    """Extract session ID from stream output."""
    if not os.path.exists(output_file):
        return
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '"type"' in line and '"result"' in line:
                    try:
                        data = json.loads(line)
                        sid = data.get('sessionId') or data.get('session_id')
                        if sid:
                            with open(CLAUDE_SESSION_FILE, 'w') as f:
                                f.write(str(sid))
                            log_status("INFO", "Session extracted from stream")
                            return
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass


def _process_success(output_file: str, loop_number: int, calls_made: int) -> int:
    """Process successful execution."""
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('is_error', False):
                log_status("ERROR", f"is_error: {data.get('result', 'unknown')}")
                reset_session("api_error")
                return 1
        except (json.JSONDecodeError, IOError):
            pass

    _write_json(PROGRESS_FILE, {"status": "completed", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
    log_status("SUCCESS", "Claude Code completed")

    if config.get('claude_use_continue'):
        save_claude_session(output_file)

    update_token_count(output_file)

    log_status("INFO", "Analyzing response...")
    result = lib_analyze_response(output_file, loop_number, RESPONSE_ANALYSIS_FILE, RALPH_DIR)

    if result is not None and not isinstance(result, bool):
        update_exit_signals_from_analysis()
        log_analysis_summary()
    elif result is True or (result is not None and result == 0):
        update_exit_signals_from_analysis()
        log_analysis_summary()
    else:
        log_status("WARN", "Analysis failed")
        try:
            if os.path.exists(RESPONSE_ANALYSIS_FILE):
                os.remove(RESPONSE_ANALYSIS_FILE)
        except Exception:
            pass

    files_changed = _count_changed_files()
    has_errors = _detect_errors(output_file)
    output_length = os.path.getsize(output_file) if os.path.exists(output_file) else 0

    circuit_ok = record_loop_result(CIRCUIT_BREAKER_STATE_FILE, loop_number,
                                    files_changed, has_errors, output_length, RALPH_DIR)
    if circuit_ok == 0 or circuit_ok is False:
        log_status("WARN", "Circuit breaker opened")
        return 3

    return 0


def _process_failure(output_file: str, exit_code: int, loop_number: int, calls_made: int) -> int:
    """Process failed execution."""
    _write_json(PROGRESS_FILE, {"status": "failed", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

    if exit_code == 124:
        log_status("WARN", "Timeout")
        files_changed = _count_changed_files()
        if files_changed > 0:
            log_status("INFO", f"Timeout but {files_changed} files changed - productive")
            if config.get('claude_use_continue'):
                save_claude_session(output_file)
            lib_analyze_response(output_file, loop_number, RESPONSE_ANALYSIS_FILE, RALPH_DIR)
            update_exit_signals_from_analysis()
            record_loop_result(CIRCUIT_BREAKER_STATE_FILE, loop_number, files_changed, False, 0, RALPH_DIR)
            return 0
        return 1

    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'rate_limit_event' in content or '5.*hour.*limit' in content.lower():
                log_status("ERROR", "API limit reached")
                return 2
        except Exception:
            pass

    log_status("ERROR", f"Execution failed ({exit_code})")
    return 1


def _count_changed_files() -> int:
    """Count changed files."""
    sha_file = os.path.join(RALPH_DIR, ".loop_start_sha")
    start_sha = ""
    if os.path.exists(sha_file):
        try:
            with open(sha_file, 'r') as f:
                start_sha = f.read().strip()
        except Exception:
            pass

    current_sha = _get_git_head()

    try:
        if start_sha and current_sha and start_sha != current_sha:
            result = subprocess.run(["git", "diff", "--name-only", start_sha, current_sha],
                                  capture_output=True, text=True, timeout=10)
            committed = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        else:
            committed = 0

        result = subprocess.run(["git", "diff", "--name-only"],
                              capture_output=True, text=True, timeout=10)
        unstaged = set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()

        result = subprocess.run(["git", "diff", "--name-only", "--cached"],
                              capture_output=True, text=True, timeout=10)
        staged = set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()

        return committed + len(unstaged | staged)
    except Exception:
        return 0


def _detect_errors(output_file: str) -> bool:
    """Detect errors in output."""
    if not os.path.exists(output_file):
        return False
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        lines = content.split('\n')
        filtered = [l for l in lines if not re.search(r'"[^"]*error[^"]*":', l)]
        filtered_text = '\n'.join(filtered)
        patterns = [r'^Error:', r'^ERROR:', r'^error:', r'\]: error', r'Link: error',
                   r'Error occurred', r'failed with error', r'[Ee]xception', r'\bFatal\b']
        for p in patterns:
            if re.search(p, filtered_text, re.MULTILINE):
                return True
    except Exception:
        pass
    return False


# =============================================================================
# Helpers
# =============================================================================

def _write_json(filepath: str, data: Any) -> None:
    """Write JSON to file."""
    try:
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_reset_circuit() -> None:
    """Handle --reset-circuit."""
    init_circuit_breaker(CIRCUIT_BREAKER_STATE_FILE, RALPH_DIR)
    reset_circuit_breaker(CIRCUIT_BREAKER_STATE_FILE, "Manual reset")
    reset_session("manual_circuit_reset")


def cmd_reset_session() -> None:
    """Handle --reset-session."""
    reset_session("manual_reset")
    print(f"{GREEN}Session reset successfully{NC}")


def cmd_circuit_status() -> None:
    """Handle --circuit-status."""
    init_circuit_breaker(CIRCUIT_BREAKER_STATE_FILE, RALPH_DIR)
    state = get_circuit_state(CIRCUIT_BREAKER_STATE_FILE)
    print(f"\n{GREEN}╔══════════════════════════════════════════╗{NC}")
    print(f"{GREEN}║  Circuit Breaker Status                 ║{NC}")
    print(f"{GREEN}╚══════════════════════════════════════════╝{NC}")
    print(f"State: {state.value}")
    print(f"Can execute: {can_execute(CIRCUIT_BREAKER_STATE_FILE)}\n")


def cmd_status() -> None:
    """Handle --status."""
    if os.path.exists(STATUS_FILE):
        print("Current Status:")
        try:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                print(json.dumps(json.load(f), indent=2))
        except (json.JSONDecodeError, IOError):
            with open(STATUS_FILE, 'r') as f:
                print(f.read())
    else:
        print("No status file found.")


# =============================================================================
# Main Loop
# =============================================================================

def main() -> int:
    """Main entry point."""
    global loop_count, config

    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(RALPH_DIR, exist_ok=True)

    config = {
        'max_calls_per_hour': DEFAULT_MAX_CALLS_PER_HOUR,
        'max_tokens_per_hour': DEFAULT_MAX_TOKENS_PER_HOUR,
        'verbose_progress': DEFAULT_VERBOSE,
        'claude_timeout_minutes': DEFAULT_CLAUDE_TIMEOUT_MINUTES,
        'claude_output_format': DEFAULT_CLAUDE_OUTPUT_FORMAT,
        'claude_allowed_tools': DEFAULT_ALLOWED_TOOLS,
        'claude_use_continue': DEFAULT_CLAUDE_USE_CONTINUE,
        'claude_session_expiry_hours': DEFAULT_CLAUDE_SESSION_EXPIRY_HOURS,
        'cb_cooldown_minutes': DEFAULT_CB_COOLDOWN_MINUTES,
        'cb_auto_reset': DEFAULT_CB_AUTO_RESET,
        'claude_code_cmd': DEFAULT_CLAUDE_CODE_CMD,
        'claude_auto_update': DEFAULT_CLAUDE_AUTO_UPDATE,
        'claude_model': '',
        'claude_effort': '',
        'dry_run': DEFAULT_DRY_RUN,
        'live_output': DEFAULT_LIVE_OUTPUT,
        'prompt_file': PROMPT_FILE,
        'ralph_shell_init_file': '',
    }

    args = sys.argv[1:]
    i = 0
    special_cmd = None

    while i < len(args):
        arg = args[i]
        if arg in ('-h', '--help'):
            print("""
Ralph Loop for Claude Code

Usage: python ralph_loop.py [OPTIONS]

Options:
    -h, --help              Show help
    -c, --calls NUM         Max calls per hour (default: 100)
    -p, --prompt FILE      Prompt file (default: .ralph/PROMPT.md)
    -s, --status           Show status and exit
    -v, --verbose          Verbose output
    -l, --live             Live streaming output
    -t, --timeout MIN      Timeout in minutes (default: 15)
    --reset-circuit        Reset circuit breaker
    --circuit-status       Show circuit breaker status
    --reset-session        Reset session
    --dry-run              Simulate without API calls
    --output-format FMT    json or text
    --allowed-tools TOOLS  Allowed tools
    --no-continue          Disable session continuity
    --session-expiry HOURS Session expiry (default: 24)
    --auto-reset-circuit   Auto-reset circuit breaker
            """)
            sys.exit(0)
        elif arg in ('-s', '--status'):
            special_cmd = 'status'
            i += 1
        elif arg == '--reset-circuit':
            special_cmd = 'reset_circuit'
            i += 1
        elif arg == '--reset-session':
            special_cmd = 'reset_session'
            i += 1
        elif arg == '--circuit-status':
            special_cmd = 'circuit_status'
            i += 1
        elif arg in ('-c', '--calls'):
            config['max_calls_per_hour'] = int(args[i + 1])
            i += 2
        elif arg in ('-p', '--prompt'):
            config['prompt_file'] = args[i + 1]
            i += 2
        elif arg in ('-v', '--verbose'):
            config['verbose_progress'] = True
            i += 1
        elif arg in ('-l', '--live'):
            config['live_output'] = True
            i += 1
        elif arg in ('-t', '--timeout'):
            config['claude_timeout_minutes'] = int(args[i + 1])
            i += 2
        elif arg == '--dry-run':
            config['dry_run'] = True
            i += 1
        elif arg == '--output-format':
            config['claude_output_format'] = args[i + 1]
            i += 2
        elif arg == '--allowed-tools':
            config['claude_allowed_tools'] = args[i + 1]
            i += 2
        elif arg == '--no-continue':
            config['claude_use_continue'] = False
            i += 1
        elif arg == '--session-expiry':
            config['claude_session_expiry_hours'] = int(args[i + 1])
            i += 2
        elif arg == '--auto-reset-circuit':
            config['cb_auto_reset'] = True
            i += 1
        else:
            i += 1

    # Handle special commands
    if special_cmd == 'status':
        cmd_status()
        return 0
    elif special_cmd == 'reset_circuit':
        cmd_reset_circuit()
        return 0
    elif special_cmd == 'reset_session':
        cmd_reset_session()
        return 0
    elif special_cmd == 'circuit_status':
        cmd_circuit_status()
        return 0

    # Load config
    load_ralphrc()
    apply_env_overrides()

    if config.get('ralph_shell_init_file') and os.path.exists(config['ralph_shell_init_file']):
        log_status("INFO", f"Sourced: {config['ralph_shell_init_file']}")

    if not validate_claude_command():
        return 1

    check_claude_version()
    check_claude_updates()

    log_status("SUCCESS", "Ralph loop starting")
    log_status("INFO", f"Max calls: {config['max_calls_per_hour']}/hour")
    log_status("INFO", f"Logs: {LOG_DIR}/ | Status: {STATUS_FILE}")

    # Check old structure
    if os.path.exists("PROMPT.md") and not os.path.exists(RALPH_DIR):
        log_status("ERROR", "Old flat structure - use .ralph/ subfolder")
        print("\nRun 'ralph-migrate' to upgrade.")
        return 1

    if not os.path.exists(config['prompt_file']):
        log_status("ERROR", f"Prompt not found: {config['prompt_file']}")
        print("\nNot a Ralph project or PROMPT.md missing.")
        return 1

    if not validate_ralph_integrity():
        log_status("ERROR", "Integrity check failed")
        print(f"\n{get_integrity_report()}")
        return 1

    init_session_tracking()

    _write_json(EXIT_SIGNALS_FILE, {"test_only_loops": [], "done_signals": [], "completion_indicators": []})
    try:
        if os.path.exists(RESPONSE_ANALYSIS_FILE):
            os.remove(RESPONSE_ANALYSIS_FILE)
    except Exception:
        pass

    log_status("INFO", "Starting main loop...")

    while True:
        loop_count += 1

        log_file = os.path.join(LOG_DIR, "ralph.log")
        if os.path.exists(log_file):
            lib_rotate_logs(log_file, max_size_mb=10.0, keep_count=4)

        update_session_last_used()
        init_call_tracking()
        log_status("LOOP", f"=== Loop #{loop_count} ===")

        if not validate_ralph_integrity():
            os.makedirs(LOG_DIR, exist_ok=True)
            log_status("ERROR", "Integrity check failed during loop")
            print(f"\n{get_integrity_report()}")
            reset_session("integrity_failure")
            update_status(loop_count, _read_int(CALL_COUNT_FILE), "integrity_failure", "halted", "files_deleted")
            break

        if should_halt_execution(CIRCUIT_BREAKER_STATE_FILE, RALPH_DIR):
            reset_session("circuit_breaker_open")
            update_status(loop_count, _read_int(CALL_COUNT_FILE), "cb_open", "halted", "stagnation")
            log_status("ERROR", "Circuit breaker opened")
            break

        if not can_make_call():
            wait_for_reset()
            continue

        exit_reason = should_exit_gracefully()
        if exit_reason:
            if exit_reason == "permission_denied":
                log_status("ERROR", "Permission denied")
                reset_session("permission_denied")
                update_status(loop_count, _read_int(CALL_COUNT_FILE), "permission_denied", "halted", "permission_denied")
                print(f"\n{RED}Permission denied - update ALLOWED_TOOLS in .ralphrc{NC}\n")
                break

            log_status("SUCCESS", f"Graceful exit: {exit_reason}")
            reset_session("project_complete")
            update_status(loop_count, _read_int(CALL_COUNT_FILE), "graceful_exit", "completed", exit_reason)
            log_status("INFO", f"Total loops: {loop_count}, Calls: {_read_int(CALL_COUNT_FILE)}")
            print_metrics_summary()
            break

        update_status(loop_count, _read_int(CALL_COUNT_FILE), "executing", "running")
        loop_start = get_epoch_seconds()

        exec_result = execute_claude_code(loop_count)

        loop_duration = get_epoch_seconds() - loop_start
        calls_after = _read_int(CALL_COUNT_FILE)
        calls_this = max(0, calls_after - 1)
        track_metrics(loop_count, loop_duration, exec_result == 0, calls_this)

        if exec_result == 0:
            update_status(loop_count, calls_after, "completed", "success")
            time.sleep(5)
        elif exec_result == 3:
            reset_session("circuit_breaker_trip")
            update_status(loop_count, calls_after, "cb_open", "halted", "stagnation")
            log_status("ERROR", "Circuit breaker opened")
            break
        elif exec_result == 2:
            update_status(loop_count, calls_after, "api_limit", "paused")
            log_status("WARN", "API limit reached")
            print(f"\n{YELLOW}API limit reached. Options: 1) Wait  2) Exit{YELLOW}")
            try:
                choice = input("Choice (1/2): ").strip()
            except (EOFError, KeyboardInterrupt):
                choice = ""
            if choice == "2":
                reset_session("api_limit_exit")
                update_status(loop_count, calls_after, "api_limit_exit", "stopped", "api_5hour_limit")
                break
            log_status("INFO", "Auto-waiting 60 minutes...")
            time.sleep(60 * 60)
        else:
            update_status(loop_count, calls_after, "failed", "error")
            log_status("WARN", "Failed, waiting 30s...")
            time.sleep(30)

        log_status("LOOP", f"=== Loop #{loop_count} done ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())

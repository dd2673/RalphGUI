#!/usr/bin/env python3
"""
wizard_utils.py - Interactive prompt utilities for Ralph enable wizard

Provides consistent, user-friendly prompts for configuration.
"""

import os
import sys
import shutil
from typing import List, Optional

# Enable ANSI color support on Windows
if sys.platform == 'win32':
    os.system('')

# Color codes
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BOLD = '\033[1m'
NC = '\033[0m'  # No Color

# Track whether to use colors (can be disabled)
USE_COLORS = True


def _color(text: str, color_code: str) -> str:
    """Apply color to text if colors are enabled."""
    if USE_COLORS:
        return f"{color_code}{text}{NC}"
    return text


def _print(text: str = "", color: str = "") -> None:
    """Print text with optional color to stderr."""
    if color:
        print(_color(text, color), file=sys.stderr)
    else:
        print(text, file=sys.stderr)


def confirm(prompt: str, default: bool = False) -> bool:
    """
    Ask a yes/no question.

    Args:
        prompt: The question to ask
        default: Default answer (False = N, True = Y)

    Returns:
        True if user answered yes, False if no.
    """
    yn_hint = "[y/N]"
    if default:
        yn_hint = "[Y/n]"

    while True:
        _print(f"{CYAN}{prompt}{NC} {yn_hint}: ", color="")
        response = input().strip().lower()

        # Handle empty response (use default)
        if not response:
            response = "y" if default else "n"

        if response in ("y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            _print("Please answer yes (y) or no (n)", color=YELLOW)


def prompt_text(prompt: str, default: str = "") -> str:
    """
    Ask for text input with optional default.

    Args:
        prompt: The prompt text
        default: Default value

    Returns:
        User's input or default if empty.
    """
    if default:
        _print(f"{CYAN}{prompt}{NC} [{default}]: ", color="")
    else:
        _print(f"{CYAN}{prompt}{NC}: ", color="")

    response = input().strip()
    return response if response else default


def prompt_number(
    prompt: str,
    default: int = 0,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """
    Ask for numeric input with optional default and range.

    Args:
        prompt: The prompt text
        default: Default value
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        The validated number.
    """
    while True:
        default_hint = f" [{default}]" if default is not None else ""
        _print(f"{CYAN}{prompt}{NC}{default_hint}: ", color="")

        response = input().strip()

        # Use default if empty
        if not response:
            if default is not None:
                return default
            else:
                _print("Please enter a number", color=YELLOW)
                continue

        # Validate it's a number
        if not response.isdigit():
            _print("Please enter a valid number", color=YELLOW)
            continue

        value = int(response)

        # Check range if specified
        if min_val is not None and value < min_val:
            _print(f"Value must be at least {min_val}", color=YELLOW)
            continue

        if max_val is not None and value > max_val:
            _print(f"Value must be at most {max_val}", color=YELLOW)
            continue

        return value


def select_option(prompt: str, *options: str) -> int:
    """
    Present a list of options for single selection.

    Args:
        prompt: The question/prompt text
        *options: Options to present

    Returns:
        Index of selected option (0-based).
    """
    num_options = len(options)

    if num_options == 0:
        return 0

    # Display prompt and options
    _print("", color="")
    _print(f"{BOLD}{prompt}{NC}", color=BOLD)
    _print("", color="")

    for i, opt in enumerate(options, 1):
        _print(f"  {CYAN}{i}){NC} {opt}", color="")

    _print("", color="")

    while True:
        _print(f"Select option [1-{num_options}]: ", color="")
        response = input().strip()

        if not response.isdigit():
            _print(f"Please enter a number between 1 and {num_options}", color=YELLOW)
            continue

        value = int(response)
        if 1 <= value <= num_options:
            return value - 1
        else:
            _print(f"Please enter a number between 1 and {num_options}", color=YELLOW)


def select_multiple(prompt: str, *options: str) -> List[int]:
    """
    Present checkboxes for multi-selection.

    Args:
        prompt: The question/prompt text
        *options: Options to present

    Returns:
        List of selected indices.
    """
    num_options = len(options)
    if num_options == 0:
        return []

    # Track selected state
    selected = [False] * num_options

    # Display instructions
    _print("", color="")
    _print(f"{BOLD}{prompt}{NC}", color=BOLD)
    _print(f"{CYAN}(Enter numbers to toggle, press Enter when done){NC}", color=CYAN)
    _print("", color="")

    while True:
        # Display options with checkboxes
        for i, opt in enumerate(options):
            checkbox = "[ ]"
            if selected[i]:
                checkbox = f"[{GREEN}x{NC}]"
            _print(f"  {CYAN}{i+1}){NC} {checkbox} {opt}", color="")

        _print("", color="")
        _print(f"Toggle [1-{num_options}] or Enter to confirm: ", color="")

        response = input().strip()

        # Empty input = done
        if not response:
            break

        # Validate it's a number in range
        if not response.isdigit():
            _print(f"Please enter a number between 1 and {num_options}", color=YELLOW)
            continue

        value = int(response)
        if 1 <= value <= num_options:
            # Toggle the selection
            idx = value - 1
            selected[idx] = not selected[idx]
        else:
            _print(f"Please enter a number between 1 and {num_options}", color=YELLOW)

        # Move cursor up to redraw (approximate)
        for _ in range(num_options + 2):
            _print("\033[A\033[K", color="")

    # Build result list
    result = [i for i, s in enumerate(selected) if s]
    return result


def select_with_default(prompt: str, default_index: int, *options: str) -> int:
    """
    Present options with a recommended default.

    Args:
        prompt: The question/prompt text
        default_index: 1-based index of default option
        *options: Options to present

    Returns:
        Index of selected option (0-based).
    """
    num_options = len(options)

    if num_options == 0:
        return 0

    _print("", color="")
    _print(f"{BOLD}{prompt}{NC}", color=BOLD)
    _print("", color="")

    for i, opt in enumerate(options, 1):
        if i == default_index:
            _print(f"  {GREEN}{i}){NC} {opt} {GREEN}(recommended){NC}", color=GREEN)
        else:
            _print(f"  {CYAN}{i}){NC} {opt}", color=CYAN)

    _print("", color="")

    while True:
        _print(f"Select option [1-{num_options}] (default: {default_index}): ", color="")
        response = input().strip()

        # Use default if empty
        if not response:
            return default_index - 1

        if not response.isdigit():
            _print(f"Please enter a number between 1 and {num_options}", color=YELLOW)
            continue

        value = int(response)
        if 1 <= value <= num_options:
            return value - 1
        else:
            _print(f"Please enter a number between 1 and {num_options}", color=YELLOW)


def print_header(title: str, phase: Optional[str] = None) -> None:
    """
    Print a section header.

    Args:
        title: The header title
        phase: Optional phase number (e.g., "1 of 5")
    """
    line = "━" * 60
    _print("", color="")
    _print(f"{BOLD}{line}{NC}", color=BOLD)
    if phase:
        _print(f"{BOLD}  {title}{NC} {CYAN}({phase}){NC}", color=BOLD)
    else:
        _print(f"{BOLD}  {title}{NC}", color=BOLD)
    _print(f"{BOLD}{line}{NC}", color=BOLD)
    _print("", color="")


def print_bullet(text: str, symbol: str = "•") -> None:
    """
    Print a bullet point item.

    Args:
        text: The text to display
        symbol: Bullet symbol (default: "•")
    """
    _print(f"  {CYAN}{symbol}{NC} {text}", color="")


def print_success(text: str) -> None:
    """Print a success message."""
    _print(f"{GREEN}✓{NC} {text}", color=GREEN)


def print_warning(text: str) -> None:
    """Print a warning message."""
    _print(f"{YELLOW}⚠{NC} {text}", color=YELLOW)


def print_error(text: str) -> None:
    """Print an error message."""
    _print(f"{RED}✗{NC} {text}", color=RED)


def print_info(text: str) -> None:
    """Print an info message."""
    _print(f"{CYAN}ℹ{NC} {text}", color=CYAN)


def print_detection_result(label: str, value: str, available: bool = True) -> None:
    """
    Print a detection result with status.

    Args:
        label: What was detected
        value: The detected value
        available: Whether the item is available
    """
    if available:
        _print(f"  {GREEN}✓{NC} {label}: {BOLD}{value}{NC}", color="")
    else:
        _print(f"  {YELLOW}○{NC} {label}: {value}", color="")


def show_progress(current: int, total: int, message: str) -> None:
    """
    Display a progress indicator.

    Args:
        current: Current step number
        total: Total steps
        message: Current step message
    """
    bar_width = 30
    filled = current * bar_width // total
    empty = bar_width - filled

    bar = "█" * filled + "░" * empty
    _print(f"\r{CYAN}[{bar}]{NC} {current}/{total} {message}", color=CYAN)


def clear_line() -> None:
    """Clear the current line."""
    _print("\r\033[K", color="")


def print_summary(title: str, **items: str) -> None:
    """
    Print a summary box.

    Args:
        title: Summary title
        **items: Key=value pairs to display

    Example:
        print_summary("Configuration", Project="my-app", Type="typescript")
    """
    _print("", color="")

    line = "─" * 60
    _print(f"{BOLD}┌─ {title} ───────────────────────────────────────┐{NC}", color=BOLD)
    _print("│", color="")

    for key, value in items.items():
        _print(f"│  {CYAN}{key:<20}{NC} {value}", color=CYAN)

    _print("│", color="")
    _print(f"{BOLD}└────────────────────────────────────────────────────┘{NC}", color=BOLD)
    _print("", color="")


def get_terminal_width() -> int:
    """Get terminal width, default to 80 if unavailable."""
    try:
        width = shutil.get_terminal_size().columns
        return width if width > 0 else 80
    except (AttributeError, OSError):
        return 80

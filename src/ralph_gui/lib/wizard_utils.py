#!/usr/bin/env python3
"""
wizard_utils.py - Interactive prompt utilities for Ralph GUI wizard
Provides consistent, user-friendly prompts for configuration

POSIX compatible, Windows compatible, Python 3.6+
"""

import sys
import re
from pathlib import Path
from typing import List, Optional, Tuple

# Colors (ANSI escape codes)
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
NC = "\033[0m"  # No Color


def _colorize(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{NC}"


def _cyan(text: str) -> str:
    return _colorize(text, CYAN)


def _green(text: str) -> str:
    return _colorize(text, GREEN)


def _yellow(text: str) -> str:
    return _colorize(text, YELLOW)


def _red(text: str) -> str:
    return _colorize(text, RED)


def _bold(text: str) -> str:
    return _colorize(text, BOLD)


# =============================================================================
# BASIC PROMPTS
# =============================================================================

def confirm(prompt: str, default: str = "n") -> bool:
    """
    Ask a yes/no question.

    Args:
        prompt: The question to ask
        default: Default answer: "y" or "n" (optional, defaults to "n")

    Returns:
        True if user answered yes, False otherwise

    Example:
        if confirm("Continue with installation?", "y"):
            print("Installing...")
    """
    default_lower = default.lower()
    yn_hint = "[y/N]" if default_lower != "y" else "[Y/n]"

    while True:
        response = input(f"{_cyan(prompt)} {yn_hint}: ").strip().lower()

        # Handle empty response (use default)
        if not response:
            response = default_lower

        if response in ("y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            print(_yellow("Please answer yes (y) or no (n)"))


def prompt_text(prompt: str, default: str = "") -> str:
    """
    Ask for text input with optional default.

    Args:
        prompt: The prompt text
        default: Default value (optional)

    Returns:
        The user's input (or default if empty)

    Example:
        project_name = prompt_text("Project name", "my-project")
    """
    if default:
        response = input(f"{_cyan(prompt)} [{default}]: ").strip()
    else:
        response = input(f"{_cyan(prompt)}: ").strip()

    return response if response else default


def prompt_number(
    prompt: str,
    default: Optional[int] = None,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """
    Ask for numeric input with optional default and range.

    Args:
        prompt: The prompt text
        default: Default value (optional)
        min_val: Minimum value (optional)
        max_val: Maximum value (optional)

    Returns:
        The validated number

    Raises:
        ValueError: If input is invalid after max attempts
    """
    while True:
        default_str = str(default) if default is not None else ""
        prompt_text = f"{_cyan(prompt)} [{default_str}]: " if default_str else f"{_cyan(prompt)}: "

        response = input(prompt_text).strip()

        # Use default if empty
        if not response:
            if default is not None:
                return default
            else:
                print(_yellow("Please enter a number"))
                continue

        # Validate it's a number
        if not re.match(r"^-?\d+$", response):
            print(_yellow("Please enter a valid number"))
            continue

        num = int(response)

        # Check range if specified
        if min_val is not None and num < min_val:
            print(_yellow(f"Value must be at least {min_val}"))
            continue

        if max_val is not None and num > max_val:
            print(_yellow(f"Value must be at most {max_val}"))
            continue

        return num


# =============================================================================
# SELECTION PROMPTS
# =============================================================================

def select_option(prompt: str, *options: str) -> str:
    """
    Present a list of options for single selection.

    Args:
        prompt: The question/prompt text
        *options: The options to choose from

    Returns:
        The selected option text

    Example:
        choice = select_option("Select package manager", "npm", "yarn", "pnpm")
        print(f"Selected: {choice}")
    """
    options_list = list(options)
    num_options = len(options_list)

    if num_options == 0:
        return ""

    # Display prompt and options
    print()
    print(_bold(prompt))
    print()

    for i, opt in enumerate(options_list, 1):
        print(f"  {_cyan(str(i))}) {opt}")

    print()

    while True:
        response = input(f"Select option [1-{num_options}]: ").strip()

        # Validate it's a number in range
        if re.match(r"^\d+$", response):
            idx = int(response)
            if 1 <= idx <= num_options:
                return options_list[idx - 1]

        print(_yellow(f"Please enter a number between 1 and {num_options}"))


def select_multiple(prompt: str, *options: str) -> str:
    """
    Present checkboxes for multi-selection.

    Args:
        prompt: The question/prompt text
        *options: The options to choose from

    Returns:
        Comma-separated list of selected indices (0-based)
        Returns empty string if nothing selected

    Example:
        selected = select_multiple("Select task sources", "beads", "github", "prd")
        # If user selects first and third: selected="0,2"
        indices = [int(x) for x in selected.split(",") if x]
        for idx in indices:
            print(f"Selected: {options[idx]}")
    """
    options_list = list(options)
    num_options = len(options_list)

    # Track selected state (False = not selected, True = selected)
    selected = [False] * num_options

    # Display instructions
    print()
    print(_bold(prompt))
    print(_cyan("(Enter numbers to toggle, press Enter when done)"))
    print()

    while True:
        # Display options with checkboxes
        for i, opt in enumerate(options_list, 1):
            checkbox = "[ ]" if not selected[i - 1] else f"[{_green('x')}]"
            print(f"  {_cyan(str(i))}) {checkbox} {opt}")

        print()
        response = input(f"Toggle [1-{num_options}] or Enter to confirm: ").strip()

        # Empty input = done
        if not response:
            break

        # Validate it's a number in range
        if re.match(r"^\d+$", response):
            idx = int(response)
            if 1 <= idx <= num_options:
                selected[idx - 1] = not selected[idx - 1]
            else:
                print(_yellow(f"Please enter a number between 1 and {num_options}"))
        else:
            print(_yellow(f"Please enter a number between 1 and {num_options}"))

    # Build result string (comma-separated indices)
    result_parts = [str(i) for i, s in enumerate(selected) if s]
    return ",".join(result_parts)


def select_with_default(prompt: str, default_index: int, *options: str) -> str:
    """
    Present options with a recommended default.

    Args:
        prompt: The question/prompt text
        default_index: 1-based index of default option
        *options: The options to choose from

    Returns:
        The selected option text

    Example:
        choice = select_with_default("Select package manager", 2, "npm", "yarn", "pnpm")
        print(f"Selected: {choice}")
    """
    options_list = list(options)
    num_options = len(options_list)

    # Display prompt and options
    print()
    print(_bold(prompt))
    print()

    for i, opt in enumerate(options_list, 1):
        if i == default_index:
            print(f"  {_green(str(i))}) {opt} {_green('(recommended)')}")
        else:
            print(f"  {_cyan(str(i))}) {opt}")

    print()

    while True:
        response = input(f"Select option [1-{num_options}] (default: {default_index}): ").strip()

        # Use default if empty
        if not response:
            return options_list[default_index - 1]

        # Validate it's a number in range
        if re.match(r"^\d+$", response):
            idx = int(response)
            if 1 <= idx <= num_options:
                return options_list[idx - 1]

        print(_yellow(f"Please enter a number between 1 and {num_options}"))


# =============================================================================
# DISPLAY UTILITIES
# =============================================================================

def print_header(title: str, phase: str = "") -> None:
    """
    Print a section header.

    Args:
        title: The header title
        phase: Optional phase number (e.g., "1 of 5")
    """
    print()
    print(f"{_bold('━' * 60)}")
    if phase:
        print(f"{_bold('  ')}{_bold(title)}{_cyan(f' ({phase})')}")
    else:
        print(f"{_bold('  ')}{_bold(title)}")
    print(f"{_bold('━' * 60)}")
    print()


def print_bullet(text: str, symbol: str = "•") -> None:
    """
    Print a bullet point item.

    Args:
        text: The text to display
        symbol: Optional symbol (defaults to "•")
    """
    print(f"  {_cyan(symbol)} {text}")


def print_success(message: str) -> None:
    """
    Print a success message.

    Args:
        message: The message to display
    """
    print(f"{_green('✓')} {message}")


def print_warning(message: str) -> None:
    """
    Print a warning message.

    Args:
        message: The message to display
    """
    print(f"{_yellow('⚠')} {message}")


def print_error(message: str) -> None:
    """
    Print an error message.

    Args:
        message: The message to display
    """
    print(f"{_red('✗')} {message}")


def print_info(message: str) -> None:
    """
    Print an info message.

    Args:
        message: The message to display
    """
    print(f"{_cyan('ℹ')} {message}")


def print_detection_result(label: str, value: str, available: bool = True) -> None:
    """
    Print a detection result with status.

    Args:
        label: What was detected
        value: The detected value
        available: Whether the item is available (True/False)
    """
    if available:
        print(f"  {_green('✓')} {label}: {_bold(value)}")
    else:
        print(f"  {_yellow('○')} {label}: {value}")


# =============================================================================
# PROGRESS DISPLAY
# =============================================================================

def show_progress(current: int, total: int, message: str) -> None:
    """
    Display a simple progress indicator.

    Args:
        current: Current step number
        total: Total steps
        message: Current step message
    """
    bar_width = 30
    filled = current * bar_width // total
    empty = bar_width - filled

    bar = "█" * filled + "░" * empty
    print(f"\r{_cyan('[' + bar + ']')} {current}/{total} {message}", end="", flush=True)


def clear_line() -> None:
    """Clear the current line."""
    print("\r\033[K", end="")


# =============================================================================
# SUMMARY DISPLAY
# =============================================================================

def print_summary(title: str, *items: str) -> None:
    """
    Print a summary box.

    Args:
        title: Summary title
        *items: Key=value pairs to display

    Example:
        print_summary("Configuration", "Project=my-app", "Type=typescript", "Tasks=15")
    """
    print()
    print(f"{_bold('┌─ ' + title + ' ─' + '─' * (36 - len(title)) + '┐')}")
    print("│")

    for item in items:
        if "=" in item:
            key, value = item.split("=", 1)
            print(f"│  {_cyan(key + ':'):<22} {value}")

    print("│")
    print(f"{_bold('└' + '─' * 58 + '┘')}")
    print()


# =============================================================================
# PATH UTILITIES (using pathlib)
# =============================================================================

def normalize_path(path: str) -> Path:
    """
    Normalize a path string to a Path object.

    Args:
        path: Path string to normalize

    Returns:
        Normalized Path object

    Example:
        config_path = normalize_path("~/.config/ralph")
    """
    return Path(path).expanduser().resolve()


def ensure_dir(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Path to the directory

    Returns:
        The path to the directory
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_relative_to(path: Path, base: Path) -> Path:
    """
    Get path relative to base, handling cross-drive on Windows.

    Args:
        path: Path to make relative
        base: Base path

    Returns:
        Relative path
    """
    try:
        return path.relative_to(base)
    except ValueError:
        # Cross-drive on Windows, return absolute path
        return path


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Basic prompts
    "confirm",
    "prompt_text",
    "prompt_number",
    # Selection prompts
    "select_option",
    "select_multiple",
    "select_with_default",
    # Display utilities
    "print_header",
    "print_bullet",
    "print_success",
    "print_warning",
    "print_error",
    "print_info",
    "print_detection_result",
    # Progress display
    "show_progress",
    "clear_line",
    # Summary display
    "print_summary",
    # Path utilities
    "normalize_path",
    "ensure_dir",
    "path_relative_to",
    # Colors (for external use)
    "CYAN",
    "GREEN",
    "YELLOW",
    "RED",
    "BOLD",
    "NC",
]


if __name__ == "__main__":
    # Demo/test when run directly
    print_header("Wizard Utils Demo")

    name = prompt_text("Your name", "Anonymous")
    print_success(f"Hello, {name}!")

    if confirm("Do you like Python?", "y"):
        print_success("Great!")
    else:
        print_warning("That's okay!")

    age = prompt_number("Your age", 25, 1, 150)
    print_info(f"You are {age} years old")

    lang = select_option("Select language", "Python", "JavaScript", "Go", "Rust")
    print_success(f"You selected: {lang}")

    print_summary("Demo Results", f"Name={name}", f"Age={age}", f"Language={lang}")

#!/usr/bin/env python3
"""
Ralph for Claude Code - Uninstallation Script
Removes Ralph commands and home directory from the system.
"""

import sys
import os
import shutil
from pathlib import Path

# Configuration
INSTALL_DIR = Path.home() / ".local" / "bin"
RALPH_HOME = Path.home() / ".ralph"

# Windows-specific
if sys.platform == "win32":
    import winreg

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'
    BOLD = '\033[1m'

def is_windows():
    return sys.platform == "win32"

def log(level: str, message: str):
    colors = {
        "INFO": Colors.BLUE,
        "WARN": Colors.YELLOW,
        "ERROR": Colors.RED,
        "SUCCESS": Colors.GREEN
    }
    color = colors.get(level, Colors.NC)
    print(f"{color}[{level}] {message}{Colors.NC}")

def check_installation() -> bool:
    """Check if Ralph is installed."""
    # Check for any of the Ralph commands
    for cmd in ["ralph", "ralph-monitor", "ralph-setup", "ralph-import",
                "ralph-migrate", "ralph-enable", "ralph-enable-ci", "ralph-stats"]:
        for ext in ["", ".bat"]:
            if (INSTALL_DIR / f"{cmd}{ext}").exists():
                return True

    # Also check for Ralph home directory
    if RALPH_HOME.exists():
        return True

    return False

def show_removal_plan():
    """Display what will be removed."""
    print("")
    log("INFO", "The following will be removed:")
    print("")

    # Commands
    print(f"Commands in {INSTALL_DIR}:")
    found_commands = False
    for cmd in ["ralph", "ralph-monitor", "ralph-setup", "ralph-import",
                "ralph-migrate", "ralph-enable", "ralph-enable-ci", "ralph-stats"]:
        for ext in ["", ".bat"]:
            path = INSTALL_DIR / f"{cmd}{ext}"
            if path.exists():
                print(f"  - {cmd}{ext}")
                found_commands = True
                break

    if not found_commands:
        print("  (no commands found)")

    # Ralph home
    if RALPH_HOME.exists():
        print("")
        print("Ralph home directory:")
        print(f"  - {RALPH_HOME} (includes templates, scripts, and libraries)")

    print("")

def confirm_uninstall(force: bool = False) -> bool:
    """Prompt user to confirm uninstallation."""
    if force:
        return True

    response = input("Are you sure you want to uninstall Ralph? [y/N] ").strip().lower()
    return response == 'y'

def remove_commands() -> int:
    """Remove Ralph commands from INSTALL_DIR."""
    log("INFO", "Removing Ralph commands...")

    removed = 0
    for cmd in ["ralph", "ralph-monitor", "ralph-setup", "ralph-import",
                "ralph-migrate", "ralph-enable", "ralph-enable-ci", "ralph-stats"]:
        for ext in ["", ".bat"]:
            path = INSTALL_DIR / f"{cmd}{ext}"
            if path.exists():
                path.unlink()
                removed += 1

    if removed > 0:
        log("SUCCESS", f"Removed {removed} command(s) from {INSTALL_DIR}")
    else:
        log("INFO", "No commands found in {INSTALL_DIR}".format(INSTALL_DIR))

    return removed

def remove_ralph_home():
    """Remove Ralph home directory."""
    log("INFO", "Removing Ralph home directory...")

    if RALPH_HOME.exists():
        shutil.rmtree(RALPH_HOME)
        log("SUCCESS", f"Removed {RALPH_HOME}")
    else:
        log("INFO", "Ralph home directory not found")

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Ralph for Claude Code - Uninstallation Script",
        add_help=False
    )
    parser.add_argument("-y", "--yes", action="store_true",
                       help="Skip confirmation prompt")
    parser.add_argument("-h", "--help", action="store_true",
                       help="Show this help message")

    args = parser.parse_args()

    if args.help:
        print("Ralph for Claude Code - Uninstallation Script")
        print("")
        print("Usage: ralph_uninstall.py [OPTIONS]")
        print("")
        print("Options:")
        print("  -y, --yes    Skip confirmation prompt")
        print("  -h, --help   Show this help message")
        print("")
        print("This script removes:")
        print(f"  - Ralph commands from {INSTALL_DIR}")
        print(f"  - Ralph home directory ({RALPH_HOME})")
        print("")
        print("Project directories created with ralph-setup are NOT removed.")
        sys.exit(0)

    print(f"\n{Colors.BOLD}Uninstalling Ralph for Claude Code...{Colors.NC}")

    # Check if installed
    if not check_installation():
        log("WARN", "Ralph does not appear to be installed")
        print("Checked locations:")
        print(f"  - {INSTALL_DIR}/{{ralph,ralph-monitor,ralph-setup,ralph-import,...}}")
        print(f"  - {RALPH_HOME}")
        sys.exit(0)

    # Show removal plan
    show_removal_plan()

    # Confirm
    if not confirm_uninstall(args.yes):
        log("INFO", "Uninstallation cancelled")
        sys.exit(0)

    print("")
    remove_commands()
    remove_ralph_home()

    print(f"\n{Colors.GREEN}Ralph for Claude Code has been uninstalled{Colors.NC}\n")
    print("Note: Project files created with ralph-setup are not removed.")
    print("You can safely delete those project directories manually if needed.")

if __name__ == "__main__":
    main()

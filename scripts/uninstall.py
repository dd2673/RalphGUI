#!/usr/bin/env python3
"""
Ralph for Claude Code - Uninstallation Script (Windows Version)

This script removes Ralph GUI from the system.
"""

import os
import sys
import shutil
from pathlib import Path


def get_ralph_home() -> Path:
    """Get Ralph home directory."""
    return Path.home() / ".ralph"


def get_install_dir() -> Path:
    """Get installation directory."""
    return Path.home() / ".local" / "bin"


def log(level: str, message: str):
    """Log a message with timestamp and color."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "INFO": "\033[94m",     # Blue
        "WARN": "\033[93m",    # Yellow
        "ERROR": "\033[91m",   # Red
        "SUCCESS": "\033[92m", # Green
    }
    color = colors.get(level, "")
    reset = "\033[0m"
    print(f"{color}[{timestamp}] [{level}] {message}{reset}")


def check_installation() -> bool:
    """Check if Ralph is installed."""
    ralph_home = get_ralph_home()
    install_dir = get_install_dir()

    # Check for Ralph commands
    commands = ["ralph.bat", "ralph-enable.bat", "ralph-setup.bat", "ralph-import.bat"]
    for cmd in commands:
        if (install_dir / cmd).exists():
            return True

    # Check for Ralph home directory
    if ralph_home.exists():
        return True

    return False


def show_removal_plan():
    """Display what will be removed."""
    ralph_home = get_ralph_home()
    install_dir = get_install_dir()

    print()
    log("INFO", "The following will be removed:")
    print()

    # Commands
    print(f"Commands in {install_dir}:")
    commands = ["ralph.bat", "ralph-enable.bat", "ralph-setup.bat", "ralph-import.bat"]
    found = False
    for cmd in commands:
        if (install_dir / cmd).exists():
            print(f"  - {cmd}")
            found = True
    if not found:
        print("  (none found)")

    # Ralph home
    if ralph_home.exists():
        print()
        print(f"Ralph home directory:")
        print(f"  - {ralph_home} (includes templates, scripts, and libraries)")

    print()


def confirm_uninstall(yes_flag: bool = False) -> bool:
    """Prompt user to confirm uninstallation."""
    if yes_flag:
        return True

    reply = input("Are you sure you want to uninstall Ralph? [y/N] ").strip().lower()
    if reply != 'y':
        log("INFO", "Uninstallation cancelled")
        return False
    return True


def remove_commands():
    """Remove Ralph commands from install directory."""
    log("INFO", "Removing Ralph commands...")
    install_dir = get_install_dir()

    commands = ["ralph.bat", "ralph-enable.bat", "ralph-enable-ci.bat",
                "ralph-import.bat", "ralph-migrate.bat", "ralph-monitor.bat",
                "ralph-setup.bat", "ralph-stats.bat"]
    removed = 0
    for cmd in commands:
        cmd_path = install_dir / cmd
        if cmd_path.exists():
            cmd_path.unlink()
            removed += 1

    if removed > 0:
        log("SUCCESS", f"Removed {removed} command(s) from {install_dir}")
    else:
        log("INFO", "No commands found in install directory")


def remove_ralph_home():
    """Remove Ralph home directory."""
    log("INFO", "Removing Ralph home directory...")
    ralph_home = get_ralph_home()

    if ralph_home.exists():
        shutil.rmtree(ralph_home)
        log("SUCCESS", f"Removed {ralph_home}")
    else:
        log("INFO", "Ralph home directory not found")


def main():
    """Main uninstallation flow."""
    print("Uninstalling Ralph for Claude Code...")

    if not check_installation():
        log("WARN", "Ralph does not appear to be installed")
        print("Checked locations:")
        print(f"  - {get_install_dir()}/ralph*.bat")
        print(f"  - {get_ralph_home()}")
        sys.exit(0)

    show_removal_plan()

    # Check for -y or --yes flag
    yes_flag = "-y" in sys.argv or "--yes" in sys.argv

    if not confirm_uninstall(yes_flag):
        sys.exit(0)

    print()
    remove_commands()
    remove_ralph_home()

    print()
    log("SUCCESS", "Ralph for Claude Code has been uninstalled")
    print()
    print("Note: Project files created with ralph-setup are not removed.")
    print("You can safely delete those project directories manually if needed.")
    print()


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Ralph for Claude Code - Uninstallation Script")
        print()
        print("Usage: python uninstall.py [OPTIONS]")
        print()
        print("Options:")
        print("  -y, --yes    Skip confirmation prompt")
        print("  -h, --help   Show this help message")
        print()
        print("This script removes:")
        print(f"  - Ralph commands from {get_install_dir()}")
        print(f"  - Ralph home directory ({get_ralph_home()})")
        print()
        print("Project directories created with ralph-setup are NOT removed.")
    else:
        main()

#!/usr/bin/env python3
"""
Ralph Global Installation Script

Installs Ralph globally to ~/.local/bin and ~/.ralph, creating
shell wrappers and copying all necessary files.
"""

import click
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


# ANSI color codes for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

# Installation directories
INSTALL_DIR = Path.home() / ".local" / "bin"
RALPH_HOME = Path.home() / ".ralph"

# Get script directory (where this script is located)
SCRIPT_DIR = Path(__file__).parent.resolve()


def log(level: str, message: str) -> None:
    """Print a colored log message."""
    color = {"INFO": BLUE, "WARN": YELLOW, "ERROR": RED, "SUCCESS": GREEN}.get(level, "")
    print(f"{color}[{level}] {message}{NC}")


def check_dependencies() -> List[str]:
    """
    Check for required dependencies.

    Returns:
        List of missing dependency names
    """
    missing = []

    # Check Node.js/npm
    if not (shutil.which("node") or shutil.which("npx")):
        missing.append("Node.js/npm")

    # Check jq
    if not shutil.which("jq"):
        missing.append("jq")

    # Check git
    if not shutil.which("git"):
        missing.append("git")

    # Check timeout command
    os_type = platform.system()
    if os_type == "Darwin":
        if not (shutil.which("gtimeout") or shutil.which("timeout")):
            missing.append("coreutils (for timeout command)")
    else:
        if not shutil.which("timeout"):
            missing.append("coreutils")

    return missing


def check_claude_cli() -> bool:
    """
    Check if Claude Code CLI is available.

    Returns:
        True if Claude CLI is found, False otherwise
    """
    return shutil.which("claude") is not None


def check_tmux() -> bool:
    """
    Check if tmux is available.

    Returns:
        True if tmux is found, False otherwise
    """
    return shutil.which("tmux") is not None


def check_path_configured() -> bool:
    """
    Check if INSTALL_DIR is in PATH.

    Returns:
        True if INSTALL_DIR is in PATH, False otherwise
    """
    path_env = os.environ.get("PATH", "")
    return str(INSTALL_DIR) in path_env.split(os.pathsep)


def create_install_dirs() -> None:
    """Create installation directories if they don't exist."""
    log("INFO", "Creating installation directories...")
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    RALPH_HOME.mkdir(parents=True, exist_ok=True)
    (RALPH_HOME / "templates").mkdir(exist_ok=True)
    (RALPH_HOME / "lib").mkdir(exist_ok=True)
    log("SUCCESS", f"Directories created: {INSTALL_DIR}, {RALPH_HOME}")


def copy_templates() -> None:
    """Copy template files to Ralph home."""
    log("INFO", "Copying template files...")
    templates_src = SCRIPT_DIR.parent.parent / "templates"
    if templates_src.exists():
        for item in templates_src.iterdir():
            if item.is_file():
                shutil.copy2(item, RALPH_HOME / "templates" / item.name)
            elif item.is_dir():
                dest_dir = RALPH_HOME / "templates" / item.name
                dest_dir.mkdir(parents=True, exist_ok=True)
                for sub_item in item.iterdir():
                    if sub_item.is_file():
                        shutil.copy2(sub_item, dest_dir / sub_item.name)
    log("SUCCESS", "Templates copied")


def copy_lib_files() -> None:
    """Copy lib scripts to Ralph home."""
    log("INFO", "Copying library files...")
    lib_src = SCRIPT_DIR.parent.parent / "lib"
    if lib_src.exists():
        for item in lib_src.iterdir():
            if item.is_file() and item.suffix == ".sh":
                shutil.copy2(item, RALPH_HOME / "lib" / item.name)
                os.chmod(RALPH_HOME / "lib" / item.name, 0o755)
    log("SUCCESS", "Library files copied")


def create_unix_wrappers() -> None:
    """Create Unix shell script wrappers for all commands."""
    log("INFO", "Creating Unix shell wrappers...")

    wrappers = {
        "ralph": '''#!/bin/bash
# Ralph for Claude Code - Main Command
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/ralph_loop.sh" "$@"
''',
        "ralph-monitor": '''#!/bin/bash
# Ralph Monitor - Global Command
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/ralph_monitor.sh" "$@"
''',
        "ralph-setup": '''#!/bin/bash
# Ralph Project Setup - Global Command
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/setup.sh" "$@"
''',
        "ralph-import": '''#!/bin/bash
# Ralph PRD Import - Global Command
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/ralph_import.sh" "$@"
''',
        "ralph-migrate": '''#!/bin/bash
# Ralph Migration - Global Command
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/migrate_to_ralph_folder.sh" "$@"
''',
        "ralph-enable": '''#!/bin/bash
# Ralph Enable - Interactive Wizard
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/ralph_enable.sh" "$@"
''',
        "ralph-enable-ci": '''#!/bin/bash
# Ralph Enable CI - Non-Interactive Version
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/ralph_enable_ci.sh" "$@"
''',
        "ralph-stats": '''#!/bin/bash
# Ralph Stats - Metrics Analytics
RALPH_HOME="$HOME/.ralph"
exec "$RALPH_HOME/ralph-stats.sh" "$@"
''',
    }

    for name, content in wrappers.items():
        wrapper_path = INSTALL_DIR / name
        wrapper_path.write_text(content)
        os.chmod(wrapper_path, 0o755)
        log("SUCCESS", f"Created: {wrapper_path}")


def create_windows_wrappers() -> None:
    """Create Windows batch file wrappers for all commands."""
    log("INFO", "Creating Windows batch wrappers...")

    wrappers = {
        "ralph.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\ralph_loop.bat" %*
''',
        "ralph-monitor.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\ralph_monitor.bat" %*
''',
        "ralph-setup.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\setup.bat" %*
''',
        "ralph-import.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\ralph_import.bat" %*
''',
        "ralph-migrate.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\migrate_to_ralph_folder.bat" %*
''',
        "ralph-enable.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\ralph_enable.bat" %*
''',
        "ralph-enable-ci.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\ralph_enable_ci.bat" %*
''',
        "ralph-stats.bat": '''@echo off
set RALPH_HOME=%USERPROFILE%\\.ralph
call "%RALPH_HOME%\\ralph-stats.bat" %*
''',
    }

    for name, content in wrappers.items():
        wrapper_path = INSTALL_DIR / name
        wrapper_path.write_text(content)
        log("SUCCESS", f"Created: {wrapper_path}")


def copy_scripts_to_ralph_home() -> None:
    """Copy actual script files to Ralph home directory."""
    log("INFO", "Copying scripts to Ralph home...")

    scripts_to_copy = [
        "ralph_loop.sh",
        "ralph_monitor.sh",
        "ralph_import.sh",
        "migrate_to_ralph_folder.sh",
        "ralph_enable.sh",
        "ralph_enable_ci.sh",
        "ralph-stats.sh",
        "setup.sh",
    ]

    src_dir = SCRIPT_DIR.parent.parent
    for script_name in scripts_to_copy:
        src = src_dir / script_name
        if src.exists():
            dst = RALPH_HOME / script_name
            shutil.copy2(src, dst)
            os.chmod(dst, 0o755)
            log("SUCCESS", f"Copied: {script_name}")

    # Also copy ralph_loop.sh as ralph_loop.bat for Windows
    ralph_loop_src = src_dir / "ralph_loop.sh"
    if ralph_loop_src.exists():
        # Create batch file version with bash call
        bat_content = '''@echo off
bash "%USERPROFILE%\\.ralph\\ralph_loop.sh" %*
'''
        bat_path = RALPH_HOME / "ralph_loop.bat"
        bat_path.write_text(bat_content)
        log("SUCCESS", "Created: ralph_loop.bat")


def check_path() -> None:
    """Check and report on PATH configuration."""
    log("INFO", "Checking PATH configuration...")

    if not check_path_configured():
        log("WARN", f"{INSTALL_DIR} is not in your PATH")
        print("")
        print("Add this to your ~/.bashrc, ~/.zshrc, or ~/.profile:")
        print(f'  export PATH="$HOME/.local/bin:$PATH"')
        print("")
        print("Then run: source ~/.bashrc (or restart your terminal)")
        print("")
    else:
        log("SUCCESS", f"{INSTALL_DIR} is already in PATH")


def do_install() -> None:
    """Perform the installation."""
    print("Installing Ralph for Claude Code globally...")
    print("")

    # Check dependencies
    missing = check_dependencies()
    if missing:
        log("ERROR", f"Missing required dependencies: {', '.join(missing)}")
        print("Please install the missing dependencies:")
        print("  Ubuntu/Debian: sudo apt-get install nodejs npm jq git coreutils")
        print("  macOS: brew install node jq git coreutils")
        print("  CentOS/RHEL: sudo yum install nodejs npm jq git coreutils")
        raise click.Abort()

    log("SUCCESS", "Dependencies check completed")

    # Check Claude CLI
    if check_claude_cli():
        log("INFO", f"Claude Code CLI found: {shutil.which('claude')}")
    else:
        log("WARN", "Claude Code CLI ('claude') not found in PATH.")
        log("INFO", "  Install globally: npm install -g @anthropic-ai/claude-code")
        log("INFO", '  Or use npx: set CLAUDE_CODE_CMD="npx @anthropic-ai/claude-code" in .ralphrc')

    # Check tmux
    if not check_tmux():
        log("WARN", "tmux not found. Install for integrated monitoring: apt-get install tmux / brew install tmux")

    # Create directories
    create_install_dirs()

    # Copy files
    copy_templates()
    copy_lib_files()
    copy_scripts_to_ralph_home()

    # Create platform-specific wrappers
    os_type = platform.system()
    if os_type == "Windows":
        create_windows_wrappers()
    else:
        create_unix_wrappers()

    # Check PATH
    check_path()

    print("")
    log("SUCCESS", "Ralph for Claude Code installed successfully!")
    print("")
    print("Global commands available:")
    print("  ralph --monitor          # Start Ralph with integrated monitoring")
    print("  ralph --help             # Show Ralph options")
    print("  ralph-setup my-project   # Create new Ralph project")
    print("  ralph-enable             # Enable Ralph in existing project (interactive)")
    print("  ralph-enable-ci          # Enable Ralph in existing project (non-interactive)")
    print("  ralph-import prd.md      # Convert PRD to Ralph project")
    print("  ralph-migrate            # Migrate existing project to .ralph/ structure")
    print("  ralph-monitor            # Manual monitoring dashboard")
    print("")
    print("Quick start:")
    print("  1. ralph-setup my-awesome-project")
    print("  2. cd my-awesome-project")
    print("  3. # Edit .ralph/PROMPT.md with your requirements")
    print("  4. ralph --monitor")
    print("")

    if not check_path_configured():
        print(f"Don't forget to add {INSTALL_DIR} to your PATH (see above)")


def do_uninstall() -> None:
    """Uninstall Ralph globally."""
    log("INFO", "Uninstalling Ralph for Claude Code...")

    # Remove command wrappers
    if platform.system() == "Windows":
        wrappers = ["ralph.bat", "ralph-monitor.bat", "ralph-setup.bat", "ralph-import.bat",
                    "ralph-migrate.bat", "ralph-enable.bat", "ralph-enable-ci.bat", "ralph-stats.bat"]
    else:
        wrappers = ["ralph", "ralph-monitor", "ralph-setup", "ralph-import",
                    "ralph-migrate", "ralph-enable", "ralph-enable-ci", "ralph-stats"]

    for wrapper in wrappers:
        wrapper_path = INSTALL_DIR / wrapper
        if wrapper_path.exists():
            wrapper_path.unlink()
            log("SUCCESS", f"Removed: {wrapper_path}")

    # Remove Ralph home
    if RALPH_HOME.exists():
        shutil.rmtree(RALPH_HOME)
        log("SUCCESS", f"Removed: {RALPH_HOME}")

    log("SUCCESS", "Ralph for Claude Code uninstalled")


@click.command()
@click.argument("action", default="install")
def install(action: str) -> None:
    """
    Globally install or uninstall Ralph.

    ACTION: 'install' (default) or 'uninstall'
    """
    if action == "install":
        do_install()
    elif action == "uninstall":
        do_uninstall()
    elif action in ("--help", "-h"):
        print("Ralph for Claude Code Installation")
        print("")
        print("Usage: ralph-install [install|uninstall]")
        print("")
        print("Commands:")
        print("  install    Install Ralph globally (default)")
        print("  uninstall  Remove Ralph installation")
        print("  --help     Show this help")
    else:
        log("ERROR", f"Unknown command: {action}")
        print("Use --help for usage information")
        raise click.Abort()


if __name__ == "__main__":
    install()

#!/usr/bin/env python3
"""
Ralph for Claude Code - Global Installation Script
Installs Ralph commands to user PATH on Windows.
"""

import sys
import os
import argparse
import shutil
import subprocess
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

def check_dependencies():
    """Check required dependencies."""
    log("INFO", "Checking dependencies...")

    missing = []

    # Check Node.js/npm
    if is_windows():
        try:
            subprocess.run(["node", "--version"], capture_output=True, check=True)
            subprocess.run(["npm", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append("Node.js/npm")
    else:
        for cmd in ["node", "npx"]:
            if not shutil.which(cmd):
                missing.append(cmd)
                break

    # Check jq
    if not shutil.which("jq"):
        missing.append("jq")

    # Check git
    if not shutil.which("git"):
        missing.append("git")

    # Check timeout
    if not shutil.which("timeout"):
        missing.append("coreutils (timeout command)")

    if missing:
        log("ERROR", f"Missing required dependencies: {', '.join(missing)}")
        print("\nPlease install the missing dependencies:")
        if is_windows():
            print("  - Node.js: https://nodejs.org/")
            print("  - jq: https://stedolan.github.io/jq/")
            print("  - git: https://git-scm.com/")
        else:
            print("  Ubuntu/Debian: sudo apt-get install nodejs npm jq git coreutils")
            print("  macOS: brew install node jq git coreutils")
        sys.exit(1)

    # Check Claude Code CLI
    if shutil.which("claude"):
        log("INFO", f"Claude Code CLI found: {shutil.which('claude')}")
    else:
        log("WARN", "Claude Code CLI ('claude') not found in PATH.")
        log("INFO", "  Install globally: npm install -g @anthropic-ai/claude-code")
        log("INFO", "  Or use npx: set CLAUDE_CODE_CMD='npx @anthropic-ai/claude-code' in .ralphrc")

    # Check tmux (optional)
    if not shutil.which("tmux"):
        log("WARN", "tmux not found. Install for integrated monitoring.")

    log("SUCCESS", "Dependencies check completed")

def create_install_dirs():
    """Create installation directories."""
    log("INFO", "Creating installation directories...")

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    RALPH_HOME.mkdir(parents=True, exist_ok=True)
    (RALPH_HOME / "templates").mkdir(exist_ok=True)
    (RALPH_HOME / "lib").mkdir(exist_ok=True)

    log("SUCCESS", f"Directories created: {INSTALL_DIR}, {RALPH_HOME}")

def get_script_dir():
    """Get the directory where this script is located."""
    # If running as a script, use the parent of scripts dir
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent

def install_scripts():
    """Install Ralph command scripts."""
    log("INFO", "Installing Ralph scripts...")

    script_dir = get_script_dir()

    # Copy templates
    src_templates = script_dir / "templates"
    if src_templates.exists():
        for item in src_templates.iterdir():
            if item.is_file():
                shutil.copy2(item, RALPH_HOME / "templates" / item.name)

    # Copy lib scripts
    src_lib = script_dir / "lib"
    if src_lib.exists():
        for item in src_lib.iterdir():
            if item.is_file():
                shutil.copy2(item, RALPH_HOME / "lib" / item.name)

    # Create command wrapper scripts
    commands = {
        "ralph": "ralph_loop.sh",
        "ralph-monitor": "ralph_monitor.sh",
        "ralph-setup": "setup.sh",
        "ralph-import": "ralph_import.sh",
        "ralph-migrate": "migrate_to_ralph_folder.sh",
        "ralph-enable": "ralph_enable.sh",
        "ralph-enable-ci": "ralph_enable_ci.sh",
        "ralph-stats": "ralph-stats.sh"
    }

    for cmd_name, target_script in commands.items():
        cmd_path = INSTALL_DIR / cmd_name
        if is_windows():
            # Windows batch script wrapper
            cmd_path = cmd_path.with_suffix(".bat")
            content = f'''@echo off
set RALPH_HOME={RALPH_HOME}
set SCRIPT_DIR={INSTALL_DIR}
call {RALPH_HOME / target_script} %*
'''
        else:
            # Unix shell script wrapper
            content = f'''#!/bin/bash
# Ralph for Claude Code - {cmd_name}

RALPH_HOME="$HOME/.ralph"
SCRIPT_DIR="$(cd "$(dirname "{{BASH_SOURCE[0]}}")" && pwd)"

exec "$RALPH_HOME/{target_script}" "$@"
'''
        cmd_path.write_text(content)
        cmd_path.chmod(0o755)

        if is_windows():
            # Create Unix-style script too for MSYS/Git Bash
            unix_path = INSTALL_DIR / cmd_name
            unix_content = f'''#!/bin/bash
# Ralph for Claude Code - {cmd_name}

RALPH_HOME="$HOME/.ralph"

exec "$RALPH_HOME/{target_script}" "$@"
'''
            unix_path.write_text(unix_content)
            unix_path.chmod(0o755)

    # Copy actual scripts to Ralph home
    scripts_to_copy = [
        "ralph_loop.sh",
        "ralph_monitor.sh",
        "ralph_import.sh",
        "migrate_to_ralph_folder.sh",
        "ralph_enable.sh",
        "ralph_enable_ci.sh",
        "ralph-stats.sh",
        "setup.sh"
    ]

    for script_name in scripts_to_copy:
        src = script_dir / script_name
        if src.exists():
            shutil.copy2(src, RALPH_HOME / script_name)
            (RALPH_HOME / script_name).chmod(0o755)

    # Make lib scripts executable
    for lib_script in (RALPH_HOME / "lib").iterdir():
        if lib_script.is_file():
            lib_script.chmod(0o755)

    log("SUCCESS", f"Ralph scripts installed to {INSTALL_DIR}")

def check_path() -> bool:
    """Check if INSTALL_DIR is in PATH."""
    log("INFO", "Checking PATH configuration...")

    if is_windows():
        # Check user PATH
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0,
                                winreg.KEY_READ) as key:
                user_path, _ = winreg.QueryValueEx(key, "Path")
                paths = [p.strip().rstrip('\\') for p in user_path.split(';')]
                install_dir_str = str(INSTALL_DIR).rstrip('\\')
                if any(p.rstrip('\\') == install_dir_str for p in paths):
                    log("SUCCESS", f"{INSTALL_DIR} is already in PATH")
                    return True
        except FileNotFoundError:
            pass

        # Check system PATH
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", 0,
                                winreg.KEY_READ) as key:
                sys_path, _ = winreg.QueryValueEx(key, "Path")
                paths = [p.strip().rstrip('\\') for p in sys_path.split(';')]
                install_dir_str = str(INSTALL_DIR).rstrip('\\')
                if any(p.rstrip('\\') == install_dir_str for p in paths):
                    log("SUCCESS", f"{INSTALL_DIR} is already in PATH (system)")
                    return True
        except FileNotFoundError:
            pass

        log("WARN", f"{INSTALL_DIR} is not in your PATH")
        print("\nPlease add this to your PATH:")
        print(f"  {INSTALL_DIR}")
        print("\nTo add permanently, run:")
        print('  setx PATH "%PATH%;' + str(INSTALL_DIR) + '"')
        print("(or use System Properties > Environment Variables)")
        return False
    else:
        # Unix-like: check if in any shell config
        current_path = os.environ.get("PATH", "")
        if str(INSTALL_DIR) in current_path.split(":"):
            log("SUCCESS", f"{INSTALL_DIR} is already in PATH")
            return True

        log("WARN", f"{INSTALL_DIR} is not in your PATH")
        print("\nAdd this to your ~/.bashrc, ~/.zshrc, or ~/.profile:")
        print(f'  export PATH="$HOME/.local/bin:$PATH"')
        print("\nThen run: source ~/.bashrc (or restart your terminal)")
        return False

def add_to_path_windows():
    """Add INSTALL_DIR to user PATH via registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0,
                            winreg.KEY_WRITE) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path = ""

            paths = [p.strip().rstrip('\\') for p in current_path.split(';') if p.strip()]
            install_dir_str = str(INSTALL_DIR).rstrip('\\')

            # Check if already in PATH
            if any(p.rstrip('\\') == install_dir_str for p in paths):
                log("INFO", f"{INSTALL_DIR} already in PATH")
                return True

            # Append to user PATH
            new_path = current_path.rstrip(';') + ';' + str(INSTALL_DIR)
            winreg.SetValueEx(key, "Path", 0, reg_type, new_path)

            log("SUCCESS", f"Added {INSTALL_DIR} to PATH")
            print("\nNote: PATH changes will take effect in new terminal sessions.")
            print("You may need to restart applications to use the new PATH.")
            return True
    except PermissionError:
        log("ERROR", "Permission denied. Try running as administrator.")
        return False
    except Exception as e:
        log("ERROR", f"Failed to update PATH: {e}")
        return False

def install():
    """Main installation."""
    print(f"\n{Colors.BOLD}Installing Ralph for Claude Code globally...{Colors.NC}\n")

    check_dependencies()
    create_install_dirs()
    install_scripts()
    in_path = check_path()

    if not in_path and is_windows():
        response = input("\nWould you like to add to PATH now? [Y/n] ").strip().lower()
        if response != 'n':
            add_to_path_windows()

    print(f"\n{Colors.GREEN}Ralph for Claude Code installed successfully!{Colors.NC}\n")
    print("Global commands available:")
    print("  ralph              # Start Ralph")
    print("  ralph --monitor    # Start Ralph with integrated monitoring")
    print("  ralph --help       # Show Ralph options")
    print("  ralph-setup        # Create new Ralph project")
    print("  ralph-enable       # Enable Ralph in existing project (interactive)")
    print("  ralph-enable-ci    # Enable Ralph in existing project (non-interactive)")
    print("  ralph-import       # Convert PRD to Ralph project")
    print("  ralph-migrate      # Migrate existing project to .ralph/ structure")
    print("  ralph-monitor      # Manual monitoring dashboard")
    print("  ralph-stats        # Metrics analytics")
    print("\nQuick start:")
    print("  1. ralph-setup my-project")
    print("  2. cd my-project")
    print("  3. # Edit .ralph/PROMPT.md with your requirements")
    print("  4. ralph --monitor")

    if not in_path:
        print(f"\n{Colors.YELLOW}Don't forget to add {INSTALL_DIR} to your PATH!{Colors.NC}")

def uninstall():
    """Uninstall Ralph."""
    print(f"\n{Colors.BOLD}Uninstalling Ralph for Claude Code...{Colors.NC}\n")

    # Check if installed
    installed = False
    for cmd in ["ralph", "ralph-monitor", "ralph-setup", "ralph-import"]:
        if (INSTALL_DIR / cmd).exists() or (INSTALL_DIR / f"{cmd}.bat").exists():
            installed = True
            break

    if not installed and not RALPH_HOME.exists():
        log("WARN", "Ralph does not appear to be installed")
        print("Checked locations:")
        print(f"  - {INSTALL_DIR}/{{ralph,ralph-monitor,ralph-setup,ralph-import}}")
        print(f"  - {RALPH_HOME}")
        sys.exit(0)

    # Show removal plan
    print("\nThe following will be removed:")
    print(f"\nCommands in {INSTALL_DIR}:")
    for cmd in ["ralph", "ralph-monitor", "ralph-setup", "ralph-import",
                "ralph-migrate", "ralph-enable", "ralph-enable-ci", "ralph-stats"]:
        for ext in ["", ".bat"]:
            path = INSTALL_DIR / f"{cmd}{ext}"
            if path.exists():
                print(f"  - {cmd}{ext}")
                break

    if RALPH_HOME.exists():
        print(f"\nRalph home directory:")
        print(f"  - {RALPH_HOME} (includes templates, scripts, and libraries)")

    # Confirm
    response = input("\nAre you sure you want to uninstall Ralph? [y/N] ").strip().lower()
    if response != 'y':
        log("INFO", "Uninstallation cancelled")
        sys.exit(0)

    # Remove commands
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

    # Remove Ralph home
    log("INFO", "Removing Ralph home directory...")
    if RALPH_HOME.exists():
        shutil.rmtree(RALPH_HOME)
        log("SUCCESS", f"Removed {RALPH_HOME}")
    else:
        log("INFO", "Ralph home directory not found")

    print(f"\n{Colors.GREEN}Ralph for Claude Code has been uninstalled{Colors.NC}\n")
    print("Note: Project files created with ralph-setup are not removed.")
    print("You can safely delete those project directories manually if needed.")

def main():
    parser = argparse.ArgumentParser(
        description="Ralph for Claude Code Installation Script",
        add_help=False
    )
    parser.add_argument("command", nargs="?", default="install",
                       choices=["install", "uninstall", "--help", "-h"])
    parser.add_argument("-y", "--yes", action="store_true",
                       help="Skip confirmation prompt for uninstall")

    args = parser.parse_args()

    if args.command in ["--help", "-h"]:
        print("Ralph for Claude Code Installation")
        print("")
        print("Usage: ralph_install.py [install|uninstall] [-y]")
        print("")
        print("Commands:")
        print("  install    Install Ralph globally (default)")
        print("  uninstall  Remove Ralph installation")
        print("  --help     Show this help")
        sys.exit(0)

    if args.command == "uninstall":
        if args.yes:
            # Override input for non-interactive uninstall
            def dummy_input(*x):
                return "y"
            import builtins
            builtins.input = dummy_input
        uninstall()
    else:
        install()

if __name__ == "__main__":
    main()

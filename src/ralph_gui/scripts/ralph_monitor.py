#!/usr/bin/env python3
"""
ralph_monitor.py - Live terminal dashboard for the Ralph loop

Usage:
    python ralph_monitor.py --mode {tui,gui,simple} --project DIR
    python ralph_monitor.py --project DIR  # defaults to tui mode
"""
import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime


class RalphMonitor:
    """Ralph Monitor - Live status dashboard"""

    # ANSI colors
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.status_file = project_dir / ".ralph" / "status.json"
        self.log_file = project_dir / ".ralph" / "logs" / "ralph.log"
        self.progress_file = project_dir / ".ralph" / "progress.json"
        self.refresh_interval = 2

    def clear_screen(self):
        """Clear screen and hide cursor"""
        print('\033[2J', end='')  # Clear screen
        print('\033[H', end='')   # Move cursor to home
        print('\033[?25l', end='')  # Hide cursor

    def show_cursor(self):
        """Show cursor"""
        print('\033[?25h', end='')

    def read_status(self) -> dict:
        """Read status.json file"""
        if not self.status_file.exists():
            return {}
        try:
            with open(self.status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def read_progress(self) -> dict:
        """Read progress.json file"""
        if not self.progress_file.exists():
            return {}
        try:
            with open(self.progress_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def read_last_logs(self, lines: int = 8) -> list:
        """Read last N lines from log file"""
        if not self.log_file.exists():
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                return [line.strip() for line in all_lines[-lines:]]
        except IOError:
            return []

    def display_tui(self):
        """Display TUI mode - full terminal UI"""
        self.clear_screen()

        # Header
        print(f"{self.WHITE}╔════════════════════════════════════════════════════════════════════════╗{self.NC}")
        print(f"{self.WHITE}║                           🤖 RALPH MONITOR                              ║{self.NC}")
        print(f"{self.WHITE}║                        Live Status Dashboard                           ║{self.NC}")
        print(f"{self.WHITE}╚════════════════════════════════════════════════════════════════════════╝{self.NC}")
        print()

        status = self.read_status()

        if status:
            loop_count = status.get("loop_count", 0)
            calls_made = status.get("calls_made_this_hour", 0)
            max_calls = status.get("max_calls_per_hour", 100)
            status_text = status.get("status", "unknown")

            print(f"{self.CYAN}┌─ Current Status ────────────────────────────────────────────────────────┐{self.NC}")
            print(f"{self.CYAN}│{self.NC} Loop Count:     {self.WHITE}#{loop_count}{self.NC}")
            status_color = self.GREEN if status_text == "running" else self.YELLOW
            print(f"{self.CYAN}│{self.NC} Status:         {status_color}{status_text}{self.NC}")
            print(f"{self.CYAN}│{self.NC} API Calls:      {calls_made}/{max_calls}")
            print(f"{self.CYAN}└─────────────────────────────────────────────────────────────────────────┘{self.NC}")
            print()
        else:
            print(f"{self.RED}┌─ Status ────────────────────────────────────────────────────────────────┐{self.NC}")
            print(f"{self.RED}│{self.NC} Status file not found. Ralph may not be running.")
            print(f"{self.RED}└─────────────────────────────────────────────────────────────────────────┘{self.NC}")
            print()

        # Progress section
        progress = self.read_progress()
        if progress.get("status") == "executing":
            indicator = progress.get("indicator", "⠋")
            elapsed = progress.get("elapsed_seconds", 0)
            last_output = progress.get("last_output", "")

            print(f"{self.YELLOW}┌─ Claude Code Progress ──────────────────────────────────────────────────┐{self.NC}")
            print(f"{self.YELLOW}│{self.NC} Status:         {indicator} Working ({elapsed}s elapsed)")
            if last_output:
                display_output = last_output[:60] + "..." if len(last_output) > 60 else last_output
                print(f"{self.YELLOW}│{self.NC} Output:         {display_output}{self.NC}")
            print(f"{self.YELLOW}└─────────────────────────────────────────────────────────────────────────┘{self.NC}")
            print()

        # Recent logs
        print(f"{self.BLUE}┌─ Recent Activity ───────────────────────────────────────────────────────┐{self.NC}")
        logs = self.read_last_logs(8)
        if logs:
            for line in logs:
                print(f"{self.BLUE}│{self.NC} {line}")
        else:
            print(f"{self.BLUE}│{self.NC} No log file found")
        print(f"{self.BLUE}└─────────────────────────────────────────────────────────────────────────┘{self.NC}")

        # Footer
        timestamp = datetime.now().strftime("%H:%M:%S")
        print()
        print(f"{self.YELLOW}Controls: Ctrl+C to exit | Refreshes every {self.refresh_interval}s | {timestamp}{self.NC}")

    def display_simple(self):
        """Display simple mode - minimal output"""
        status = self.read_status()
        if status:
            loop_count = status.get("loop_count", 0)
            calls_made = status.get("calls_made_this_hour", 0)
            max_calls = status.get("max_calls_per_hour", 100)
            status_text = status.get("status", "unknown")

            print(f"Ralph: {status_text} | Loop: #{loop_count} | Calls: {calls_made}/{max_calls}")
        else:
            print("Ralph: No status available")

    def display_gui(self):
        """GUI mode - meant to be integrated with PySide6 GUI"""
        # This would emit signals or return data for GUI consumption
        status = self.read_status()
        logs = self.read_last_logs(20)
        return {
            "status": status,
            "logs": logs,
            "timestamp": datetime.now().isoformat()
        }

    def run_tui(self):
        """Run TUI monitor loop"""
        try:
            self.show_cursor()
            while True:
                self.display_tui()
                time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            self.show_cursor()
            print("\nMonitor stopped.")


def main():
    parser = argparse.ArgumentParser(description="Ralph Monitor - Live status dashboard")
    parser.add_argument(
        "--mode",
        choices=["tui", "gui", "simple"],
        default="tui",
        help="Display mode (default: tui)"
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)"
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=2,
        help="Refresh interval in seconds (default: 2)"
    )
    args = parser.parse_args()

    monitor = RalphMonitor(args.project)
    monitor.refresh_interval = args.refresh

    if args.mode == "tui":
        monitor.run_tui()
    elif args.mode == "simple":
        monitor.display_simple()
    elif args.mode == "gui":
        result = monitor.display_gui()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

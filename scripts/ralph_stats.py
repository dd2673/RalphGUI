#!/usr/bin/env python3
"""
Ralph Stats - Metrics analytics for Ralph loop execution.

Reads .ralph/logs/metrics.jsonl and prints a JSON summary.
"""

import os
import sys
import click
from pathlib import Path
from typing import Dict, Any, List
import json


RALPH_DIR = ".ralph"
METRICS_FILE = f"{RALPH_DIR}/logs/metrics.jsonl"


@click.command()
@click.option("--project-dir", default=".", help="Project directory")
@click.option("--json", "output_json", is_flag=True, help="Output result as JSON")
def stats(project_dir: str, output_json: bool) -> None:
    """
    Display Ralph loop execution statistics.

    Reads metrics from .ralph/logs/metrics.jsonl and outputs a summary.

    Examples:

        ralph-stats              # Show stats for current project

        ralph-stats --project-dir ./my-project

        ralph-stats --json       # JSON output for automation
    """
    project_path = Path(project_dir).resolve()
    metrics_file = project_path / METRICS_FILE

    if not metrics_file.exists():
        error_msg = "No metrics file found. Run ralph first to generate metrics."
        if output_json:
            print(json.dumps({"error": error_msg}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(metrics_file) as f:
            lines = f.readlines()
    except IOError as e:
        error_msg = f"Failed to read metrics file: {e}"
        if output_json:
            print(json.dumps({"error": error_msg}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Parse metrics
    metrics: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                metrics.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not metrics:
        error_msg = "No valid metrics found in metrics file."
        if output_json:
            print(json.dumps({"error": error_msg}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Calculate statistics
    total_loops = len(metrics)
    successful = sum(1 for m in metrics if m.get("success", False))
    total_calls = sum(m.get("calls", 0) for m in metrics)

    durations = [m.get("duration", 0) for m in metrics if "duration" in m]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Format output
    if output_json:
        result = {
            "total_loops": total_loops,
            "successful": successful,
            "avg_duration": round(avg_duration, 2) if avg_duration else 0,
            "total_calls": total_calls
        }
        print(json.dumps(result))
    else:
        print("Ralph Loop Statistics")
        print("=" * 40)
        print(f"Total Loops:     {total_loops}")
        print(f"Successful:      {successful}")
        print(f"Avg Duration:    {avg_duration:.2f}s" if avg_duration else "Avg Duration:    N/A")
        print(f"Total Calls:     {total_calls}")


if __name__ == "__main__":
    stats()

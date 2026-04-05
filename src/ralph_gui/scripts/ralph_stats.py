#!/usr/bin/env python3
"""
ralph_stats.py - Metrics analytics for Ralph loop execution
Reads .ralph/logs/metrics.jsonl and prints a JSON summary

Usage:
    python ralph_stats.py [--project-dir DIR] [--json]
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Ralph statistics")
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    args = parser.parse_args()

    project_dir = args.project_dir
    metrics_file = project_dir / ".ralph" / "logs" / "metrics.jsonl"

    if not metrics_file.exists():
        error_msg = "No metrics file found. Run ralph first to generate metrics."
        if args.json:
            print(json.dumps({"error": error_msg}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Read and parse metrics
    loops = []
    try:
        with open(metrics_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        loops.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        error_msg = f"Failed to read metrics file: {e}"
        if args.json:
            print(json.dumps({"error": error_msg}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    if not loops:
        if args.json:
            print(json.dumps({
                "total_loops": 0,
                "successful": 0,
                "avg_duration": 0,
                "total_calls": 0
            }))
        else:
            print("No metrics data found.")
        return

    # Calculate statistics
    total_loops = len(loops)
    successful = sum(1 for loop in loops if loop.get("success", False))
    total_calls = sum(loop.get("calls", 0) for loop in loops)

    durations = [loop.get("duration", 0) for loop in loops if "duration" in loop]
    avg_duration = sum(durations) / len(durations) if durations else 0

    if args.json:
        result = {
            "total_loops": total_loops,
            "successful": successful,
            "avg_duration": round(avg_duration, 2),
            "total_calls": total_calls
        }
        print(json.dumps(result))
    else:
        print(f"Total Loops: {total_loops}")
        print(f"Successful: {successful}")
        print(f"Avg Duration: {avg_duration:.2f}s")
        print(f"Total Calls: {total_calls}")


if __name__ == "__main__":
    main()

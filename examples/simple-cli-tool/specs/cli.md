# Simple CLI Tool Specification

## Overview

A lightweight command-line task management tool.

## Features

- Add tasks with title and priority
- List all tasks
- Mark tasks as complete
- Delete tasks
- Persist to JSON file

## Commands

| Command | Description |
|---------|-------------|
| `add <title>` | Add a new task |
| `list` | List all tasks |
| `done <id>` | Mark task as complete |
| `delete <id>` | Delete a task |

## Options

| Option | Description |
|--------|-------------|
| `--priority` | Task priority (high/medium/low) |
| `--help` | Show help |

## Data Format

Tasks stored in `~/.tasks.json`:

```json
{
  "tasks": [
    {
      "id": 1,
      "title": "Task title",
      "priority": "high",
      "completed": false,
      "created_at": "2026-04-03T10:00:00"
    }
  ]
}
```

## Technical Details

- Language: Python 3.10+
- Dependencies: None (stdlib only)
- Platform: Windows, macOS, Linux

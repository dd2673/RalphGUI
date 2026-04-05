# Task Management CLI Tool - Product Requirements Document

## Overview

Build a simple command-line task management tool for individual use.

## Core Features

### Task Management
- Create tasks with title and description
- Mark tasks as complete/incomplete
- List all tasks
- Delete tasks
- Simple priority (high, medium, low)

### Data Storage
- Tasks stored in JSON file
- File location: ~/.tasks.json

### Interface
- Command-line interface
- Simple commands: add, done, list, delete

## Technical Requirements

- Python 3.10+
- No external dependencies (stdlib only)
- Cross-platform (Windows, macOS, Linux)

## Success Criteria
- User can add, list, complete, and delete tasks
- Tasks persist across sessions
- Works offline
- Fast and lightweight

## Usage Examples

```bash
# Add a task
python task.py add "Buy groceries" --priority high

# List tasks
python task.py list

# Mark task as done
python task.py done 1

# Delete a task
python task.py delete 2
```

## Priority
1. Basic CRUD operations
2. Priority support
3. Due dates (optional)

## Timeline
Target MVP in 1-2 days of development.

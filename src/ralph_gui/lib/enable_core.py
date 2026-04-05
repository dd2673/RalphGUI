#!/usr/bin/env python3
"""
enable_core.py - Shared logic for ralph enable commands

Provides idempotency checks, safe file creation, and project detection.
Used by ralph_enable.py and ralph_enable_ci.py.
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Exit codes
ENABLE_SUCCESS = 0
ENABLE_ERROR = 1
ENABLE_ALREADY_ENABLED = 2
ENABLE_INVALID_ARGS = 3
ENABLE_FILE_NOT_FOUND = 4
ENABLE_DEPENDENCY_MISSING = 5
ENABLE_PERMISSION_DENIED = 6

# Color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'

# Configuration
ENABLE_USE_COLORS = os.environ.get('ENABLE_USE_COLORS', 'true').lower() == 'true'
ENABLE_FORCE = os.environ.get('ENABLE_FORCE', 'false').lower() == 'true'
ENABLE_SKIP_TASKS = os.environ.get('ENABLE_SKIP_TASKS', 'false').lower() == 'true'
ENABLE_PROJECT_NAME = os.environ.get('ENABLE_PROJECT_NAME', '')
ENABLE_PROJECT_TYPE = os.environ.get('ENABLE_PROJECT_TYPE', '')
ENABLE_TASK_CONTENT = os.environ.get('ENABLE_TASK_CONTENT', '')


def _color(color: str, text: str) -> str:
    """Apply color if colors are enabled."""
    if ENABLE_USE_COLORS:
        return f"{color}{text}{NC}"
    return text


def enable_log(level: str, message: str) -> None:
    """Log a message with a level prefix and optional color."""
    color_map = {
        'INFO': BLUE,
        'WARN': YELLOW,
        'ERROR': RED,
        'SUCCESS': GREEN,
        'SKIP': CYAN,
    }
    color = color_map.get(level, '')
    prefix = _color(color, f"[{level}]")
    print(f"{prefix} {message}")


# =============================================================================
# IDEMPOTENCY CHECKS
# =============================================================================

RALPH_STATE = "none"
RALPH_MISSING_FILES = []


def check_existing_ralph() -> int:
    """
    Check if .ralph directory exists and its state.

    Returns:
        0 - No .ralph directory, safe to proceed
        1 - .ralph exists but incomplete (partial setup)
        2 - .ralph exists and fully initialized

    Sets global RALPH_STATE: "none" | "partial" | "complete"
    Sets global RALPH_MISSING_FILES: list of missing files if partial
    """
    global RALPH_STATE, RALPH_MISSING_FILES

    ralph_dir = Path('.ralph')

    if not ralph_dir.is_dir():
        RALPH_STATE = "none"
        RALPH_MISSING_FILES = []
        return 0

    required_files = [
        ".ralph/PROMPT.md",
        ".ralph/fix_plan.md",
        ".ralph/AGENT.md",
        ".ralphrc",
    ]

    missing = []
    found = 0

    for file_path in required_files:
        if Path(file_path).is_file():
            found += 1
        else:
            missing.append(file_path)

    RALPH_MISSING_FILES = missing

    if found == 0:
        RALPH_STATE = "none"
        return 0
    elif len(missing) > 0:
        RALPH_STATE = "partial"
        return 1
    else:
        RALPH_STATE = "complete"
        return 2


def is_ralph_enabled() -> bool:
    """
    Simple check if Ralph is fully enabled.

    Returns:
        True - Ralph is fully enabled
        False - Ralph is not enabled or only partially
    """
    check_existing_ralph()
    return RALPH_STATE == "complete"


# =============================================================================
# SAFE FILE OPERATIONS
# =============================================================================


def safe_create_file(target: str, content: str) -> int:
    """
    Create a file only if it doesn't exist (or force overwrite).

    Parameters:
        target: Target file path
        content: Content to write (can be empty string)

    Returns:
        0 - File created/overwritten successfully
        1 - File already exists (skipped, only when ENABLE_FORCE is not true)
        2 - Error creating file
    """
    target_path = Path(target)

    if target_path.is_file():
        if ENABLE_FORCE:
            enable_log("INFO", f"Overwriting {target} (--force)")
        else:
            enable_log("SKIP", f"{target} already exists")
            return 1

    # Create parent directory if needed
    parent_dir = target_path.parent
    if not parent_dir.is_dir():
        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            enable_log("ERROR", f"Failed to create directory: {parent_dir}")
            return 2
        except OSError as e:
            enable_log("ERROR", f"Failed to create directory: {parent_dir} - {e}")
            return 2

    # Write content to file
    try:
        target_path.write_text(content + '\n', encoding='utf-8')
        if target_path.is_file() and ENABLE_FORCE:
            enable_log("SUCCESS", f"Overwrote {target}")
        else:
            enable_log("SUCCESS", f"Created {target}")
        return 0
    except PermissionError:
        enable_log("ERROR", f"Permission denied: {target}")
        return 2
    except OSError as e:
        enable_log("ERROR", f"Failed to create: {target} - {e}")
        return 2


def safe_create_dir(target: str) -> int:
    """
    Create a directory only if it doesn't exist.

    Parameters:
        target: Target directory path

    Returns:
        0 - Directory created or already exists
        1 - Error creating directory
    """
    target_path = Path(target)

    if target_path.is_dir():
        return 0

    try:
        target_path.mkdir(parents=True, exist_ok=True)
        enable_log("SUCCESS", f"Created directory: {target}")
        return 0
    except PermissionError:
        enable_log("ERROR", f"Permission denied: {target}")
        return 1
    except OSError as e:
        enable_log("ERROR", f"Failed to create directory: {target} - {e}")
        return 1


# =============================================================================
# DIRECTORY STRUCTURE
# =============================================================================


def create_ralph_structure() -> int:
    """
    Create the .ralph/ directory structure.

    Creates:
        .ralph/
        .ralph/specs/
        .ralph/examples/
        .ralph/logs/
        .ralph/docs/generated/

    Returns:
        0 - Structure created successfully
        1 - Error creating structure
    """
    dirs = [
        ".ralph",
        ".ralph/specs",
        ".ralph/examples",
        ".ralph/logs",
        ".ralph/docs/generated",
    ]

    for dir_path in dirs:
        if safe_create_dir(dir_path) != 0:
            return 1

    return 0


# =============================================================================
# PROJECT DETECTION
# =============================================================================

# Exported detection results
DETECTED_PROJECT_NAME = ""
DETECTED_PROJECT_TYPE = "unknown"
DETECTED_FRAMEWORK = ""
DETECTED_BUILD_CMD = ""
DETECTED_TEST_CMD = ""
DETECTED_RUN_CMD = ""


def detect_project_context() -> None:
    """
    Detect project type, name, and build commands.

    Detects:
        - Project type: javascript, typescript, python, rust, go, unknown
        - Framework: nextjs, fastapi, express, react, vue, django, flask, etc.
        - Build/test/run commands based on detected tooling

    Sets globals:
        DETECTED_PROJECT_NAME - Project name (from package.json, folder, etc.)
        DETECTED_PROJECT_TYPE - Language/type
        DETECTED_FRAMEWORK - Framework if detected
        DETECTED_BUILD_CMD - Build command
        DETECTED_TEST_CMD - Test command
        DETECTED_RUN_CMD - Run/start command
    """
    global DETECTED_PROJECT_NAME, DETECTED_PROJECT_TYPE, DETECTED_FRAMEWORK
    global DETECTED_BUILD_CMD, DETECTED_TEST_CMD, DETECTED_RUN_CMD

    # Reset detection results
    DETECTED_PROJECT_NAME = ""
    DETECTED_PROJECT_TYPE = "unknown"
    DETECTED_FRAMEWORK = ""
    DETECTED_BUILD_CMD = ""
    DETECTED_TEST_CMD = ""
    DETECTED_RUN_CMD = ""

    # Detect from package.json (JavaScript/TypeScript)
    if Path('package.json').is_file():
        DETECTED_PROJECT_TYPE = "javascript"

        # Check for TypeScript
        package_content = Path('package.json').read_text(encoding='utf-8')
        if '"typescript"' in package_content or Path('tsconfig.json').is_file():
            DETECTED_PROJECT_TYPE = "typescript"

        # Extract project name
        try:
            import json
            with open('package.json', 'r', encoding='utf-8') as f:
                pkg = json.load(f)
                DETECTED_PROJECT_NAME = pkg.get('name', '')
        except (json.JSONDecodeError, OSError):
            # Fallback: grep for name field
            match = re.search(r'"name"\s*:\s*"([^"]*)"', package_content)
            if match:
                DETECTED_PROJECT_NAME = match.group(1)

        # Detect framework
        if '"next"' in package_content:
            DETECTED_FRAMEWORK = "nextjs"
        elif '"express"' in package_content:
            DETECTED_FRAMEWORK = "express"
        elif '"react"' in package_content:
            DETECTED_FRAMEWORK = "react"
        elif '"vue"' in package_content:
            DETECTED_FRAMEWORK = "vue"

        # Set build commands
        DETECTED_BUILD_CMD = "npm run build"
        DETECTED_TEST_CMD = "npm test"
        DETECTED_RUN_CMD = "npm start"

        # Check for yarn
        if Path('yarn.lock').is_file():
            DETECTED_BUILD_CMD = "yarn build"
            DETECTED_TEST_CMD = "yarn test"
            DETECTED_RUN_CMD = "yarn start"

        # Check for pnpm
        if Path('pnpm-lock.yaml').is_file():
            DETECTED_BUILD_CMD = "pnpm build"
            DETECTED_TEST_CMD = "pnpm test"
            DETECTED_RUN_CMD = "pnpm start"

    # Detect from pyproject.toml or setup.py (Python)
    if Path('pyproject.toml').is_file() or Path('setup.py').is_file():
        DETECTED_PROJECT_TYPE = "python"

        # Extract project name from pyproject.toml
        if Path('pyproject.toml').is_file():
            pyproject_content = Path('pyproject.toml').read_text(encoding='utf-8')
            match = re.search(r'^name\s*=\s*"([^"]*)"', pyproject_content, re.MULTILINE)
            if match:
                DETECTED_PROJECT_NAME = match.group(1)

            # Detect framework
            if 'fastapi' in pyproject_content:
                DETECTED_FRAMEWORK = "fastapi"
            elif 'django' in pyproject_content:
                DETECTED_FRAMEWORK = "django"
            elif 'flask' in pyproject_content:
                DETECTED_FRAMEWORK = "flask"

        # Set build commands (prefer uv if detected)
        if Path('uv.lock').is_file() or _command_exists('uv'):
            DETECTED_BUILD_CMD = "uv sync"
            DETECTED_TEST_CMD = "uv run pytest"
            DETECTED_RUN_CMD = f"uv run python -m {DETECTED_PROJECT_NAME or 'main'}"
        else:
            DETECTED_BUILD_CMD = "pip install -e ."
            DETECTED_TEST_CMD = "pytest"
            DETECTED_RUN_CMD = f"python -m {DETECTED_PROJECT_NAME or 'main'}"

    # Detect from Cargo.toml (Rust)
    if Path('Cargo.toml').is_file():
        DETECTED_PROJECT_TYPE = "rust"
        cargo_content = Path('Cargo.toml').read_text(encoding='utf-8')
        match = re.search(r'^name\s*=\s*"([^"]*)"', cargo_content, re.MULTILINE)
        if match:
            DETECTED_PROJECT_NAME = match.group(1)
        DETECTED_BUILD_CMD = "cargo build"
        DETECTED_TEST_CMD = "cargo test"
        DETECTED_RUN_CMD = "cargo run"

    # Detect from go.mod (Go)
    if Path('go.mod').is_file():
        DETECTED_PROJECT_TYPE = "go"
        go_mod_content = Path('go.mod').read_text(encoding='utf-8')
        first_line = go_mod_content.split('\n')[0] if go_mod_content else ''
        match = re.match(r'module\s+(.+)', first_line)
        if match:
            DETECTED_PROJECT_NAME = match.group(1)
        DETECTED_BUILD_CMD = "go build"
        DETECTED_TEST_CMD = "go test ./..."
        DETECTED_RUN_CMD = "go run ."

    # Fallback project name to folder name
    if not DETECTED_PROJECT_NAME:
        DETECTED_PROJECT_NAME = Path.cwd().name


def _command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    import shutil
    return shutil.which(cmd) is not None


# =============================================================================
# GIT DETECTION
# =============================================================================

DETECTED_GIT_REPO = False
DETECTED_GIT_REMOTE = ""
DETECTED_GIT_GITHUB = False


def detect_git_info() -> None:
    """
    Detect git repository information.

    Sets globals:
        DETECTED_GIT_REPO - True if in git repo
        DETECTED_GIT_REMOTE - Remote URL (origin)
        DETECTED_GIT_GITHUB - True if GitHub remote
    """
    global DETECTED_GIT_REPO, DETECTED_GIT_REMOTE, DETECTED_GIT_GITHUB

    DETECTED_GIT_REPO = False
    DETECTED_GIT_REMOTE = ""
    DETECTED_GIT_GITHUB = False

    # Check if in git repo
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            DETECTED_GIT_REPO = True

            # Get remote URL
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                DETECTED_GIT_REMOTE = result.stdout.strip()

            # Check if GitHub
            if 'github.com' in DETECTED_GIT_REMOTE:
                DETECTED_GIT_GITHUB = True
    except (subprocess.TimeoutExpired, OSError):
        pass


# =============================================================================
# TASK SOURCE DETECTION
# =============================================================================

DETECTED_BEADS_AVAILABLE = False
DETECTED_GITHUB_AVAILABLE = False
DETECTED_PRD_FILES = []


def detect_task_sources() -> None:
    """
    Detect available task sources.

    Sets globals:
        DETECTED_BEADS_AVAILABLE - True if .beads directory exists
        DETECTED_GITHUB_AVAILABLE - True if GitHub remote detected
        DETECTED_PRD_FILES - List of potential PRD files found
    """
    global DETECTED_BEADS_AVAILABLE, DETECTED_GITHUB_AVAILABLE, DETECTED_PRD_FILES

    DETECTED_BEADS_AVAILABLE = False
    DETECTED_GITHUB_AVAILABLE = False
    DETECTED_PRD_FILES = []

    # Check for beads
    if Path('.beads').is_dir():
        DETECTED_BEADS_AVAILABLE = True

    # Check for GitHub (reuse git detection)
    detect_git_info()
    DETECTED_GITHUB_AVAILABLE = DETECTED_GIT_GITHUB

    # Search for PRD/spec files
    search_dirs = ['docs', 'specs', '.', 'requirements']
    prd_patterns = ['*prd*.md', '*PRD*.md', '*requirements*.md', '*spec*.md', '*specification*.md']

    for search_dir in search_dirs:
        dir_path = Path(search_dir)
        if dir_path.is_dir():
            for pattern in prd_patterns:
                for match in dir_path.glob(pattern):
                    if match.is_file():
                        DETECTED_PRD_FILES.append(str(match))
                    # Check subdirectories up to maxdepth 2
                for subdir in dir_path.iterdir():
                    if subdir.is_dir():
                        for pattern in prd_patterns:
                            for match in subdir.glob(pattern):
                                if match.is_file():
                                    DETECTED_PRD_FILES.append(str(match))


# =============================================================================
# TEMPLATE GENERATION
# =============================================================================


def get_templates_dir() -> Optional[str]:
    """
    Get the templates directory path.

    Returns:
        Path to templates directory or None if not found
    """
    # Check global installation first
    home_templates = Path.home() / '.ralph' / 'templates'
    if home_templates.is_dir():
        return str(home_templates)

    # Check local installation (development)
    # For Python, we use the package directory
    lib_dir = Path(__file__).parent
    local_templates = lib_dir / 'templates'
    if local_templates.is_dir():
        return str(local_templates)

    return None


def generate_prompt_md(
    project_name: Optional[str] = None,
    project_type: Optional[str] = None,
    framework: Optional[str] = None,
    objectives: Optional[str] = None
) -> str:
    """
    Generate PROMPT.md with project context.

    Parameters:
        project_name: Project name
        project_type: Project type (typescript, python, etc.)
        framework: Framework if any (optional)
        objectives: Custom objectives (optional, newline-separated)

    Returns:
        Generated PROMPT.md content
    """
    if project_name is None:
        project_name = Path.cwd().name
    if project_type is None:
        project_type = "unknown"
    if framework is None:
        framework = ""

    framework_line = f"**Framework:** {framework}" if framework else ""

    if objectives:
        objectives_section = objectives
    else:
        objectives_section = """- 审查代码库并了解当前状态
- 遵循 fix_plan.md 中的任务
- 每轮循环实现一个任务
- 为新功能编写测试
- 根据需要更新文档"""

    return f"""# Ralph 开发指南

## 背景
你是 Ralph，一个自主 AI 开发智能体，正在开发 **{project_name}** 项目。

**项目类型:** {project_type}
{framework_line}

## 当前目标
{objectives_section}

## 核心原则
- 每轮循环只做一个任务 - 专注于最重要的事情
- 在假设某些内容未实现之前，先搜索代码库
- 用清晰的文档编写全面的测试
- 用你的学习更新 fix_plan.md
- 用描述性消息提交工作代码

## 受保护的文件（请勿修改）
以下文件和目录是 Ralph 基础设施的一部分。
在任何情况下都不得删除、移动、重命名或覆盖这些文件：
- .ralph/（整个目录及其所有内容）
- .ralphrc（项目配置）

执行清理、重构或重组任务时：
- 这些文件不是项目代码的一部分
- 它们是 Ralph 的内部控制文件，保持开发循环运行
- 删除它们将破坏 Ralph 并停止所有自主开发

## 测试指南
- 将测试限制在每轮循环总工作量的约 20%
- 优先级：实现 > 文档 > 测试
- 只为你实现的新功能编写测试

## 构建与运行
参见 AGENT.md 中的构建和运行说明。

## 状态报告（关键）

在你的回复末尾，始终包含此状态块：

```
---RALPH_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
TASKS_COMPLETED_THIS_LOOP: <number>
FILES_MODIFIED: <number>
TESTS_STATUS: PASSING | FAILING | NOT_RUN
WORK_TYPE: IMPLEMENTATION | TESTING | DOCUMENTATION | REFACTORING
EXIT_SIGNAL: false | true
RECOMMENDATION: <one line summary of what to do next>
---END_RALPH_STATUS---
```

## 当前任务
遵循 fix_plan.md，选择最重要的任务来实现。
"""


def generate_agent_md(
    build_cmd: Optional[str] = None,
    test_cmd: Optional[str] = None,
    run_cmd: Optional[str] = None
) -> str:
    """
    Generate AGENT.md with detected build commands.

    Parameters:
        build_cmd: Build command
        test_cmd: Test command
        run_cmd: Run command

    Returns:
        Generated AGENT.md content
    """
    if build_cmd is None:
        build_cmd = "echo 'No build command configured'"
    if test_cmd is None:
        test_cmd = "echo 'No test command configured'"
    if run_cmd is None:
        run_cmd = "echo 'No run command configured'"

    return f"""# Ralph Agent 配置指南

## 构建说明

```bash
# 构建项目
{build_cmd}
```

## 测试说明

```bash
# 运行测试
{test_cmd}
```

## 运行说明

```bash
# 启动/运行项目
{run_cmd}
```

## 备注
- 构建过程变更时更新此文件
- 根据需要添加环境设置说明
- 包含任何先决条件或依赖项
"""


def generate_fix_plan_md(tasks: Optional[str] = None) -> str:
    """
    Generate fix_plan.md with imported tasks.

    Parameters:
        tasks: Tasks to include (newline-separated, markdown checkbox format)

    Returns:
        Generated fix_plan.md content
    """
    if tasks:
        high_priority = tasks
    else:
        high_priority = """- [ ] 审查代码库并了解架构
- [ ] 识别并记录关键组件
- [ ] 设置开发环境"""

    medium_priority = """- [ ] 实现核心功能
- [ ] 添加测试覆盖率
- [ ] 更新文档"""

    low_priority = """- [ ] 性能优化
- [ ] 代码清理和重构"""

    return f"""# Ralph 修复计划

## 高优先级
{high_priority}

## 中优先级
{medium_priority}

## 低优先级
{low_priority}

## 已完成
- [x] 项目已启用 Ralph

## 备注
- 首先关注 MVP 功能
- 确保每个功能都有适当的测试
- 每个重要里程碑后更新此文件
"""


def generate_ralphrc(
    project_name: Optional[str] = None,
    project_type: Optional[str] = None,
    task_sources: str = "local"
) -> str:
    """
    Generate .ralphrc configuration file.

    Parameters:
        project_name: Project name
        project_type: Project type
        task_sources: Task sources (local, beads, github)

    Returns:
        Generated .ralphrc content
    """
    if project_name is None:
        project_name = Path.cwd().name
    if project_type is None:
        project_type = "unknown"

    # Auto-detect Claude Code CLI command
    claude_cmd = "claude"
    if not _command_exists('claude'):
        if _command_exists('npx'):
            claude_cmd = "npx @anthropic-ai/claude-code"

    return f'''# .ralphrc - Ralph project configuration
# Generated by: ralph enable
# Documentation: https://github.com/frankbria/ralph-claude-code

# Project identification
PROJECT_NAME="{project_name}"
PROJECT_TYPE="{project_type}"

# Claude Code CLI command
# If "claude" is not in your PATH, set to your installation:
#   "npx @anthropic-ai/claude-code"  (uses npx, no global install needed)
#   "/path/to/claude"                (custom path)
CLAUDE_CODE_CMD="{claude_cmd}"

# Loop settings
MAX_CALLS_PER_HOUR=100
CLAUDE_TIMEOUT_MINUTES=15
CLAUDE_OUTPUT_FORMAT="json"
# Token limit per hour (0 = disabled). One invocation can use 100k+ tokens.
# Recommended: 500000 for light use, 2000000 for heavy use.
#MAX_TOKENS_PER_HOUR=0

# Tool permissions
# Comma-separated list of allowed tools
# Safe git subcommands only - broad Bash(git *) allows destructive commands like git clean/git rm (Issue #149)
ALLOWED_TOOLS="Write,Read,Edit,Bash(git add *),Bash(git commit *),Bash(git diff *),Bash(git log *),Bash(git status),Bash(git status *),Bash(git push *),Bash(git pull *),Bash(git fetch *),Bash(git checkout *),Bash(git branch *),Bash(git stash *),Bash(git merge *),Bash(git tag *),Bash(npm *),Bash(pytest)"

# Session management
SESSION_CONTINUITY=true
SESSION_EXPIRY_HOURS=24

# Task sources (for ralph enable --sync)
# Options: local, beads, github (comma-separated for multiple)
TASK_SOURCES="{task_sources}"
GITHUB_TASK_LABEL="ralph-task"
BEADS_FILTER="status:open"

# Circuit breaker thresholds
CB_NO_PROGRESS_THRESHOLD=3
CB_SAME_ERROR_THRESHOLD=5
CB_OUTPUT_DECLINE_THRESHOLD=70

# Auto-update Claude CLI at startup
CLAUDE_AUTO_UPDATE=true

# Shell init file (optional)
# Source this file before running claude — useful when claude requires environment
# variables or PATH entries defined in a non-bash shell config (e.g. ~/.zshrc).
# Leave commented out unless needed.
#RALPH_SHELL_INIT_FILE="~/.zshrc"
'''


# =============================================================================
# MAIN ENABLE LOGIC
# =============================================================================


def enable_ralph_in_directory(
    force: bool = False,
    skip_tasks: bool = False,
    project_name: Optional[str] = None,
    project_type: Optional[str] = None,
    task_content: Optional[str] = None
) -> int:
    """
    Main function to enable Ralph in current directory.

    Parameters:
        force: Force overwrite existing
        skip_tasks: Skip task import
        project_name: Override project name
        project_type: Override project type
        task_content: Pre-imported task content

    Returns:
        ENABLE_SUCCESS (0) - Success
        ENABLE_ERROR (1) - Error
        ENABLE_ALREADY_ENABLED (2) - Already enabled (and no force flag)
    """
    global ENABLE_FORCE, ENABLE_SKIP_TASKS, ENABLE_PROJECT_NAME, ENABLE_PROJECT_TYPE, ENABLE_TASK_CONTENT
    global DETECTED_PROJECT_TYPE, DETECTED_FRAMEWORK, DETECTED_PROJECT_NAME

    # Set globals for backward compatibility
    ENABLE_FORCE = force
    ENABLE_SKIP_TASKS = skip_tasks
    ENABLE_PROJECT_NAME = project_name or ''
    ENABLE_PROJECT_TYPE = project_type or ''
    ENABLE_TASK_CONTENT = task_content or ''

    # Check existing state
    check_existing_ralph()

    if RALPH_STATE == "complete" and not force:
        enable_log("INFO", "Ralph is already enabled in this project")
        enable_log("INFO", "Use --force to overwrite existing configuration")
        return ENABLE_ALREADY_ENABLED

    # Detect project context
    detect_project_context()

    # Use detected or provided project name
    if not project_name:
        project_name = DETECTED_PROJECT_NAME

    # Use detected or provided project type
    if project_type:
        DETECTED_PROJECT_TYPE = project_type

    enable_log("INFO", f"Enabling Ralph for: {project_name}")
    enable_log("INFO", f"Project type: {DETECTED_PROJECT_TYPE}")
    if DETECTED_FRAMEWORK:
        enable_log("INFO", f"Framework: {DETECTED_FRAMEWORK}")

    # Create directory structure
    if create_ralph_structure() != 0:
        enable_log("ERROR", "Failed to create .ralph/ structure")
        return ENABLE_ERROR

    # Generate and create files
    prompt_content = generate_prompt_md(
        project_name,
        DETECTED_PROJECT_TYPE,
        DETECTED_FRAMEWORK
    )
    safe_create_file(".ralph/PROMPT.md", prompt_content)

    agent_content = generate_agent_md(
        DETECTED_BUILD_CMD,
        DETECTED_TEST_CMD,
        DETECTED_RUN_CMD
    )
    safe_create_file(".ralph/AGENT.md", agent_content)

    fix_plan_content = generate_fix_plan_md(task_content)
    safe_create_file(".ralph/fix_plan.md", fix_plan_content)

    # Copy .gitignore template to project root (if available)
    templates_dir = get_templates_dir()
    if templates_dir:
        gitignore_path = Path(templates_dir) / '.gitignore'
        if gitignore_path.is_file():
            gitignore_content = gitignore_path.read_text(encoding='utf-8')
            safe_create_file(".gitignore", gitignore_content)
        else:
            enable_log("WARN", ".gitignore template not found, skipping")
    else:
        enable_log("WARN", ".gitignore template not found, skipping")

    # Detect task sources for .ralphrc
    detect_task_sources()
    task_sources = "local"
    if DETECTED_BEADS_AVAILABLE:
        task_sources = f"beads,{task_sources}"
    if DETECTED_GITHUB_AVAILABLE:
        task_sources = f"github,{task_sources}"

    # Generate .ralphrc
    ralphrc_content = generate_ralphrc(project_name, DETECTED_PROJECT_TYPE, task_sources)
    safe_create_file(".ralphrc", ralphrc_content)

    enable_log("SUCCESS", "Ralph enabled successfully!")

    return ENABLE_SUCCESS


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description='Enable Ralph in current directory')
    parser.add_argument('--force', action='store_true', help='Force overwrite existing')
    parser.add_argument('--skip-tasks', action='store_true', help='Skip task import')
    parser.add_argument('--project-name', help='Override project name')
    parser.add_argument('--project-type', help='Override project type')
    parser.add_argument('--no-colors', action='store_true', help='Disable colors')

    args = parser.parse_args()

    global ENABLE_USE_COLORS
    if args.no_colors:
        ENABLE_USE_COLORS = False

    exit_code = enable_ralph_in_directory(
        force=args.force,
        skip_tasks=args.skip_tasks,
        project_name=args.project_name,
        project_type=args.project_type
    )

    sys.exit(exit_code)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Create Ralph Project Files Script

Creates the basic Ralph project structure including:
- Directory structure: src/, templates/specs/
- Template files: PROMPT.md, AGENT.md, fix_plan.md
- .gitignore file
- Lightweight setup scripts

This is a lightweight initialization script - the full ralph_loop.sh
functionality is provided by the Python scripts in this project.
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional


# ANSI color codes for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
PURPLE = "\033[0;35m"
NC = "\033[0m"


def log(level: str, message: str) -> None:
    """Print a colored log message."""
    color = {
        "INFO": BLUE,
        "WARN": YELLOW,
        "ERROR": RED,
        "SUCCESS": GREEN,
        "LOOP": PURPLE,
    }.get(level, "")
    print(f"{color}[{level}] {message}{NC}")


# Template content for PROMPT.md
PROMPT_TEMPLATE = """# Ralph 开发指南

## 背景
你是 Ralph，一个自主 AI 开发智能体，正在开发一个 [你的项目名称] 项目。

## 当前目标
1. 学习 .ralph/specs/* 了解项目规格
2. 查看 .ralph/fix_plan.md 了解当前优先级
3. 使用最佳实践实现最高优先级的任务
4. 对复杂任务使用并行子智能体（最多 100 个并发）
5. 每次实现后运行测试
6. 更新文档和 fix_plan.md

## 核心原则
- 每次循环只做一个任务 - 专注于最重要的事情
- 在假设某些内容未实现之前，先搜索代码库
- 对昂贵操作（文件搜索、分析）使用子智能体
- 编写有清晰文档的全面测试
- 用你的学习更新 .ralph/fix_plan.md
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

## 测试指南（重要）
- 将测试限制在每次循环总工作量的约 20%
- 优先级：实现 > 文档 > 测试
- 只为你实现的新功能编写测试
- 除非测试损坏，否则不要重构现有测试
- 不要添加"额外测试覆盖率"作为忙乱工作
- 先关注核心功能，全面测试稍后进行

## 执行指南
- 做出更改之前：使用子智能体搜索代码库
- 实现之后：只运行修改代码的必要测试
- 如果测试失败：在当前工作中修复它们
- 保持 AGENT.md 更新，包含构建/运行说明
- 记录测试和实现的原因
- 不要有占位符实现 - 要正确构建

## 完成感知
如果你认为项目已完成或接近完成：
- 更新 .ralph/fix_plan.md 反映完成状态
- 总结已完成的工作
- 记录任何剩余的小任务
- 不要继续做忙乱工作，如大量测试
- 不要实现规格中未包含的功能

## 文件结构
- .ralph/specs/：项目规格和需求
- src/：源代码实现
- .ralph/examples/：使用示例和测试用例
- .ralph/fix_plan.md：优先级待办列表
- .ralph/AGENT.md：项目构建和运行说明

## 当前任务
遵循 .ralph/fix_plan.md，选择最重要的任务来实现。
用你的判断来确定什么会对项目进展产生最大影响。

记住：质量优先于速度。一次性正确构建。知道何时完成。
"""

# Template content for fix_plan.md
FIX_PLAN_TEMPLATE = """# Ralph 修复计划

## 高优先级
- [ ] 设置基本项目结构和构建系统
- [ ] 定义核心数据结构和类型
- [ ] 实现基本的输入/输出处理
- [ ] 创建测试框架和初始测试

## 中优先级
- [ ] 添加错误处理和验证
- [ ] 实现核心业务逻辑
- [ ] 添加配置管理
- [ ] 创建用户文档

## 低优先级
- [ ] 性能优化
- [ ] 扩展功能集
- [ ] 与外部服务集成
- [ ] 高级错误恢复

## 已完成
- [x] 项目初始化

## 备注
- 首先关注 MVP 功能
- 确保每个功能都有适当的测试
- 每个重要里程碑后更新此文件
"""

# Template content for AGENT.md
AGENT_TEMPLATE = """# Agent 构建指南

## 项目设置
```bash
# 安装依赖（Node.js 项目示例）
npm install

# 或 Python 项目
pip install -r requirements.txt

# 或 Rust 项目
cargo build
```

## 运行测试
```bash
# Node.js
npm test

# Python
pytest

# Rust
cargo test
```

## 构建命令
```bash
# 生产构建
npm run build
# 或
cargo build --release
```

## 开发服务器
```bash
# 启动开发服务器
npm run dev
# 或
cargo run
```

## 关键经验
- 学习新的构建优化时更新此部分
- 记录任何陷阱或特殊设置要求
- 跟踪最快的测试/构建周期
"""

# Template content for .gitignore
GITIGNORE_TEMPLATE = """# Ralph generated files (inside .ralph/ subfolder)
.ralph/.call_count
.ralph/.last_reset
.ralph/.exit_signals
.ralph/status.json
.ralph/.ralph_session
.ralph/.ralph_session_history
.ralph/.claude_session_id
.ralph/.response_analysis
.ralph/.circuit_breaker_state
.ralph/.circuit_breaker_history

# Ralph logs and generated docs
.ralph/logs/*
!.ralph/logs/.gitkeep
.ralph/docs/generated/*
!.ralph/docs/generated/.gitkeep

# General logs
*.log

# OS files
.DS_Store
Thumbs.db

# Temporary files
*.tmp
.temp/

# Node modules (if using Node.js projects)
node_modules/

# Python cache (if using Python projects)
__pycache__/
*.pyc

# Rust build (if using Rust projects)
target/

# IDE files
.vscode/
.idea/
*.swp
*.swo

# Ralph backup directories (created by migration)
.ralph_backup_*
"""

# Gitkeep placeholder
GITKEEP_PLACEHOLDER = ""


def create_directories(base_path: Path) -> List[Path]:
    """
    Create the Ralph project directory structure.

    Args:
        base_path: Base directory for the project

    Returns:
        List of created directory paths
    """
    dirs = [
        base_path / "src",
        base_path / "templates" / "specs",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        log("SUCCESS", f"Created directory: {d}")

    return dirs


def create_template_files(base_path: Path) -> List[Path]:
    """
    Create template files in the project.

    Args:
        base_path: Base directory for the project

    Returns:
        List of created file paths
    """
    files = []

    # PROMPT.md
    prompt_path = base_path / "templates" / "PROMPT.md"
    prompt_path.write_text(PROMPT_TEMPLATE)
    files.append(prompt_path)
    log("SUCCESS", f"Created: {prompt_path}")

    # fix_plan.md
    fix_plan_path = base_path / "templates" / "fix_plan.md"
    fix_plan_path.write_text(FIX_PLAN_TEMPLATE)
    files.append(fix_plan_path)
    log("SUCCESS", f"Created: {fix_plan_path}")

    # AGENT.md
    agent_path = base_path / "templates" / "AGENT.md"
    agent_path.write_text(AGENT_TEMPLATE)
    files.append(agent_path)
    log("SUCCESS", f"Created: {agent_path}")

    return files


def create_gitignore(base_path: Path) -> Optional[Path]:
    """
    Create .gitignore file if it doesn't exist.

    Args:
        base_path: Base directory for the project

    Returns:
        Path to created .gitignore or None if it already exists
    """
    gitignore_path = base_path / ".gitignore"
    if gitignore_path.exists():
        log("WARN", f".gitignore already exists, skipping")
        return None

    gitignore_path.write_text(GITIGNORE_TEMPLATE)
    log("SUCCESS", f"Created: {gitignore_path}")
    return gitignore_path


def create_gitkeep_files(base_path: Path) -> List[Path]:
    """
    Create .gitkeep files in typically empty directories.

    Args:
        base_path: Base directory for the project

    Returns:
        List of created .gitkeep file paths
    """
    files = []

    # These directories might be empty, add .gitkeep to preserve them
    gitkeep_dirs = [
        base_path / "templates" / "specs",
    ]

    for d in gitkeep_dirs:
        gitkeep_path = d / ".gitkeep"
        if not gitkeep_path.exists():
            gitkeep_path.write_text(GITKEEP_PLACEHOLDER)
            files.append(gitkeep_path)
            log("SUCCESS", f"Created: {gitkeep_path}")

    return files


def create_files(base_path: Path = Path("."), verbose: bool = True) -> dict:
    """
    Create all Ralph project files.

    Args:
        base_path: Base directory for the project (default: current directory)
        verbose: Whether to print progress messages

    Returns:
        Dictionary with counts of created items
    """
    base_path = Path(base_path).resolve()

    if verbose:
        log("INFO", f"Creating Ralph project structure in: {base_path}")

    # Track created items
    result = {
        "directories": [],
        "files": [],
    }

    # Create directory structure
    dirs = create_directories(base_path)
    result["directories"].extend([str(d) for d in dirs])

    # Create template files
    files = create_template_files(base_path)
    result["files"].extend([str(f) for f in files])

    # Create .gitignore
    gitignore = create_gitignore(base_path)
    if gitignore:
        result["files"].append(str(gitignore))

    # Create .gitkeep files
    gitkeeps = create_gitkeep_files(base_path)
    result["files"].extend([str(g) for g in gitkeeps])

    return result


def main() -> None:
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create Ralph project files and directory structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_files.py                    # Create in current directory
  python create_files.py --path /my/project  # Create in specific directory
  python create_files.py --quiet             # Suppress output
        """,
    )

    parser.add_argument(
        "--path",
        type=Path,
        default=Path("."),
        help="Base directory for the project (default: current directory)",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output messages",
    )

    args = parser.parse_args()

    result = create_files(args.path, verbose=not args.quiet)

    if not args.quiet:
        print()
        log("SUCCESS", "All files created successfully!")
        print()
        print("Project structure:")
        print("  ├── src/")
        print("  ├── templates/")
        print("  │   ├── specs/")
        print("  │   ├── PROMPT.md")
        print("  │   ├── fix_plan.md")
        print("  │   └── AGENT.md")
        print("  └── .gitignore")
        print()
        print(f"Created {len(result['directories'])} directories and {len(result['files'])} files.")


if __name__ == "__main__":
    main()

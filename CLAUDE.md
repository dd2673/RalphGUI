# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Ralph GUI 是一个 Windows 桌面应用程序，用于管理 Ralph for Claude Code 项目。采用 PySide6 (Qt) 构建，MVP 架构。

## 常用命令

### 运行
```bash
python src/ralph_gui/main.py
```

### 构建
```bash
build.bat                       # 构建 Windows 可执行文件
```

## 架构

### 目录结构
```
src/ralph_gui/
├── main.py          # 应用入口
├── app.py           # RalphApp 应用类
├── main_window.py   # 主窗口 (View)
├── presenters/      # Presenter 层 - 业务逻辑
├── services/        # Service 层 - CLI、状态、配置、日志
├── models/          # Model 层 - 数据模型
├── views/           # View 层 - UI 组件
├── lib/             # lib 层 - Python 库模块 (date_utils, file_protection, log_utils, timeout_utils)
├── scripts/         # scripts 层 - Python 脚本 (ralph_stats, ralph_monitor)
├── templates/       # 模板文件 (PROMPT.md, AGENT.md, fix_plan.md)
├── examples/        # 示例项目 (rest-api, simple-cli-tool)
└── i18n/            # 国际化
```

### MVP 架构
- **Views**: `main_window.py`, `views/` - UI 组件，PySide6 widgets
- **Presenters**: `presenters/` - 连接 View 与 Model，处理业务逻辑
- **Services**: `services/` - CLI 调用、状态管理、配置管理、日志
- **Models**: `models/` - 数据模型 (CircuitBreaker, LoopState, Project 等)

### 核心模型
- `CircuitBreakerModel` - 回路断路器状态 (CLOSED/HALF_OPEN/OPEN)
- `LoopStateModel` - 循环状态
- `Project` - 项目信息
- `RateLimitModel` - API 速率限制

### 关键服务
- `CLIService` - 调用 `ralph_loop.sh` 脚本管理循环
- `StateService` - 管理 Ralph 状态文件
- `ConfigService` - 管理 `.ralphrc` 配置
- `LogService` - 日志管理

## 技术栈
- Python 3.10+
- PySide6 >= 6.6.0 (Qt GUI)
- PyYAML >= 6.0
- PyInstaller (打包)


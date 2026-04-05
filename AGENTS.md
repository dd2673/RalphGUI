# AGENTS.md

本文件为 AI 代理提供项目上下文，用于指导代码交互和开发工作。

---

## 项目概述

**Ralph GUI** 是一个 Windows 桌面应用程序，用于管理 Ralph for Claude Code 项目。它提供了一个图形化界面来控制 Claude Code CLI 的循环执行，包括启动/停止/暂停循环、监控断路器状态、实时日志输出等功能。

### 核心功能

- **图形化界面** - 选择项目目录，启动/停止/暂停循环
- **回路断路器** - 三态断路器（CLOSED/HALF_OPEN/OPEN）防止无限循环
- **实时日志监控** - 监控面板显示执行日志
- **项目设置管理** - 配置管理和初始化（`.ralphrc`）
- **会话管理** - 支持会话连续性和过期控制
- **速率限制** - 内置 API 调用管理，每小时限制和倒计时
- **PRD 导入** - 从外部源导入任务
- **国际化支持** - 支持中英文界面（i18n）

### 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| GUI 框架 | PySide6 >= 6.6.0 (Qt) |
| 配置解析 | PyYAML >= 6.0 |
| 终端 UI | Textual >= 0.50.0 |
| 打包工具 | PyInstaller |
| 测试框架 | pytest + pytest-qt |

---

## 项目结构

```
ralph-gui/
├── src/ralph_gui/              # 主应用源码
│   ├── __init__.py             # 包初始化
│   ├── __main__.py             # 模块入口 (python -m ralph_gui)
│   ├── main.py                 # 应用入口
│   ├── app.py                  # RalphApp 应用类
│   ├── main_window.py          # 主窗口 (View)
│   ├── models/                 # 数据模型层
│   │   ├── circuit_breaker.py  # 断路器状态模型
│   │   ├── loop_state.py       # 循环状态模型
│   │   ├── project.py          # 项目信息模型
│   │   ├── rate_limit.py       # API 速率限制模型
│   │   └── session.py          # 会话管理模型
│   ├── services/               # 服务层
│   │   ├── cli_service.py      # CLI 调用、循环管理
│   │   ├── state_service.py    # 状态管理服务
│   │   ├── config_service.py   # 配置管理服务
│   │   └── log_service.py      # 日志服务
│   ├── presenters/             # Presenter 层 - 业务逻辑
│   │   ├── loop_presenter.py   # 循环控制逻辑
│   │   ├── settings_presenter.py # 设置逻辑
│   │   └── startup_presenter.py # 启动逻辑
│   ├── views/                  # View 层 - UI 组件
│   │   ├── theme.py            # 主题配色定义
│   │   ├── settings_panel.py   # 设置面板
│   │   ├── startup_dialog.py   # 启动对话框
│   │   └── widgets/            # 自定义组件
│   │       ├── metric_display.py  # 指标显示组件
│   │       └── status_card.py     # 状态卡片组件
│   ├── lib/                    # 内部库模块（应用内）
│   │   ├── circuit_breaker.py  # 断路器核心逻辑
│   │   ├── date_utils.py       # 日期工具
│   │   ├── enable_core.py      # 启用逻辑
│   │   ├── file_protection.py  # 文件保护
│   │   ├── log_utils.py        # 日志工具
│   │   ├── response_analyzer.py # 响应分析
│   │   ├── task_sources.py     # 任务源
│   │   ├── timeout_utils.py    # 超时工具
│   │   └── wizard_utils.py     # 向导工具
│   ├── scripts/                # 内置 Python 脚本
│   │   ├── ralph_setup.py      # 项目设置
│   │   ├── ralph_import.py     # 导入 PRD
│   │   ├── ralph_install.py    # 安装
│   │   ├── ralph_migrate.py    # 迁移
│   │   ├── ralph_monitor.py    # 监控面板
│   │   ├── ralph_stats.py      # 统计信息
│   │   └── ralph_uninstall.py  # 卸载
│   ├── templates/              # 模板文件
│   │   ├── PROMPT.md           # 提示模板
│   │   ├── AGENT.md            # 代理模板
│   │   ├── fix_plan.md         # 任务计划模板
│   │   ├── ralphrc.template    # 配置模板
│   │   └── gitignore.template  # gitignore 模板
│   ├── i18n/                   # 国际化
│   │   ├── __init__.py         # i18n 初始化和 tr() 函数
│   │   ├── zh_CN.py            # 简体中文翻译
│   │   └── en_US.py            # 英文翻译
│   ├── utils/                  # 工具函数
│   │   └── json_helpers.py     # JSON 辅助工具
│   └── examples/               # 示例文件
├── lib/                        # 独立库模块（可直接导入）
│   ├── circuit_breaker.py      # 断路器核心逻辑
│   ├── date_utils.py
│   ├── enable_core.py
│   ├── file_protection.py
│   ├── log_utils.py
│   ├── response_analyzer.py
│   ├── task_sources.py
│   ├── timeout_utils.py
│   └── wizard_utils.py
├── scripts/                    # 独立 CLI 脚本
│   ├── ralph_loop.py           # 主循环执行
│   ├── ralph_enable.py         # 启用项目
│   ├── ralph_enable_ci.py      # CI 模式启用
│   ├── ralph_import.py         # 导入 PRD
│   ├── ralph_monitor.py        # 监控面板
│   ├── ralph_stats.py          # 统计信息
│   ├── setup.py                # 项目设置
│   ├── install.py              # 安装
│   ├── migrate.py              # 迁移
│   ├── create_files.py         # 文件创建
│   └── uninstall.py            # 卸载
├── tests/                      # 测试套件
│   ├── conftest.py             # pytest 配置和 fixtures
│   ├── test_models/            # 模型测试
│   ├── test_services/          # 服务测试
│   ├── test_presenters/        # Presenter 测试
│   ├── test_i18n/              # 国际化测试
│   ├── test_gui_e2e.py         # GUI 端到端测试
│   ├── test_gui_debug.py       # GUI 调试测试
│   ├── test_gui_verbose.py     # GUI 详细测试
│   ├── test_error_detection.py # 错误检测测试
│   └── test_stuck_loop_detection.py # 卡循环检测测试
├── wrappers/                   # Windows 批处理包装器
│   ├── ralph.bat               # 主入口
│   ├── ralph-enable.bat        # 启用项目
│   ├── ralph-enable-ci.bat     # CI 模式
│   ├── ralph-import.bat        # 导入 PRD
│   ├── ralph-monitor.bat       # 监控
│   ├── ralph-stats.bat         # 统计
│   ├── ralph-setup.bat         # 设置
│   ├── ralph-migrate.bat       # 迁移
│   └── install.bat             # 安装
├── docs/                       # 文档
├── examples/                   # 示例项目
│   ├── rest-api/               # REST API 示例
│   └── simple-cli-tool/        # CLI 工具示例（待完善）
├── build/                      # 构建输出
│   └── pyinstaller/            # PyInstaller 输出
│       └── RalphGUI.exe        # 可执行文件
├── run.py                      # Python 启动器
├── build.bat                   # 构建脚本
├── start.bat                   # 启动脚本
├── pyproject.toml              # 项目配置
├── pyinstaller.spec            # PyInstaller 配置
└── requirements.txt            # 依赖列表
```

---

## MVP 架构

项目采用 **Model-View-Presenter (MVP)** 架构模式：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    View     │ ←→  │  Presenter  │ ←→  │    Model    │
│ (PySide6)   │     │ (业务逻辑)   │     │  (数据模型)  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ↓
                    ┌─────────────┐
                    │  Services   │
                    │ (CLI/State) │
                    └─────────────┘
```

### 层级职责

| 层级 | 目录 | 职责 |
|------|------|------|
| **View** | `views/`, `main_window.py` | UI 渲染、用户交互、信号发射 |
| **Presenter** | `presenters/` | 连接 View 与 Model，处理业务逻辑，状态转换 |
| **Model** | `models/` | 数据结构、状态管理、持久化 |
| **Service** | `services/` | 外部调用（CLI）、文件 I/O、配置管理 |
| **Lib** | `lib/`, `src/ralph_gui/lib/` | 核心算法和工具函数 |

---

## 核心组件

### 回路断路器 (Circuit Breaker)

三态断路器用于检测执行停滞，防止无限循环消耗 token：

```
CLOSED (正常) → HALF_OPEN (监控) → OPEN (停止)
     ↑                                    │
     └────────────────────────────────────┘
              (冷却后恢复)
```

**状态说明：**
- `CLOSED`: 正常运行，检测到进度
- `HALF_OPEN`: 监控模式，检查是否恢复
- `OPEN`: 检测到停滞，执行暂停

**触发条件：**
- 连续 3 次循环无进度
- 连续 5 次相同错误
- 连续 2 次权限拒绝

**冷却时间：** 30 分钟

**相关文件：**
- `lib/circuit_breaker.py` - 核心逻辑
- `src/ralph_gui/lib/circuit_breaker.py` - 应用内副本
- `src/ralph_gui/models/circuit_breaker.py` - GUI 模型

### CLI 服务

`CLIService` 是核心服务，负责：
- 查找和调用 Claude Code CLI
- 管理循环进程
- 解析输出和状态
- 处理超时和错误

**关键方法：**
```python
start_loop(project_dir, options, progress_callback)  # 启动循环
stop_loop(timeout=10)                                 # 停止循环
is_loop_running()                                     # 检查状态
reset_circuit(project_dir)                           # 重置断路器
get_status(project_dir)                              # 获取状态
```

### 数据模型

| 模型 | 文件 | 说明 |
|------|------|------|
| `CircuitBreakerModel` | `models/circuit_breaker.py` | 断路器状态 |
| `LoopStateModel` | `models/loop_state.py` | 循环状态 |
| `Project` | `models/project.py` | 项目信息 |
| `RateLimitModel` | `models/rate_limit.py` | API 速率限制 |
| `Session` | `models/session.py` | 会话管理 |

### UI 组件

| 组件 | 文件 | 说明 |
|------|------|------|
| `MetricDisplay` | `views/widgets/metric_display.py` | 指标显示组件 |
| `StatusCard` | `views/widgets/status_card.py` | 状态卡片组件 |
| `SettingsPanel` | `views/settings_panel.py` | 设置面板 |
| `StartupDialog` | `views/startup_dialog.py` | 启动对话框 |

### 国际化 (i18n)

支持中英文界面切换：

```python
from ralph_gui.i18n import tr

# 使用翻译
text = tr("key_name")
text = tr("key_with_args", name="value")
```

**语言文件：**
- `src/ralph_gui/i18n/zh_CN.py` - 简体中文（默认）
- `src/ralph_gui/i18n/en_US.py` - 英文

---

## 常用命令

### 运行应用

```bash
# 方式 1: 使用启动器
python run.py

# 方式 2: 模块方式
python -m ralph_gui

# 方式 3: 直接运行
python src/ralph_gui/main.py

# 方式 4: 使用批处理
start.bat
```

### 测试

```bash
# 运行所有测试
pytest

# 运行特定目录测试
pytest tests/test_models/
pytest tests/test_services/
pytest tests/test_presenters/
pytest tests/test_i18n/

# 运行单个测试
pytest tests/test_services/test_cli_service.py::test_name

# 带覆盖率
pytest --cov=src/ralph_gui

# 详细输出
pytest -v tests/test_gui_e2e.py
```

### 构建

```bash
# 构建 Windows 可执行文件
build.bat

# 输出位置
# build/pyinstaller/RalphGUI.exe
# dist/RalphGUI/
```

### CLI 脚本

```bash
# 独立脚本（项目根目录）
python scripts/ralph_enable.py
python scripts/ralph_enable_ci.py   # CI 模式（非交互）
python scripts/ralph_import.py
python scripts/ralph_monitor.py
python scripts/ralph_stats.py

# 或使用批处理包装器
wrappers\ralph-enable.bat
wrappers\ralph-monitor.bat
```

---

## 配置

### 项目配置文件 (`.ralphrc`)

每个 Ralph 项目可包含 `.ralphrc` 配置文件：

```bash
# .ralphrc - Ralph 项目配置
PROJECT_NAME="my-project"
PROJECT_TYPE="typescript"

# Claude Code CLI 命令
CLAUDE_CODE_CMD="claude"

# 循环设置
MAX_CALLS_PER_HOUR=100
CLAUDE_TIMEOUT_MINUTES=15
CLAUDE_OUTPUT_FORMAT="json"

# 工具权限
ALLOWED_TOOLS="Write,Read,Edit,Bash(git *),Bash(npm *),Bash(pytest)"

# 会话管理
SESSION_CONTINUITY=true
SESSION_EXPIRY_HOURS=24

# 断路器阈值
CB_NO_PROGRESS_THRESHOLD=3
CB_SAME_ERROR_THRESHOLD=5
```

### Ralph 目录结构

每个项目会创建 `.ralph/` 目录：

```
.ralph/
├── PROMPT.md              # 主提示文件
├── AGENT.md               # 代理指令
├── fix_plan.md            # 任务计划
├── status.json            # 当前状态
├── .circuit_breaker_state # 断路器状态
├── .circuit_breaker_history
├── .ralph_session         # 会话信息
├── .call_count            # 调用计数
├── .token_count           # Token 计数
├── .loop_start_sha        # 循环起点 SHA
├── .exit_signals          # 退出信号
├── logs/
│   ├── ralph.log          # 主日志
│   └── metrics.jsonl      # 指标日志
├── specs/                 # 规格文件
├── docs/                  # 生成的文档
└── examples/              # 示例文件
```

---

## 开发规范

### 代码风格

- 使用 Python 3.10+ 特性（类型提示、dataclass 等）
- 遵循 PEP 8 编码规范
- 使用 dataclass 定义数据模型
- 使用 pathlib 处理文件路径

### 测试规范

- 所有新功能必须有单元测试
- 使用 `pytest` 和 `pytest-qt`
- 测试覆盖率目标：100%
- 使用 `conftest.py` 中的 fixtures

**常用 fixtures：**
```python
qapp_instance      # QApplication 实例
temp_project_dir   # 临时项目目录
mock_ralph_files   # 模拟 Ralph 文件结构
```

### 日志规范

- 使用 `lib/log_utils.py` 或 `src/ralph_gui/lib/log_utils.py` 中的日志工具
- 不同模块使用不同日志器：
  - `get_cli_logger()` - CLI 相关
  - `get_service_logger()` - 服务层

### Windows 兼容性

- 项目专为 Windows 平台设计
- 使用 `subprocess` 管理进程
- 使用 `os.path` 或 `pathlib` 处理路径
- 批处理包装器在 `wrappers/` 目录

---

## 实现状态

| 组件 | 状态 | 测试覆盖率 |
|------|------|-----------|
| MVP 架构 | ✅ 完成 | 100% |
| 主窗口 UI | ✅ 完成 | 手动测试 |
| 循环控制 | ✅ 完成 | 100% |
| 断路器 | ✅ 完成 | 100% |
| 状态管理 | ✅ 完成 | 100% |
| 配置管理 | ✅ 完成 | 100% |
| 日志监控 | ✅ 完成 | 手动测试 |
| 暗色主题 | ✅ 完成 | 手动测试 |
| CLI 脚本 | ✅ 完成 | 100% |
| 库模块 | ✅ 完成 | 100% |
| 国际化 (i18n) | ✅ 完成 | 100% |
| 自定义组件 | ✅ 完成 | 手动测试 |

**待开发功能：**
- Windows 系统通知 (P1)
- 系统托盘支持 (P1)
- simple-cli-tool 示例完善 (P3)

---

## 相关文档

- `CLAUDE.md` - Claude Code 指导文档
- `README.md` - 项目说明
- `IMPLEMENTATION_STATUS.md` - 实现状态
- `IMPLEMENTATION_PLAN.md` - 实现计划
- `TESTING.md` - 测试指南
- `CONTRIBUTING.md` - 贡献指南
- `docs/` - 详细文档目录
  - `docs/用户指南/` - 用户指南系列
  - `docs/CLI选项参考.md` - CLI 选项文档

---

## 快速参考

### 导入示例

```python
# 模型
from ralph_gui.models.circuit_breaker import CircuitBreakerModel, CircuitBreakerState
from ralph_gui.models.loop_state import LoopStateModel
from ralph_gui.models.project import Project
from ralph_gui.models.rate_limit import RateLimitModel
from ralph_gui.models.session import Session

# 服务
from ralph_gui.services.cli_service import CLIService, LoopOptions
from ralph_gui.services.state_service import StateService
from ralph_gui.services.config_service import ConfigService
from ralph_gui.services.log_service import LogService

# Presenter
from ralph_gui.presenters.loop_presenter import LoopPresenter
from ralph_gui.presenters.settings_presenter import SettingsPresenter
from ralph_gui.presenters.startup_presenter import StartupPresenter

# View 组件
from ralph_gui.views.widgets.metric_display import MetricDisplay
from ralph_gui.views.widgets.status_card import StatusCard
from ralph_gui.views.theme import Colors

# 国际化
from ralph_gui.i18n import tr

# 库模块
from lib.circuit_breaker import init_circuit_breaker, can_execute, record_loop_result
from lib.response_analyzer import analyze_response
from lib.log_utils import get_cli_logger
```

### 状态检查

```python
# 检查断路器状态
cb = CircuitBreakerModel.from_project(project_dir)
if cb.is_open:
    print(f"Circuit open: {cb.reason}")

# 检查循环状态
cli = CLIService()
if cli.is_loop_running():
    status = cli.get_status(project_dir)

# 检查速率限制
rate_limit = RateLimitModel.from_project(project_dir)
if rate_limit.is_limited:
    print(f"Rate limited, reset in: {rate_limit.reset_in}")
```

### 启动循环

```python
from ralph_gui.services.cli_service import CLIService, LoopOptions

cli = CLIService()
options = LoopOptions(
    max_calls=100,
    timeout_minutes=15,
    output_format="json"
)

def on_progress(data):
    print(f"Loop {data['loop_number']}: {data['line']}")

cli.start_loop(project_dir, options, progress_callback=on_progress)
```

### 使用国际化

```python
from ralph_gui.i18n import tr, TRANSLATIONS
from ralph_gui.i18n import EN_TRANSLATIONS, ZH_TRANSLATIONS

# 获取翻译
text = tr("app.title")  # "Ralph GUI"
text = tr("loop.running", count=5)  # "正在运行 (第 5 次循环)"

# 切换语言
from ralph_gui.i18n import TRANSLATIONS
TRANSLATIONS = EN_TRANSLATIONS  # 切换到英文
```
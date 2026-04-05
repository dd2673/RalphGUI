#!/usr/bin/env python3
"""
Ralph Monitor - 实时监控仪表板

提供三种监控模式:
- TUI 模式: 使用 textual 库实现文字界面 (推荐)
- GUI 模式: 调用 ralph-gui 的 PySide6 组件
- Simple 模式: 简单打印状态信息，不实时更新
"""
import sys
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator, List, Dict, Any

import click

# 添加 ralph-gui 路径以便导入模块
RALPH_GUI_SRC = Path(__file__).parent.parent / "src"
if RALPH_GUI_SRC.exists():
    sys.path.insert(0, str(RALPH_GUI_SRC))

# 项目根目录
PROJECT_ROOT = Path.cwd()
RALPH_DIR = PROJECT_ROOT / ".ralph"
STATUS_FILE = RALPH_DIR / "status.json"
LOG_DIR = RALPH_DIR / "logs"
CIRCUIT_BREAKER_FILE = RALPH_DIR / ".circuit_breaker_state"
SESSION_FILE = RALPH_DIR / ".ralph_session"


@dataclass
class LoopState:
    """Ralph 循环状态"""
    loop_count: int = 0
    circuit_state: str = "UNKNOWN"  # CLOSED/HALF_OPEN/OPEN
    calls_made: int = 0
    calls_limit: int = 100
    tokens_used: int = 0
    tokens_limit: int = 0  # 0 = disabled
    session_id: str = ""
    last_activity: str = ""
    session_duration: str = ""
    last_error: Optional[str] = None
    status: str = "unknown"
    exit_reason: Optional[str] = None


def read_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """读取 JSON 文件"""
    if not file_path.exists():
        return None
    try:
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_loop_state() -> LoopState:
    """获取当前循环状态"""
    state = LoopState()

    # 读取 status.json
    status_data = read_json(STATUS_FILE)
    if status_data:
        state.loop_count = status_data.get("loop_number", status_data.get("loop_count", 0))
        state.calls_made = status_data.get("calls_this_hour", status_data.get("calls_made_this_hour", 0))
        state.calls_limit = status_data.get("max_calls_per_hour", 100)
        state.tokens_used = status_data.get("tokens_used_this_hour", 0)
        state.tokens_limit = status_data.get("max_tokens_per_hour", 0)
        state.status = status_data.get("status", "unknown")
        state.last_activity = status_data.get("last_updated", "")

    # 读取电路断路器状态
    cb_data = read_json(CIRCUIT_BREAKER_FILE)
    if cb_data:
        state.circuit_state = cb_data.get("state", "UNKNOWN")
        state.last_error = cb_data.get("reason")

    # 读取会话信息
    session_data = read_json(SESSION_FILE)
    if session_data:
        state.session_id = session_data.get("session_id", "")
        if "created_at" in session_data:
            try:
                created = datetime.fromisoformat(session_data["created_at"])
                duration = datetime.now() - created
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                state.session_duration = f"{hours}h {minutes}m {seconds}s"
            except (ValueError, TypeError):
                pass

    return state


def check_tmux_available() -> bool:
    """检查 tmux 是否可用（跨平台）"""
    import shutil
    return shutil.which("tmux") is not None


def tail_log_file(log_file: Path, lines: int = 100) -> Iterator[str]:
    """模拟 tail -f 功能，实时读取日志

    Args:
        log_file: 日志文件路径
        lines: 初始读取的行数

    Yields:
        日志文件的新增内容
    """
    if not log_file.exists():
        return

    with open(log_file, 'r', encoding='utf-8') as f:
        # 跳到文件末尾
        f.seek(0, os.SEEK_END)
        file_pos = f.tell()

        while True:
            # 读取新内容
            line = f.readline()
            if line:
                file_pos = f.tell()
                yield line.rstrip('\n')
            else:
                # 等待新内容
                import time
                time.sleep(0.5)
                try:
                    # 检查文件是否被截断
                    current_size = os.path.getsize(log_file)
                    if current_size < file_pos:
                        # 文件被截断，重新开始
                        f.seek(0)
                        file_pos = 0
                    else:
                        f.seek(file_pos)
                except OSError:
                    break


def get_recent_log_lines(count: int = 10) -> List[str]:
    """获取最近的日志行

    Args:
        count: 要获取的行数

    Returns:
        日志行列表
    """
    if not LOG_DIR.exists():
        return []

    log_files = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        return []

    # 读取最新的日志文件
    latest_log = log_files[0]
    try:
        with open(latest_log, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-count:] if line.strip()]
    except IOError:
        return []


def get_progress_info() -> Dict[str, Any]:
    """获取 Claude Code 执行进度信息"""
    progress_file = RALPH_DIR / "progress.json"
    data = read_json(progress_file)
    if data:
        return {
            "status": data.get("status", "idle"),
            "indicator": data.get("indicator", ""),
            "elapsed_seconds": data.get("elapsed_seconds", 0),
            "last_output": data.get("last_output", "")
        }
    return {"status": "idle", "indicator": "", "elapsed_seconds": 0, "last_output": ""}


def print_simple_status() -> None:
    """简单模式: 打印当前状态信息"""
    state = get_loop_state()

    print("=" * 60)
    print("RALPH MONITOR - Simple Mode")
    print("=" * 60)
    print(f"Loop Count:      #{state.loop_count}")
    print(f"Status:          {state.status}")
    print(f"Circuit State:   {state.circuit_state}")
    print(f"API Calls:       {state.calls_made}/{state.calls_limit}")
    if state.tokens_limit > 0:
        print(f"Tokens Used:     {state.tokens_used}/{state.tokens_limit}")
    if state.session_id:
        print(f"Session ID:      {state.session_id[:16]}...")
    if state.session_duration:
        print(f"Session Time:    {state.session_duration}")
    print(f"Last Activity:  {state.last_activity}")
    if state.last_error:
        print(f"Last Error:     {state.last_error}")
    print()

    # 显示最近日志
    print("Recent Logs:")
    logs = get_recent_log_lines(5)
    if logs:
        for log in logs:
            print(f"  {log}")
    else:
        print("  No logs available")
    print("=" * 60)


# TUI 模式需要 textual 库
TEXTUAL_AVAILABLE = False
try:
    from textual.app import App, ComposeResult
    from textual.widgets import Static, Log, Header, Footer
    from textual.containers import Container, ScrollableContainer
    from textual.binding import Binding
    TEXTUAL_AVAILABLE = True
except ImportError:
    pass


if TEXTUAL_AVAILABLE:
    class RalphMonitorApp(App):
        """Ralph 监控 TUI 应用"""

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("r", "refresh", "Refresh"),
        ]

        CSS = """
        Screen {
            background: $surface;
        }
        #header {
            height: 3;
            background: $primary;
            color: $text;
            dock: top;
        }
        #status-container {
            height: auto;
            padding: 1;
            background: $surface-darken-1;
            border: solid $primary;
        }
        #log-container {
            height: 1fr;
            border: solid $primary;
            margin: 1 0;
        }
        #footer {
            height: 1;
            background: $surface-darken-2;
            dock: bottom;
        }
        .status-label {
            color: $text-muted;
            width: 16;
        }
        .status-value {
            color: $text;
        }
        .status-closed {
            color: $success;
        }
        .status-half-open {
            color: $warning;
        }
        .status-open {
            color: $error;
        }
        """

        def __init__(self, project_root: Path = PROJECT_ROOT):
            super().__init__()
            self.project_root = project_root
            self.title = "Ralph Monitor"
            self.sub_title = "Live Status Dashboard"

        def compose(self) -> ComposeResult:
            """创建 UI 组件"""
            yield Header(self.title, id="header")

            with Container(id="status-container"):
                yield Static("Loop Count: #0", id="loop-count")
                yield Static("Status: unknown", id="status")
                yield Static("Circuit: UNKNOWN", id="circuit")
                yield Static("API Calls: 0/100", id="api-calls")
                yield Static("Tokens: 0/0", id="tokens")
                yield Static("Session: -", id="session")
                yield Static("Duration: -", id="duration")
                yield Static("Last Activity: -", id="activity")
                yield Static("Last Error: -", id="error")

            with ScrollableContainer(id="log-container"):
                yield Log(id="log-view")

            yield Footer()

        def on_mount(self) -> None:
            """应用挂载时初始化"""
            self.set_timer(1, self.update_status)

        def update_status(self) -> None:
            """更新状态显示"""
            state = get_loop_state()
            progress = get_progress_info()

            # 更新状态显示
            self.query_one("#loop-count", Static).update(f"Loop Count: #{state.loop_count}")
            self.query_one("#status", Static).update(f"Status: {state.status}")

            # 电路断路器状态着色
            circuit_widget = self.query_one("#circuit", Static)
            if state.circuit_state == "CLOSED":
                circuit_widget.update(f"[green]Circuit: {state.circuit_state}[/green]")
            elif state.circuit_state == "HALF_OPEN":
                circuit_widget.update(f"[yellow]Circuit: {state.circuit_state}[/yellow]")
            elif state.circuit_state == "OPEN":
                circuit_widget.update(f"[red]Circuit: {state.circuit_state}[/red]")
            else:
                circuit_widget.update(f"Circuit: {state.circuit_state}")

            # API 调用
            self.query_one("#api-calls", Static).update(
                f"API Calls: {state.calls_made}/{state.calls_limit}"
            )

            # Token 使用
            if state.tokens_limit > 0:
                self.query_one("#tokens", Static).update(
                    f"Tokens: {state.tokens_used}/{state.tokens_limit}"
                )
            else:
                self.query_one("#tokens", Static).update("Tokens: unlimited")

            # 会话信息
            session_str = state.session_id[:16] + "..." if state.session_id else "-"
            self.query_one("#session", Static).update(f"Session: {session_str}")
            self.query_one("#duration", Static).update(f"Duration: {state.session_duration or '-'}")

            # 最后活动时间
            self.query_one("#activity", Static).update(
                f"Last Activity: {state.last_activity or '-'}"
            )

            # 最后错误
            if state.last_error:
                self.query_one("#error", Static).update(f"[red]Error: {state.last_error}[/red]")
            else:
                self.query_one("#error", Static).update("Last Error: -")

            # 执行进度
            if progress["status"] == "executing":
                log_view = self.query_one("#log-view", Log)
                indicator = progress.get("indicator", "⠋")
                elapsed = progress.get("elapsed_seconds", 0)
                log_view.write_line(f"[yellow]{indicator} Working... ({elapsed}s elapsed)[/yellow]")

            # 更新日志
            self.update_logs()

            # 定时更新
            self.set_timer(2, self.update_status)

        def update_logs(self) -> None:
            """更新日志显示"""
            logs = get_recent_log_lines(20)
            log_view = self.query_one("#log-view", Log)

            # 清空并重新显示
            for log in logs:
                log_view.write_line(log)

        def action_quit(self) -> None:
            """退出应用"""
            self.exit()

        def action_refresh(self) -> None:
            """手动刷新"""
            self.update_status()


def run_tui_mode() -> None:
    """运行 TUI 模式"""
    if not TEXTUAL_AVAILABLE:
        print("错误: textual 库未安装")
        print("请运行: pip install textual")
        print("或者使用简单模式: ralph-monitor --mode simple")
        sys.exit(1)

    app = RalphMonitorApp()
    app.run()


def run_gui_mode() -> None:
    """运行 GUI 模式 - 调用 ralph-gui"""
    # 尝试导入并运行 ralph-gui
    gui_module = RALPH_GUI_SRC / "ralph_gui"
    if gui_module.exists():
        try:
            # 使用 subprocess 调用 ralph-gui
            subprocess.run([
                sys.executable, "-m", "ralph_gui"
            ], cwd=str(RALPH_GUI_SRC.parent))
        except Exception as e:
            print(f"启动 GUI 失败: {e}")
            print("请确保已安装 ralph-gui 依赖")
            sys.exit(1)
    else:
        print("错误: ralph-gui 模块未找到")
        print("请先构建 ralph-gui")
        sys.exit(1)


@click.command()
@click.option(
    '--mode',
    type=click.Choice(['tui', 'gui', 'simple']),
    default='tui',
    help='监控模式: tui (文字界面), gui (图形界面), simple (简单输出)'
)
@click.option(
    '--project',
    '-p',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help='Ralph 项目目录 (默认: 当前目录)'
)
def monitor(mode: str, project: Optional[Path]) -> None:
    """Ralph 监控仪表板

    提供实时监控 Ralph 循环状态的功能。
    支持三种模式:
    \b
    - tui: 文字界面 (推荐, 需要 textual 库)
    - gui: 图形界面 (需要 PySide6)
    - simple: 简单输出, 不实时更新
    """
    global PROJECT_ROOT, RALPH_DIR, STATUS_FILE, LOG_DIR

    # 设置项目目录
    if project:
        PROJECT_ROOT = project
        RALPH_DIR = PROJECT_ROOT / ".ralph"
        STATUS_FILE = RALPH_DIR / "status.json"
        LOG_DIR = RALPH_DIR / "logs"

    # 检查 Ralph 项目
    if not RALPH_DIR.exists():
        click.echo(f"错误: {RALPH_DIR} 目录不存在")
        click.echo("请确保在 Ralph 项目目录中运行此命令")
        sys.exit(1)

    required_files = ["PROMPT.md", "fix_plan.md", "AGENT.md"]
    missing = [f for f in required_files if not (RALPH_DIR / f).exists()]
    if missing:
        click.echo(f"警告: 缺少必要文件: {', '.join(missing)}")

    # 根据模式运行
    if mode == 'tui':
        # 检查 tmux 是否可用, 如果可用可以考虑集成
        if check_tmux_available():
            click.echo("检测到 tmux 可用, 可使用 tmux 会话运行监控")
        run_tui_mode()
    elif mode == 'gui':
        run_gui_mode()
    else:  # simple
        print_simple_status()


if __name__ == "__main__":
    monitor()

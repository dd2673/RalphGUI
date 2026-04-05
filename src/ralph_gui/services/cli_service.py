"""
CLI服务 - 纯Python实现，不依赖外部bash脚本
Windows兼容
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

# 导入本项目模块
from ..lib.response_analyzer import analyze_response, parse_json_response
from ..lib.enable_core import enable_ralph_in_directory, ENABLE_SUCCESS
from ..models.circuit_breaker import CircuitBreakerModel, CircuitBreakerState
from ..lib.log_utils import get_cli_logger, get_service_logger

# 获取日志器
logger = get_cli_logger()
service_logger = get_service_logger()


@dataclass
class LoopOptions:
    """循环选项"""
    max_calls: int = 100
    max_tokens: int = 0
    timeout_minutes: int = 15
    output_format: str = "json"
    allowed_tools: Optional[str] = None
    no_continue: bool = False
    dangerously_skip_permissions: bool = True
    verbose: bool = False
    append_previous_summary: bool = True


@dataclass
class LoopStatus:
    """循环状态"""
    is_running: bool = False
    loop_number: int = 0
    calls_made: int = 0
    total_calls: int = 0
    start_time: Optional[datetime] = None
    last_output: Optional[str] = None
    error: Optional[str] = None


class CLIService:
    """CLI服务 - 纯Python实现"""

    # 类级别缓存：避免每次启动都搜索 Claude 命令
    _claude_cmd_cache: Optional[str] = None

    # 内存管理常量
    MAX_OUTPUT_LINES: int = 1000  # 日志输出最大行数
    MAX_JSON_LENGTH: int = 5000   # JSON响应最大字符数

    def __init__(self, ralph_home: Optional[Path] = None):
        """
        初始化CLI服务

        ralph_home: Ralph安装目录，默认为~/.ralph
        """
        if ralph_home is None:
            ralph_home = Path.home() / ".ralph"
        self.ralph_home = ralph_home
        self.process: Optional[subprocess.Popen] = None
        self._loop_status = LoopStatus()
        self._loop_count = 0  # 跟踪循环编号
        self._output_buffer: List[str] = []
        self._callbacks: Dict[str, Callable] = {}
        self._timeout_seconds: float = 0
        self._loop_start_time: Optional[datetime] = None
        logger.debug(f"CLIService initialized. ralph_home={self.ralph_home}")

    def find_claude_command(self) -> Optional[str]:
        """查找Claude Code CLI命令（带缓存）"""
        # 如果已有缓存，直接返回
        if CLIService._claude_cmd_cache is not None:
            logger.debug(f"Using cached Claude command: {CLIService._claude_cmd_cache}")
            return CLIService._claude_cmd_cache

        logger.debug("Searching for Claude Code command...")

        # 优先从ralph_home查找
        claude_cmd = self.ralph_home / "claude"
        if claude_cmd.exists():
            logger.info(f"Found Claude command in ralph_home: {claude_cmd}")
            CLIService._claude_cmd_cache = str(claude_cmd)
            return str(claude_cmd)

        # 从PATH查找
        for cmd in ["claude", "claude-code", "npx @anthropic-ai/claude-code"]:
            path = shutil.which(cmd)
            if path:
                logger.info(f"Found Claude command in PATH: {path}")
                CLIService._claude_cmd_cache = cmd
                return cmd

        # Windows: 尝试常见安装位置
        if sys.platform == 'win32':
            local_appdata = os.environ.get('LOCALAPPDATA')
            if local_appdata:
                paths = [
                    Path(local_appdata) / "Programs" / "claude" / "claude.exe",
                    Path(local_appdata) / "claude" / "claude.exe",
                ]
                for p in paths:
                    if p.exists():
                        logger.info(f"Found Claude command at Windows installation path: {p}")
                        CLIService._claude_cmd_cache = str(p)
                        return str(p)

        logger.warning("Claude Code command not found")
        CLIService._claude_cmd_cache = None
        return None

    def is_ralph_available(self) -> bool:
        """检查Claude Code CLI是否可用"""
        available = self.find_claude_command() is not None
        logger.debug(f"RALPH availability check: {available}")
        return available

    def _validate_project_path(self, project_dir: Path) -> bool:
        """
        安全验证：检查项目路径是否安全

        禁止在系统目录运行，防止误操作造成系统损坏。
        """
        if not project_dir:
            return False

        try:
            # 获取绝对路径并规范化
            project_path = project_dir.resolve()

            # 系统目录列表（Windows）
            system_paths = []
            if sys.platform == 'win32':
                # Windows 系统目录
                windows_dir = Path(os.environ.get('WINDIR', 'C:\\Windows'))
                program_files = Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files'))
                program_files_x86 = Path(os.environ.get('PROGRAMFILES(x86)', 'C:\\Program Files (x86)'))
                system_paths = [
                    windows_dir,
                    windows_dir / 'System32',
                    windows_dir / 'SysWOW64',
                    program_files,
                    program_files_x86,
                    Path('C:\\'),
                    Path('C:/Windows'),
                    Path('C:/Windows/System32'),
                ]
            else:
                # Unix 系统目录
                system_paths = [
                    Path('/'),
                    Path('/usr'),
                    Path('/usr/bin'),
                    Path('/usr/sbin'),
                    Path('/bin'),
                    Path('/sbin'),
                    Path('/etc'),
                    Path('/var'),
                    Path('/sys'),
                    Path('/proc'),
                    Path('/dev'),
                ]

            # 检查项目路径是否在系统目录内
            for sys_path in system_paths:
                try:
                    sys_path_resolved = sys_path.resolve()
                    # 使用相对路径检查，而不是 startswith（更安全）
                    if project_path == sys_path_resolved or project_path.is_relative_to(sys_path_resolved):
                        logger.error(f"项目路径在系统目录内，禁止运行: {project_path} vs {sys_path_resolved}")
                        return False
                except (ValueError, OSError):
                    # is_relative_to 在某些路径上可能失败，忽略并继续
                    continue

            # 检查是否是符号链接到系统目录
            if project_path.exists():
                try:
                    if project_path.is_symlink():
                        target = project_path.resolve()
                        for sys_path in system_paths:
                            if target.is_relative_to(sys_path.resolve()):
                                logger.error(f"项目路径是系统目录的符号链接，禁止运行")
                                return False
                except (OSError, RuntimeError):
                    pass

            logger.debug(f"项目路径安全检查通过: {project_path}")
            return True

        except Exception as e:
            logger.error(f"项目路径安全检查失败: {e}")
            return False

    def get_ralph_dir(self) -> Path:
        """获取Ralph目录"""
        return self.ralph_home

    def _get_status_file(self, project_dir: Path) -> Path:
        """获取状态文件路径"""
        return project_dir / ".ralph" / "status.json"

    def _ensure_ralph_structure(self, project_dir: Path) -> bool:
        """确保.ralph目录结构存在"""
        logger.debug(f"Ensuring .ralph structure exists in {project_dir}")
        try:
            ralph_dir = project_dir / ".ralph"
            ralph_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f".ralph directory ensured: {ralph_dir}")
            return True
        except OSError as e:
            logger.error(f"Failed to create .ralph directory: {e}", exc_info=True)
            return False

    def _init_circuit_breaker(self, project_dir: Path) -> Optional[CircuitBreakerModel]:
        """初始化断路器"""
        logger.debug(f"Initializing circuit breaker for {project_dir}")
        try:
            cb = CircuitBreakerModel.from_project(project_dir)
            cb.attempt_recovery()
            cb.save(project_dir)
            logger.info(f"Circuit breaker initialized. State: {cb.state}")
            return cb
        except Exception as e:
            logger.error(f"Failed to initialize circuit breaker: {e}", exc_info=True)
            return None

    def _get_session_id(self, project_dir: Path) -> Optional[str]:
        """获取或初始化会话ID"""
        session_file = project_dir / ".ralph" / ".claude_session_id"
        if session_file.exists():
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception:
                pass
        return None

    def _save_session_id(self, project_dir: Path, session_id: str) -> None:
        """保存会话ID"""
        session_file = project_dir / ".ralph" / ".claude_session_id"
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                f.write(session_id)
            logger.debug(f"Session ID saved: {session_id[:20]}...")
        except Exception as e:
            logger.warning(f"Failed to save session ID: {e}")

    def _build_loop_context(self, project_dir: Path, loop_number: int, append_previous_summary: bool = True) -> str:
        """构建循环上下文"""
        context = f"Loop #{loop_number}. "

        # 检查 fix_plan.md 剩余任务
        fix_plan = project_dir / ".ralph" / "fix_plan.md"
        if fix_plan.exists():
            try:
                with open(fix_plan, 'r', encoding='utf-8') as f:
                    content = f.read()
                import re
                incomplete = len(re.findall(r'^ *- *\[\s*\]', content, re.MULTILINE))
                context += f"Remaining tasks: {incomplete}. "
            except Exception:
                pass

        # 检查上次工作摘要（仅当启用时）
        if append_previous_summary:
            analysis_file = project_dir / ".ralph" / ".response_analysis"
            if analysis_file.exists():
                try:
                    with open(analysis_file, 'r', encoding='utf-8') as f:
                        analysis = json.load(f)
                    prev = analysis.get('analysis', {}).get('work_summary', '')
                    if prev:
                        context += f"Previous: {prev[:200]} "
                except Exception:
                    pass

        return context[:500]

    def start_loop(
        self,
        project_dir: Path,
        options: LoopOptions = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> subprocess.Popen:
        """
        启动Ralph循环

        直接使用Python实现，通过subprocess调用Claude Code CLI。
        使用 -p 参数传递 prompt 内容。
        """
        logger.info(f"Starting Ralph loop. project_dir={project_dir}")

        # 如果当前没有在运行，说明是新的循环开始，重置计数器
        if not self._loop_status.is_running:
            self._loop_count = 0


        # 【安全验证】- 项目路径安全检查
        if not self._validate_project_path(project_dir):
            error_msg = f"项目路径不安全: {project_dir}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        if options is None:
            options = LoopOptions()

        # 【诊断日志】- 统一调用 ConfigService 进行项目诊断
        from .config_service import ConfigService
        logger.info("=" * 60)
        logger.info("【诊断】正在检查项目配置...")
        
        diagnostic_result = ConfigService.diagnose_project(project_dir)
        
        # 记录诊断结果摘要
        passed = sum(1 for v in diagnostic_result['checks'].values() if v)
        total = len(diagnostic_result['checks'])
        logger.info(f"【诊断】检查完成: {passed}/{total} 项通过")
        
        # 检查关键项是否通过
        check_passed = (
            diagnostic_result['checks'].get('project_dir_exists', False) and
            diagnostic_result['checks'].get('project_dir_writable', False)
        )
        
        if not check_passed:
            logger.error("【诊断】关键检查未通过，可能无法正常启动")
        
        logger.info("=" * 60)

        claude_cmd = self.find_claude_command()

        if not claude_cmd:
            logger.error("Claude Code CLI not found. Cannot start loop.")
            raise RuntimeError("Claude Code CLI not found. Please install Claude Code.")

        # 确保.ralph目录存在
        if not self._ensure_ralph_structure(project_dir):
            logger.error("Failed to ensure .ralph directory structure")

        # 初始化断路器
        cb = self._init_circuit_breaker(project_dir)
        if cb:
            logger.info(f"Circuit breaker state: {cb.state.value}")
        else:
            logger.warning("Circuit breaker not initialized")

        # 构建Claude Code命令参数
        cmd_args = []
        logger.debug(f"Loop options: max_calls={options.max_calls}, max_tokens={options.max_tokens}, timeout={options.timeout_minutes}")

        # 输出格式
        if options.output_format == "json":
            cmd_args.extend(["--output-format", "json"])

        # 继续模式 (会话恢复)
        if not options.no_continue:
            session_id = self._get_session_id(project_dir)
            if session_id:
                cmd_args.extend(["--resume", session_id])
                logger.debug(f"Resuming session: {session_id[:20]}...")

        # 跳过权限检查（危险模式）
        if options.dangerously_skip_permissions:
            cmd_args.append("--dangerously-skip-permissions")

        # 允许的工具 - 使用 --allowedTools 格式
        if options.allowed_tools:
            cmd_args.append("--allowedTools")
            tools = [t.strip() for t in options.allowed_tools.split(',')]
            cmd_args.extend(tools)
            logger.debug(f"Allowed tools: {options.allowed_tools}")

        # 详细输出
        if options.verbose:
            cmd_args.append("--verbose")

        # 添加循环上下文
        self._loop_count += 1
        loop_context = self._build_loop_context(project_dir, self._loop_count, options.append_previous_summary)
        if loop_context:
            cmd_args.extend(["--append-system-prompt", loop_context])
            logger.debug(f"Loop context: {loop_context[:100]}...")

        # 读取 prompt 内容，通过 -p 参数传递
        prompt_content = ""
        prompt_file = project_dir / ".ralph" / "PROMPT.md"
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_content = f.read()
                logger.debug(f"Prompt file loaded: {prompt_file} ({len(prompt_content)} chars)")
            except Exception as e:
                logger.error(f"Failed to read prompt file: {e}", exc_info=True)

        # 设置环境变量
        env = os.environ.copy()
        env["RALPH_PROJECT_DIR"] = str(project_dir)
        env["RALPH_LOOP"] = "true"
        
        # 【通信详情日志】- 记录环境变量
        logger.info("=" * 60)
        logger.info("【通信诊断】环境变量设置:")
        logger.info(f"  RALPH_PROJECT_DIR={env.get('RALPH_PROJECT_DIR')}")
        logger.info(f"  RALPH_LOOP={env.get('RALPH_LOOP')}")
        logger.info("=" * 60)

        # 启动进程
        self._loop_status = LoopStatus(
            is_running=True,
            total_calls=options.max_calls,
            start_time=datetime.now()
        )
        # 存储超时秒数用于超时检查
        self._timeout_seconds = options.timeout_minutes * 60 if options.timeout_minutes else 0
        self._loop_start_time = datetime.now()
        logger.info(f"Loop status initialized. max_calls={options.max_calls}, timeout={options.timeout_minutes}m")

        try:
            # 构建完整命令
            final_cmd = [claude_cmd] + cmd_args
            
            # 将 prompt 内容直接作为参数传递
            if prompt_content:
                final_cmd.extend(["-p", prompt_content])
            
            # 【通信详情日志】- 记录完整命令参数
            logger.info("=" * 60)
            logger.info("【通信诊断】Claude 命令构建详情:")
            logger.info(f"  命令路径: {claude_cmd}")
            logger.info(f"  基础参数: {cmd_args}")
            logger.info(f"  总参数数量: {len(cmd_args)}")
            
            # 记录会话恢复信息
            if not options.no_continue:
                session_id = self._get_session_id(project_dir)
                if session_id:
                    logger.info(f"  会话恢复: 是 (session_id: {session_id[:30]}...)")
                else:
                    logger.info("  会话恢复: 否 (无会话ID)")
            else:
                logger.info("  会话恢复: 否 (用户禁用)")
            
            # 记录 prompt 内容摘要
            if prompt_content:
                logger.info(f"  Prompt 文件: {prompt_file}")
                logger.info(f"  Prompt 长度: {len(prompt_content)} 字符")
                # 记录 prompt 前500字符作为摘要
                prompt_summary = prompt_content[:500].replace('\n', ' ')
                if len(prompt_content) > 500:
                    prompt_summary += "..."
                logger.info(f"  Prompt 摘要: {prompt_summary}")
                
                # 【诊断文件】- 将完整 prompt 写入诊断文件
                diagnostic_dir = project_dir / ".ralph" / "logs"
                diagnostic_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                diagnostic_file = diagnostic_dir / f"diagnostic_prompt_{timestamp}.md"
                try:
                    with open(diagnostic_file, 'w', encoding='utf-8') as f:
                        f.write(f"# Diagnostic Prompt Log\n\n")
                        f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
                        f.write(f"**Project**: {project_dir}\n\n")
                        f.write(f"**Loop Number**: {self._loop_status.loop_number + 1}\n\n")
                        f.write("---\n\n")
                        f.write("## Command Arguments\n\n")
                        f.write(f"```\n{cmd_args}\n```\n\n")
                        f.write("## Environment Variables\n\n")
                        f.write(f"- RALPH_PROJECT_DIR: {env.get('RALPH_PROJECT_DIR')}\n")
                        f.write(f"- RALPH_LOOP: {env.get('RALPH_LOOP')}\n\n")
                        f.write("## Full Prompt Content\n\n")
                        f.write(prompt_content)
                    logger.info(f"  诊断文件已保存: {diagnostic_file}")
                except Exception as e:
                    logger.warning(f"  保存诊断文件失败: {e}")
            else:
                logger.warning("  Prompt 内容: 空 (未找到 PROMPT.md 或读取失败)")
            
            logger.info("=" * 60)
            
            # 记录完整命令（不含 prompt 内容用于显示）
            cmd_display = [claude_cmd] + [arg for arg in cmd_args if len(arg) < 100]
            logger.info(f"Starting subprocess: {' '.join(cmd_display)}")
            logger.debug(f"Full cmd_args length: {len(str(cmd_args))} chars")

            # 启动进程
            self.process = subprocess.Popen(
                final_cmd,
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
                stdin=subprocess.DEVNULL,  # 不使用 stdin
                text=True,
                bufsize=-1,  # 使用系统默认缓冲（更可靠）
                env=env
            )
            
            # 【进程生命周期日志】- 启动成功记录
            logger.info("=" * 60)
            logger.info("【进程诊断】进程启动成功:")
            logger.info(f"  PID: {self.process.pid}")
            logger.info(f"  启动时间: {datetime.now().isoformat()}")
            logger.info(f"  工作目录: {project_dir}")
            logger.info(f"  命令长度: {len(' '.join(final_cmd))} 字符")
            logger.info(f"  超时设置: {options.timeout_minutes} 分钟")
            logger.info("=" * 60)

            # 启动输出监听线程
            if self.process.stdout:
                reader_thread = threading.Thread(
                    target=self._read_loop_output,
                    args=(project_dir, cb, progress_callback),
                    daemon=True
                )
                reader_thread.start()
                logger.debug("Output reader thread started")

            return self.process

        except Exception as e:
            self._loop_status.is_running = False
            self._loop_status.error = str(e)
            logger.exception(f"Failed to start loop: {e}")
            raise

    def _read_loop_output(
        self,
        project_dir: Path,
        cb: Optional[CircuitBreakerModel],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]]
    ) -> None:
        """后台线程：读取循环输出并进行分析"""
        if not self.process or not self.process.stdout:
            logger.error("No process or stdout not available")
            return

        loop_start_time = datetime.now()
        timeout_seconds = self._timeout_seconds
        loop_ended_notified = False  # 跟踪是否已发送结束通知
        output_lines_for_session = []  # 用于提取会话ID的输出行
        lines_read = 0  # 统计读取的行数
        bytes_read = 0  # 统计读取的字节数

        # 创建循环输出日志文件
        logs_dir = project_dir / ".ralph" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        loop_log_file = logs_dir / f"loop_output_{timestamp}.log"

        logger.info("=" * 60)
        logger.info("【进程诊断】开始读取进程输出...")
        logger.info(f"  输出日志文件: {loop_log_file}")
        logger.info("=" * 60)

        try:
            with open(loop_log_file, 'w', encoding='utf-8') as log_file:
                log_file.write(f"=== Loop Output Log Started at {datetime.now()} ===\n")
                log_file.write(f"Timeout: {timeout_seconds}s, Project: {project_dir}\n")
                log_file.write("=" * 50 + "\n")
                log_file.flush()

                while True:
                    line = self.process.stdout.readline()
                    lines_read += 1
                    if line:
                        bytes_read += len(line.encode('utf-8'))

                    # 诊断日志：记录前几次 readline 的结果
                    if lines_read <= 3:
                        poll_result = self.process.poll()
                        logger.warning(
                            f"【诊断】readline #{lines_read}: "
                            f"内容长度={len(line)} "
                            f"进程状态={'运行中' if poll_result is None else f'已退出({poll_result})'} "
                            f"前30字符={(line[:30] if line else '(empty)')!r}"
                        )

                    logger.debug(f"readline returned: {line[:100] if line else '(empty)'}")
                    if not line:
                        # 进程正常结束，通知回调
                        logger.debug("Process ended, notifying callback")
                        logger.debug(f"progress_callback is None: {progress_callback is None}, loop_ended_notified: {loop_ended_notified}")

                        # 尝试从输出中提取会话ID
                        self._extract_session_from_output(project_dir, output_lines_for_session)

                        if not loop_ended_notified and progress_callback:
                            try:
                                progress_callback({
                                    "loop_number": self._loop_status.loop_number,
                                    "line": "",
                                    "buffer": self._output_buffer.copy(),
                                    "circuit_breaker": cb.state.value if cb else None,
                                    "loop_ended": True,
                                    "end_reason": "process_ended",
                                    "error": None
                                })
                            except Exception:
                                pass
                        break

                    # 保存输出到日志文件
                    log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
                    log_file.flush()

                    # 超时检查
                    if timeout_seconds > 0:
                        elapsed = (datetime.now() - loop_start_time).total_seconds()
                        if elapsed >= timeout_seconds:
                            timeout_min = int(timeout_seconds // 60)
                            logger.warning(f"Loop timeout after {elapsed:.1f} seconds ({timeout_min}m)")
                            self._loop_status.error = f"Timeout after {timeout_min} minutes"
                            # 通知回调
                            if progress_callback:
                                try:
                                    progress_callback({
                                        "loop_number": self._loop_status.loop_number,
                                        "line": "",
                                        "buffer": self._output_buffer.copy(),
                                        "circuit_breaker": cb.state.value if cb else None,
                                        "loop_ended": True,
                                        "end_reason": "timeout",
                                        "error": self._loop_status.error
                                    })
                                    loop_ended_notified = True
                                except Exception:
                                    pass
                            self.stop_loop()
                            break

                    line = line.rstrip('\n')
                    self._output_buffer.append(line)
                    self._loop_status.last_output = line
                    output_lines_for_session.append(line)  # 保存用于会话ID提取

                    # 内存管理：自动清理过大的缓冲区
                    self._trim_output_buffer()
                    self._truncate_large_json_in_buffer()

                    # 注意：不要在每行输出时增加循环计数
                    # 循环计数由 LoopPresenter 在每次调用完成后增加

                    # 检查断路器状态
                    if cb:
                        if cb.is_open and not cb.check_cooldown():
                            # 断路器打开且未冷却，终止循环
                            logger.warning(f"Circuit breaker opened: {cb.reason}")
                            cb.save(project_dir)  # 保存断路器状态
                            self._loop_status.error = f"Circuit breaker open: {cb.reason}"
                            # 通过回调通知状态变化
                            if progress_callback:
                                try:
                                    progress_callback({
                                        "loop_number": self._loop_status.loop_number,
                                        "line": "",
                                        "buffer": self._output_buffer.copy(),
                                        "circuit_breaker": cb.state.value,
                                        "loop_ended": True,
                                        "end_reason": "circuit_opened",
                                        "circuit_opened": True,
                                        "error": self._loop_status.error
                                    })
                                    loop_ended_notified = True
                                except Exception:
                                    pass
                            self.stop_loop()
                            break

                    # 尝试解析 JSON 输出并更新断路器状态
                    output_file = project_dir / ".ralph" / "logs" / "claude_output.json"
                    if output_file.exists():
                        logger.debug(f"【响应解析】发现输出文件: {output_file}")
                        # 分析响应文件
                        analysis_result = analyze_response(output_file, self._loop_status.loop_number)
                        logger.debug(f"【响应解析】analyze_response 返回: {analysis_result}")
                        if analysis_result:
                            # 检查进度
                            if cb:
                                analysis_file = project_dir / ".ralph" / ".response_analysis"
                                if analysis_file.exists():
                                    try:
                                        with open(analysis_file, 'r', encoding='utf-8') as f:
                                            analysis = json.load(f)
                                        analysis_data = analysis.get("analysis", {})
                                        logger.debug(f"【响应解析】分析数据: {analysis_data}")

                                        if analysis_data.get("has_progress", False):
                                            logger.info("【响应解析】检测到进度，记录到断路器")
                                            cb.record_progress(self._loop_status.loop_number, project_dir)
                                        elif analysis_data.get("is_stuck", False):
                                            logger.warning("【响应解析】检测到卡循环，记录错误")
                                            cb.record_error("Stuck loop detected", project_dir)

                                        # 状态已立即持久化，不需要额外调用
                                        # cb.save(project_dir)
                                    except (json.JSONDecodeError, OSError) as e:
                                        logger.warning(f"【响应解析】读取分析文件失败: {e}")
                                        pass

                    # 尝试从当前行解析 JSON（用于流式输出）
                    if line.strip().startswith(('{', '[')):
                        logger.debug(f"【响应解析】检测到 JSON 行: {line[:200]}...")
                        try:
                            data = json.loads(line)
                            logger.debug("【响应解析】JSON 解析成功")

                            # 提取会话ID
                            session_id = (data.get('sessionId') or
                                         data.get('session_id') or
                                         data.get('metadata', {}).get('session_id'))
                            if session_id:
                                logger.info(f"【响应解析】从 JSON 中提取到 session_id: {session_id[:30]}...")
                                self._save_session_id(project_dir, str(session_id))
                                logger.info("【响应解析】session_id 已保存")
                            else:
                                logger.debug("【响应解析】JSON 中无 session_id")

                            # 检查是否有 RALPH_STATUS 块
                            if isinstance(data, dict) and 'result' in data:
                                result_text = data.get('result', '')
                                logger.debug(f"【响应解析】提取到 result 字段 ({len(result_text)} 字符)")
                                if '---RALPH_STATUS---' in result_text:
                                    logger.info("【响应解析】检测到 RALPH_STATUS 块")
                                    for status_line in result_text.split('\n'):
                                        if status_line.startswith('STATUS:'):
                                            status = status_line.split(':', 1)[1].strip()
                                            logger.info(f"【响应解析】状态: {status}")
                                            if status == 'COMPLETE':
                                                loop_ended_notified = True
                                                logger.info("【响应解析】循环标记为完成")
                                            break
                        except json.JSONDecodeError as e:
                            logger.debug(f"【响应解析】JSON 解析失败: {e}")
                            pass

                    # 回调进度
                    if progress_callback:
                        try:
                            logger.debug(f"Calling progress_callback with line: {line[:50] if line else '(empty)'}")
                            progress_callback({
                                "loop_number": self._loop_status.loop_number,
                                "line": line,
                                "buffer": self._output_buffer.copy(),
                                "circuit_breaker": cb.state.value if cb else None
                            })
                            logger.debug("progress_callback completed")
                        except Exception as e:
                            logger.error(f"progress_callback error: {e}")

        except Exception as e:
            logger.exception(f"Error reading loop output: {e}")
        finally:
            # 【进程生命周期日志】- 进程结束记录
            end_time = datetime.now()
            duration = (end_time - loop_start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info("【进程诊断】进程结束:")
            logger.info(f"  结束时间: {end_time.isoformat()}")
            logger.info(f"  运行时长: {duration:.2f} 秒 ({duration/60:.2f} 分钟)")
            logger.info(f"  输出行数: {lines_read}")
            logger.info(f"  输出字节: {bytes_read}")
            
            # 获取退出码
            if self.process:
                try:
                    # 非阻塞检查退出码
                    exit_code = self.process.poll()
                    if exit_code is not None:
                        logger.info(f"  退出码: {exit_code}")
                        if exit_code == 0:
                            logger.info("  退出状态: 正常结束")
                        elif exit_code < 0:
                            logger.warning(f"  退出状态: 被信号终止 ({exit_code})")
                        else:
                            logger.warning(f"  退出状态: 异常退出 ({exit_code})")
                    else:
                        logger.warning("  退出码: 无法获取 (进程仍在运行或已清理)")
                except Exception as e:
                    logger.warning(f"  退出码获取失败: {e}")
            
            # 检查是否超时
            if timeout_seconds > 0 and duration >= timeout_seconds:
                logger.warning(f"  结束原因: 超时 (限制 {timeout_seconds} 秒)")
            elif loop_ended_notified:
                logger.info("  结束原因: 正常完成")
            else:
                logger.info("  结束原因: 进程结束")
            
            logger.info("=" * 60)
            self._loop_status.is_running = False

    def _extract_session_from_output(self, project_dir: Path, lines: List[str]) -> None:
        """从输出行中提取会话ID"""
        logger.debug(f"【响应解析】从最后 {min(20, len(lines))} 行提取 session_id...")
        for line in lines[-20:]:  # 只检查最后20行
            if not line.strip().startswith('{'):
                continue
            try:
                data = json.loads(line)
                session_id = (data.get('sessionId') or 
                             data.get('session_id') or 
                             data.get('metadata', {}).get('session_id'))
                if session_id:
                    logger.info(f"【响应解析】从输出中提取到 session_id: {session_id[:30]}...")
                    self._save_session_id(project_dir, str(session_id))
                    logger.info("【响应解析】session_id 已保存到文件")
                    break
            except json.JSONDecodeError:
                continue
        else:
            logger.debug("【响应解析】在最后 20 行中未找到 session_id")

    def stop_loop(self, timeout: int = 10) -> bool:
        """停止Ralph循环"""
        logger.info("Stopping Ralph loop...")
        if not self.process:
            logger.debug("No process to stop")
            return True

        try:
            # 先检查是否是僵尸进程
            if self._is_zombie_process(self.process):
                logger.warning(f"Process {self.process.pid} is already a zombie, cleaning up...")
                self._cleanup_zombie_process(self.process)
                self.process = None
                self._loop_status.is_running = False
                return True

            logger.debug(f"Sending terminate signal to process (PID: {self.process.pid})")
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
                logger.debug("Process terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("Process did not terminate in time, killing...")
                self.process.kill()
                self.wait_for_process(timeout=5)
                logger.debug("Process killed")

            # 确保进程资源被释放
            self.wait_for_process(timeout=5)
            self.process = None
            self._loop_status.is_running = False
            logger.info("Ralph loop stopped successfully")
            return True
        except Exception as e:
            logger.exception(f"Error stopping loop: {e}")
            self._cleanup_current_process()
            self._loop_status.is_running = False
            return False

    def force_kill_process(self) -> bool:
        """强制杀死当前进程（不留痕迹）"""
        logger.warning("Force killing process...")
        if not self.process:
            logger.debug("No process to kill")
            return True

        try:
            pid = self.process.pid
            logger.warning(f"Force killing process PID: {pid}")

            # 首先尝试 kill 信号（最强制）
            try:
                import signal
                import os
                os.kill(pid, signal.SIGKILL)
                logger.info(f"Sent SIGKILL to process {pid}")
            except (ProcessLookupError, PermissionError) as e:
                logger.warning(f"Could not send SIGKILL: {e}")
                # 回退到 Windows API
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
                    if handle:
                        kernel32.TerminateProcess(handle, 1)
                        kernel32.CloseHandle(handle)
                        logger.info(f"Force killed process {pid} via Windows API")
                except Exception as api_error:
                    logger.error(f"Failed to kill via Windows API: {api_error}")

            # 确保资源释放
            self._cleanup_current_process()
            logger.info("Process force killed successfully")
            return True
        except Exception as e:
            logger.exception(f"Error force killing process: {e}")
            self._cleanup_current_process()
            return False

    def wait_for_process(self, timeout: int = 10) -> int:
        """
        等待进程退出并释放资源

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            退出码，-1 表示进程不存在或无法等待
        """
        if not self.process:
            return -1

        pid = self.process.pid
        try:
            # poll() 检查进程是否已退出
            exit_code = self.process.poll()
            if exit_code is not None:
                logger.debug(f"Process {pid} already exited with code {exit_code}")
                return exit_code

            # 进程仍在运行，调用 wait() 等待
            logger.debug(f"Waiting for process {pid} to exit...")
            exit_code = self.process.wait(timeout=timeout)
            logger.debug(f"Process {pid} exited with code {exit_code}")
            return exit_code

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout waiting for process {pid} to exit")
            return -1
        except Exception as e:
            logger.error(f"Error waiting for process {pid}: {e}")
            return -1

    def _is_zombie_process(self, proc: subprocess.Popen) -> bool:
        """
        检查进程是否是僵尸进程

        僵尸进程：进程已退出但父进程未调用 wait() 回收其资源
        """
        if not proc:
            return False

        # poll() 返回 None 表示进程仍在运行
        # 如果进程已退出（返回码不是 None），但对象仍然存在，说明可能是僵尸
        exit_code = proc.poll()
        if exit_code is None:
            return False  # 进程仍在运行，不是僵尸

        # 进程已退出但尚未被等待 - 僵尸状态
        logger.debug(f"Process {proc.pid} is in zombie state (exited with {exit_code}, not yet waited)")
        return True

    def _cleanup_zombie_process(self, proc: subprocess.Popen) -> None:
        """清理僵尸进程，回收其资源"""
        if not proc:
            return

        try:
            # 僵尸进程必须被 wait() 才能回收资源
            exit_code = proc.wait(timeout=5)
            logger.info(f"Cleaned up zombie process {proc.pid}, exit code: {exit_code}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout waiting for zombie process {proc.pid}")
        except Exception as e:
            logger.error(f"Error cleaning up zombie process {proc.pid}: {e}")

    def _cleanup_current_process(self) -> None:
        """清理当前进程，确保资源释放"""
        if self.process:
            try:
                # 检查僵尸状态
                if self._is_zombie_process(self.process):
                    self._cleanup_zombie_process(self.process)
                elif self.process.poll() is None:
                    # 进程还在运行，尝试终止
                    try:
                        self.process.terminate()
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=5)
                    except Exception:
                        pass
                else:
                    # 进程已退出但未等待
                    self.process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"Error during process cleanup: {e}")
            finally:
                self.process = None

    def is_loop_running(self) -> bool:
        """检查循环是否在运行"""
        if not self.process:
            return False
        running = self.process.poll() is None
        logger.debug(f"Loop running status: {running}")
        return running

    def reset_circuit(self, project_dir: Path) -> bool:
        """重置回路断路器状态"""
        logger.info(f"Resetting circuit breaker for {project_dir}")
        try:
            cb = CircuitBreakerModel.from_project(project_dir)
            cb.state = CircuitBreakerState.CLOSED
            cb.consecutive_no_progress = 0
            cb.consecutive_same_error = 0
            cb.consecutive_permission_denials = 0
            cb.last_change = datetime.now()
            cb.opened_at = None
            cb.reason = "Manual reset"
            result = cb.save(project_dir)
            if result:
                logger.info("Circuit breaker reset successfully")
            else:
                logger.error("Failed to save circuit breaker state")
            return result
        except Exception as e:
            logger.exception(f"Error resetting circuit breaker: {e}")
            return False

    def get_status(self, project_dir: Path) -> Dict[str, Any]:
        """获取Ralph状态"""
        logger.debug(f"Getting status for {project_dir}")
        status_file = self._get_status_file(project_dir)

        if status_file.exists():
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
                    logger.debug(f"Status loaded from file: {status_file}")
                    return status
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error reading status file: {e}")

        # 如果状态文件不存在，构建状态
        status = {
            "is_running": self.is_loop_running(),
            "loop_number": self._loop_status.loop_number,
            "calls_made": self._loop_status.calls_made,
            "total_calls": self._loop_status.total_calls,
            "start_time": self._loop_status.start_time.isoformat() if self._loop_status.start_time else None,
        }
        logger.debug(f"Status built from loop status: {status}")

        # 添加断路器状态
        try:
            cb = CircuitBreakerModel.from_project(project_dir)
            status["circuit_breaker"] = {
                "state": cb.state.value,
                "reason": cb.reason,
                "consecutive_no_progress": cb.consecutive_no_progress,
                "total_opens": cb.total_opens
            }
            logger.debug(f"Circuit breaker status added: {status['circuit_breaker']}")
        except Exception as e:
            logger.error(f"Error getting circuit breaker status: {e}")

        return status

    def run_enable_wizard(
        self,
        project_dir: Path,
        from_source: str = None,
        label: str = None,
        force: bool = False,
        non_interactive: bool = False,
    ) -> int:
        """
        运行启用向导

        使用 enable_core.enable_ralph_in_directory() 实现
        """
        import os
        # 保存当前工作目录
        original_cwd = os.getcwd()
        try:
            # 切换到项目目录
            os.chdir(str(project_dir))
            result = enable_ralph_in_directory(
                force=force,
                skip_tasks=non_interactive,
                project_name=label,
                project_type=from_source
            )
            return result
        finally:
            # 恢复原始工作目录
            os.chdir(original_cwd)

    def run_enable_ci(
        self,
        project_dir: Path,
        from_source: str = None,
        label: str = None,
        force: bool = False,
    ) -> int:
        """
        运行CI模式启用（非交互）

        使用 enable_core.enable_ralph_in_directory() 实现
        """
        return self.run_enable_wizard(
            project_dir=project_dir,
            from_source=from_source,
            label=label,
            force=force,
            non_interactive=True
        )

    def read_loop_output(self) -> Optional[str]:
        """读取循环输出（非阻塞）- 跨平台兼容版本
        
        注意：此方法为备用读取方式。主要的输出读取由 _read_loop_output 后台线程处理。
        """
        # 直接从缓冲区获取输出（由后台线程填充）
        if self._output_buffer:
            return self._output_buffer[-1]
        return None

    def get_buffered_output(self) -> List[str]:
        """获取缓冲的输出行"""
        return self._output_buffer.copy()

    def _trim_output_buffer(self) -> None:
        """内存管理：修剪过大的输出缓冲区"""
        if len(self._output_buffer) > self.MAX_OUTPUT_LINES:
            # 保留最后 MAX_OUTPUT_LINES 行
            excess = len(self._output_buffer) - self.MAX_OUTPUT_LINES
            self._output_buffer = self._output_buffer[excess:]
            logger.debug(f"Trimmed {excess} lines from output buffer, kept {self.MAX_OUTPUT_LINES} lines")

    def _truncate_large_json_in_buffer(self) -> None:
        """内存管理：截断缓冲区中过大的JSON响应"""
        for i, line in enumerate(self._output_buffer):
            if len(line) > self.MAX_JSON_LENGTH and line.strip().startswith(('{', '[')):
                # 截断过大的 JSON 行
                self._output_buffer[i] = line[:self.MAX_JSON_LENGTH] + "...[truncated]"
                logger.debug(f"Truncated JSON line {i} from {len(line)} to {self.MAX_JSON_LENGTH} chars")

    def clear_buffer(self) -> None:
        """清空输出缓冲区"""
        self._output_buffer.clear()

    def register_callback(self, event: str, callback: Callable) -> None:
        """注册事件回调"""
        self._callbacks[event] = callback

    def trigger_callback(self, event: str, data: Dict[str, Any]) -> None:
        """触发事件回调"""
        if event in self._callbacks:
            try:
                self._callbacks[event](data)
            except Exception:
                pass

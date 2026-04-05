"""
循环控制Presenter
"""
import threading
import time
from pathlib import Path
from typing import Optional, Callable
from ..services import StateService, CLIService, ConfigService, LogService
from ..services.cli_service import LoopOptions
from ..models.circuit_breaker import CircuitBreakerState
from ..lib.log_utils import get_service_logger, get_cli_logger

# 获取日志器
logger = get_service_logger()
cli_logger = get_cli_logger()


class LoopPresenter:
    """循环控制Presenter"""

    def __init__(
        self,
        state_service: StateService,
        cli_service: CLIService,
        config_service: ConfigService,
        log_service: LogService
    ):
        self.state_service = state_service
        self.cli_service = cli_service
        self.config_service = config_service
        self.log_service = log_service

        self._is_running = False
        self._is_paused = False
        self._stop_event = threading.Event()
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_count = 0
        self._calls_made = 0
        self._start_time: Optional[float] = None
        self._failures = 0

        # 回调
        self._on_status_change: Optional[Callable] = None
        self._on_log_line: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        logger.debug("LoopPresenter initialized")

    def set_callbacks(
        self,
        on_status_change: Callable = None,
        on_log_line: Callable = None,
        on_error: Callable = None
    ):
        """设置回调函数"""
        logger.debug(f"Setting callbacks: status_change={on_status_change is not None}, log_line={on_log_line is not None}, error={on_error is not None}")
        self._on_status_change = on_status_change
        self._on_log_line = on_log_line
        self._on_error = on_error

    def _handle_progress(self, progress_data: dict):
        """处理进度回调"""
        logger.debug(f"_handle_progress called: line='{progress_data.get('line', '')[:50]}...', loop_ended={progress_data.get('loop_ended')}")
        # 优先处理普通输出行 - 转发到 UI
        if self._on_log_line:
            line = progress_data.get("line", "")
            if line:
                self._on_log_line(line)

        # 处理断路器状态变化
        if progress_data.get("circuit_opened"):
            circuit_state = progress_data.get("circuit_breaker", "OPEN")
            error_msg = progress_data.get("error", "")
            logger.warning(f"Circuit breaker opened: {circuit_state}")
            # 更新状态
            loop_state = self.state_service.load_loop_state()
            loop_state.status = "stopped"
            self.state_service.save_loop_state(loop_state)
            # 通知UI
            if self._on_status_change:
                self._on_status_change(self.get_status())
            # 通知错误
            if self._on_error and error_msg:
                self._on_error(error_msg)
            # 停止循环
            self._stop_event.set()

        # 处理循环结束（单次调用完成）
        if progress_data.get("loop_ended"):
            end_reason = progress_data.get("end_reason", "unknown")
            error_msg = progress_data.get("error")
            call_num = progress_data.get("loop_number", self._calls_made)

            # 跟踪失败次数
            if error_msg:
                self._failures += 1
                self._log_status(f"调用 #{call_num} 失败 ({self._failures}次失败) - {error_msg}")
            else:
                self._log_status(f"调用 #{call_num} 完成 (累计{self._calls_made}次, 失败{self._failures}次)")

            logger.info(f"Single call ended: reason={end_reason}, failures={self._failures}")

            # 如果有错误，通知错误回调
            if self._on_error and error_msg:
                self._on_error(error_msg)

    def start(self) -> bool:
        """启动循环"""
        logger.info("Starting loop...")
        if self._is_running:
            logger.warning("Loop already running, ignoring start request")
            return False

        try:
            self._is_running = True
            self._is_paused = False
            self._stop_event.clear()
            self._loop_count = 0
            self._calls_made = 0
            self._failures = 0
            self._start_time = time.time()

            # 启动循环线程
            self._loop_thread = threading.Thread(
                target=self._run_loop,
                daemon=True
            )
            self._loop_thread.start()

            self._update_status("running")
            self._log_status(f"开始运行 (00:00:00)")
            logger.info("Loop started successfully")
            return True

        except Exception as e:
            logger.exception(f"Failed to start loop: {e}")
            self._is_running = False
            if self._on_error:
                self._on_error(str(e))
            return False

    def _run_loop(self):
        """主循环线程 - 实现 Ralph 循环逻辑"""
        logger.info("Main loop thread started")

        max_calls = self.config_service.get("MAX_CALLS_PER_HOUR", 100)
        timeout = self.config_service.get("CLAUDE_TIMEOUT_MINUTES", 15)
        loop_delay = self.config_service.get("LOOP_DELAY_SECONDS", 5)
        dangerously_skip_permissions = self.config_service.get("DANGEROUSLY_SKIP_PERMISSIONS", False)
        max_iterations_without_progress = self.config_service.get("MAX_ITERATIONS_WITHOUT_PROGRESS", 0)

        logger.debug(f"Loop config: max_calls={max_calls}, timeout={timeout}, delay={loop_delay}, skip_perms={dangerously_skip_permissions}, max_iter_no_progress={max_iterations_without_progress}")

        while not self._stop_event.is_set():
            self._loop_count += 1
            logger.info(f"=== Loop #{self._loop_count} ===")

            # 循环开始时立即更新状态到 UI
            self._update_status("running")
            if self._on_status_change:
                self._on_status_change(self.get_status())

            # 检查调用次数限制
            if self._calls_made >= max_calls:
                logger.info(f"Max calls reached: {self._calls_made}/{max_calls}")
                if self._on_error:
                    self._on_error(f"已达到最大调用次数限制: {self._calls_made}/{max_calls}")
                break

            # 检查断路器状态
            circuit = self.state_service.load_circuit_breaker()
            if circuit.is_open:
                logger.warning(f"Circuit breaker is open: {circuit.reason}")
                if self._on_error:
                    self._on_error(f"断路器已打开: {circuit.reason}")
                break

            # 检查最大无进度迭代次数限制
            if max_iterations_without_progress > 0 and circuit.consecutive_no_progress >= max_iterations_without_progress:
                logger.warning(f"Max iterations without progress reached: {circuit.consecutive_no_progress}/{max_iterations_without_progress}")
                if self._on_error:
                    self._on_error(f"已达到最大无进度迭代次数: {circuit.consecutive_no_progress}/{max_iterations_without_progress}")
                break

            try:
                # 执行单次调用
                options = LoopOptions(
                    max_calls=max_calls - self._calls_made,
                    timeout_minutes=timeout,
                    dangerously_skip_permissions=dangerously_skip_permissions,
                    no_continue=not self.config_service.get("SESSION_CONTINUITY", True),
                    append_previous_summary=self.config_service.get("APPEND_PREVIOUS_SUMMARY", True),
                )

                self._log_status(f"开始调用 #{self._calls_made + 1} (失败{self._failures}次)")
                cli_logger.info(f"Starting CLI call #{self._calls_made + 1}")
                process = self.cli_service.start_loop(
                    self.state_service.project_dir,
                    options,
                    self._handle_progress
                )
                
                # 等待进程完成
                if process:
                    process.wait()
                    logger.debug(f"Process completed with code: {process.returncode}")

                self._calls_made += 1

                # 更新状态（每次调用完成后）
                self._update_status("running")
                if self._on_status_change:
                    self._on_status_change(self.get_status())

            except Exception as e:
                logger.exception(f"Error in loop iteration: {e}")
                if self._on_error:
                    self._on_error(f"循环执行错误: {str(e)}")

            # 检查是否需要停止
            if self._stop_event.is_set():
                logger.info("Stop event detected, breaking loop")
                break

            # 循环间隔
            logger.debug(f"Waiting {loop_delay}s before next iteration...")
            for _ in range(loop_delay):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

        # 循环结束
        self._is_running = False
        self._update_status("stopped")
        if self._on_status_change:
            self._on_status_change(self.get_status())
        logger.info(f"Main loop thread ended. Total loops: {self._loop_count}, calls: {self._calls_made}")

    def stop(self, timeout: int = 30) -> bool:
        """停止循环

        Args:
            timeout: 等待线程结束的超时时间（秒）

        Returns:
            True if stopped successfully
        """
        logger.info("Stopping loop...")
        if not self._is_running:
            logger.debug("Loop not running, nothing to stop")
            return True

        try:
            self._stop_event.set()
            cli_logger.info("Stopping CLI loop")
            self.cli_service.stop_loop()
            self.log_service.stop()

            # 等待线程结束（带超时）
            if self._loop_thread and self._loop_thread.is_alive():
                logger.debug(f"Waiting for loop thread to finish (timeout={timeout}s)...")
                self._loop_thread.join(timeout=timeout)
                if self._loop_thread.is_alive():
                    logger.warning("Loop thread did not finish within timeout")
                else:
                    logger.debug("Loop thread finished")

            self._is_running = False
            logger.debug("Loop stopped, updating status")

            self._update_status("stopped")
            self._log_status(f"停止运行 ({self._get_elapsed_time()})")
            logger.info("Loop stopped successfully")
            return True

        except Exception as e:
            logger.exception(f"Error stopping loop: {e}")
            if self._on_error:
                self._on_error(str(e))
            return False

    def pause(self) -> bool:
        """暂停/继续循环"""
        action = "resuming" if self._is_paused else "pausing"
        logger.info(f"{action.capitalize()} loop")
        self._is_paused = not self._is_paused

        if self._is_paused:
            self._update_status("paused")
            self._log_status(f"暂停 ({self._get_elapsed_time()})")
            logger.info("Loop paused")
        else:
            self._update_status("running")
            self._log_status(f"恢复 ({self._get_elapsed_time()})")
            logger.info("Loop resumed")

        return True

    def reset_circuit(self) -> bool:
        """重置回路"""
        logger.info("Resetting circuit breaker...")
        success = self.cli_service.reset_circuit(self.state_service.project_dir)
        if success:
            circuit = self.state_service.load_circuit_breaker()
            circuit.state = CircuitBreakerState.CLOSED
            circuit.consecutive_no_progress = 0
            self.state_service.save_circuit_breaker(circuit)
            self._update_status(circuit.state.value)
            self._log_status(f"重置断路器 ({self._get_elapsed_time()})")
            logger.info("Circuit breaker reset successfully")
        else:
            logger.error("Failed to reset circuit breaker")
        return success

    def _update_status(self, status: str):
        """更新状态

        Args:
            status: 状态字符串 (running, stopped, paused)
        """
        logger.debug(f"Updating status to: {status}")
        loop_state = self.state_service.load_loop_state()
        loop_state.status = status
        loop_state.loop_count = self._loop_count
        loop_state.calls_made_this_hour = self._calls_made
        self.state_service.save_loop_state(loop_state)

        # 传递完整的 status dict 给回调
        if self._on_status_change:
            self._on_status_change(self.get_status())

    def get_status(self) -> dict:
        """获取当前状态"""
        loop_state = self.state_service.load_loop_state()
        circuit = self.state_service.load_circuit_breaker()

        status = {
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "status": loop_state.status,
            "loop_count": self._loop_count,
            "circuit_state": circuit.state.value,
            "calls_made": self._calls_made,
            "failures": self._failures,
            "max_calls": self.config_service.get("MAX_CALLS_PER_HOUR", 100),
        }
        logger.debug(f"Status retrieved: {status}")
        return status

    def _get_elapsed_time(self) -> str:
        """获取已运行时间格式化字符串"""
        if self._start_time is None:
            return "00:00:00"
        elapsed = int(time.time() - self._start_time)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _log_status(self, message: str):
        """发送状态日志到UI"""
        if self._on_log_line:
            self._on_log_line(message)

    @property
    def is_running(self) -> bool:
        return self._is_running

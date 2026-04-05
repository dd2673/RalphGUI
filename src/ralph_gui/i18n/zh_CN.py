"""
中文翻译模块
"""
from typing import Dict

TRANSLATIONS: Dict[str, str] = {
    # 应用标题
    "app_title": "Ralph - Claude Code 自动化开发助手",
    "app_title_with_project": "Ralph - {project_name}",

    # 菜单
    "menu_file": "文件",
    "menu_settings": "设置",
    "menu_help": "帮助",
    "open_project": "打开项目...",
    "exit": "退出",
    "settings_panel": "设置面板",
    "about": "关于",

    # 系统托盘菜单
    "show_window": "显示窗口",
    "start_loop": "开始循环",
    "stop_loop": "停止循环",
    "quit": "退出",

    # 系统通知
    "notification_loop_started": "循环已启动",
    "notification_loop_started_msg": "Ralph 开发循环已开始运行",
    "notification_loop_stopped": "循环已停止",
    "notification_loop_stopped_msg": "Ralph 开发循环已停止",
    "notification_error": "运行错误",
    "notification_circuit_open": "断路器已打开",
    "notification_circuit_open_msg": "循环因异常已停止",
    "minimized_to_tray": "已最小化到系统托盘",

    # 启动对话框
    "select_project_directory": "选择项目目录",
    "select_directory_instruction": "请选择一个已存在的项目目录，或创建新项目",
    "browse": "浏览...",
    "confirm": "确定",
    "cancel": "取消",
    "directory_not_found": "目录不存在",
    "directory_does_not_exist": "所选目录不存在，请重新选择",
    "not_git_repo_prompt": "所选目录不是 Git 仓库。是否要初始化为 Git 仓库并启用 Ralph？",
    "git_init_failed": "Git 初始化失败: {reason}",
    "recent_directories": "最近使用的目录",
    "clear_history": "清除历史",
    "clear_history_confirm": "确定要清除所有历史目录记录吗？",
    "no_recent_directories": "暂无历史目录",

    # 初始化对话框
    "init_ralph": "初始化 Ralph",
    "init_ralph_prompt": "是否要在当前目录初始化 Ralph 项目？",
    "init_ralph_description": "初始化将创建必要的配置文件，使该目录受 Ralph 管理。",
    "yes_initialize": "是",
    "no_thanks": "否",
    "initializing": "正在初始化...",
    "init_success": "初始化成功！",
    "init_failed": "初始化失败",
    "init_failed_reason": "初始化失败: {reason}",

    # 仪表盘
    "dashboard": "仪表盘",
    "circuit_breaker": "回路状态",
    "loop_count": "循环计数",
    "api_calls": "API 调用",
    "memory_usage": "内存使用",
    "tokens_used": "令牌使用",
    "this_hour": "本小时",
    "status": "状态",
    "running": "运行中",
    "stopped": "已停止",
    "paused": "已暂停",
    "waiting": "等待中",
    "last_action": "无",
    "next_reset": "下次重置",
    "unlimited": "无限制",

    # SpinBox 后缀
    "suffix_calls_per_hour": " 次/小时",
    "suffix_tokens_per_hour": " tokens/小时",
    "suffix_minutes": " 分钟",
    "suffix_hours": " 小时",

    # 回路状态
    "state_closed": "正常",
    "state_half_open": "监控中",
    "state_open": "已触发",
    "state_closed_desc": "回路正常工作",
    "state_half_open_desc": "正在检测恢复",
    "state_open_desc": "回路已触发，请检查",
    "state_open_reason": "已触发: {reason}",
    "state_unknown": "未知",
    "state_unknown_desc": "未知状态",

    # 控制按钮
    "start": "开始",
    "stop": "停止",
    "pause": "暂停",
    "resume": "继续",
    "reset_circuit": "重置回路",

    # 日志
    "logs": "日志输出",
    "claude_output": "Claude 输出",
    "log_error": "错误: {error}",
    "clear_logs": "清空",
    "check_project": "检查项目",
    "export_logs": "导出日志",
    "auto_scroll": "自动滚动",
    "no_logs_yet": "暂无日志输出",
    "no_claude_output_yet": "暂无 Claude 输出",
    "log_project_loaded": "项目已加载: {dir_path}",
    "log_loop_started": "循环已开始",
    "log_loop_stopped": "循环已停止",
    "log_loop_paused": "循环已暂停",
    "log_loop_resumed": "循环已继续",
    "log_circuit_reset": "回路已重置",
    "export_success": "导出成功",
    "export_failed": "导出失败",
    "log_export_success": "日志已导出到:\n{path}",
    "log_export_failed": "导出日志失败:\n{error}",

    # 设置
    "settings": "配置设置",
    "max_calls_per_hour": "每小时最大调用次数",
    "max_tokens_per_hour": "每小时最大令牌数",
    "timeout_minutes": "超时时间（分钟）",
    "session_continuity": "会话连续性",
    "session_expiry_hours": "会话过期时间（小时）",
    "append_previous_summary": "传递上一轮工作摘要",
    "cb_auto_reset": "自动重置回路",
    "dangerously_skip_permissions": "危险：跳过权限检查",
    "no_progress_threshold": "无进度阈值",
    "same_error_threshold": "相同错误阈值",
    "cooldown_minutes": "冷却时间（分钟）",
    "permission_denial_threshold": "权限拒绝阈值",
    "loop_delay_seconds": "循环间隔（秒）",
    "enabled": "启用",
    "disabled": "禁用",
    "save_settings": "保存设置",
    "settings_saved": "设置已保存",
    "settings_save_failed": "保存设置失败",
    "reset_to_defaults": "重置默认",
    "confirm_reset": "确认重置",
    "confirm_reset_message": "确定要重置所有设置为默认值吗？",
    "reset_success": "已重置为默认设置",
    "select_project_first": "请先选择项目目录",

    # 帮助
    "help": "帮助",
    "about_text": "Ralph for Claude Code v{version}\n\n一个自主AI开发循环系统。",

    # 错误消息
    "error": "错误",
    "error_project_not_found": "项目目录不存在",
    "error_ralph_not_enabled": "该项目未启用 Ralph",
    "error_loop_start_failed": "启动循环失败",
    "error_circuit_reset_failed": "重置回路失败",
    "error_unknown": "未知错误",
    "error_no_claude_cli": "未找到 Claude Code CLI\n\n请先安装 Claude Code: npm install -g @anthropic/claude-code",
    "error_git_not_found": "未找到 Git\n\n请先安装 Git",

    # 确认对话框
    "confirm_stop": "确认停止",
    "confirm_stop_message": "确定要停止当前循环吗？",
    "confirm_exit": "确认退出",
    "confirm_exit_message": "Ralph 正在运行中，确定要退出吗？",
    "yes": "是",
    "no": "否",

    # 状态栏
    "ready": "就绪",
    "elapsed_time": "运行时间",
    "executing": "执行中",
    "analyzing": "分析中",
    "waiting_for_rate_limit": "等待速率限制重置",
    "circuit_breaker_open": "回路已触发",
    "project_loaded": "项目已加载",
    "project_initialized": "项目已初始化",
    "project_not_initialized": "项目未初始化: {dir_path}",

    # 目录选择
    "no_project_selected": "未选择项目",
    "not_initialized": "未初始化",
    "initialized": "已初始化",
    "change_directory": "更改目录",

    # 断路器原因
    "cb_reason_manual_reset": "手动重置",
    "cb_reason_progress_detected": "检测到进度，回路已恢复",
    "cb_reason_no_progress": "连续 {count} 次循环无进度",
    "cb_reason_same_error": "相同错误重复 {count} 次",
    "cb_reason_same_output": "相同输出重复 {count} 次",
    "cb_reason_permission_denied": "权限被拒绝 {count} 次 - 请在 .ralphrc 中更新 ALLOWED_TOOLS",
    "cb_reason_monitoring": "监控中：{count} 次循环无进度",
    "cb_reason_cooldown_complete": "冷却完成，尝试恢复",
    "cb_reason_recovery_failed": "恢复失败，{count} 次循环后打开回路",
    "cb_reason_circuit_open": "回路已打开，执行已停止",
    "cb_reason_stuck_loop": "检测到卡循环",
    "cb_reason_unknown": "未知原因",
}

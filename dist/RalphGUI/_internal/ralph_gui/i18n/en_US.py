"""
English (US) translation module
"""
from typing import Dict

TRANSLATIONS: Dict[str, str] = {
    # App title
    "app_title": "Ralph - Claude Code Automation Assistant",
    "app_title_with_project": "Ralph - {project_name}",

    # Menu
    "menu_file": "File",
    "menu_settings": "Settings",
    "menu_help": "Help",
    "open_project": "Open Project...",
    "exit": "Exit",
    "settings_panel": "Settings Panel",
    "about": "About",

    # System tray menu
    "show_window": "Show Window",
    "start_loop": "Start Loop",
    "stop_loop": "Stop Loop",
    "quit": "Quit",

    # System notifications
    "notification_loop_started": "Loop Started",
    "notification_loop_started_msg": "Ralph development loop has started",
    "notification_loop_stopped": "Loop Stopped",
    "notification_loop_stopped_msg": "Ralph development loop has stopped",
    "notification_error": "Runtime Error",
    "notification_circuit_open": "Circuit Breaker Open",
    "notification_circuit_open_msg": "Loop stopped due to exception",
    "minimized_to_tray": "Minimized to system tray",

    # Startup dialog
    "select_project_directory": "Select Project Directory",
    "select_directory_instruction": "Please select an existing project directory or create a new one",
    "browse": "Browse...",
    "confirm": "OK",
    "cancel": "Cancel",
    "directory_not_found": "Directory not found",
    "directory_does_not_exist": "The selected directory does not exist. Please select again.",
    "not_git_repo_prompt": "The selected directory is not a Git repository. Would you like to initialize it as a Git repository and enable Ralph?",
    "git_init_failed": "Git initialization failed: {reason}",
    "recent_directories": "Recent Directories",
    "clear_history": "Clear History",
    "clear_history_confirm": "Are you sure you want to clear all recent directory records?",
    "no_recent_directories": "No recent directories",

    # Initialize dialog
    "init_ralph": "Initialize Ralph",
    "init_ralph_prompt": "Would you like to initialize a Ralph project in this directory?",
    "init_ralph_description": "Initialization will create necessary configuration files to enable Ralph management for this directory.",
    "yes_initialize": "Yes",
    "no_thanks": "No",
    "initializing": "Initializing...",
    "init_success": "Initialization successful!",
    "init_failed": "Initialization failed",
    "init_failed_reason": "Initialization failed: {reason}",

    # Dashboard
    "dashboard": "Dashboard",
    "circuit_breaker": "Circuit Breaker",
    "loop_count": "Loop Count",
    "api_calls": "API Calls",
    "memory_usage": "Memory Usage",
    "tokens_used": "Tokens Used",
    "this_hour": "This Hour",
    "status": "Status",
    "running": "Running",
    "stopped": "Stopped",
    "paused": "Paused",
    "waiting": "Waiting",
    "last_action": "Last Action",
    "next_reset": "Next Reset",
    "unlimited": "Unlimited",

    # SpinBox suffixes
    "suffix_calls_per_hour": " calls/hour",
    "suffix_tokens_per_hour": " tokens/hour",
    "suffix_minutes": " minutes",
    "suffix_hours": " hours",

    # Circuit breaker states
    "state_closed": "Normal",
    "state_half_open": "Monitoring",
    "state_open": "Triggered",
    "state_closed_desc": "Circuit breaker operating normally",
    "state_half_open_desc": "Monitoring for recovery",
    "state_open_desc": "Circuit breaker triggered, please check",
    "state_open_reason": "Triggered: {reason}",
    "state_unknown": "Unknown",
    "state_unknown_desc": "Unknown state",

    # Control buttons
    "start": "Start",
    "stop": "Stop",
    "pause": "Pause",
    "resume": "Resume",
    "reset_circuit": "Reset Circuit",

    # Logs
    "logs": "Log Output",
    "claude_output": "Claude Output",
    "log_error": "Error: {error}",
    "clear_logs": "Clear",
    "check_project": "Check Project",
    "export_logs": "Export Logs",
    "auto_scroll": "Auto Scroll",
    "no_logs_yet": "No log output yet",
    "no_claude_output_yet": "No Claude output yet",
    "log_project_loaded": "Project loaded: {dir_path}",
    "log_loop_started": "Loop started",
    "log_loop_stopped": "Loop stopped",
    "log_loop_paused": "Loop paused",
    "log_loop_resumed": "Loop resumed",
    "log_circuit_reset": "Circuit breaker reset",
    "export_success": "Export Success",
    "export_failed": "Export Failed",
    "log_export_success": "Logs exported to:\n{path}",
    "log_export_failed": "Failed to export logs:\n{error}",

    # Settings
    "settings": "Settings",
    "max_calls_per_hour": "Max Calls Per Hour",
    "max_tokens_per_hour": "Max Tokens Per Hour",
    "timeout_minutes": "Timeout (minutes)",
    "session_continuity": "Session Continuity",
    "session_expiry_hours": "Session Expiry (hours)",
    "append_previous_summary": "Append Previous Summary",
    "cb_auto_reset": "Auto Reset Circuit",
    "dangerously_skip_permissions": "Danger: Skip Permission Checks",
    "no_progress_threshold": "No Progress Threshold",
    "same_error_threshold": "Same Error Threshold",
    "cooldown_minutes": "Cooldown (minutes)",
    "permission_denial_threshold": "Permission Denial Threshold",
    "loop_delay_seconds": "Loop Delay (seconds)",
    "enabled": "Enabled",
    "disabled": "Disabled",
    "save_settings": "Save Settings",
    "settings_saved": "Settings saved",
    "settings_save_failed": "Failed to save settings",
    "reset_to_defaults": "Reset to Defaults",
    "confirm_reset": "Confirm Reset",
    "confirm_reset_message": "Are you sure you want to reset all settings to default values?",
    "reset_success": "Reset to default settings",
    "select_project_first": "Please select a project directory first",

    # Help
    "help": "Help",
    "about_text": "Ralph for Claude Code v{version}\n\nAn autonomous AI development loop system.",

    # Error messages
    "error": "Error",
    "error_project_not_found": "Project directory does not exist",
    "error_ralph_not_enabled": "Ralph is not enabled for this project",
    "error_loop_start_failed": "Failed to start loop",
    "error_circuit_reset_failed": "Failed to reset circuit breaker",
    "error_unknown": "Unknown error",
    "error_no_claude_cli": "Claude Code CLI not found\n\nPlease install Claude Code first: npm install -g @anthropic/claude-code",
    "error_git_not_found": "Git not found\n\nPlease install Git first",

    # Confirmation dialogs
    "confirm_stop": "Confirm Stop",
    "confirm_stop_message": "Are you sure you want to stop the current loop?",
    "confirm_exit": "Confirm Exit",
    "confirm_exit_message": "Ralph is running. Are you sure you want to exit?",
    "yes": "Yes",
    "no": "No",

    # Status bar
    "ready": "Ready",
    "elapsed_time": "Elapsed Time",
    "executing": "Executing",
    "analyzing": "Analyzing",
    "waiting_for_rate_limit": "Waiting for rate limit reset",
    "circuit_breaker_open": "Circuit breaker triggered",
    "project_loaded": "Project loaded",
    "project_initialized": "Project initialized",
    "project_not_initialized": "Project not initialized: {dir_path}",

    # Directory selection
    "no_project_selected": "No project selected",
    "not_initialized": "Not Initialized",
    "initialized": "Initialized",
    "change_directory": "Change Directory",

    # Circuit breaker reasons
    "cb_reason_manual_reset": "Manual reset",
    "cb_reason_progress_detected": "Progress detected, circuit recovered",
    "cb_reason_no_progress": "No progress detected in {count} consecutive loops",
    "cb_reason_same_error": "Same error repeated {count} times",
    "cb_reason_same_output": "Same output repeated {count} times",
    "cb_reason_permission_denied": "Permission denied {count} times - update ALLOWED_TOOLS in .ralphrc",
    "cb_reason_monitoring": "Monitoring: {count} loops without progress",
    "cb_reason_cooldown_complete": "Cooldown complete, attempting recovery",
    "cb_reason_recovery_failed": "Recovery failed, opening circuit after {count} loops",
    "cb_reason_circuit_open": "Circuit breaker is open, execution halted",
    "cb_reason_stuck_loop": "Stuck loop detected",
    "cb_reason_unknown": "Unknown reason",
}

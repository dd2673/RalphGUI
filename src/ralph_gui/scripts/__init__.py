"""
Ralph scripts - Python implementations of Ralph CLI commands
"""
from .ralph_stats import main as stats_main
from .ralph_monitor import main as monitor_main
from .ralph_import import main as import_main
from .ralph_install import main as install_main
from .ralph_uninstall import main as uninstall_main
from .ralph_setup import main as setup_main
from .ralph_migrate import main as migrate_main

__all__ = [
    "stats_main",
    "monitor_main",
    "import_main",
    "install_main",
    "uninstall_main",
    "setup_main",
    "migrate_main",
]

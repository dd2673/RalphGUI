#!/usr/bin/env python3
"""
Ralph GUI - Python 启动器
统一入口点，支持模块方式启动
"""
import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ralph_gui.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def main():
    """主入口函数"""
    try:
        logger.info("=" * 50)
        logger.info("Ralph GUI 启动中...")
        logger.info("=" * 50)

        # 检查 Python 版本
        if sys.version_info < (3, 8):
            logger.error(f"需要 Python 3.8+，当前版本: {sys.version}")
            sys.exit(1)

        logger.info(f"Python 版本: {sys.version}")

        # 确保 src 目录在 Python 路径中
        src_path = Path(__file__).parent / "src"
        if src_path.exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
            logger.info(f"添加路径到 sys.path: {src_path}")

        # 初始化 Ralph 日志系统
        from ralph_gui.lib.log_utils import init_logger
        log_dir = Path(__file__).parent / "logs"
        init_logger(log_dir, level="DEBUG")
        logger.info(f"Ralph 日志系统初始化完成. 日志目录: {log_dir}")

        # 导入并启动应用
        from ralph_gui.main import main as ralph_main
        logger.info("启动 Ralph GUI 应用...")
        ralph_main()

    except KeyboardInterrupt:
        logger.info("用户中断，应用退出")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"应用启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Ralph GUI - 主入口
"""
import sys
from pathlib import Path
from ralph_gui.app import RalphApp


def main():
    """主函数"""
    # 创建并运行应用 (RalphApp 内部处理 QApplication)
    ralph_app = RalphApp()
    ralph_app.run()


if __name__ == "__main__":
    main()

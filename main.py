"""Hash Trading Bot 入口."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.utils.config import load_config
from app.utils.logger import get_logger


def main() -> int:
    logger = get_logger()
    logger.info("启动 Hash Trading Bot")

    cfg = load_config()

    app = QApplication(sys.argv)
    app.setApplicationName("Hash Trading Bot")
    app.setQuitOnLastWindowClosed(True)

    win = MainWindow(cfg)
    win.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

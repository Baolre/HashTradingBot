"""桌面通知 + 声音."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .logger import get_logger

logger = get_logger(__name__)


class Notifier(QObject):
    """基于 QSystemTrayIcon 的简易通知器."""

    def __init__(self, parent: Optional[QObject] = None, icon: Optional[QIcon] = None):
        super().__init__(parent)
        self._tray: Optional[QSystemTrayIcon] = None
        if QApplication.instance() is not None and QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(icon or QIcon(), parent)
            self._tray.setToolTip("Hash Trading Bot")
            self._tray.show()

    def toast(self, title: str, message: str, duration_ms: int = 5000) -> None:
        logger.info("[TOAST] %s - %s", title, message)
        if self._tray is not None:
            try:
                self._tray.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)
                return
            except Exception as e:  # noqa: BLE001
                logger.warning("托盘通知失败: %s", e)

    def beep(self) -> None:
        try:
            app = QApplication.instance()
            if app is not None:
                app.beep()
        except Exception:  # noqa: BLE001
            pass

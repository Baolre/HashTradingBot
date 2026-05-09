"""桌面通知 + 声音 + Bark 手机推送."""
from __future__ import annotations

import threading
from typing import Optional

import httpx
from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .logger import get_logger

logger = get_logger(__name__)


class BarkPusher:
    """Bark iOS 推送（异步，不阻塞 UI 线程）."""

    def __init__(self, key: str = "", server: str = "https://api.day.app",
                 sound: str = "alarm", group: str = "hash_alert"):
        self.key = key
        self.server = server.rstrip("/")
        self.sound = sound
        self.group = group
        self._enabled = bool(key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def update(self, key: str = "", server: str = "", sound: str = "", group: str = ""):
        if key:
            self.key = key
            self._enabled = bool(key)
        if server:
            self.server = server.rstrip("/")
        if sound:
            self.sound = sound
        if group:
            self.group = group

    def push(self, title: str, body: str, url: str = "") -> None:
        """异步发送 Bark 推送（不阻塞主线程）."""
        if not self._enabled:
            return
        thread = threading.Thread(target=self._do_push, args=(title, body, url), daemon=True)
        thread.start()

    def _do_push(self, title: str, body: str, url: str) -> None:
        try:
            payload = {
                "title": title,
                "body": body,
                "group": self.group,
                "sound": self.sound,
                "level": "timeSensitive",
            }
            if url:
                payload["url"] = url

            api_url = f"{self.server}/{self.key}"
            with httpx.Client(timeout=10) as client:
                resp = client.post(api_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 200:
                        logger.info("[Bark] 推送成功: %s", title)
                    else:
                        logger.warning("[Bark] 推送返回异常: %s", data)
                else:
                    logger.warning("[Bark] HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("[Bark] 推送失败: %s", e)


class Notifier(QObject):
    """桌面通知 + 声音 + Bark 手机推送."""

    def __init__(self, parent: Optional[QObject] = None, icon: Optional[QIcon] = None,
                 bark_key: str = "", bark_server: str = "https://api.day.app",
                 bark_sound: str = "alarm", bark_group: str = "hash_alert"):
        super().__init__(parent)
        self._tray: Optional[QSystemTrayIcon] = None
        if QApplication.instance() is not None and QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(icon or QIcon(), parent)
            self._tray.setToolTip("Hash Trading Bot")
            self._tray.show()

        # Bark 推送器
        self.bark = BarkPusher(key=bark_key, server=bark_server,
                               sound=bark_sound, group=bark_group)

    def toast(self, title: str, message: str, duration_ms: int = 5000) -> None:
        logger.info("[TOAST] %s - %s", title, message)
        if self._tray is not None:
            try:
                self._tray.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)
            except Exception as e:
                logger.warning("托盘通知失败: %s", e)

    def beep(self) -> None:
        try:
            app = QApplication.instance()
            if app is not None:
                app.beep()
        except Exception:
            pass

    def push_to_phone(self, title: str, body: str, url: str = "") -> None:
        """推送到手机（Bark）."""
        self.bark.push(title, body, url)

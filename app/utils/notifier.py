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


class Notifier(QObject):
    """桌面托盘通知 + 声音 beep + Bark iOS 手机推送."""

    def __init__(self, parent: Optional[QObject] = None, icon: Optional[QIcon] = None):
        super().__init__(parent)
        self._tray: Optional[QSystemTrayIcon] = None
        if QApplication.instance() is not None and QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(icon or QIcon(), parent)
            self._tray.setToolTip("Hash Trading Bot")
            self._tray.show()

    # ---------- 桌面通知 ----------
    def toast(self, title: str, message: str, duration_ms: int = 5000) -> None:
        logger.info("[TOAST] %s - %s", title, message)
        if self._tray is not None:
            try:
                self._tray.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)
                return
            except Exception as e:  # noqa: BLE001
                logger.warning("托盘通知失败: %s", e)

    # ---------- 声音 ----------
    def beep(self) -> None:
        try:
            app = QApplication.instance()
            if app is not None:
                app.beep()
        except Exception:  # noqa: BLE001
            pass

    # ---------- 手机推送 (Bark) ----------
    def push_bark(
        self,
        title: str,
        body: str,
        key: str,
        server: str = "https://api.day.app",
        sound: str = "alarm",
        group: str = "hash_alert",
        url: str = "",
        timeout: float = 8.0,
    ) -> None:
        """向 Bark 发送 iOS 推送。

        参数:
            key: Bark 设备 key（必填），可在 Bark App 首页复制
            server: 自建时可替换；默认官方 https://api.day.app
            sound: 铃声名；alarm/bell/minuet/calypso 等
            group: 推送分组，方便在手机上折叠
            url: 点击推送时跳转的 URL（可选）
        """
        if not key:
            logger.info("未配置 Bark Key，跳过手机推送")
            return

        def _send():
            try:
                endpoint = f"{server.rstrip('/')}/{key}"
                payload = {
                    "title": title,
                    "body": body,
                    "sound": sound,
                    "group": group,
                }
                if url:
                    payload["url"] = url
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(endpoint, json=payload)
                    if resp.status_code >= 400:
                        logger.warning(
                            "Bark 推送失败 status=%s body=%s",
                            resp.status_code, resp.text[:200],
                        )
                    else:
                        logger.info("Bark 推送成功: %s", title)
            except Exception as e:  # noqa: BLE001
                logger.warning("Bark 推送异常: %s", e)

        # 放后台线程，避免阻塞 UI
        threading.Thread(target=_send, daemon=True).start()

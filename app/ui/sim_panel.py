"""模拟器面板 - 最小可用实现（保证不崩）."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..utils.config import SimConfig


class SimPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = SimConfig()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        tip = QLabel(
            "模拟交易功能开发中：将根据 AI 预测信号在历史数据上回测下注收益。\n"
            "当前保留控件框架以保证主程序稳定，完整实现待后续迭代。"
        )
        tip.setWordWrap(True)
        root.addWidget(tip)

        btns = QHBoxLayout()
        self.btn_start = QPushButton("开始模拟")
        self.btn_stop = QPushButton("停止模拟")
        self.btn_reset = QPushButton("重置")
        self.btn_stop.setEnabled(False)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_stop)
        btns.addWidget(self.btn_reset)
        btns.addStretch()
        root.addLayout(btns)

        self.lbl_balance = QLabel("余额: -")
        root.addWidget(self.lbl_balance)
        root.addStretch()

    def collect_config(self) -> SimConfig:
        """返回一份 SimConfig 副本（避免把 dict 传给 simulator 导致崩溃）."""
        return SimConfig(
            initial_balance=self._cfg.initial_balance,
            base_bet=self._cfg.base_bet,
            max_bet=self._cfg.max_bet,
            strategy=self._cfg.strategy,
            target=self._cfg.target,
        )

    def refresh(self, state) -> None:
        if isinstance(state, dict):
            bal = state.get("balance")
            if bal is not None:
                self.lbl_balance.setText(f"余额: {bal:.2f}")

    def update_curve(self, curve) -> None:
        # TODO: 画余额曲线
        pass

    def append_record(self, record) -> None:
        # TODO: 列表追加 record
        pass

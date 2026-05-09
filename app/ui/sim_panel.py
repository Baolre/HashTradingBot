"""UI 组件。"""
from PySide6.QtWidgets import QWidget, QPushButton

class SimPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.btn_start = QPushButton("开始模拟")
        self.btn_stop = QPushButton("停止模拟")
        self.btn_reset = QPushButton("重置")

    def collect_config(self):
        return {}

    def refresh(self, state):
        self.update()

    def update_curve(self, curve):
        self.update()

    def append_record(self, record):
        self.update()

"""UI 组件。"""
from PySide6.QtWidgets import QWidget

class DragonPanel(QWidget):
    def __init__(self):
        super().__init__()

    def refresh(self, dragons):
        self.update()

    @staticmethod
    def scan_dragons(analyzer, label, threshold):
        return []

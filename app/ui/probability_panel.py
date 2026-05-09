"""UI 组件。"""
from PySide6.QtWidgets import QWidget

class ProbabilityPanel(QWidget):
    def __init__(self):
        super().__init__()

    def refresh(self, analyzer, prediction):
        self.update()

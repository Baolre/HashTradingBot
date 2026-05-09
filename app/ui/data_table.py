"""UI 组件。"""
from PySide6.QtWidgets import QWidget

class DataTablePanel(QWidget):
    def __init__(self):
        super().__init__()

    def refresh(self, analyzer):
        self.update()

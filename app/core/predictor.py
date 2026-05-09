"""AI预测器存根。"""
from dataclasses import dataclass

@dataclass
class Predictor:
    def __init__(self, cfg):
        self.cfg = cfg

    def predict(self, analyzer):
        return None

    def update_config(self, cfg):
        self.cfg = cfg

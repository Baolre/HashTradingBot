"""模拟器。"""
from dataclasses import dataclass

@dataclass
class SimRecord:
    balance: float = 0
    bet: float = 0
    result: str = ''

class Simulator:
    def __init__(self, cfg, predictor):
        self.cfg = cfg
        self.predictor = predictor
        self.is_running = False
        self.state = {'balance': cfg.initial_balance}

    def update_config(self, cfg):
        self.cfg = cfg

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False

    def reset(self, cfg):
        self.state = {'balance': cfg.initial_balance}

    def on_new_period(self, period, analyzer):
        return None

    @property
    def balance_curve(self):
        return []

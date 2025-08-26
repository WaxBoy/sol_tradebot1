from dataclasses import dataclass

@dataclass
class Portfolio:
    base_balance: float  # SOL or USDC
    peak_equity: float

    def update_peak(self, equity: float):
        if equity > self.peak_equity:
            self.peak_equity = equity

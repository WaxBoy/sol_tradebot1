from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

@dataclass
class Position:
    token: str
    symbol: str
    entry_price: float
    size: float                 # tokens qty
    base_spent: float           # SOL/USDC spent for buy
    strategy: str
    entry_ts: datetime
    stop_loss: float
    ttl_sec: int
    trailing_pct: Optional[float] = None
    tp_layers: Optional[List[float]] = None   # as profit multipliers (e.g. [0.5,1.0])
    peak_price: Optional[float] = None
    status: str = "OPEN"
    notes: str = ""
    # NEW
    original_size: float = 0.0
    realized_pnl_amount: float = 0.0  # cumulative realized PnL from prior partial exits
    
    def update_peak(self, current_price: float):
        if self.peak_price is None or current_price > self.peak_price:
            self.peak_price = current_price

    def age_sec(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        return int((now - self.entry_ts).total_seconds())

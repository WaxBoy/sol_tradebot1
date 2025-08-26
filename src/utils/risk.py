from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import math

@dataclass
class RiskState:
    day_str: str
    start_equity: float
    current_equity: float
    peak_equity: float
    trades_today: int = 0
    halted: bool = False

class RiskManager:
    def __init__(self, cfg):
        self.cfg = cfg
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        start = cfg.risk.capital_base if cfg.mode == "paper" else cfg.risk.capital_base
        self.state = RiskState(day_str=day, start_equity=start, current_equity=start, peak_equity=start)

    def _refresh_day_if_needed(self):
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if day != self.state.day_str:
            self.state = RiskState(day_str=day, start_equity=self.state.current_equity,
                                   current_equity=self.state.current_equity, peak_equity=self.state.current_equity)

    def can_open_trade(self) -> bool:
        self._refresh_day_if_needed()
        if self.state.halted:
            return False
        if self.state.trades_today >= self.cfg.risk.max_trades_per_day:
            return False
        return True

    def register_trade_open(self):
        self.state.trades_today += 1

    def register_trade_close(self, pnl_amount: float):
        self.state.current_equity += pnl_amount
        if self.state.current_equity > self.state.peak_equity:
            self.state.peak_equity = self.state.current_equity

        # Check daily loss
        day_drawdown = (self.state.current_equity - self.state.start_equity) / max(1e-9, self.state.start_equity)
        if day_drawdown <= -self.cfg.risk.daily_loss_limit_pct:
            self.state.halted = True

        # Check session drawdown
        peak_dd = (self.state.current_equity - self.state.peak_equity) / max(1e-9, self.state.peak_equity)
        if peak_dd <= -self.cfg.risk.max_drawdown_pct:
            self.state.halted = True

    def position_size_from_risk(self, stop_loss_pct: float) -> float:
        # Risk amount = per_trade_risk_pct * current_equity
        risk_amount = self.cfg.risk.per_trade_risk_pct * self.state.current_equity
        if stop_loss_pct <= 0:
            return 0.0
        # Notional = risk_amount / stop_loss_pct
        return risk_amount / stop_loss_pct

    def halt(self):
        self.state.halted = True

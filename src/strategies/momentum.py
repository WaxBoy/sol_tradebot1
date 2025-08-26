from src.strategies import EntryPlan

class MomentumBreakoutStrategy:
    def __init__(self, cfg):
        self.cfg = cfg.strategies.momentum_breakout

    def check(self, facts, risk_mgr):
        if not self.cfg.enabled:
            return EntryPlan(False, reason="disabled")
        if facts.recent_change_pct < self.cfg.min_change_pct:
            return EntryPlan(False, reason="no_momentum")
        notional = risk_mgr.position_size_from_risk(self.cfg.stop_loss_pct)
        ttl = 1800
        return EntryPlan(True, base_to_spend=notional, stop_loss_pct=self.cfg.stop_loss_pct,
                         tp_layers=self.cfg.take_profit_layers,
                         trailing_pct=self.cfg.trailing_stop_pct, ttl_sec=ttl, reason="momentum_breakout")

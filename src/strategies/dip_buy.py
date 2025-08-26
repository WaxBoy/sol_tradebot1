from src.strategies import EntryPlan

class DipBuyStrategy:
    def __init__(self, cfg):
        self.cfg = cfg.strategies.dip_buy

    def check(self, facts, risk_mgr):
        if not self.cfg.enabled:
            return EntryPlan(False, reason="disabled")
        # We assume facts.recent_change_pct encodes recovery from dip (positive after a big negative)
        # For a simple proxy: require recent_change positive while a known dip (set upstream) is present.
        # Here we only check positivity as a proxy.
        if facts.recent_change_pct <= 0.0:
            return EntryPlan(False, reason="no_bounce")
        notional = risk_mgr.position_size_from_risk(self.cfg.stop_loss_pct)
        ttl = 3600
        return EntryPlan(True, base_to_spend=notional, stop_loss_pct=self.cfg.stop_loss_pct,
                         tp_layers=[self.cfg.take_profit_pct],
                         trailing_pct=self.cfg.trailing_stop_pct, ttl_sec=ttl, reason="dip_buy")

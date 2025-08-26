from datetime import datetime, timezone
from src.strategies import EntryPlan

class NewListingSnipeStrategy:
    def __init__(self, cfg):
        self.cfg = cfg.strategies.new_listing_snipe

    def check(self, facts, risk_mgr):
        if not self.cfg.enabled:
            return EntryPlan(False, reason="disabled")
        if facts.age_sec > self.cfg.max_age_sec:
            return EntryPlan(False, reason="too_old_for_snipe")
        # Allocate based on risk% and SL
        notional = risk_mgr.position_size_from_risk(self.cfg.stop_loss_pct)
        # TTL short for snipes
        ttl = 600
        return EntryPlan(True, base_to_spend=notional, stop_loss_pct=self.cfg.stop_loss_pct,
                         tp_layers=[self.cfg.take_profit_pct],
                         trailing_pct=self.cfg.trailing_stop_pct, ttl_sec=ttl, reason="new_listing")

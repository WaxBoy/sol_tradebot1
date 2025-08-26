class EntryPlan:
    def __init__(self, ok: bool, base_to_spend: float = 0.0, stop_loss_pct: float = 0.20,
                 tp_layers=None, trailing_pct=None, ttl_sec: int = 1800, reason: str = ""):
        self.ok = ok
        self.base_to_spend = base_to_spend
        self.stop_loss_pct = stop_loss_pct
        self.tp_layers = tp_layers or []
        self.trailing_pct = trailing_pct
        self.ttl_sec = ttl_sec
        self.reason = reason

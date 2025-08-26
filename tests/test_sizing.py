from types import SimpleNamespace
from src.utils.risk import RiskManager

class Cfg:
    mode = "paper"
    risk = SimpleNamespace(
        capital_base=100.0,
        per_trade_risk_pct=0.02,
        daily_loss_limit_pct=0.10,
        max_drawdown_pct=0.20,
        max_concurrent_trades=5,
        max_trades_per_day=50
    )

def test_position_size_from_risk():
    rm = RiskManager(Cfg())
    size = rm.position_size_from_risk(stop_loss_pct=0.20)  # 20% SL
    # risk_amount = 2% of 100 = 2; notional = 2/0.2=10
    assert abs(size - 10.0) < 1e-9

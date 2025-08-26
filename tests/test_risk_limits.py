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

def test_daily_loss_limit_halts():
    rm = RiskManager(Cfg())
    assert rm.can_open_trade()
    rm.register_trade_close(-11.0)  # lose 11 on 100 = -11%
    assert not rm.can_open_trade()

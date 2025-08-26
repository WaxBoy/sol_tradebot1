from datetime import datetime, timezone
from src.core.position import Position
from src.utils.exit import ExitEngine

class Cfg:
    pass

def backtest_single_trade(series):
    # Simulate entry at first price, TP at +50% (sell half), trail 20%
    pos = Position(
        token="tok",
        symbol="TOK",
        entry_price=series[0],
        size=100.0,
        base_spent=100.0,
        strategy="backtest",
        entry_ts=datetime.now(timezone.utc),
        stop_loss=series[0] * 0.8,
        ttl_sec=10_000,
        trailing_pct=0.2,
        tp_layers=[0.5]
    )
    engine = ExitEngine(Cfg())
    realized = 0.0
    size = pos.size
    for p in series[1:]:
        act = engine.check(pos, p)
        if act:
            if act.action == "TP":
                sold = size * 0.5
                realized += sold * p - (pos.base_spent * 0.5)
                size -= sold
                if act.tp_index is not None and pos.tp_layers:
                    pos.tp_layers[act.tp_index] = 9.99
                if act.new_stop_loss:
                    pos.stop_loss = act.new_stop_loss
            elif act.action in ("TRAIL", "SL", "TTL"):
                realized += size * p - (pos.base_spent * (size/pos.size))
                size = 0.0
                break
    return realized

def test_backtest_path_moon_then_trail():
    # Price path: 1.0 -> 1.6 (TP half) -> 1.9 (peak) -> 1.52 (20% off peak triggers trail) 
    series = [1.0, 1.6, 1.9, 1.52]
    pnl = backtest_single_trade(series)
    # First half: +0.3 * 50 = +15; Second half: entry 1.0, exit 1.52 => +0.52 * 50 = +26
    # total approx +41 (minor rounding differences)
    assert pnl > 35.0

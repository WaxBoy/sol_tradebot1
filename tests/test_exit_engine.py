from datetime import datetime, timezone
from src.utils.exit import ExitEngine
from src.core.position import Position
from types import SimpleNamespace

class Cfg:
    pass

def make_pos():
    return Position(
        token="tok",
        symbol="TOK",
        entry_price=1.0,
        size=100.0,
        base_spent=100.0,
        strategy="test",
        entry_ts=datetime.now(timezone.utc),
        stop_loss=0.8,
        ttl_sec=9999,
        trailing_pct=0.2,
        tp_layers=[0.5, 1.0]
    )

def test_tp_then_trail():
    engine = ExitEngine(Cfg())
    pos = make_pos()
    # Hit first TP @ 1.5
    act = engine.check(pos, 1.5)
    assert act and act.action == "TP"
    # After TP, price peaks to 1.8 then drops to 1.44 (20% off peak)
    pos.update_peak(1.8)
    act2 = engine.check(pos, 1.44)
    assert act2 and act2.action == "TRAIL"

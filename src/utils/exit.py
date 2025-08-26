from dataclasses import dataclass
from typing import List, Optional, Tuple
from src.core.position import Position

@dataclass
class ExitAction:
    action: str             # "TP", "SL", "TRAIL", "TTL"
    qty_to_sell: float      # tokens
    price: float            # price at decision
    new_stop_loss: Optional[float] = None
    tp_index: Optional[int] = None
    reason: str = ""

class ExitEngine:
    def __init__(self, cfg):
        self.cfg = cfg

    def check(self, pos: Position, current_price: float) -> Optional[ExitAction]:
        # Update trailing peak
        pos.update_peak(current_price)

        # Stop-loss
        if current_price <= pos.stop_loss:
            return ExitAction("SL", qty_to_sell=pos.size, price=current_price, reason="StopLoss")

        # Time-based TTL
        if pos.age_sec() >= pos.ttl_sec:
            return ExitAction("TTL", qty_to_sell=pos.size, price=current_price, reason="TTL")

        # TP layers
        if pos.tp_layers:
            # Each layer is profit pct (e.g., 0.5 => +50%)
            for i, tp_pct in enumerate(pos.tp_layers):
                tp_price = pos.entry_price * (1.0 + tp_pct)
                # If not yet taken (we encode by removing layer after taking)
                if current_price >= tp_price:
                    # sell 50% if multiple layers, or all if last layer
                    portion = 0.5 if i < len(pos.tp_layers) - 1 else 1.0
                    qty = pos.size * portion
                    # Move SL to breakeven after first TP
                    new_sl = max(pos.stop_loss, pos.entry_price) if i == 0 else pos.stop_loss
                    # Remove this layer by setting it to a huge value (or caller can mutate)
                    return ExitAction("TP", qty_to_sell=qty, price=current_price, new_stop_loss=new_sl, tp_index=i, reason=f"TP@{tp_pct:.0%}")

        # Trailing stop
        if pos.trailing_pct and pos.peak_price:
            trail = pos.peak_price * (1 - pos.trailing_pct)
            if current_price <= trail and current_price > pos.stop_loss:
                return ExitAction("TRAIL", qty_to_sell=pos.size, price=current_price, reason="TrailingStop")

        return None

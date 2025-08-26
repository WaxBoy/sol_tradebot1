import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import aiosqlite
import time

from src.utils.logging_utils import jlog
from src.utils.db import open_sqlite
from src.data.discovery import Discovery
from src.utils.scoring import TokenFacts, score_token
from src.core.trader import Trader
from src.utils.risk import RiskManager
from src.utils.exit import ExitEngine
from src.core.position import Position
from src.strategies.new_listing import NewListingSnipeStrategy
from src.strategies.momentum import MomentumBreakoutStrategy
from src.strategies.dip_buy import DipBuyStrategy


LAMPORTS_PER_SOL = 1_000_000_000  # for quotes if using SOL mint

class Bot:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger
        self.discovery = Discovery(cfg, logger)
        self.trader = Trader(cfg, logger)
        self.risk = RiskManager(cfg)
        self.exit_engine = ExitEngine(cfg)
        self.strategies = [
            NewListingSnipeStrategy(cfg),
            MomentumBreakoutStrategy(cfg),
            DipBuyStrategy(cfg),
        ]
        self._stop = asyncio.Event()

    async def _await_liquidity(self, address: str, timeout_sec: int = 300, interval_sec: float = 5.0):
        """
        Poll DexScreener until a Solana pair with USD liquidity appears or timeout.
        Returns (liquidity_usd, decimals, symbol, pairCreatedAt_ms) or (None, None, None, None) on timeout.
        """
        deadline = time.time() + timeout_sec
        while time.time() < deadline and not self._stop.is_set():
            liq, dec, sym, created_ms = await self._dexscreener_token_enrich(address)
            if liq and liq > 0.0:
                return liq, dec, sym, created_ms
            await asyncio.sleep(interval_sec)
        return None, None, None, None


    async def _dexscreener_token_enrich(self, address: str) -> Tuple[Optional[float], Optional[int], Optional[str], Optional[int]]:
        """
        Query DexScreener for this mint and return:
        (liquidity_usd, decimals, symbol, pairCreatedAt_ms)
        Only considers Solana pairs; picks the one with highest USD liquidity.
        """
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        try:
            r = await self.trader.client.get(url, timeout=10.0)
            if r.status_code != 200:
                return None, None, None, None
            data = r.json()
            pairs = data.get("pairs") or []
            best_liq = -1.0
            best = None
            for p in pairs:
                if (p.get("chainId") or "").lower() != "solana":
                    continue
                liq = float(((p.get("liquidity") or {}).get("usd")) or 0.0)
                if liq > best_liq:
                    best_liq = liq
                    best = p
            if not best or best_liq < 0:
                return None, None, None, None
            base = best.get("baseToken") or {}
            dec = base.get("decimals")
            sym = base.get("symbol")
            created_ms = best.get("pairCreatedAt")
            return best_liq, (int(dec) if dec is not None else None), sym, (int(created_ms) if created_ms else None)
        except Exception:
            return None, None, None, None


    async def graceful_shutdown(self):
        self._stop.set()
        await self.discovery.stop()
        await self.trader.close()

    async def run(self):
        jlog(self.logger, "START", mode=self.cfg.mode)
        async with open_sqlite(self.cfg) as db:
            await self._loop(db)

    async def _loop(self, db: aiosqlite.Connection):
        # Main event loop: discovery → score → strategies → trade → manage exits
        open_positions: Dict[str, Position] = {}

        async for event in self.discovery.stream():
            if self._stop.is_set():
                break

            # Normalize + enrich event (fake momentum & spread initially)
            addr = event.get("token") or event.get("address")
            if not addr:
                jlog(self.logger, "DISCOVERY_SKIP", reason="no_address", raw=event)
                continue

            symbol = event.get("symbol") or event.get("name") or "???"
            liquidity_usd = float(event.get("liquidity_usd") or 0.0)
            decimals = int(event.get("decimals") or 6)
            ts_val = event.get("ts") or event.get("seen_at") or time.time()

            # Enrich from DexScreener if liquidity is unknown/zero
            # Wait for a pool to exist before scoring (prevents 0.0 liquidity spam)
            if liquidity_usd <= 0.0:
                liq, dec, sym, created_ms = await self._await_liquidity(addr, timeout_sec=300, interval_sec=5.0)
                if not liq or liq <= 0.0:
                    jlog(self.logger, "DISCOVERY_SKIP", reason="no_liquidity_after_wait", token=addr)
                    continue  # skip scoring until a pool appears
                liquidity_usd = liq
                if dec is not None:
                    decimals = dec
                if sym and (symbol == "???" or not symbol):
                    symbol = sym
                if created_ms:
                    ts_val = (created_ms / 1000.0)


            age_sec = int(datetime.now(timezone.utc).timestamp() - float(ts_val))

            facts = TokenFacts(
                token=addr,
                symbol=symbol,
                liquidity_usd=liquidity_usd,
                price=1e-6,                 # placeholder until quoted
                total_supply=None,          # could fetch later
                decimals=decimals,
                age_sec=age_sec,
                spread_pct=2.0,
                recent_change_pct=0.25,     # simulate +25% last 5m for demo
            )



            # Score gate
            sr = score_token(facts, self.cfg)
            jlog(self.logger, "SCORE", token=facts.token, symbol=facts.symbol, score=sr.score, approved=sr.approved, reason=sr.reason)
            if not sr.approved:
                continue

            # Strategy check (first match wins)
            entry_plan = None
            for strat in self.strategies:
                plan = strat.check(facts, self.risk)
                if plan.ok:
                    entry_plan = plan
                    break
            if not entry_plan:
                continue

            # Risk checks
            if not self.risk.can_open_trade():
                jlog(self.logger, "RISK_DENY", reason="cannot_open_trade")
                continue

            # Quote buy (paper): assume buying with SOL base; convert base_to_spend SOL → token qty
            # Use a pseudo price from liquidity (very rough) to make paper deterministic:
            est_price = max(1e-9, min(0.001, 100.0 / max(1.0, facts.liquidity_usd)))  # higher liq => lower price heuristic
            qty = await self.trader.execute_buy(self.cfg.mode, est_price, entry_plan.base_to_spend, facts.decimals)
            if qty <= 0:
                jlog(self.logger, "BUY_FAIL", token=facts.token, reason="qty<=0")
                continue

            # Record position
            pos = Position(
                token=facts.token,
                symbol=facts.symbol,
                entry_price=est_price,
                size=qty,
                base_spent=entry_plan.base_to_spend,
                strategy=entry_plan.reason,
                entry_ts=datetime.now(timezone.utc),
                stop_loss=est_price * (1 - entry_plan.stop_loss_pct),
                ttl_sec=entry_plan.ttl_sec,
                trailing_pct=entry_plan.trailing_stop_pct,
                tp_layers=entry_plan.tp_layers.copy(),
                peak_price=est_price,
                # NEW:
                original_size=qty,
                realized_pnl_amount=0.0,
            )

            open_positions[facts.token] = pos
            self.risk.register_trade_open()
            jlog(self.logger, "BUY", token=pos.token, symbol=pos.symbol, price=pos.entry_price, size=pos.size, strategy=pos.strategy)

            # Manage exits opportunistically (demo: one check after brief delay)
            await asyncio.sleep(1.0)
            # Simulate a small price path: +60%, then pullback 20% from peak
            price_now = pos.entry_price * 1.6
            act = self.exit_engine.check(pos, price_now)
            if act and act.action == "TP":
                # Partial sell, adjust pos
                proceeds = await self.trader.execute_sell(self.cfg.mode, price_now, act.qty_to_sell)
                pnl_amount = proceeds - (pos.base_spent * (act.qty_to_sell / pos.size))
                self.risk.register_trade_close(pnl_amount)
                pos.size -= act.qty_to_sell
                if act.new_stop_loss:
                    pos.stop_loss = act.new_stop_loss
                # mark layer consumed
                if act.tp_index is not None and pos.tp_layers and 0 <= act.tp_index < len(pos.tp_layers):
                    pos.tp_layers[act.tp_index] = 9.99   # sentinel high so it won't trigger again
                jlog(self.logger, "TAKE_PROFIT", token=pos.token, price=price_now, qty=act.qty_to_sell, pnl_amount=pnl_amount)

            # Trailing stop after pullback
            price_now = pos.entry_price * 1.28
            act2 = self.exit_engine.check(pos, price_now)
            if act2 and act2.action in ("TRAIL", "SL", "TTL") or pos.size <= 1e-12:
                proceeds = await self.trader.execute_sell(self.cfg.mode, price_now, pos.size)
                pnl_amount = proceeds - (pos.base_spent * (pos.size / (pos.size + (act.qty_to_sell if act and act.action == "TP" else 0))))
                self.risk.register_trade_close(pnl_amount)
                jlog(self.logger, "SELL", token=pos.token, price=price_now, qty=pos.size, reason=act2.reason if act2 else "manual")
                # Write trade row
                await self._write_trade(db, pos, exit_price=price_now, pnl_amount=pnl_amount, reason=act2.reason if act2 else "Exit")
                del open_positions[pos.token]

            # In a full bot, you'd keep a background loop polling prices and checking exits periodically.

    async def _write_trade(self, db, pos: Position, exit_price: float, pnl_amount: float, reason: str):
        pnl_pct = (exit_price - pos.entry_price) / max(1e-9, pos.entry_price)
        await db.execute(
            "INSERT INTO trades(token, symbol, strategy, entry_ts, exit_ts, entry_price, exit_price, size, pnl_amount, pnl_pct, reason) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (pos.token, pos.symbol, pos.strategy, pos.entry_ts.isoformat(), datetime.now(timezone.utc).isoformat(),
             pos.entry_price, exit_price, pos.size, pnl_amount, pnl_pct, reason)
        )
        await db.commit()

import time
import httpx
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class QuoteResult:
    ok: bool
    price: float
    out_amount: float
    price_impact_pct: float
    route_info: Dict[str, Any]

class Trader:
    def __init__(self, cfg, logger: logging.Logger):
        self.cfg = cfg
        self.logger = logger
        self.client = httpx.AsyncClient(timeout=10.0, headers={"Accept": "application/json"})

    async def quote_jupiter(self, in_mint: str, out_mint: str, amount: int, slippage_bps: int = 100) -> QuoteResult:
        # Quote API: /v6/quote or /swap/v1/quote depending on Jupiter version. We'll use v6 here.
        url = f"{self.cfg.execution.jupiter.base_url}/v6/quote"
        params = {
            "inputMint": in_mint,
            "outputMint": out_mint,
            "amount": str(amount),    # in minor units (lamports or token decimals)
            "slippageBps": str(slippage_bps),
            "onlyDirectRoutes": "false"
        }
        try:
            r = await self.client.get(url, params=params)
            if r.status_code != 200:
                return QuoteResult(False, 0.0, 0.0, 0.0, {"status": r.status_code, "body": r.text})
            data = r.json()
            route = data["data"][0]
            price = float(route["outAmount"]) / float(amount) if amount else 0.0
            price_impact = float(route.get("priceImpactPct", 0)) * 100.0
            return QuoteResult(True, price, float(route["outAmount"]), price_impact, route)
        except Exception as e:
            return QuoteResult(False, 0.0, 0.0, 0.0, {"error": str(e)})

    async def simulate_buy(self, price: float, base_amount: float, decimals_out: int) -> float:
        # returns output token amount (qty)
        # price = out/base; qty = base_amount * (1/price)
        if price <= 0:
            return 0.0
        qty = base_amount / price
        return qty

    async def simulate_sell(self, price: float, qty: float) -> float:
        return price * qty

    async def execute_buy(self, mode: str, price: float, base_amount: float, decimals_out: int) -> float:
        if mode == "paper":
            return await self.simulate_buy(price, base_amount, decimals_out)
        # For "live": construct and submit Jupiter swap transaction (omitted in this sample).
        # We keep live path guarded and log a clear error if not configured.
        raise RuntimeError("Live execution not configured in this sample. Set RPC and wallet first.")

    async def execute_sell(self, mode: str, price: float, qty: float) -> float:
        if mode == "paper":
            return await self.simulate_sell(price, qty)
        raise RuntimeError("Live execution not configured in this sample. Set RPC and wallet first.")

    async def close(self):
        await self.client.aclose()

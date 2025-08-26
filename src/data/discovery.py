# src/data/discovery.py
import asyncio
import json
import time
from typing import AsyncIterator, Dict, Optional

import aiohttp


class Discovery:
    """
    Token discovery engine.
    - Uses PumpPortal (free) websocket for real-time Pump.fun new tokens
    - (Optional) DexScreener polling can remain disabled when Birdeye is off
    """

    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger
        # read config defensively to avoid crashes if keys are missing
        self._pp_enabled = getattr(getattr(self.cfg.discovery, "pump_fun", object()), "enabled", True)
        self._pp_ws_url = (
            getattr(getattr(self.cfg.discovery, "pump_fun", object()), "websocket_url", None)
            or "wss://pumpportal.fun/api/data"
        )
        self._dex_enabled = getattr(getattr(self.cfg.discovery, "dexscreener", object()), "enabled", False)
        self._stop = asyncio.Event()

    async def stop(self):
        self._stop.set()

    async def stream(self) -> AsyncIterator[Dict]:
        """
        Yields discovered token dicts:
        {
          "source": "pumpportal",
          "address": "<mint>",   # SPL mint address
          "symbol": "<symbol>" or None,
          "name": "<name>" or None,
          "seen_at": <unix_ts_float>
        }
        """
        tasks = []
        queue: asyncio.Queue = asyncio.Queue()

        if self._pp_enabled:
            tasks.append(asyncio.create_task(self._pumpportal_stream(queue)))
        else:
            self.logger.warning("PumpPortal discovery disabled by config.")

        if self._dex_enabled:
            tasks.append(asyncio.create_task(self._dexscreener_poll(queue)))
        else:
            self.logger.info("DexScreener polling disabled by config.")

        if not tasks:
            self.logger.error("No discovery sources enabled; nothing to stream.")
            return

        try:
            while not self._stop.is_set():
                evt = await queue.get()
                if evt is None:
                    break
                yield evt
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    # ---------- PumpPortal (Pump.fun) ----------
    async def _pumpportal_stream(self, q: asyncio.Queue):
        """
        Connects to PumpPortal WS and subscribes to new token events.
        Docs: https://pumpportal.fun/data-api/real-time (subscribeNewToken)
        """
        backoff = 1
        max_backoff = 60
        while not self._stop.is_set():
            try:
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=None)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.ws_connect(self._pp_ws_url, heartbeat=20) as ws:
                        # subscribe to new token creation events
                        await ws.send_json({"method": "subscribeNewToken"})
                        self.logger.info("PumpPortal connected & subscribed to new tokens.")
                        backoff = 1  # reset backoff on success

                        async for msg in ws:
                            if self._stop.is_set():
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                except json.JSONDecodeError:
                                    continue

                                evt = self._to_event(data)
                                if evt:
                                    await q.put(evt)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"PumpPortal WS error: {e}")
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)

    def _to_event(self, data: Dict) -> Optional[Dict]:
        """
        Normalize PumpPortal event payload -> internal discovery event.
        PumpPortal commonly includes fields like: mint, symbol, name, created_timestamp, etc.
        We defensively pick what we need.
        """
        mint = data.get("mint") or data.get("tokenMint") or data.get("address")
        if not mint:
            return None
        name = data.get("name") or data.get("tokenName")
        symbol = data.get("symbol") or data.get("tokenSymbol")
        ts = float(data.get("created_timestamp") or data.get("timestamp") or time.time())

        return {
            "source": "pumpportal",
            "address": mint,
            "symbol": symbol,
            "name": name,
            "seen_at": ts,
        }

    # ---------- DexScreener (optional; keep disabled) ----------
    async def _dexscreener_poll(self, q: asyncio.Queue):
        """
        Optional backup polling using DexScreener search.
        NOTE: DexScreener has no public 'new pairs' endpoint; do not rely on this for discovery.
        This remains OFF by default.
        """
        import aiohttp

        poll_interval = getattr(getattr(self.cfg.discovery, "dexscreener", object()), "poll_interval", 45)
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        seen: set = set()

        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            txt = await resp.text()
                            self.logger.error(f"DexScreener non-200: {resp.status} {txt[:200]}")
                        else:
                            payload = await resp.json()
                            for pair in payload.get("pairs", []):
                                addr = (pair.get("baseToken") or {}).get("address")
                                if not addr or addr in seen:
                                    continue
                                seen.add(addr)
                                await q.put({
                                    "source": "dexscreener",
                                    "address": addr,
                                    "symbol": (pair.get("baseToken") or {}).get("symbol"),
                                    "name": (pair.get("baseToken") or {}).get("name"),
                                    "seen_at": time.time(),
                                })
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"DexScreener poll error: {e}")

                await asyncio.sleep(poll_interval)

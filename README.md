# Solana Memecoin Autopilot (Paper + Live)

A production-style trading bot that **discovers**, **scores**, **trades**, and **manages risk** for Solana memecoins. Ships with:
- Paper mode (default) — deterministic quotes for safe testing
- Modular strategies (New Listing Snipe, Momentum Breakout, Dip-Buy)
- Risk manager (per-trade risk, daily loss limit, max drawdown, concurrency caps)
- Exit engine (SL, layered TP, trailing stop, TTL)
- SQLite persistence + JSONL logs + CSV trade ledger
- Unit tests + backtest example

> **Note:** Live mode requires Jupiter/RPC configuration and wallet setup. Start in paper mode.

---

## 1) Quick Start (Windows 11, Python 3.11)

```powershell
cd sol-tradebot
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

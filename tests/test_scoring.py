from types import SimpleNamespace
from src.utils.scoring import TokenFacts, score_token

class Cfg:
    scoring = SimpleNamespace(
        min_liquidity=5000.0,
        max_fdv=10_000_000.0,
        max_fdv_liq_ratio=500.0,
        honeypot_test_amount_sol=0.05,
        max_spread_pct=5.0,
        momentum_window_sec=300,
        momentum_min_change=0.20
    )

def test_high_liquidity_tight_spread_passes():
    facts = TokenFacts(
        token="tok",
        symbol="TOK",
        liquidity_usd=12000.0,
        price=0.0001,
        total_supply=1_000_000_000,  # FDV = 100k
        decimals=6,
        age_sec=600,
        spread_pct=1.0,
        recent_change_pct=0.30
    )
    sr = score_token(facts, Cfg())
    assert sr.approved, sr.reason
    assert sr.score >= 45.0

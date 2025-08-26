from dataclasses import dataclass
from typing import Optional

@dataclass
class TokenFacts:
    token: str
    symbol: str
    liquidity_usd: float
    price: float
    total_supply: Optional[float]  # in tokens
    decimals: int
    age_sec: int
    spread_pct: float
    recent_change_pct: float  # over momentum window

@dataclass
class ScoreResult:
    approved: bool
    score: float
    reason: str

def compute_fdv(price: float, total_supply: Optional[float]) -> Optional[float]:
    if total_supply is None:
        return None
    return price * total_supply

def score_token(facts: TokenFacts, cfg) -> ScoreResult:
    # Hard fails
    if facts.liquidity_usd < cfg.scoring.min_liquidity:
        return ScoreResult(False, 0.0, f"low_liquidity({facts.liquidity_usd}<{cfg.scoring.min_liquidity})")
    if facts.spread_pct > cfg.scoring.max_spread_pct:
        return ScoreResult(False, 0.0, f"wide_spread({facts.spread_pct}>{cfg.scoring.max_spread_pct})")

    fdv = compute_fdv(facts.price, facts.total_supply)
    if fdv is not None:
        if fdv > cfg.scoring.max_fdv:
            return ScoreResult(False, 0.0, f"fdv_high({fdv}>{cfg.scoring.max_fdv})")
        if facts.liquidity_usd > 0 and fdv / facts.liquidity_usd > cfg.scoring.max_fdv_liq_ratio:
            return ScoreResult(False, 0.0, f"fdv_liq_ratio_high({fdv/facts.liquidity_usd:.1f}>{cfg.scoring.max_fdv_liq_ratio})")

    # Weighted score (simple)
    score = 0.0
    # Liquidity: cap at 20k = full 30 points
    liq_score = min(facts.liquidity_usd / 20000.0, 1.0) * 30
    score += liq_score
    # Spread tighter better: 0% = 20, 5% = 0
    spr_score = max(0.0, (cfg.scoring.max_spread_pct - facts.spread_pct) / cfg.scoring.max_spread_pct) * 20
    score += spr_score
    # Momentum (if positive) adds up to 20 points at +50%
    mom_score = max(0.0, min(facts.recent_change_pct / 0.5, 1.0)) * 20
    score += mom_score
    # Age slight bonus if > 5 minutes (survived initial chaos): up to 10
    age_score = min(facts.age_sec / 300.0, 1.0) * 10
    score += age_score
    # FDV reasonability bonus up to 20 (if provided)
    if fdv is not None and facts.liquidity_usd > 0:
        ratio = fdv / facts.liquidity_usd
        # best @ ~100x (arbitrary), worse as goes to 0 or very high
        if ratio <= 0:
            fdv_score = 0.0
        else:
            fdv_score = max(0.0, 1.0 - abs(ratio - 100.0)/400.0) * 20
        score += fdv_score

    approved = score >= 45.0
    return ScoreResult(approved, score, "ok" if approved else "score_below_threshold")

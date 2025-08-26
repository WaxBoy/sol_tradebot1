from dataclasses import dataclass, field
from typing import List, Optional
import yaml

@dataclass
class DiscoveryBirdeye:
    enabled: bool = True
    api_key: str = ""
    min_liquidity: float = 5000.0
    meme_platforms: bool = True
    url: str = "wss://public-api.birdeye.so/socket"

@dataclass
class DiscoveryDexscreener:
    enabled: bool = True
    poll_interval: int = 30
    new_pairs_url: str = "https://api.dexscreener.com/latest/dex/search?q=solana"
    max_pair_age_sec: int = 180

@dataclass
class DiscoveryJupiter:
    token_list_check: bool = True

@dataclass
class Discovery:
    birdeye: DiscoveryBirdeye = field(default_factory=DiscoveryBirdeye)
    dexscreener: DiscoveryDexscreener = field(default_factory=DiscoveryDexscreener)
    jupiter: DiscoveryJupiter = field(default_factory=DiscoveryJupiter)

@dataclass
class Scoring:
    min_liquidity: float = 5000.0
    max_fdv: float = 10_000_000.0
    max_fdv_liq_ratio: float = 500.0
    honeypot_test_amount_sol: float = 0.05
    max_spread_pct: float = 5.0
    momentum_window_sec: int = 300
    momentum_min_change: float = 0.20

@dataclass
class StrategyNewListing:
    enabled: bool = True
    max_age_sec: int = 120
    slippage: float = 0.01
    stop_loss_pct: float = 0.20
    take_profit_pct: float = 0.50
    trailing_stop_pct: float = 0.20

@dataclass
class StrategyMomentum:
    enabled: bool = True
    min_change_pct: float = 0.30
    stop_loss_pct: float = 0.15
    take_profit_layers: List[float] = field(default_factory=lambda: [0.50, 1.0])
    trailing_stop_pct: float = 0.20

@dataclass
class StrategyDipBuy:
    enabled: bool = True
    dip_pct: float = 0.25
    bounce_pct: float = 0.05
    stop_loss_pct: float = 0.15
    take_profit_pct: float = 0.40
    trailing_stop_pct: float = 0.25

@dataclass
class Strategies:
    new_listing_snipe: StrategyNewListing = field(default_factory=StrategyNewListing)
    momentum_breakout: StrategyMomentum = field(default_factory=StrategyMomentum)
    dip_buy: StrategyDipBuy = field(default_factory=StrategyDipBuy)

@dataclass
class Risk:
    capital_base: float = 100.0
    per_trade_risk_pct: float = 0.02
    daily_loss_limit_pct: float = 0.10
    max_drawdown_pct: float = 0.20
    max_concurrent_trades: int = 5
    max_trades_per_day: int = 50

@dataclass
class ExecJupiter:
    base_url: str = "https://api.jup.ag"
    api_key: str = ""

@dataclass
class ExecRaydium:
    use_fallback: bool = True
    rpc_endpoint: str = ""

@dataclass
class Execution:
    slippage_tolerance: float = 0.005
    jupiter: ExecJupiter = field(default_factory=ExecJupiter)
    raydium: ExecRaydium = field(default_factory=ExecRaydium)
    base_mint: str = "So11111111111111111111111111111111111111112"
    quote_mint: str = "EPjFWdd5AufqSSqe..."  # USDC mint placeholder

@dataclass
class LoggingAlerts:
    trade_open: bool = True
    trade_close: bool = True
    risk_events: bool = True

@dataclass
class LoggingConfig:
    level: str = "INFO"
    json: bool = True
    log_file: str = "logs/tradebot.jsonl"
    trades_csv: str = "logs/trades.csv"
    discord_webhook: str = ""
    alerts: LoggingAlerts = field(default_factory=LoggingAlerts)

@dataclass
class Database:
    path: str = "tradebot.db"

@dataclass
class Config:
    mode: str = "paper"
    dry_run: bool = False
    paper_start_balance: float = 100.0
    base_asset: str = "SOL"
    discovery: Discovery = field(default_factory=Discovery)
    scoring: Scoring = field(default_factory=Scoring)
    strategies: Strategies = field(default_factory=Strategies)
    risk: Risk = field(default_factory=Risk)
    execution: Execution = field(default_factory=Execution)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    database: Database = field(default_factory=Database)

def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    def merge(dc, cls):
        obj = cls()
        for k, v in dc.items():
            if hasattr(obj, k):
                attr = getattr(obj, k)
                if hasattr(attr, "__dataclass_fields__"):  # nested dataclass
                    setattr(obj, k, merge(v, type(attr)))
                else:
                    setattr(obj, k, v)
        return obj
    return merge(data, Config)

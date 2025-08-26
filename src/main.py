import argparse
import asyncio
import logging
from src.config import load_config
from src.bot import Bot
from src.utils.logging_utils import setup_logging
from src.utils.db import ensure_dirs, init_db, open_sqlite

def build_parser():
    p = argparse.ArgumentParser("sol-tradebot")
    p.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    p.add_argument("--status", action="store_true", help="Print status and exit")
    p.add_argument("--dry-run", action="store_true", help="Force paper mode")
    p.add_argument("--mode", choices=["paper", "live"], help="Override mode")
    p.add_argument("--max-trades", type=int, help="Override max_concurrent_trades")
    p.add_argument("-v", "--verbose", action="store_true", help="Set logging to DEBUG")
    return p

async def print_status(db_path: str):
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        # Open positions
        async with db.execute("SELECT token, symbol, entry_price, size, strategy, entry_ts FROM positions WHERE status='OPEN'") as cur:
            rows = await cur.fetchall()
            print("Open Positions:")
            for r in rows:
                print(f"  {r[0]} ({r[1]}): size={r[3]} @ {r[2]} via {r[4]} at {r[5]}")
        # Summary
        async with db.execute("SELECT COUNT(*), SUM(pnl_amount), AVG(pnl_pct) FROM trades") as cur:
            row = await cur.fetchone()
            count = row[0] or 0
            total = row[1] or 0.0
            avg = row[2] or 0.0
            print(f"Closed trades: {count}, Total PnL: {total:.4f}, Avg PnL%: {avg:.2%}")

def main():
    parser = build_parser()
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.dry_run:
        cfg.mode = "paper"
    if args.mode:
        cfg.mode = args.mode
    if args.max_trades is not None:
        cfg.risk.max_concurrent_trades = args.max_trades

    log_level = "DEBUG" if args.verbose else cfg.logging.level
    logger = setup_logging(cfg, level=log_level)

    ensure_dirs(cfg)
    asyncio.run(init_db(cfg))

    if args.status:
        asyncio.run(print_status(cfg.database.path))
        return

    bot = Bot(cfg, logger=logger)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt: stopping...")
        asyncio.run(bot.graceful_shutdown())

if __name__ == "__main__":
    main()

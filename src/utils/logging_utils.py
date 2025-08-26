import json
import logging
import os
from logging.handlers import RotatingFileHandler
from dataclasses import asdict
from typing import Any, Dict

class JsonLineFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra"):
            try:
                payload.update(record.extra)  # type: ignore
            except Exception:
                pass
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(cfg, level=None):
    os.makedirs(os.path.dirname(cfg.logging.log_file), exist_ok=True)
    logger = logging.getLogger("tradebot")
    logger.setLevel(getattr(logging, (level or cfg.logging.level).upper()))
    logger.propagate = False

        # Console (human) — include event extras if present
    class ConsoleFormatter(logging.Formatter):
        def format(self, record):
            msg = super().format(record)
            extra = getattr(record, "extra", None)
            if isinstance(extra, dict) and extra:
                # Show a compact kv tail for human-readability
                tail = " " + " ".join(f"{k}={v}" for k, v in extra.items() if k not in ("msg","logger"))
                return f"{msg}{tail}"
            return msg

    ch = logging.StreamHandler()
    ch.setLevel(logger.level)
    ch.setFormatter(ConsoleFormatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    # JSONL file
    if cfg.logging.json:
        fh = RotatingFileHandler(cfg.logging.log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        fh.setLevel(logger.level)
        fh.setFormatter(JsonLineFormatter())
        logger.addHandler(fh)

    return logger

def jlog(logger, event: str, **fields):
    logger.info(event, extra={"extra": {"event": event, **fields}})

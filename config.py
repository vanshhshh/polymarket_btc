from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw in (None, "") else float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw in (None, "") else int(raw)


@dataclass(frozen=True)
class Settings:
    binance_symbol: str = os.getenv("BINANCE_SYMBOL", "btcusdt").lower()
    prediction_horizon_seconds: int = _int("PREDICTION_HORIZON_SECONDS", 300)
    edge_threshold: float = _float("EDGE_THRESHOLD", 0.05)
    edge_safety_buffer: float = _float("EDGE_SAFETY_BUFFER", 0.03)
    max_yes_no_ask_sum: float = _float("MAX_YES_NO_ASK_SUM", 1.08)
    max_contrarian_distance_bps: float = _float("MAX_CONTRARIAN_DISTANCE_BPS", 2.0)
    contrarian_confidence: float = _float("CONTRARIAN_CONFIDENCE", 0.25)
    min_executable_price: float = _float("MIN_EXECUTABLE_PRICE", 0.25)
    max_executable_price: float = _float("MAX_EXECUTABLE_PRICE", 0.90)
    late_uncertainty_seconds: int = _int("LATE_UNCERTAINTY_SECONDS", 120)
    late_uncertainty_distance_bps: float = _float("LATE_UNCERTAINTY_DISTANCE_BPS", 2.0)
    min_entry_seconds_remaining: int = _int("MIN_ENTRY_SECONDS_REMAINING", 150)
    min_history_points: int = _int("MIN_HISTORY_POINTS", 20)
    poll_interval_seconds: int = _int("POLL_INTERVAL_SECONDS", 5)

    paper_trading: bool = _bool("PAPER_TRADING", True)
    enable_live_trading: bool = _bool("ENABLE_LIVE_TRADING", False)

    bankroll: float = _float("BANKROLL", 100.0)
    max_bet_fraction: float = _float("MAX_BET_FRACTION", 0.05)
    max_market_exposure_fraction: float = _float("MAX_MARKET_EXPOSURE_FRACTION", 0.05)
    daily_loss_limit_fraction: float = _float("DAILY_LOSS_LIMIT_FRACTION", 0.20)
    drawdown_halt_fraction: float = _float("DRAWDOWN_HALT_FRACTION", 0.40)
    loss_cooldown_count: int = _int("LOSS_COOLDOWN_COUNT", 3)
    loss_cooldown_seconds: int = _int("LOSS_COOLDOWN_SECONDS", 1800)
    min_market_seconds_remaining: int = _int("MIN_MARKET_SECONDS_REMAINING", 45)
    min_top_liquidity: float = _float("MIN_TOP_LIQUIDITY", 1.0)

    sqlite_path: str = os.getenv("SQLITE_PATH", "monitoring/trades.sqlite3")

    gamma_host: str = os.getenv("GAMMA_HOST", "https://gamma-api.polymarket.com")
    clob_host: str = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
    polymarket_market_slug: str | None = os.getenv("POLYMARKET_MARKET_SLUG") or None
    yes_token_id: str | None = os.getenv("POLYMARKET_YES_TOKEN_ID") or None
    no_token_id: str | None = os.getenv("POLYMARKET_NO_TOKEN_ID") or None

    polymarket_private_key: str | None = os.getenv("POLYMARKET_PRIVATE_KEY") or None
    polymarket_funder_address: str | None = os.getenv("POLYMARKET_FUNDER_ADDRESS") or None
    polymarket_signature_type: int = _int("POLYMARKET_SIGNATURE_TYPE", 2)


settings = Settings()

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


@dataclass(frozen=True)
class Settlement:
    market_slug: str
    start_time: datetime
    end_time: datetime
    start_price: float
    end_price: float
    outcome: str


def load_decisions(sqlite_path: str) -> pd.DataFrame:
    path = Path(sqlite_path)
    if not path.exists():
        return pd.DataFrame()
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query("SELECT * FROM decisions ORDER BY id", conn)


def evaluated_trades(sqlite_path: str) -> pd.DataFrame:
    df = load_decisions(sqlite_path)
    if df.empty:
        return df
    trades = df[(df["side"].isin(["YES", "NO"])) & (df["size"] > 0)].copy()
    if trades.empty:
        return trades

    settlements: dict[str, Settlement] = {}
    rows = []
    now = datetime.now(timezone.utc)
    for row in trades.to_dict("records"):
        slug = row.get("market_slug")
        if not slug:
            continue
        settlement = settlements.get(slug)
        if settlement is None:
            settlement = settle_market(slug, row.get("market_start_time"), row.get("market_end_time"), now)
            if settlement is None:
                continue
            settlements[slug] = settlement

        price = float(row["executable_price"])
        stake = float(row["size"])
        side = row["side"]
        win = side == settlement.outcome
        pnl = stake * ((1.0 / price) - 1.0) if win else -stake
        rows.append(
            {
                **row,
                "settled_outcome": settlement.outcome,
                "start_price": settlement.start_price,
                "end_price": settlement.end_price,
                "paper_pnl": pnl,
                "paper_win": win,
            }
        )
    return pd.DataFrame(rows)


def settle_market(
    slug: str,
    start_time_raw: str | None,
    end_time_raw: str | None,
    now: datetime | None = None,
) -> Settlement | None:
    now = now or datetime.now(timezone.utc)
    start_time = _parse_time(start_time_raw)
    end_time = _parse_time(end_time_raw)
    if start_time is None and slug.startswith("btc-updown-5m-"):
        try:
            start_time = datetime.fromtimestamp(int(slug.rsplit("-", 1)[-1]), timezone.utc)
        except ValueError:
            return None
    if start_time is None:
        return None
    end_time = end_time or datetime.fromtimestamp(start_time.timestamp() + 300, timezone.utc)
    if now < end_time:
        return None

    start_price = binance_boundary_price(start_time)
    end_price = binance_boundary_price(end_time)
    if start_price is None or end_price is None:
        return None
    return Settlement(
        market_slug=slug,
        start_time=start_time,
        end_time=end_time,
        start_price=start_price,
        end_price=end_price,
        outcome="YES" if end_price >= start_price else "NO",
    )


def binance_boundary_price(ts: datetime) -> float | None:
    start_ms = int(ts.astimezone(timezone.utc).timestamp() // 60 * 60 * 1000)
    params = {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "startTime": start_ms,
        "endTime": start_ms + 60_000,
        "limit": 1,
    }
    response = requests.get("https://api.binance.com/api/v3/klines", params=params, timeout=10)
    response.raise_for_status()
    rows = response.json()
    if not rows:
        return None
    return float(rows[0][1])


def parse_features(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None

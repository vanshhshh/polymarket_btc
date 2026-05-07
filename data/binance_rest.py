from __future__ import annotations

from datetime import datetime, timezone

import aiohttp


class BinanceRestClient:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.upper()

    async def close_price_at_minute(self, ts: datetime) -> float | None:
        start_ms = int(ts.astimezone(timezone.utc).timestamp() // 60 * 60 * 1000)
        params = {
            "symbol": self.symbol.upper(),
            "interval": "1m",
            "startTime": start_ms,
            "endTime": start_ms + 60_000,
            "limit": 1,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.binance.com/api/v3/klines", params=params, timeout=10) as resp:
                resp.raise_for_status()
                rows = await resp.json()
        if not rows:
            return None
        return float(rows[0][1])

    async def recent_1m_closes(self, limit: int = 60) -> list[tuple[float, float]]:
        params = {
            "symbol": self.symbol.upper(),
            "interval": "1m",
            "limit": limit,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.binance.com/api/v3/klines", params=params, timeout=10) as resp:
                resp.raise_for_status()
                rows = await resp.json()
        return [(float(row[4]), float(row[5])) for row in rows]

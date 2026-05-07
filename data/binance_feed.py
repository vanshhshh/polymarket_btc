from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import websockets

from data.schemas import FeatureSnapshot


@dataclass
class BinanceState:
    last_price: float | None = None
    last_trade_ts: datetime | None = None
    minute_closes: deque[float] = field(default_factory=lambda: deque(maxlen=180))
    minute_volumes: deque[float] = field(default_factory=lambda: deque(maxlen=180))
    buy_qty_rolling: deque[float] = field(default_factory=lambda: deque(maxlen=300))
    sell_qty_rolling: deque[float] = field(default_factory=lambda: deque(maxlen=300))
    best_bid_qty: float = 0.0
    best_ask_qty: float = 0.0
    best_bid: float | None = None
    best_ask: float | None = None

    def snapshot(self) -> FeatureSnapshot | None:
        if self.last_price is None:
            return None
        return FeatureSnapshot(
            timestamp=datetime.now(timezone.utc),
            price=self.last_price,
            features={
                "last_price": self.last_price,
                "best_bid": self.best_bid or self.last_price,
                "best_ask": self.best_ask or self.last_price,
                "best_bid_qty": self.best_bid_qty,
                "best_ask_qty": self.best_ask_qty,
                "buy_qty_rolling": sum(self.buy_qty_rolling),
                "sell_qty_rolling": sum(self.sell_qty_rolling),
                "minute_closes_count": float(len(self.minute_closes)),
            },
        )


class BinanceLiveFeed:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.lower()
        self.state = BinanceState()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="binance-live-feed")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        streams = "/".join(
            [
                f"{self.symbol}@trade",
                f"{self.symbol}@kline_1m",
                f"{self.symbol}@depth5@100ms",
            ]
        )
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        while not self._stop.is_set():
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        self._handle(json.loads(raw))
            except Exception:
                await asyncio.sleep(3)

    def _handle(self, payload: dict) -> None:
        data = payload.get("data", {})
        event_type = data.get("e")
        if event_type == "trade":
            self._handle_trade(data)
        elif event_type == "kline":
            self._handle_kline(data)
        elif event_type == "depthUpdate":
            self._handle_depth(data)

    def _handle_trade(self, data: dict) -> None:
        price = float(data["p"])
        qty = float(data["q"])
        self.state.last_price = price
        self.state.last_trade_ts = datetime.fromtimestamp(data["T"] / 1000, timezone.utc)
        is_buyer_maker = bool(data.get("m"))
        if is_buyer_maker:
            self.state.sell_qty_rolling.append(qty)
            self.state.buy_qty_rolling.append(0.0)
        else:
            self.state.buy_qty_rolling.append(qty)
            self.state.sell_qty_rolling.append(0.0)

    def _handle_kline(self, data: dict) -> None:
        candle = data["k"]
        if candle.get("x"):
            self.state.minute_closes.append(float(candle["c"]))
            self.state.minute_volumes.append(float(candle["v"]))
        if self.state.last_price is None:
            self.state.last_price = float(candle["c"])

    def _handle_depth(self, data: dict) -> None:
        bids = data.get("b", [])
        asks = data.get("a", [])
        if bids:
            self.state.best_bid = float(bids[0][0])
            self.state.best_bid_qty = float(bids[0][1])
        if asks:
            self.state.best_ask = float(asks[0][0])
            self.state.best_ask_qty = float(asks[0][1])


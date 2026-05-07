from __future__ import annotations

from data.binance_feed import BinanceState
from data.schemas import FeatureSnapshot
from features.microstructure import order_book_imbalance, spread_bps, trade_flow_imbalance
from features.technical import pct_return, rolling_zscore, rsi


class FeaturePipeline:
    def build(self, state: BinanceState) -> FeatureSnapshot | None:
        base = state.snapshot()
        if base is None:
            return None

        closes = list(state.minute_closes)
        if not closes or closes[-1] != base.price:
            closes.append(base.price)

        bid = state.best_bid or base.price
        ask = state.best_ask or base.price
        features = dict(base.features)
        features.update(
            {
                "ret_1m": pct_return(closes, 1),
                "ret_3m": pct_return(closes, 3),
                "ret_5m": pct_return(closes, 5),
                "ret_15m": pct_return(closes, 15),
                "zscore_20m": rolling_zscore(closes, 20),
                "rsi_14": rsi(closes, 14),
                "book_imbalance": order_book_imbalance(state.best_bid_qty, state.best_ask_qty),
                "trade_flow_imbalance": trade_flow_imbalance(
                    sum(state.buy_qty_rolling),
                    sum(state.sell_qty_rolling),
                ),
                "spread_bps": spread_bps(bid, ask),
            }
        )
        return FeatureSnapshot(timestamp=base.timestamp, price=base.price, features=features)


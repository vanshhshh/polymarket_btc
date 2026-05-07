from __future__ import annotations


def safe_ratio(num: float, den: float) -> float:
    return 0.0 if den == 0 else num / den


def order_book_imbalance(bid_qty: float, ask_qty: float) -> float:
    return safe_ratio(bid_qty - ask_qty, bid_qty + ask_qty)


def trade_flow_imbalance(buy_qty: float, sell_qty: float) -> float:
    return safe_ratio(buy_qty - sell_qty, buy_qty + sell_qty)

def spread_bps(bid: float, ask: float) -> float:
    mid = (bid + ask) / 2
    return safe_ratio(ask - bid, mid) * 10_000


from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from monitoring.performance import evaluated_trades


SINCE_FIX_MARKET = "btc-updown-5m-1778175000"


def main() -> None:
    trades = evaluated_trades(settings.sqlite_path)
    if trades.empty:
        print("No settled paper trades yet.")
        return

    print_summary("All settled", trades)
    current = trades[trades["market_slug"] >= SINCE_FIX_MARKET].copy()
    if not current.empty:
        print()
        print_summary("Current strategy window", current)
    print("\nBy market:")
    by_market = trades.groupby("market_slug").agg(
        trades=("id", "count"),
        pnl=("paper_pnl", "sum"),
        win_rate=("paper_win", "mean"),
        outcome=("settled_outcome", "last"),
    )
    print(by_market.tail(20).to_string())


def print_summary(label: str, trades) -> None:
    pnl = trades["paper_pnl"].sum()
    win_rate = trades["paper_win"].mean()
    print(f"{label}:")
    print(f"  Settled trades: {len(trades)}")
    print(f"  Paper P&L: ${pnl:.2f}")
    print(f"  Win rate: {win_rate:.1%}")


if __name__ == "__main__":
    main()

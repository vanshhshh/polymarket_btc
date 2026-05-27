from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from monitoring.performance import evaluated_trades, parse_features


def main() -> None:
    trades = evaluated_trades(settings.sqlite_path)
    if trades.empty:
        print("No settled paper trades yet.")
        return

    df = add_diagnostics(trades)
    print_overview(df)
    print_group("By side", df, ["side"])
    print_group("By side + price paid", df, ["side", "price_bucket"])
    print_group("By side + distance from start", df, ["side", "distance_bucket"])
    print_group("By side + time left", df, ["side", "time_bucket"])
    print_group("By reason", df, ["reason"])
    print_extremes(df)


def add_diagnostics(trades: pd.DataFrame) -> pd.DataFrame:
    df = trades.copy()
    features = df["features_json"].apply(parse_features)
    df["last_price_at_entry"] = features.apply(lambda f: _num(f.get("last_price")))
    df["market_start_price_at_entry"] = features.apply(lambda f: _num(f.get("market_start_price")))
    df["distance_bps"] = features.apply(lambda f: _num(f.get("distance_to_start_bps")))
    df["seconds_remaining"] = features.apply(lambda f: _num(f.get("market_seconds_remaining")))
    df["ret_1m_bps"] = features.apply(lambda f: _num(f.get("ret_1m")) * 10_000 if _num(f.get("ret_1m")) is not None else None)
    df["ret_5m_bps"] = features.apply(lambda f: _num(f.get("ret_5m")) * 10_000 if _num(f.get("ret_5m")) is not None else None)
    df["flow"] = features.apply(lambda f: _num(f.get("trade_flow_imbalance")))
    df["rsi_14"] = features.apply(lambda f: _num(f.get("rsi_14")))

    df["price_bucket"] = pd.cut(
        df["executable_price"].astype(float),
        bins=[0, 0.25, 0.4, 0.6, 0.75, 1.0],
        labels=["<=25c", "25-40c", "40-60c", "60-75c", ">75c"],
        include_lowest=True,
    ).astype(str)
    df["distance_bucket"] = pd.cut(
        df["distance_bps"],
        bins=[-10_000, -10, -5, -2, 2, 5, 10, 10_000],
        labels=["<=-10bps", "-10..-5", "-5..-2", "-2..+2", "+2..+5", "+5..+10", ">=+10bps"],
        include_lowest=True,
    ).astype(str)
    df["time_bucket"] = pd.cut(
        df["seconds_remaining"],
        bins=[0, 120, 180, 240, 300, 10_000],
        labels=["<=2m", "2-3m", "3-4m", "4-5m", ">5m"],
        include_lowest=True,
    ).astype(str)
    return df


def print_overview(df: pd.DataFrame) -> None:
    print("Settled paper trades")
    print(f"  Count: {len(df)}")
    print(f"  P&L: ${df['paper_pnl'].sum():.2f}")
    print(f"  Win rate: {df['paper_win'].mean():.1%}")
    print(f"  Avg stake: ${df['size'].mean():.2f}")
    print(f"  Avg price paid: {df['executable_price'].mean():.2f}")
    print()


def print_group(label: str, df: pd.DataFrame, cols: list[str]) -> None:
    grouped = (
        df.groupby(cols, dropna=False, observed=True)
        .agg(
            trades=("id", "count"),
            pnl=("paper_pnl", "sum"),
            win_rate=("paper_win", "mean"),
            avg_price=("executable_price", "mean"),
            avg_edge=("edge", "mean"),
            avg_distance_bps=("distance_bps", "mean"),
        )
        .reset_index()
        .sort_values(["pnl", "trades"], ascending=[True, False])
    )
    print(label + ":")
    print(grouped.to_string(index=False, formatters=_formatters()))
    print()


def print_extremes(df: pd.DataFrame) -> None:
    cols = [
        "timestamp",
        "market_slug",
        "side",
        "executable_price",
        "size",
        "paper_pnl",
        "paper_win",
        "settled_outcome",
        "distance_bps",
        "seconds_remaining",
        "reason",
    ]
    print("Worst individual entries:")
    print(df.sort_values("paper_pnl").head(12)[cols].to_string(index=False, formatters=_formatters()))
    print()
    print("Best individual entries:")
    print(df.sort_values("paper_pnl", ascending=False).head(12)[cols].to_string(index=False, formatters=_formatters()))


def _formatters() -> dict:
    return {
        "pnl": _money,
        "paper_pnl": _money,
        "win_rate": _pct,
        "avg_price": _price,
        "executable_price": _price,
        "avg_edge": _num3,
        "avg_distance_bps": _num2,
        "distance_bps": _num2,
        "seconds_remaining": _num0,
    }


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value) -> str:
    return f"${float(value):.2f}"


def _pct(value) -> str:
    return f"{float(value):.1%}"


def _price(value) -> str:
    return f"{float(value):.2f}"


def _num3(value) -> str:
    return f"{float(value):.3f}"


def _num2(value) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}"


def _num0(value) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.0f}"


if __name__ == "__main__":
    main()

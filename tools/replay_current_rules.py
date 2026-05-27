from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from data.schemas import Bbo, FeatureSnapshot, MarketSnapshot
from execution.edge import choose_trade
from models.ensemble import HeuristicDirectionModel
from monitoring.performance import load_decisions, settle_market
from risk.manager import RiskManager


def main() -> None:
    df = load_decisions(settings.sqlite_path)
    if df.empty:
        print("No decisions to replay.")
        return

    model = HeuristicDirectionModel()
    risk = RiskManager(
        bankroll=settings.bankroll,
        max_bet_fraction=settings.max_bet_fraction,
        max_market_exposure_fraction=settings.max_market_exposure_fraction,
        min_market_seconds_remaining=-999_999,
        min_top_liquidity=0.0,
    )

    replayed = []
    for row in df.to_dict("records"):
        features = _features(row.get("features_json"))
        if not features:
            continue
        market = _market(row)
        snapshot = FeatureSnapshot(_parse_time(row.get("timestamp")) or datetime.now(timezone.utc), features.get("last_price", 0.0), features)
        prob = model.predict_up_probability(snapshot)
        decision = choose_trade(
            snapshot,
            market,
            prob,
            settings.edge_threshold,
            settings.edge_safety_buffer,
            settings.max_yes_no_ask_sum,
            settings.min_history_points,
            settings.max_contrarian_distance_bps,
            settings.contrarian_confidence,
            settings.min_executable_price,
            settings.max_executable_price,
            settings.late_uncertainty_seconds,
            settings.late_uncertainty_distance_bps,
            settings.min_entry_seconds_remaining,
            settings.min_directional_distance_bps,
            settings.min_directional_confidence,
        )
        decision = risk.approve(decision, market)
        if decision.side == "SKIP":
            continue
        risk.record(decision, market)
        settlement = settle_market(market.slug or "", row.get("market_start_time"), row.get("market_end_time"))
        if settlement is None:
            continue
        win = decision.side == settlement.outcome
        pnl = decision.size * ((1.0 / decision.executable_price) - 1.0) if win else -decision.size
        replayed.append(
            {
                "timestamp": decision.timestamp.isoformat(),
                "market_slug": market.slug,
                "side": decision.side,
                "price": decision.executable_price,
                "size": decision.size,
                "model_prob_up": prob,
                "edge": decision.edge,
                "outcome": settlement.outcome,
                "win": win,
                "pnl": pnl,
            }
        )

    if not replayed:
        print("Current rules would not take any settled trades from the log.")
        return

    out = pd.DataFrame(replayed)
    print(f"Replay trades: {len(out)}")
    print(f"Replay P&L: ${out['pnl'].sum():.2f}")
    print(f"Replay win rate: {out['win'].mean():.1%}")
    print()
    print(out.groupby("market_slug").agg(trades=("side", "count"), pnl=("pnl", "sum"), win_rate=("win", "mean"), outcome=("outcome", "last")).to_string())


def _features(raw: str | None) -> dict[str, float]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {key: value for key, value in data.items() if isinstance(value, int | float)}


def _market(row: dict) -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=_parse_time(row.get("timestamp")) or datetime.now(timezone.utc),
        slug=row.get("market_slug"),
        question=row.get("market_question"),
        start_time=_parse_time(row.get("market_start_time")),
        end_time=_parse_time(row.get("market_end_time")),
        yes_token_id=str(row.get("yes_token_id") or ""),
        no_token_id=str(row.get("no_token_id") or ""),
        yes=Bbo(_num(row.get("yes_bid")), 10_000.0, _num(row.get("yes_ask")), 10_000.0),
        no=Bbo(_num(row.get("no_bid")), 10_000.0, _num(row.get("no_ask")), 10_000.0),
    )


def _parse_time(value) -> datetime | None:
    if not value or pd.isna(value):
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _num(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


if __name__ == "__main__":
    main()

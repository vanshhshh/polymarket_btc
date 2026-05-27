from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

from config import settings
from data.binance_rest import BinanceRestClient
from data.binance_feed import BinanceLiveFeed
from execution.edge import choose_trade, force_signal_only
from execution.live import LiveExecutor
from execution.paper import PaperExecutor
from features.pipeline import FeaturePipeline
from models.ensemble import HeuristicDirectionModel
from monitoring.database import DecisionLog
from polymarket.client import PolymarketReadClient
from polymarket.market_finder import MarketFinder
from risk.manager import RiskManager


async def _resolve_start_price(binance_rest: BinanceRestClient, start_time: datetime | None) -> float | None:
    if start_time is None:
        return None
    try:
        return await binance_rest.close_price_at_minute(start_time)
    except Exception:
        return None


async def _warm_feed_history(binance_rest: BinanceRestClient, feed: BinanceLiveFeed) -> None:
    try:
        rows = await binance_rest.recent_1m_closes(limit=60)
    except Exception:
        return
    for close, volume in rows:
        feed.state.minute_closes.append(close)
        feed.state.minute_volumes.append(volume)
    if rows and feed.state.last_price is None:
        feed.state.last_price = rows[-1][0]


async def run() -> None:
    if settings.enable_live_trading and settings.paper_trading:
        raise RuntimeError("Choose either PAPER_TRADING=true or ENABLE_LIVE_TRADING=true, not both.")

    feed = BinanceLiveFeed(settings.binance_symbol)
    binance_rest = BinanceRestClient(settings.binance_symbol)
    feature_pipeline = FeaturePipeline()
    model = HeuristicDirectionModel()
    poly_client = PolymarketReadClient(settings.gamma_host, settings.clob_host)
    market_finder = MarketFinder(settings, poly_client)
    risk = RiskManager(
        bankroll=settings.bankroll,
        max_bet_fraction=settings.max_bet_fraction,
        max_market_exposure_fraction=settings.max_market_exposure_fraction,
        min_market_seconds_remaining=settings.min_market_seconds_remaining,
        min_top_liquidity=settings.min_top_liquidity,
    )
    log = DecisionLog(settings.sqlite_path)
    executor = PaperExecutor() if settings.paper_trading else LiveExecutor(settings.enable_live_trading)

    tracked = await market_finder.resolve()
    start_price = await _resolve_start_price(binance_rest, tracked.start_time)
    await _warm_feed_history(binance_rest, feed)
    print(f"Tracking market: {tracked.slug or 'manual token IDs'}", flush=True)
    print("Starting Binance feed...", flush=True)
    await feed.start()

    try:
        while True:
            now = datetime.now(timezone.utc)
            if tracked.end_time is not None:
                remaining = (tracked.end_time - now).total_seconds()
                if remaining < settings.min_market_seconds_remaining:
                    tracked = await market_finder.resolve()
                    start_price = await _resolve_start_price(binance_rest, tracked.start_time)
                    print(f"Rotated market: {tracked.slug or 'manual token IDs'}", flush=True)
                    now = datetime.now(timezone.utc)

            if start_price is None and tracked.start_time is not None and now >= tracked.start_time:
                start_price = await _resolve_start_price(binance_rest, tracked.start_time)

            features = feature_pipeline.build(feed.state)
            if features is None:
                await asyncio.sleep(settings.poll_interval_seconds)
                continue

            market = await poly_client.get_snapshot(
                yes_token_id=tracked.yes_token_id,
                no_token_id=tracked.no_token_id,
                slug=tracked.slug,
                question=tracked.question,
                start_time=tracked.start_time,
                end_time=tracked.end_time,
            )
            if start_price is not None:
                features.features["market_start_price"] = start_price
                features.features["distance_to_start_bps"] = ((features.price / start_price) - 1.0) * 10_000
            if tracked.end_time is not None:
                features.features["market_seconds_remaining"] = max(
                    (tracked.end_time - datetime.now(timezone.utc)).total_seconds(),
                    0.0,
                )
            model_prob = model.predict_up_probability(features)
            decision = choose_trade(
                features,
                market,
                model_prob,
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
            if settings.signal_only_mode:
                decision = force_signal_only(decision)
            decision = risk.approve(decision, market)
            if decision.side != "SKIP":
                decision = await executor.execute(decision)
                risk.record(decision, market)
            else:
                decision = replace(decision, reason=f"paper_{decision.reason}" if settings.paper_trading else decision.reason)

            log.write(decision, market)
            print(
                f"{decision.timestamp.isoformat()} side={decision.side} "
                f"prob_up={decision.model_prob_up:.3f} edge={decision.edge:.3f} "
                f"price={decision.executable_price} size={decision.size} reason={decision.reason}",
                flush=True,
            )
            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        await feed.stop()


if __name__ == "__main__":
    asyncio.run(run())

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from data.schemas import Decision, MarketSnapshot


class RiskManager:
    def __init__(
        self,
        bankroll: float,
        max_bet_fraction: float,
        max_market_exposure_fraction: float,
        min_market_seconds_remaining: int,
        min_top_liquidity: float,
    ) -> None:
        self.bankroll = bankroll
        self.max_bet_fraction = max_bet_fraction
        self.max_market_exposure_fraction = max_market_exposure_fraction
        self.min_market_seconds_remaining = min_market_seconds_remaining
        self.min_top_liquidity = min_top_liquidity
        self.peak_bankroll = bankroll
        self.market_exposure: dict[str, float] = {}

    def approve(self, decision: Decision, market: MarketSnapshot) -> Decision:
        if decision.side == "SKIP":
            return decision
        if decision.executable_price is None or decision.executable_price <= 0:
            return replace(decision, side="SKIP", size=0.0, reason="risk_no_executable_price")

        if market.end_time is not None:
            remaining = (market.end_time - datetime.now(timezone.utc)).total_seconds()
            if remaining < self.min_market_seconds_remaining:
                return replace(decision, side="SKIP", size=0.0, reason="risk_market_too_close_to_expiry")

        top_liquidity = market.yes.ask_size if decision.side == "YES" else market.no.ask_size
        if top_liquidity < self.min_top_liquidity:
            return replace(decision, side="SKIP", size=0.0, reason="risk_insufficient_top_liquidity")

        size = self._half_kelly_size(decision.edge, decision.executable_price)
        max_size = self.bankroll * self.max_bet_fraction
        market_key = self._market_key(decision, market)
        max_market_exposure = self.bankroll * self.max_market_exposure_fraction
        remaining_market_exposure = max_market_exposure - self.market_exposure.get(market_key, 0.0)
        if remaining_market_exposure <= 0:
            return replace(decision, side="SKIP", size=0.0, reason="risk_market_exposure_full")

        liquidity_capped = min(size, max_size, remaining_market_exposure, top_liquidity * decision.executable_price)
        if liquidity_capped <= 0:
            return replace(decision, side="SKIP", size=0.0, reason="risk_zero_size")

        return replace(decision, size=round(liquidity_capped, 2), reason=f"risk_approved_{decision.reason}")

    def record(self, decision: Decision, market: MarketSnapshot) -> None:
        if decision.side == "SKIP" or decision.size <= 0:
            return
        market_key = self._market_key(decision, market)
        self.market_exposure[market_key] = self.market_exposure.get(market_key, 0.0) + decision.size

    @staticmethod
    def _market_key(decision: Decision, market: MarketSnapshot) -> str:
        return decision.market_slug or f"{market.yes_token_id}:{market.no_token_id}"

    def _half_kelly_size(self, edge: float, price: float) -> float:
        denominator = max(1.0 - price, 0.01)
        fraction = max(edge / denominator, 0.0) / 2.0
        return self.bankroll * fraction

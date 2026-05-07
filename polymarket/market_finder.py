from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from config import Settings
from polymarket.client import PolymarketReadClient, extract_market_meta, extract_token_ids


@dataclass(frozen=True)
class TrackedMarket:
    slug: str | None
    question: str | None
    start_time: datetime | None
    end_time: datetime | None
    yes_token_id: str
    no_token_id: str


class MarketFinder:
    def __init__(self, settings: Settings, client: PolymarketReadClient) -> None:
        self.settings = settings
        self.client = client

    async def resolve(self) -> TrackedMarket:
        if self.settings.yes_token_id and self.settings.no_token_id:
            return TrackedMarket(
                slug=self.settings.polymarket_market_slug,
                question=None,
                start_time=None,
                end_time=None,
                yes_token_id=self.settings.yes_token_id,
                no_token_id=self.settings.no_token_id,
            )

        if self.settings.polymarket_market_slug:
            market = await self.client.get_market_by_slug(self.settings.polymarket_market_slug)
        else:
            market = await self.client.find_btc_5m_market(self.settings.min_market_seconds_remaining)

        if not market:
            raise RuntimeError(
                "Could not auto-discover a BTC 5m Polymarket market. "
                "Set POLYMARKET_YES_TOKEN_ID and POLYMARKET_NO_TOKEN_ID in .env."
            )

        yes_token_id, no_token_id = extract_token_ids(market)
        if not yes_token_id or not no_token_id:
            raise RuntimeError("Resolved market did not contain usable YES/NO token IDs.")

        slug, question, start_time, end_time = extract_market_meta(market)
        return TrackedMarket(slug, question, start_time, end_time, yes_token_id, no_token_id)

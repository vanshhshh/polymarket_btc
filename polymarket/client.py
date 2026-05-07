from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import aiohttp

from data.schemas import Bbo, MarketSnapshot


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return value if isinstance(value, list) else []


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return None


class PolymarketReadClient:
    def __init__(self, gamma_host: str, clob_host: str) -> None:
        self.gamma_host = gamma_host.rstrip("/")
        self.clob_host = clob_host.rstrip("/")

    async def find_btc_5m_market(self, min_seconds_remaining: int = 0) -> dict[str, Any] | None:
        async with aiohttp.ClientSession() as session:
            markets = await self._probe_btc_5m_slugs(session)
            if not markets:
                markets = await self._search_public(session, "bitcoin up or down")
            if not markets:
                markets = await self._search_public(session, "btc updown 5m")

        now = datetime.now(timezone.utc)
        markets = [
            market
            for market in markets
            if self._looks_like_live_btc_5m(market)
            and (
                (_parse_time(market.get("endDate") or market.get("endDateIso")) or datetime.min.replace(tzinfo=timezone.utc))
                > now
            )
            and (
                (
                    (_parse_time(market.get("endDate") or market.get("endDateIso")) or now) - now
                ).total_seconds()
                >= min_seconds_remaining
            )
        ]
        if not markets:
            return None

        def sort_key(market: dict[str, Any]) -> datetime:
            return _parse_time(market.get("endDate") or market.get("endDateIso")) or datetime.max.replace(
                tzinfo=timezone.utc
            )

        return sorted(markets, key=sort_key)[0]

    async def _probe_btc_5m_slugs(self, session: aiohttp.ClientSession) -> list[dict[str, Any]]:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        base = now_ts - (now_ts % 300)
        slugs = [f"btc-updown-5m-{base + offset * 300}" for offset in range(-2, 25)]
        markets = []
        for slug in slugs:
            try:
                async with session.get(f"{self.gamma_host}/markets/slug/{slug}", timeout=5) as resp:
                    if resp.status != 200:
                        continue
                    market = await resp.json()
                    if isinstance(market, dict) and market:
                        markets.append(market)
            except (aiohttp.ClientError, TimeoutError):
                continue
        return markets

    async def _search_public(self, session: aiohttp.ClientSession, query: str) -> list[dict[str, Any]]:
        async with session.get(
            f"{self.gamma_host}/public-search",
            params={"q": query, "limit": "100"},
            timeout=10,
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json()

        markets = []
        for event in payload.get("events", []):
            event_markets = event.get("markets") or []
            if event_markets:
                markets.extend(event_markets)
            elif event.get("clobTokenIds"):
                markets.append(event)
        return markets

    @staticmethod
    def _looks_like_live_btc_5m(market: dict[str, Any]) -> bool:
        text = " ".join(
            str(market.get(key, ""))
            for key in ("question", "slug", "description", "groupItemTitle", "title")
        ).lower()
        if market.get("closed") or market.get("archived"):
            return False
        if "btc-updown-5m" in text:
            return True
        has_5m = bool(re.search(r"(?<!\d)5m\b|5-minute", text))
        return "bitcoin" in text and "up or down" in text and has_5m

    async def get_market_by_slug(self, slug: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.gamma_host}/markets/slug/{slug}", timeout=10) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_snapshot(
        self,
        yes_token_id: str,
        no_token_id: str,
        slug: str | None = None,
        question: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MarketSnapshot:
        yes, no = await self.get_books([yes_token_id, no_token_id])
        return MarketSnapshot(
            timestamp=datetime.now(timezone.utc),
            slug=slug,
            question=question,
            start_time=start_time,
            end_time=end_time,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            yes=yes,
            no=no,
        )

    async def get_books(self, token_ids: list[str]) -> list[Bbo]:
        async with aiohttp.ClientSession() as session:
            tasks = [self._get_book(session, token_id) for token_id in token_ids]
            return [await task for task in tasks]

    async def _get_book(self, session: aiohttp.ClientSession, token_id: str) -> Bbo:
        async with session.get(f"{self.clob_host}/book", params={"token_id": token_id}, timeout=10) as resp:
            resp.raise_for_status()
            book = await resp.json()

        bids = _as_list(book.get("bids"))
        asks = _as_list(book.get("asks"))
        best_bid = self._best_level(bids, best="bid")
        best_ask = self._best_level(asks, best="ask")
        return Bbo(
            bid_price=best_bid[0],
            bid_size=best_bid[1],
            ask_price=best_ask[0],
            ask_size=best_ask[1],
        )

    @staticmethod
    def _best_level(levels: list[Any], best: str) -> tuple[float | None, float]:
        parsed = []
        for level in levels:
            if isinstance(level, dict):
                price = level.get("price")
                size = level.get("size")
            elif isinstance(level, (list, tuple)) and len(level) >= 2:
                price, size = level[0], level[1]
            else:
                continue
            try:
                parsed.append((float(price), float(size)))
            except (TypeError, ValueError):
                continue
        if not parsed:
            return None, 0.0
        return (max if best == "bid" else min)(parsed, key=lambda item: item[0])


def extract_token_ids(market: dict[str, Any]) -> tuple[str | None, str | None]:
    outcomes = _as_list(market.get("outcomes"))
    token_ids = _as_list(market.get("clobTokenIds"))
    if len(outcomes) != len(token_ids):
        return None, None
    mapping = {str(outcome).lower(): str(token_id) for outcome, token_id in zip(outcomes, token_ids)}
    return mapping.get("yes") or mapping.get("up"), mapping.get("no") or mapping.get("down")


def extract_market_meta(market: dict[str, Any]) -> tuple[str | None, str | None, datetime | None, datetime | None]:
    slug = market.get("slug")
    question = market.get("question")
    start_time = _parse_time(market.get("startDate") or market.get("startDateIso"))
    end_time = _parse_time(market.get("endDate") or market.get("endDateIso"))
    if slug and slug.startswith("btc-updown-5m-"):
        try:
            start_time = datetime.fromtimestamp(int(slug.rsplit("-", 1)[-1]), timezone.utc)
        except ValueError:
            pass
    return slug, question, start_time, end_time

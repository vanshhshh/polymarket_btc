from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Bbo:
    bid_price: float | None = None
    bid_size: float = 0.0
    ask_price: float | None = None
    ask_size: float = 0.0


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime
    slug: str | None
    question: str | None
    start_time: datetime | None
    end_time: datetime | None
    yes_token_id: str
    no_token_id: str
    yes: Bbo
    no: Bbo


@dataclass(frozen=True)
class FeatureSnapshot:
    timestamp: datetime
    price: float
    features: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    timestamp: datetime
    market_slug: str | None
    side: str
    model_prob_up: float
    executable_price: float | None
    edge: float
    size: float
    reason: str
    features: dict[str, float]

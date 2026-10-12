"""Normalized contracts, observations and labels kept separate."""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any


class DataInvalid(ValueError):
    """Missing or unreliable information, not permission to invent a proxy."""


def utc(value: str | int | float | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, (int, float)):
        result = datetime.fromtimestamp(value, timezone.utc)
    else:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise DataInvalid("Naive timestamps are forbidden")
    return result.astimezone(timezone.utc)


def probability(value: float) -> float:
    if not isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Probability/price must be finite and in [0, 1]")
    return value


@dataclass(frozen=True)
class Stamp:
    event_time: datetime
    available_time: datetime | None
    ingested_time: datetime
    quality: str = "VERIFIED"

    def __post_init__(self) -> None:
        for value in (self.event_time, self.ingested_time, self.available_time):
            if value is not None:
                utc(value)
        if self.available_time and self.available_time < self.event_time:
            raise DataInvalid("Availability precedes event time")

    def require_asof(self, entry: datetime, *, online: bool = False) -> None:
        if self.quality != "VERIFIED" or self.available_time is None:
            raise DataInvalid("Historical availability not verified")
        if self.event_time > entry or self.available_time > entry:
            raise DataInvalid("Future-data leakage")
        if online and self.ingested_time > entry:
            raise DataInvalid("Data not yet ingested by this shadow engine")


@dataclass(frozen=True)
class Market:
    source: str
    market_id: str
    cluster_id: str
    question: str
    rules: str
    scheduled_close: datetime
    stamp: Stamp
    yes_token: str | None = None
    no_token: str | None = None
    minimum_shares: float = 1.0
    share_step: float = 1.0


@dataclass(frozen=True)
class Quote:
    market_id: str
    stamp: Stamp
    market_probability: float
    bid: float | None = None
    ask: float | None = None
    ask_depth: tuple[tuple[float, float], ...] = ()
    minimum_shares: float = 1.0
    share_step: float = 1.0

    def __post_init__(self) -> None:
        probability(self.market_probability)
        if self.bid is not None:
            probability(self.bid)
        if self.ask is not None:
            probability(self.ask)
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise DataInvalid("Crossed quote")
        if self.minimum_shares <= 0 or self.share_step <= 0:
            raise DataInvalid("Invalid venue size constraints")
        for price, size in self.ask_depth:
            probability(price)
            if size <= 0 or not isfinite(size):
                raise DataInvalid("Invalid depth")


@dataclass(frozen=True)
class Label:
    market_id: str
    outcome: int
    available_time: datetime
    source_hash: str

    def __post_init__(self) -> None:
        if self.outcome not in (0, 1):
            raise DataInvalid("Fractional/voided settlement is outside binary PM-C1")
        utc(self.available_time)


@dataclass(frozen=True)
class ResearchRow:
    market: Market
    quote: Quote
    label: Label
    entry_time: datetime
    fee_rate: float | None = None
    fee_source: str = "UNKNOWN"

    def require_valid(self) -> None:
        if not (self.market.market_id == self.quote.market_id == self.label.market_id):
            raise DataInvalid("Mismatched market/quote/label")
        self.market.stamp.require_asof(self.entry_time)
        self.quote.stamp.require_asof(self.entry_time)
        if self.label.available_time <= self.entry_time:
            raise DataInvalid("Entry after outcome became known")


def stamp_dict(s: Stamp) -> dict[str, Any]:
    return {"event_time": s.event_time.isoformat(), "available_time": s.available_time.isoformat() if s.available_time else None,
            "ingested_time": s.ingested_time.isoformat(), "quality": s.quality}

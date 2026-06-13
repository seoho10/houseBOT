"""Shared data models used across scraper, analyzer, store, notifier."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


EventKind = Literal["NEW_LISTING", "PRICE_CHANGE", "LISTING_REMOVED"]


@dataclass(frozen=True)
class Listing:
    article_id: str
    complex_id: str
    size_label: str          # e.g. "84" for grouping (rounded 전용면적 in ㎡)
    size_sqm: float          # raw 전용면적
    price_manwon: int        # price in 만원 units
    building: str            # e.g. "101동" — may be empty
    floor: str               # e.g. "12층" or "중층" — may be empty
    direction: str           # e.g. "남향" — may be empty
    registered_ymd: str      # YYYY-MM-DD or empty
    article_url: str


@dataclass(frozen=True)
class Event:
    kind: EventKind
    complex_id: str
    article_id: str
    detail: str
    article_url: str


@dataclass(frozen=True)
class SizeSummary:
    size_label: str
    count: int
    min_price: int
    avg_price: int
    max_price: int

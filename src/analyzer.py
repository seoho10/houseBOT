"""Pure analysis functions over Listing snapshots."""
from __future__ import annotations

from src.models import Event, Listing, SizeSummary


def detect_changes(
    previous: list[Listing], current: list[Listing], threshold_pct: float
) -> list[Event]:
    prev_by_id = {l.article_id: l for l in previous}
    curr_by_id = {l.article_id: l for l in current}

    events: list[Event] = []

    for article_id, l in curr_by_id.items():
        if article_id not in prev_by_id:
            events.append(Event(
                kind="NEW_LISTING",
                complex_id=l.complex_id,
                article_id=article_id,
                detail=f"{l.size_label}㎡, {_format_price(l.price_manwon)}, {l.building} {l.floor}, {l.direction}",
                article_url=l.article_url,
            ))

    for article_id, prev_l in prev_by_id.items():
        if article_id not in curr_by_id:
            events.append(Event(
                kind="LISTING_REMOVED",
                complex_id=prev_l.complex_id,
                article_id=article_id,
                detail=f"{prev_l.size_label}㎡, {_format_price(prev_l.price_manwon)}",
                article_url=prev_l.article_url,
            ))

    for article_id, curr_l in curr_by_id.items():
        if article_id not in prev_by_id:
            continue
        prev_l = prev_by_id[article_id]
        if prev_l.price_manwon == curr_l.price_manwon:
            continue
        pct = abs(curr_l.price_manwon - prev_l.price_manwon) / prev_l.price_manwon * 100
        if pct >= threshold_pct:
            signed_pct = pct if curr_l.price_manwon >= prev_l.price_manwon else -pct
            events.append(Event(
                kind="PRICE_CHANGE",
                complex_id=curr_l.complex_id,
                article_id=article_id,
                detail=(
                    f"{curr_l.size_label}㎡: {prev_l.price_manwon} → "
                    f"{curr_l.price_manwon} ({signed_pct:+.1f}%)"
                ),
                article_url=curr_l.article_url,
            ))

    return events


def _format_price(manwon: int) -> str:
    """Format 만원 integer as '12억 5,000' or '5,000'."""
    eok = manwon // 10000
    rest = manwon % 10000
    if eok and rest:
        return f"{eok}억 {rest:,}"
    if eok:
        return f"{eok}억"
    return f"{rest:,}"


def confirmed_on(listings: list[Listing], ymd: str) -> list[Listing]:
    """Listings whose Naver 확인 date (registered_ymd, 'YYYY-MM-DD') equals ymd.

    Used to surface only *today's* new listings in alerts — the raw new-vs-
    previous diff floods on the first run and whenever the snapshot is stale.
    """
    return [l for l in listings if l.registered_ymd == ymd]


def summarize_by_size(listings: list[Listing]) -> dict[str, SizeSummary]:
    """Group listings by size and compute aggregate statistics."""
    by_size: dict[str, list[Listing]] = {}
    for l in listings:
        by_size.setdefault(l.size_label, []).append(l)
    result = {}
    for size, items in by_size.items():
        prices = [l.price_manwon for l in items]
        result[size] = SizeSummary(
            size_label=size,
            count=len(items),
            min_price=min(prices),
            avg_price=sum(prices) // len(prices),
            max_price=max(prices),
        )
    return result


def _size_sort_key(size_label: str) -> tuple[int, str]:
    """Sort size labels numerically ('59' < '84' < '108'); non-numeric last."""
    return (int(size_label), "") if size_label.isdigit() else (10**9, size_label)


def lowest_by_size(listings: list[Listing]) -> list[Listing]:
    """Cheapest listing within each size, ordered by size (㎡ ascending).

    Replaces a global "TOP-N cheapest", which collapsed onto the smallest size
    and hid the best price in every other size bucket.
    """
    cheapest: dict[str, Listing] = {}
    for l in listings:
        cur = cheapest.get(l.size_label)
        if cur is None or l.price_manwon < cur.price_manwon:
            cheapest[l.size_label] = l
    return [cheapest[k] for k in sorted(cheapest, key=_size_sort_key)]

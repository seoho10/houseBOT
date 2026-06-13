"""Telegram message formatting and sending."""
from __future__ import annotations

from dataclasses import dataclass

from src.config import ApartmentConfig
from src.models import Event, Listing, SizeSummary


@dataclass(frozen=True)
class ComplexReport:
    apartment: ApartmentConfig
    listings_today: list[Listing]
    count_today: int
    count_yesterday: int
    size_summaries: dict[str, SizeSummary]
    new_listings: list[Listing]
    price_changes: list[Event]
    top_lowest: list[Listing]


def _format_price(manwon: int) -> str:
    eok = manwon // 10000
    rest = manwon % 10000
    if eok and rest:
        return f"{eok}억 {rest:,}"
    if eok:
        return f"{eok}억"
    return f"{rest:,}"


def _link(url: str, text: str) -> str:
    safe = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return f'<a href="{url}">{safe}</a>'


def _format_listing_line(l: Listing) -> str:
    parts = [
        f"{l.size_label}㎡",
        _format_price(l.price_manwon),
        f"{l.building} {l.floor}".strip(),
        l.direction,
    ]
    inner = ", ".join(p for p in parts if p)
    return _link(l.article_url, inner)


def format_daily_summary(
    date: str, reports: list[ComplexReport], sheets_url: str
) -> str:
    lines: list[str] = []
    lines.append(f"🏠 <b>houseBOT 일일 요약</b> ({date})")
    lines.append("")

    for r in reports:
        complex_url = f"https://new.land.naver.com/complexes/{r.apartment.complex_id}"
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append(f"📍 {_link(complex_url, r.apartment.name)}")
        lines.append("━━━━━━━━━━━━━━━━━━")
        diff = r.count_today - r.count_yesterday
        diff_str = (f"+{diff}" if diff > 0 else f"{diff}") if diff != 0 else "변동 없음"
        lines.append(f"📊 매물 수: {r.count_today}건 (어제 {r.count_yesterday}건, {diff_str})")
        lines.append("")
        if r.size_summaries:
            lines.append("💰 평형별 시세")
            for size, s in sorted(r.size_summaries.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 999):
                lines.append(
                    f" • {size}㎡  최저 {_format_price(s.min_price)} / "
                    f"평균 {_format_price(s.avg_price)} ({s.count}건)"
                )
            lines.append("")
        if r.new_listings:
            lines.append(f"🆕 신규 매물 ({len(r.new_listings)}건)")
            for l in r.new_listings:
                lines.append(f" • {_format_listing_line(l)}")
            lines.append("")
        if r.price_changes:
            lines.append(f"📉 가격 변동 ({len(r.price_changes)}건)")
            for e in r.price_changes:
                lines.append(f" • {_link(e.article_url, e.detail)}")
            lines.append("")
        if r.top_lowest:
            lines.append("🏷 최저가 TOP")
            for i, l in enumerate(r.top_lowest, 1):
                lines.append(f" {i}. {_format_listing_line(l)}")
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 {_link(sheets_url, '전체 추이 보기 → Google Sheets')}")

    return "\n".join(lines)


@dataclass(frozen=True)
class ComplexChanges:
    apartment: ApartmentConfig
    new_listings: list[Listing]
    price_changes: list[Event]


def format_light_check(time: str, complex_changes: list[ComplexChanges]) -> str:
    if not complex_changes or all(
        not c.new_listings and not c.price_changes for c in complex_changes
    ):
        raise ValueError("format_light_check called with no changes — caller should skip send")

    lines = [f"🔔 <b>변동 알림</b> ({time})", ""]
    for c in complex_changes:
        if not c.new_listings and not c.price_changes:
            continue
        complex_url = f"https://new.land.naver.com/complexes/{c.apartment.complex_id}"
        lines.append(f"📍 {_link(complex_url, c.apartment.name)}")
        if c.new_listings:
            lines.append(f"🆕 신규 매물 {len(c.new_listings)}건")
            for l in c.new_listings:
                lines.append(f" • {_format_listing_line(l)}")
        if c.price_changes:
            lines.append(f"📉 가격 변동 {len(c.price_changes)}건")
            for e in c.price_changes:
                lines.append(f" • {_link(e.article_url, e.detail)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_error(message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"🚨 <b>houseBOT 에러</b>\n\n{safe}"

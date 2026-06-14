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
    lowest_by_size: list[Listing]


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


def _render_complex_block(r: ComplexReport, count_line: str) -> list[str]:
    """Shared per-complex section: 매물 수, 평형별 시세, 신규 매물, 가격 변동, 평형별 최저가."""
    complex_url = f"https://new.land.naver.com/complexes/{r.apartment.complex_id}"
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        f"📍 {_link(complex_url, r.apartment.name)}",
        "━━━━━━━━━━━━━━━━━━",
        count_line,
        "",
    ]
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
    if r.lowest_by_size:
        lines.append("🏷 평형별 최저가")
        for l in r.lowest_by_size:
            lines.append(f" • {_format_listing_line(l)}")
        lines.append("")
    return lines


def format_daily_summary(
    date: str, reports: list[ComplexReport], sheets_url: str
) -> str:
    lines: list[str] = [f"🏠 <b>houseBOT 일일 요약</b> ({date})", ""]

    for r in reports:
        diff = r.count_today - r.count_yesterday
        diff_str = (f"+{diff}" if diff > 0 else f"{diff}") if diff != 0 else "변동 없음"
        count_line = f"📊 매물 수: {r.count_today}건 (어제 {r.count_yesterday}건, {diff_str})"
        lines.extend(_render_complex_block(r, count_line))

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 {_link(sheets_url, '전체 추이 보기 → Google Sheets')}")

    return "\n".join(lines)


def format_check(time: str, reports: list[ComplexReport], has_changes: bool) -> str:
    """2시간 변동 체크 메시지. 매물 수·평형별 시세·신규 매물·평형별 최저가를
    항상 디폴트로 보여주고, 변동이 없으면 맨 위에 '변동 없음'만 추가한다."""
    lines = [f"🔔 <b>houseBOT 변동 체크</b> ({time} 기준)"]
    if not has_changes:
        lines.append("변동 없음 ✅")
    lines.append("")
    for r in reports:
        count_line = f"📊 매물 수: {r.count_today}건"
        lines.extend(_render_complex_block(r, count_line))
    return "\n".join(lines).rstrip()


def format_error(message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"🚨 <b>houseBOT 에러</b>\n\n{safe}"


import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


@retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _post_telegram(token: str, chat_id: str, html: str) -> None:
    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": html,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=15.0,
    )
    if resp.status_code != 200 or not resp.json().get("ok"):
        raise RuntimeError(f"Telegram send failed: {resp.status_code} {resp.text}")


def send_message(token: str, chat_id: str, html: str, dry_run: bool = False) -> None:
    if dry_run:
        print("[DRY_RUN] Telegram message would be:")
        print(html)
        return
    _post_telegram(token, chat_id, html)

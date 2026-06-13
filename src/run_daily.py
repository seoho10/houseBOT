"""Daily summary entrypoint — runs at 08:30 KST via GitHub Actions."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.analyzer import detect_changes, summarize_by_size, top_n_lowest
from src.config import load_settings
from src.naver_scraper import fetch_listings
from src.sheets_store import SheetsStore
from src.telegram_notifier import (
    ComplexReport, format_daily_summary, format_error, send_message,
)


KST = timezone(timedelta(hours=9))
PRICE_CHANGE_THRESHOLD_PCT = 3.0
TOP_N = 3
DEDUP_WINDOW_MINUTES = 360  # skip if another host already ran daily within 6h


def _was_recently_run(store: SheetsStore, mode: str, max_minutes: int) -> bool:
    when_str = store.last_successful_run_for_mode(mode)
    if not isinstance(when_str, str) or not when_str:
        return False
    try:
        last = datetime.strptime(when_str, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except (ValueError, TypeError):
        return False
    diff_min = (datetime.now(KST) - last).total_seconds() / 60
    return 0 <= diff_min < max_minutes


def main() -> None:
    settings = load_settings()
    store = SheetsStore(settings.sheets_id, settings.google_sa_info)
    store.ensure_tabs()

    if _was_recently_run(store, "daily", DEDUP_WINDOW_MINUTES):
        print("Daily already ran within last 6h on another host - skipping.")
        return

    apartments = store.load_apartments()
    if not apartments:
        print("No active apartments - nothing to do.")
        return

    now = datetime.now(KST)
    today_str = now.strftime("%Y-%m-%d")
    when_str = now.strftime("%Y-%m-%d %H:%M")

    previous_all = store.load_latest()
    previous_by_complex: dict[str, list] = {}
    for l in previous_all:
        previous_by_complex.setdefault(l.complex_id, []).append(l)

    reports: list[ComplexReport] = []
    all_today: list = []
    all_events: list = []
    failures: list[str] = []

    for apt in apartments:
        try:
            today_listings = fetch_listings(apt.complex_id)
        except Exception as e:
            failures.append(f"{apt.name} ({apt.complex_id}): {e}")
            continue

        prev = previous_by_complex.get(apt.complex_id, [])
        events = detect_changes(prev, today_listings, threshold_pct=PRICE_CHANGE_THRESHOLD_PCT)
        summaries = summarize_by_size(today_listings)
        store.append_history(today_str, apt.complex_id, summaries)

        all_today.extend(today_listings)
        all_events.extend(events)

        new_listings = [
            l for l in today_listings
            if any(e.kind == "NEW_LISTING" and e.article_id == l.article_id for e in events)
        ]
        price_events = [e for e in events if e.kind == "PRICE_CHANGE"]
        reports.append(ComplexReport(
            apartment=apt,
            listings_today=today_listings,
            count_today=len(today_listings),
            count_yesterday=len(prev),
            size_summaries=summaries,
            new_listings=new_listings,
            price_changes=price_events,
            top_lowest=top_n_lowest(today_listings, TOP_N),
        ))

    if all_today:
        store.save_latest(all_today, scraped_at=when_str)
    if all_events:
        store.append_events(all_events, when=when_str)

    sheets_url = f"https://docs.google.com/spreadsheets/d/{settings.sheets_id}/edit"
    if reports:
        msg = format_daily_summary(today_str, reports, sheets_url)
        if failures:
            msg += "\n\n" + format_error("일부 단지 수집 실패:\n" + "\n".join(failures))
        send_message(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            html=msg,
            dry_run=settings.dry_run,
        )
    elif failures:
        send_message(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            html=format_error("일부 단지 수집 실패:\n" + "\n".join(failures)),
            dry_run=settings.dry_run,
        )

    store.append_run_log(
        when=when_str, mode="daily",
        result="SUCCESS" if not failures else "PARTIAL",
        complex_count=len(reports), listing_count=len(all_today),
        message=" | ".join(failures) if failures else "",
    )


if __name__ == "__main__":
    main()

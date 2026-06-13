"""Light change check entrypoint — runs every 2 hours 09-21 KST via GitHub Actions."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.analyzer import detect_changes
from src.config import load_settings
from src.naver_scraper import fetch_listings
from src.sheets_store import SheetsStore
from src.telegram_notifier import (
    ComplexChanges, format_error, format_light_check, send_message,
)


KST = timezone(timedelta(hours=9))
PRICE_CHANGE_THRESHOLD_PCT = 3.0


def main() -> None:
    settings = load_settings()
    store = SheetsStore(settings.sheets_id, settings.google_sa_info)
    store.ensure_tabs()
    apartments = store.load_apartments()
    if not apartments:
        return

    now = datetime.now(KST)
    when_str = now.strftime("%Y-%m-%d %H:%M")
    time_str = now.strftime("%H:%M")

    previous_all = store.load_latest()
    prev_by_complex: dict[str, list] = {}
    for l in previous_all:
        prev_by_complex.setdefault(l.complex_id, []).append(l)

    changes_per_complex: list[ComplexChanges] = []
    all_today: list = []
    all_events: list = []
    failures: list[str] = []

    for apt in apartments:
        try:
            today_listings = fetch_listings(apt.complex_id)
        except Exception as e:
            failures.append(f"{apt.name} ({apt.complex_id}): {e}")
            continue
        all_today.extend(today_listings)
        prev = prev_by_complex.get(apt.complex_id, [])
        events = detect_changes(prev, today_listings, threshold_pct=PRICE_CHANGE_THRESHOLD_PCT)
        new_event_ids = {e.article_id for e in events if e.kind == "NEW_LISTING"}
        new_listings = [l for l in today_listings if l.article_id in new_event_ids]
        price_events = [e for e in events if e.kind == "PRICE_CHANGE"]
        if new_listings or price_events:
            changes_per_complex.append(ComplexChanges(
                apartment=apt, new_listings=new_listings, price_changes=price_events,
            ))
            all_events.extend([e for e in events if e.kind in ("NEW_LISTING", "PRICE_CHANGE")])

    has_changes = bool(changes_per_complex)

    if has_changes:
        store.save_latest(all_today, scraped_at=when_str)
        store.append_events(all_events, when=when_str)
        msg = format_light_check(time_str, changes_per_complex)
        send_message(
            token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id,
            html=msg, dry_run=settings.dry_run,
        )

    if failures:
        send_message(
            token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id,
            html=format_error("일부 단지 수집 실패:\n" + "\n".join(failures)),
            dry_run=settings.dry_run,
        )

    store.append_run_log(
        when=when_str, mode="check",
        result="SUCCESS" if not failures else "PARTIAL",
        complex_count=len(apartments), listing_count=len(all_today),
        message="changes" if has_changes else "no-changes",
    )


if __name__ == "__main__":
    main()

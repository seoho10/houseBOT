"""Light change check entrypoint — runs every 2 hours 09-21 KST via GitHub Actions."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.analyzer import confirmed_on, detect_changes, lowest_by_size, summarize_by_size
from src.config import load_settings
from src.naver_scraper import fetch_listings
from src.sheets_store import SheetsStore
from src.telegram_notifier import (
    ComplexReport, format_check, format_error, send_message,
)


KST = timezone(timedelta(hours=9))
PRICE_CHANGE_THRESHOLD_PCT = 3.0
DEDUP_WINDOW_MINUTES = 30  # skip if another host already ran check within 30 min


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

    if _was_recently_run(store, "check", DEDUP_WINDOW_MINUTES):
        print("Check already ran within last 30 min on another host - skipping.")
        return

    apartments = store.load_apartments()
    if not apartments:
        return

    now = datetime.now(KST)
    when_str = now.strftime("%Y-%m-%d %H:%M")
    time_str = now.strftime("%H:%M")
    today_str = now.strftime("%Y-%m-%d")

    previous_all = store.load_latest()
    prev_by_complex: dict[str, list] = {}
    for l in previous_all:
        prev_by_complex.setdefault(l.complex_id, []).append(l)

    reports: list[ComplexReport] = []
    all_today: list = []
    all_events: list = []
    failures: list[str] = []
    has_changes = False

    for apt in apartments:
        try:
            today_listings = fetch_listings(apt.complex_id)
        except Exception as e:
            failures.append(f"{apt.name} ({apt.complex_id}): {e}")
            continue
        all_today.extend(today_listings)
        prev = prev_by_complex.get(apt.complex_id, [])
        events = detect_changes(prev, today_listings, threshold_pct=PRICE_CHANGE_THRESHOLD_PCT)

        # 변동 판정: 이전 스냅샷 대비 새로 등장 + 확인일자가 오늘인 매물, 또는 가격 변동.
        # (맨 위 '변동 없음' 표시 여부를 결정. diff 조건이 2시간마다 중복 변동 표시를 막는다.)
        new_event_ids = {e.article_id for e in events if e.kind == "NEW_LISTING"}
        changed_new = [
            l for l in confirmed_on(today_listings, today_str)
            if l.article_id in new_event_ids
        ]
        price_events = [e for e in events if e.kind == "PRICE_CHANGE"]
        if changed_new or price_events:
            has_changes = True
            all_events.extend([e for e in events if e.kind in ("NEW_LISTING", "PRICE_CHANGE")])

        # 디폴트 표시 블록은 일일 요약과 동일하게 구성한다.
        # 신규 매물 = 오늘 확인(등록)일자 매물 전체(상시 정보).
        reports.append(ComplexReport(
            apartment=apt,
            listings_today=today_listings,
            count_today=len(today_listings),
            count_yesterday=len(prev),
            size_summaries=summarize_by_size(today_listings),
            new_listings=confirmed_on(today_listings, today_str),
            price_changes=price_events,
            lowest_by_size=lowest_by_size(today_listings),
        ))

    if has_changes:
        store.save_latest(all_today, scraped_at=when_str)
        store.append_events(all_events, when=when_str)

    # 변동이 있든 없든 2시간마다 현재 상태(매물 수·시세·최저가·신규)를 항상 보낸다.
    # 단, 모든 단지 수집이 실패한 경우엔 오해를 줄 수 있어 보내지 않는다.
    all_failed = bool(failures) and not all_today
    if not all_failed:
        msg = format_check(time_str, reports, has_changes=has_changes)
        if failures:
            msg += "\n\n" + format_error("일부 단지 수집 실패:\n" + "\n".join(failures))
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

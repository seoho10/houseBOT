from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from src.models import Listing
from src.config import ApartmentConfig, Settings

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")


def _settings(dry=False):
    return Settings(
        telegram_bot_token="tok", telegram_chat_id="cid",
        sheets_id="sid", google_sa_info={"client_email": "x"},
        dry_run=dry,
    )


def _make_listing(article_id, complex_id, price, ymd="2026-06-12"):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label="84",
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd=ymd,
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


@patch("src.run_daily.send_message")
@patch("src.run_daily.fetch_listings")
@patch("src.run_daily.SheetsStore")
@patch("src.run_daily.load_settings")
def test_run_daily_happy_path(mock_load_settings, MockStore, mock_fetch, mock_send):
    mock_load_settings.return_value = _settings(dry=False)

    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = [_make_listing("a1", "8692", 130000)]

    mock_fetch.return_value = [
        _make_listing("a1", "8692", 125000),  # price drop
        _make_listing("a2", "8692", 140000),  # new listing
    ]

    from src.run_daily import main
    main()

    store.ensure_tabs.assert_called_once()
    store.save_latest.assert_called_once()
    store.append_history.assert_called_once()
    store.append_events.assert_called_once()
    store.append_run_log.assert_called_once()
    mock_send.assert_called_once()
    sent_text = mock_send.call_args.kwargs.get("html") or mock_send.call_args.args[2]
    assert "성복" in sent_text


@patch("src.run_daily.send_message")
@patch("src.run_daily.fetch_listings")
@patch("src.run_daily.SheetsStore")
@patch("src.run_daily.load_settings")
def test_run_daily_continues_on_single_complex_failure(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="A", complex_id="111", interested_sizes=(), active=True),
        ApartmentConfig(name="B", complex_id="222", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = []

    def fetch_side_effect(complex_id):
        if complex_id == "111":
            raise RuntimeError("Naver fetch failed for complex 111")
        return [_make_listing("a1", "222", 100000)]

    mock_fetch.side_effect = fetch_side_effect

    from src.run_daily import main
    main()  # should NOT raise

    mock_send.assert_called_once()


@patch("src.run_daily.send_message")
@patch("src.run_daily.fetch_listings")
@patch("src.run_daily.SheetsStore")
@patch("src.run_daily.load_settings")
def test_run_daily_new_listings_only_today(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = []  # empty -> diff would flag everything as new

    mock_fetch.return_value = [
        _make_listing("old1", "8692", 100000, ymd="2026-01-01"),
        _make_listing("old2", "8692", 110000, ymd="2026-01-02"),
        _make_listing("new1", "8692", 120000, ymd=TODAY),
    ]

    from src.run_daily import main
    main()

    sent_text = mock_send.call_args.kwargs.get("html") or mock_send.call_args.args[2]
    # Only the one confirmed today counts as 신규, not all three.
    assert "🆕 신규 매물 (1건)" in sent_text

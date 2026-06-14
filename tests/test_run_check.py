from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from src.config import ApartmentConfig, Settings
from src.models import Listing

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")


def _settings():
    return Settings(
        telegram_bot_token="tok", telegram_chat_id="cid", sheets_id="sid",
        google_sa_info={"client_email": "x"}, dry_run=False,
    )


def _make_listing(article_id, complex_id, price, ymd="2026-06-12"):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label="84",
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd=ymd,
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


@patch("src.run_check.send_message")
@patch("src.run_check.fetch_listings")
@patch("src.run_check.SheetsStore")
@patch("src.run_check.load_settings")
def test_run_check_sends_no_change_message(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = [_make_listing("a1", "8692", 125000)]
    mock_fetch.return_value = [_make_listing("a1", "8692", 125000)]  # identical

    from src.run_check import main
    main()

    # 변동이 없어도 "변동 없음" 메시지를 항상 보낸다.
    mock_send.assert_called_once()
    assert "변동 없음" in mock_send.call_args.kwargs["html"]
    store.save_latest.assert_not_called()  # no change → no overwrite needed


@patch("src.run_check.send_message")
@patch("src.run_check.fetch_listings")
@patch("src.run_check.SheetsStore")
@patch("src.run_check.load_settings")
def test_run_check_sends_when_new_listing(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = [_make_listing("a1", "8692", 125000)]
    mock_fetch.return_value = [
        _make_listing("a1", "8692", 125000),
        _make_listing("a2", "8692", 130000, ymd=TODAY),  # new + confirmed today
    ]

    from src.run_check import main
    main()

    mock_send.assert_called_once()
    store.save_latest.assert_called_once()
    store.append_events.assert_called_once()


@patch("src.run_check.send_message")
@patch("src.run_check.fetch_listings")
@patch("src.run_check.SheetsStore")
@patch("src.run_check.load_settings")
def test_run_check_ignores_new_listing_not_confirmed_today(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = [_make_listing("a1", "8692", 125000)]
    mock_fetch.return_value = [
        _make_listing("a1", "8692", 125000),
        _make_listing("a2", "8692", 130000, ymd="2026-01-01"),  # new to us, but old confirm date
    ]

    from src.run_check import main
    main()

    # newly-appeared but not confirmed today -> not a 신규 alert, no price change
    # -> still sends a "변동 없음" message (2시간마다 항상 발송)
    mock_send.assert_called_once()
    assert "변동 없음" in mock_send.call_args.kwargs["html"]

from unittest.mock import MagicMock
from src.sheets_store import SheetsStore, REQUIRED_TABS


def test_ensure_tabs_creates_missing(mocker):
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book

    # Only 'settings' exists
    existing_ws = MagicMock()
    existing_ws.title = "settings"
    fake_book.worksheets.return_value = [existing_ws]

    store = SheetsStore(sheets_id="abc", sa_info={"client_email": "x"}, client=fake_client)
    store.ensure_tabs()

    added_titles = {call.kwargs.get("title") or call.args[0] for call in fake_book.add_worksheet.call_args_list}
    expected_missing = set(REQUIRED_TABS) - {"settings"}
    assert added_titles == expected_missing


def test_ensure_tabs_idempotent_when_all_present(mocker):
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book

    wsets = [MagicMock() for _ in REQUIRED_TABS]
    for ws, name in zip(wsets, REQUIRED_TABS):
        ws.title = name
    fake_book.worksheets.return_value = wsets

    store = SheetsStore(sheets_id="abc", sa_info={"client_email": "x"}, client=fake_client)
    store.ensure_tabs()

    fake_book.add_worksheet.assert_not_called()


from src.config import ApartmentConfig


def _stub_book_with_settings(rows):
    """Build a fake gspread book whose 'settings' tab returns `rows` (excluding header)."""
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book

    settings_ws = MagicMock()
    settings_ws.title = "settings"
    settings_ws.get_all_values.return_value = [
        ["단지명", "단지ID", "관심평형", "활성화"],
    ] + rows
    fake_book.worksheets.return_value = [settings_ws]
    fake_book.worksheet.return_value = settings_ws
    return fake_client, fake_book


def test_load_apartments_returns_active_only():
    rows = [
        ["성복", "8692", "", "TRUE"],
        ["서원", "8425", "84, 114", "TRUE"],
        ["꺼진단지", "9999", "", "FALSE"],
    ]
    fake_client, _ = _stub_book_with_settings(rows)
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    apts = store.load_apartments()
    assert len(apts) == 2
    assert apts[0].name == "성복"
    assert apts[0].complex_id == "8692"
    assert apts[0].interested_sizes == ()
    assert apts[1].interested_sizes == ("84", "114")


def test_load_apartments_handles_empty():
    fake_client, _ = _stub_book_with_settings([])
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)
    assert store.load_apartments() == []


from src.models import Listing


def _stub_book_with_tab(tab_name, rows_inc_header):
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book
    ws = MagicMock()
    ws.title = tab_name
    ws.get_all_values.return_value = rows_inc_header
    fake_book.worksheets.return_value = [ws]
    fake_book.worksheet.return_value = ws
    return fake_client, fake_book, ws


def _make_listing(article_id="a1", complex_id="8692", price=125000):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label="84",
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


def test_save_latest_clears_and_writes():
    fake_client, _, ws = _stub_book_with_tab(
        "latest",
        [["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    listings = [_make_listing("a1"), _make_listing("a2", price=130000)]
    store.save_latest(listings, scraped_at="2026-06-13 08:30")

    ws.clear.assert_called_once()
    update_calls = ws.update.call_args_list
    assert update_calls[0].args[0] == "A1"
    written_rows = update_calls[0].args[1]
    assert written_rows[0][0] == "단지ID"
    assert len(written_rows) == 1 + 2


def test_load_latest_parses_rows():
    fake_client, _, ws = _stub_book_with_tab(
        "latest",
        [
            ["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"],
            ["8692", "a1", "84", "125000", "101동", "10층", "남향", "2026-06-12",
             "https://new.land.naver.com/complexes/8692?articleNo=a1", "2026-06-13 08:30"],
        ],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    listings = store.load_latest()
    assert len(listings) == 1
    assert listings[0].article_id == "a1"
    assert listings[0].price_manwon == 125000
    assert listings[0].complex_id == "8692"


def test_load_latest_empty_returns_empty():
    fake_client, _, _ = _stub_book_with_tab(
        "latest",
        [["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)
    assert store.load_latest() == []


from src.models import Event, SizeSummary


def test_append_history_writes_one_row_per_size():
    fake_client, _, ws = _stub_book_with_tab(
        "history",
        [["날짜", "단지ID", "평형", "매물수", "최저가", "평균가", "최고가"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    summaries = {
        "84": SizeSummary("84", count=3, min_price=125000, avg_price=129000, max_price=132000),
        "114": SizeSummary("114", count=2, min_price=180000, avg_price=185000, max_price=190000),
    }
    store.append_history(date="2026-06-13", complex_id="8692", summaries=summaries)

    ws.append_rows.assert_called_once()
    rows_written = ws.append_rows.call_args.args[0]
    assert len(rows_written) == 2


def test_append_events_writes_each_event():
    fake_client, _, ws = _stub_book_with_tab(
        "events",
        [["시각", "종류", "단지ID", "매물ID", "상세", "매물URL"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    events = [
        Event(kind="NEW_LISTING", complex_id="8692", article_id="a1",
              detail="84㎡, 12억", article_url="https://x/a1"),
        Event(kind="PRICE_CHANGE", complex_id="8692", article_id="a2",
              detail="84㎡: 130000 → 125000", article_url="https://x/a2"),
    ]
    store.append_events(events, when="2026-06-13 10:30")

    ws.append_rows.assert_called_once()
    rows = ws.append_rows.call_args.args[0]
    assert len(rows) == 2
    assert rows[0][1] == "NEW_LISTING"


def test_append_run_log_writes_one_row():
    fake_client, _, ws = _stub_book_with_tab(
        "run_log",
        [["시각", "모드", "결과", "단지수", "매물수", "메시지"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    store.append_run_log(when="2026-06-13 08:30", mode="daily",
                         result="SUCCESS", complex_count=2, listing_count=17, message="")

    ws.append_row.assert_called_once()
    row = ws.append_row.call_args.args[0]
    assert row[1] == "daily" and row[2] == "SUCCESS"

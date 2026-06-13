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

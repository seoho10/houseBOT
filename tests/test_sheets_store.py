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

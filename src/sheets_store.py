"""Google Sheets persistence layer for houseBOT."""
from __future__ import annotations

from typing import Optional

import gspread
from google.oauth2.service_account import Credentials


REQUIRED_TABS = ("settings", "latest", "history", "events", "run_log")

_HEADERS = {
    "settings": ["단지명", "단지ID", "관심평형", "활성화"],
    "latest": ["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"],
    "history": ["날짜", "단지ID", "평형", "매물수", "최저가", "평균가", "최고가"],
    "events": ["시각", "종류", "단지ID", "매물ID", "상세", "매물URL"],
    "run_log": ["시각", "모드", "결과", "단지수", "매물수", "메시지"],
}

_DEFAULT_SETTINGS_ROWS = [
    ["성복역현대홈타운", "8692", "", "TRUE"],
    ["서원마을3단지아이파크", "8425", "", "TRUE"],
]


def _new_client(sa_info: dict) -> gspread.Client:
    creds = Credentials.from_service_account_info(
        sa_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


class SheetsStore:
    def __init__(
        self,
        sheets_id: str,
        sa_info: dict,
        client: Optional[gspread.Client] = None,
    ):
        self._client = client or _new_client(sa_info)
        self._book = self._client.open_by_key(sheets_id)

    def ensure_tabs(self) -> None:
        existing = {ws.title for ws in self._book.worksheets()}
        for tab in REQUIRED_TABS:
            if tab in existing:
                continue
            ws = self._book.add_worksheet(title=tab, rows=200, cols=20)
            ws.update("A1", [_HEADERS[tab]])
            if tab == "settings":
                ws.update("A2", _DEFAULT_SETTINGS_ROWS)

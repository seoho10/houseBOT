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
                ws = self._book.worksheet(tab)
                values = ws.get_all_values()
                is_empty = not values or all(
                    not any(cell.strip() for cell in row) for row in values
                )
                if is_empty:
                    ws.update("A1", [_HEADERS[tab]])
                    if tab == "settings":
                        ws.update("A2", _DEFAULT_SETTINGS_ROWS)
                continue
            ws = self._book.add_worksheet(title=tab, rows=200, cols=20)
            ws.update("A1", [_HEADERS[tab]])
            if tab == "settings":
                ws.update("A2", _DEFAULT_SETTINGS_ROWS)

    def save_latest(self, listings: list["Listing"], scraped_at: str) -> None:
        ws = self._book.worksheet("latest")
        ws.clear()
        header = _HEADERS["latest"]
        rows = [header]
        for l in listings:
            rows.append([
                l.complex_id, l.article_id, l.size_label, str(l.price_manwon),
                l.building, l.floor, l.direction, l.registered_ymd,
                l.article_url, scraped_at,
            ])
        ws.update("A1", rows)

    def load_latest(self) -> list["Listing"]:
        from src.models import Listing
        ws = self._book.worksheet("latest")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        result = []
        for row in rows[1:]:
            row = (row + [""] * 10)[:10]
            complex_id, article_id, size, price_str, building, floor, direction, ymd, url, _scraped = row
            if not article_id.strip():
                continue
            try:
                price = int(price_str)
            except ValueError:
                continue
            result.append(Listing(
                article_id=article_id, complex_id=complex_id, size_label=size,
                size_sqm=0.0, price_manwon=price, building=building, floor=floor,
                direction=direction, registered_ymd=ymd, article_url=url,
            ))
        return result

    def append_history(
        self, date: str, complex_id: str, summaries: dict[str, "SizeSummary"]
    ) -> None:
        ws = self._book.worksheet("history")
        rows = [
            [date, complex_id, s.size_label, s.count, s.min_price, s.avg_price, s.max_price]
            for s in summaries.values()
        ]
        if rows:
            ws.append_rows(rows)

    def append_events(self, events: list["Event"], when: str) -> None:
        if not events:
            return
        ws = self._book.worksheet("events")
        rows = [
            [when, e.kind, e.complex_id, e.article_id, e.detail, e.article_url]
            for e in events
        ]
        ws.append_rows(rows)

    def append_run_log(
        self, when: str, mode: str, result: str,
        complex_count: int, listing_count: int, message: str = ""
    ) -> None:
        ws = self._book.worksheet("run_log")
        ws.append_row([when, mode, result, complex_count, listing_count, message])

    def last_successful_run_for_mode(self, mode: str) -> str | None:
        """Return the 'when' string of the most recent fully-successful run for `mode`,
        or None. PARTIAL or all-failed runs are treated as not-yet-run so other
        hosts will retry. Used by multi-host dedup."""
        ws = self._book.worksheet("run_log")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return None
        for row in reversed(rows[1:]):
            row = (row + [""] * 6)[:6]
            when, log_mode, result, _, listing_count_str, _ = row
            if log_mode != mode:
                continue
            if result == "SUCCESS":
                return when
            # PARTIAL counts as success only when at least some listings were captured
            if result == "PARTIAL":
                try:
                    if int(listing_count_str) > 0:
                        return when
                except (ValueError, TypeError):
                    pass
        return None

    def load_apartments(self) -> list["ApartmentConfig"]:
        from src.config import ApartmentConfig  # local import to avoid circularity
        ws = self._book.worksheet("settings")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        result = []
        for row in rows[1:]:
            row = (row + ["", "", "", ""])[:4]
            name, complex_id, sizes_raw, active_raw = row
            if not complex_id.strip():
                continue
            active = active_raw.strip().upper() == "TRUE"
            if not active:
                continue
            sizes = tuple(s.strip() for s in sizes_raw.split(",") if s.strip())
            result.append(ApartmentConfig(
                name=name.strip(),
                complex_id=complex_id.strip(),
                interested_sizes=sizes,
                active=True,
            ))
        return result

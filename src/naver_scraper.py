"""Naver real-estate scraping. Network code lives here; parsing helpers too."""
from __future__ import annotations

import re
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.models import Listing


_EOK_RE = re.compile(r"^\s*(\d+)\s*억(?:\s*([\d,]+))?\s*$")


def parse_korean_price(raw: str) -> int:
    """Convert Naver price strings to 만원 units.

    Examples:
        "5,000"      -> 5000
        "8억"        -> 80000
        "12억 5,000" -> 125000
    """
    if not raw:
        return 0
    s = raw.strip()
    m = _EOK_RE.match(s)
    if m:
        eok = int(m.group(1))
        rest_str = (m.group(2) or "0").replace(",", "")
        rest = int(rest_str) if rest_str else 0
        return eok * 10000 + rest
    plain = s.replace(",", "")
    if not plain.isdigit():
        raise ValueError(f"Unparseable price: {raw!r}")
    return int(plain)


def parse_listings(response: dict, complex_id: str) -> list[Listing]:
    """Convert a Naver `/api/articles/complex/{id}` JSON response into Listings.

    Filters out non-sale (non-A1) trade types.
    """
    if "articleList" not in response:
        raise ValueError("Naver response missing 'articleList' key")

    listings: list[Listing] = []
    for item in response["articleList"]:
        if item.get("tradeTypeCode") != "A1":
            continue
        article_id = str(item["articleNo"])
        size_sqm = float(item.get("area2") or 0.0)
        size_label = str(round(size_sqm)) if size_sqm else "?"
        price_manwon = parse_korean_price(item.get("dealOrWarrantPrc", ""))
        building = item.get("buildingName", "") or ""
        floor_raw = item.get("floorInfo", "") or ""
        floor = _format_floor(floor_raw)
        direction = item.get("direction", "") or ""
        ymd_raw = item.get("articleConfirmYmd", "") or ""
        registered_ymd = _format_ymd(ymd_raw)
        url = f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}"

        listings.append(Listing(
            article_id=article_id,
            complex_id=complex_id,
            size_label=size_label,
            size_sqm=size_sqm,
            price_manwon=price_manwon,
            building=building,
            floor=floor,
            direction=direction,
            registered_ymd=registered_ymd,
            article_url=url,
        ))
    return listings


def _format_floor(raw: str) -> str:
    """'10/15' -> '10층'.  '저/15' or '저층' -> '저층'.  '' -> ''."""
    if not raw:
        return ""
    if "/" in raw:
        cur = raw.split("/", 1)[0]
        return f"{cur}층"
    return raw


def _format_ymd(raw: str) -> str:
    """'20260612' -> '2026-06-12'.  Anything else -> ''."""
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return ""


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_BASE_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://new.land.naver.com/",
    "Origin": "https://new.land.naver.com",
    "sec-ch-ua": '"Chromium";v="120", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
_REQUEST_DELAY_SEC = 1.5
_MAX_PAGES = 20


class NaverFetchError(RuntimeError):
    pass


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _get_page(client: httpx.Client, complex_id: str, page: int) -> dict:
    resp = client.get(
        f"https://new.land.naver.com/api/articles/complex/{complex_id}",
        params={"realEstateType": "APT", "tradeType": "A1", "order": "rank", "page": page},
        headers={**_BASE_HEADERS, "Referer": f"https://new.land.naver.com/complexes/{complex_id}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def _warm_up(client: httpx.Client, complex_id: str) -> None:
    """Hit the complex page once so the API call looks like a normal browser session."""
    try:
        client.get(
            f"https://new.land.naver.com/complexes/{complex_id}",
            headers=_BASE_HEADERS,
            timeout=15.0,
        )
    except Exception:
        pass  # best-effort; main API call still has its own retries


def fetch_listings(complex_id: str) -> list[Listing]:
    """Fetch all sale listings for a complex, paginated, with retry."""
    all_listings: list[Listing] = []
    try:
        with httpx.Client(http2=False, follow_redirects=True) as client:
            _warm_up(client, complex_id)
            time.sleep(_REQUEST_DELAY_SEC)
            for page in range(1, _MAX_PAGES + 1):
                if page > 1:
                    time.sleep(_REQUEST_DELAY_SEC)
                data = _get_page(client, complex_id, page)
                all_listings.extend(parse_listings(data, complex_id=complex_id))
                if not data.get("isMoreData"):
                    break
    except Exception as e:
        raise RuntimeError(
            f"Naver fetch failed for complex {complex_id} after retries: {e}"
        ) from e
    return all_listings

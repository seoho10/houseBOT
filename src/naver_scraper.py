"""Naver real-estate scraping. Network code lives here; parsing helpers too."""
from __future__ import annotations

import re

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

"""Naver real-estate scraping. Network code lives here; parsing helpers too."""
from __future__ import annotations

import re


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

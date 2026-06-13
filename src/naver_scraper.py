"""Naver real-estate scraping. Network code lives here; parsing helpers too.

The Naver article API (`/api/articles/complex/{id}`) rejects plain HTTP clients
with 401 ("unauthorized user"): it requires BOTH the session cookies set during a
real page load AND an `Authorization: Bearer <JWT>` header that the web app mints
client-side. We drive a headless Chromium (Playwright) to obtain both, then issue
the paginated fetches from inside the page context so cookies ride along for free
and we attach the captured token. See `_browser_fetch_pages`.
"""
from __future__ import annotations

import re
import time

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
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_REQUEST_DELAY_SEC = 1.0
_MAX_PAGES = 20
_NAV_TIMEOUT_MS = 45000
_TOKEN_WAIT_TICKS = 40       # 40 * 250ms = 10s to capture the auth token
_TOKEN_WAIT_MS = 250
_BROWSER_ATTEMPTS = 3

# Runs inside the page context: same-origin `fetch` carries Naver's session
# cookies automatically; we attach the JWT the web app uses. Returns the parsed
# JSON on success, or {__status, __body} so Python can raise on non-200.
_FETCH_JS = """async ({cid, page, token}) => {
  const url = `https://new.land.naver.com/api/articles/complex/${cid}`
    + `?realEstateType=APT&tradeType=A1&order=rank&page=${page}`;
  const r = await fetch(url, {headers: {'Accept': 'application/json', 'Authorization': token}});
  if (!r.ok) return {__status: r.status, __body: (await r.text()).slice(0, 300)};
  return await r.json();
}"""


def _paginate(get_one_page) -> list[dict]:
    """Walk pages via `get_one_page(page_num) -> dict` until isMoreData is falsey.

    Pulled out so the stop logic is unit-testable without a live browser.
    """
    pages: list[dict] = []
    for page_num in range(1, _MAX_PAGES + 1):
        data = get_one_page(page_num)
        pages.append(data)
        if not data.get("isMoreData"):
            break
    return pages


def _browser_fetch_once(complex_id: str) -> list[dict]:
    """One headless-browser session: load the complex page, capture the auth
    token from the app's own article request, then fetch every sale page."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(
                user_agent=_USER_AGENT,
                locale="ko-KR",
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()

            token: dict[str, str] = {}

            def _on_request(req) -> None:
                if "/api/articles/complex/" in req.url and "auth" not in token:
                    auth = req.all_headers().get("authorization")
                    if auth:
                        token["auth"] = auth

            page.on("request", _on_request)
            page.goto(
                f"https://new.land.naver.com/complexes/{complex_id}",
                wait_until="networkidle",
                timeout=_NAV_TIMEOUT_MS,
            )

            for _ in range(_TOKEN_WAIT_TICKS):
                if "auth" in token:
                    break
                page.wait_for_timeout(_TOKEN_WAIT_MS)
            if "auth" not in token:
                raise RuntimeError("could not obtain Naver auth token from page session")

            def _get_one_page(page_num: int) -> dict:
                if page_num > 1:
                    page.wait_for_timeout(int(_REQUEST_DELAY_SEC * 1000))
                data = page.evaluate(
                    _FETCH_JS, {"cid": complex_id, "page": page_num, "token": token["auth"]}
                )
                status = data.get("__status")
                if status is not None:
                    raise RuntimeError(
                        f"article API returned {status}: {data.get('__body', '')}"
                    )
                return data

            return _paginate(_get_one_page)
        finally:
            browser.close()


def _browser_fetch_pages(complex_id: str) -> list[dict]:
    """`_browser_fetch_once` with retries. A fresh session re-mints the token,
    so retrying also recovers from token/401 hiccups, not just network blips."""
    last_err: Exception | None = None
    for attempt in range(_BROWSER_ATTEMPTS):
        try:
            return _browser_fetch_once(complex_id)
        except Exception as e:  # noqa: BLE001 - surfaced via fetch_listings wrapper
            last_err = e
            if attempt < _BROWSER_ATTEMPTS - 1:
                time.sleep(2 * (attempt + 1))
    assert last_err is not None
    raise last_err


def fetch_listings(complex_id: str, *, page_fetcher=None) -> list[Listing]:
    """Fetch all sale (A1) listings for a complex, paginated.

    `page_fetcher(complex_id) -> list[dict]` is an injection seam for tests;
    it defaults to the Playwright browser fetcher.
    """
    fetch = page_fetcher or _browser_fetch_pages
    try:
        raw_pages = fetch(complex_id)
    except Exception as e:
        raise RuntimeError(f"Naver fetch failed for complex {complex_id}: {e}") from e

    all_listings: list[Listing] = []
    for data in raw_pages:
        all_listings.extend(parse_listings(data, complex_id=complex_id))
    return all_listings

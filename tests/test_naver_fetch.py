import json
import os
import httpx
import pytest
import respx

from src.naver_scraper import fetch_listings


@respx.mock
def test_fetch_listings_single_page(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        resp = json.load(f)

    url = "https://new.land.naver.com/api/articles/complex/8692"
    respx.get(url).mock(return_value=httpx.Response(200, json=resp))

    listings = fetch_listings("8692")
    assert len(listings) == 2


@respx.mock
def test_fetch_listings_paginates(fixture_dir):
    page1 = {
        "isMoreData": True,
        "articleList": [
            {"articleNo": "p1a", "tradeTypeCode": "A1", "dealOrWarrantPrc": "10억",
             "area1": 84.0, "area2": 59.0, "direction": "남", "articleConfirmYmd": "20260601",
             "buildingName": "101동", "floorInfo": "5/15"}
        ],
    }
    page2 = {
        "isMoreData": False,
        "articleList": [
            {"articleNo": "p2a", "tradeTypeCode": "A1", "dealOrWarrantPrc": "11억",
             "area1": 84.0, "area2": 60.0, "direction": "동", "articleConfirmYmd": "20260602",
             "buildingName": "102동", "floorInfo": "8/15"}
        ],
    }
    route = respx.get("https://new.land.naver.com/api/articles/complex/8692")
    route.side_effect = [httpx.Response(200, json=page1), httpx.Response(200, json=page2)]

    listings = fetch_listings("8692")
    assert {l.article_id for l in listings} == {"p1a", "p2a"}


@respx.mock
def test_fetch_listings_retries_on_5xx(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        ok_resp = json.load(f)

    route = respx.get("https://new.land.naver.com/api/articles/complex/8692")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(200, json=ok_resp),
    ]

    listings = fetch_listings("8692")
    assert len(listings) == 2


@respx.mock
def test_fetch_listings_raises_after_max_retries():
    route = respx.get("https://new.land.naver.com/api/articles/complex/8692")
    route.side_effect = [httpx.Response(503)] * 10

    with pytest.raises(RuntimeError, match="failed"):
        fetch_listings("8692")

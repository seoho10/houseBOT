import json
import os

import pytest

from src.naver_scraper import _MAX_PAGES, _paginate, fetch_listings


def test_fetch_listings_single_page(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        resp = json.load(f)

    listings = fetch_listings("8692", page_fetcher=lambda cid: [resp])
    assert len(listings) == 2


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

    listings = fetch_listings("8692", page_fetcher=lambda cid: [page1, page2])
    assert {l.article_id for l in listings} == {"p1a", "p2a"}


def test_fetch_listings_wraps_fetch_errors():
    def boom(cid):
        raise RuntimeError("could not obtain Naver auth token from page session")

    with pytest.raises(RuntimeError, match="failed"):
        fetch_listings("8692", page_fetcher=boom)


def test_paginate_stops_on_is_more_data_false():
    pages = [
        {"isMoreData": True, "articleList": []},
        {"isMoreData": True, "articleList": []},
        {"isMoreData": False, "articleList": []},
        {"isMoreData": True, "articleList": []},  # must never be reached
    ]
    seen = []

    def get_one(n):
        seen.append(n)
        return pages[n - 1]

    out = _paginate(get_one)
    assert len(out) == 3
    assert seen == [1, 2, 3]


def test_paginate_honors_max_pages():
    def get_one(n):
        return {"isMoreData": True, "articleList": []}  # never stops on its own

    out = _paginate(get_one)
    assert len(out) == _MAX_PAGES

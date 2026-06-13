import json
import os
from src.naver_scraper import parse_listings


def test_parse_listings_filters_to_sale_only(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        resp = json.load(f)

    listings = parse_listings(resp, complex_id="8692")

    # Third one is 전세, should be filtered out
    assert len(listings) == 2
    assert all(l.complex_id == "8692" for l in listings)


def test_parse_listings_extracts_fields(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        resp = json.load(f)

    listings = parse_listings(resp, complex_id="8692")

    first = next(l for l in listings if l.article_id == "2425167890")
    assert first.price_manwon == 125000
    assert first.size_label == "85"  # round(84.92) = 85
    assert first.size_sqm == 84.92
    assert first.direction == "남향"
    assert first.building == "101동"
    assert first.floor == "10층"
    assert first.registered_ymd == "2026-06-12"
    assert first.article_url == "https://new.land.naver.com/complexes/8692?articleNo=2425167890"

    second = next(l for l in listings if l.article_id == "2425167891")
    assert second.price_manwon == 180000
    assert second.size_label == "115"  # round(114.7) = 115


def test_parse_listings_empty_response(fixture_dir):
    assert parse_listings({"articleList": []}, complex_id="8692") == []


def test_parse_listings_missing_articleList_raises():
    import pytest
    with pytest.raises(ValueError, match="articleList"):
        parse_listings({"isMoreData": False}, complex_id="8692")

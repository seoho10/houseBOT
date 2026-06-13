import pytest
from src.naver_scraper import parse_korean_price


@pytest.mark.parametrize("raw,expected", [
    ("5,000", 5000),
    ("8억", 80000),
    ("10억", 100000),
    ("12억 5,000", 125000),
    ("12억 5,500", 125500),
    ("1억", 10000),
    ("1억 1,234", 11234),
    ("3,500", 3500),
])
def test_parse_korean_price(raw, expected):
    assert parse_korean_price(raw) == expected


def test_parse_korean_price_empty_returns_zero():
    assert parse_korean_price("") == 0


def test_parse_korean_price_invalid_raises():
    with pytest.raises(ValueError):
        parse_korean_price("abc")

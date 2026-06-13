from src.models import Listing
from src.analyzer import detect_changes


def L(article_id="a1", complex_id="8692", price=125000, size="84"):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label=size,
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


def test_detect_new_listing():
    prev = []
    curr = [L(article_id="a1")]
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert len(events) == 1
    assert events[0].kind == "NEW_LISTING"
    assert events[0].article_id == "a1"


def test_detect_removed_listing():
    prev = [L(article_id="a1")]
    curr = []
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert len(events) == 1
    assert events[0].kind == "LISTING_REMOVED"


def test_detect_price_change_above_threshold():
    prev = [L(article_id="a1", price=130000)]
    curr = [L(article_id="a1", price=125000)]  # -3.85%, above 3% threshold
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert len(events) == 1
    assert events[0].kind == "PRICE_CHANGE"
    assert "130000" in events[0].detail and "125000" in events[0].detail


def test_price_change_below_threshold_ignored():
    prev = [L(article_id="a1", price=130000)]
    curr = [L(article_id="a1", price=129000)]  # -0.77%, below threshold
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert events == []


def test_unchanged_listing_produces_no_event():
    prev = [L(article_id="a1", price=130000)]
    curr = [L(article_id="a1", price=130000)]
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert events == []


def test_multiple_changes_in_one_call():
    prev = [L(article_id="a1", price=130000), L(article_id="a2", price=140000)]
    curr = [L(article_id="a1", price=120000), L(article_id="a3", price=150000)]
    events = detect_changes(prev, curr, threshold_pct=3.0)
    kinds = sorted(e.kind for e in events)
    assert kinds == ["LISTING_REMOVED", "NEW_LISTING", "PRICE_CHANGE"]

from src.models import Listing
from src.analyzer import confirmed_on, detect_changes


def L(article_id="a1", complex_id="8692", price=125000, size="84", ymd="2026-06-12"):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label=size,
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd=ymd,
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


def test_confirmed_on_keeps_only_matching_date():
    listings = [
        L(article_id="today1", ymd="2026-06-14"),
        L(article_id="old1", ymd="2026-06-12"),
        L(article_id="today2", ymd="2026-06-14"),
    ]
    out = confirmed_on(listings, "2026-06-14")
    assert {l.article_id for l in out} == {"today1", "today2"}


def test_confirmed_on_empty_when_none_match():
    assert confirmed_on([L(ymd="2026-06-12")], "2026-06-14") == []


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


from src.analyzer import summarize_by_size, top_n_lowest


def test_summarize_by_size_groups_correctly():
    listings = [
        L(article_id="a1", price=125000, size="84"),
        L(article_id="a2", price=130000, size="84"),
        L(article_id="a3", price=132000, size="84"),
        L(article_id="a4", price=180000, size="114"),
        L(article_id="a5", price=190000, size="114"),
    ]
    by_size = summarize_by_size(listings)
    assert set(by_size.keys()) == {"84", "114"}

    s84 = by_size["84"]
    assert s84.count == 3
    assert s84.min_price == 125000
    assert s84.max_price == 132000
    assert s84.avg_price == 129000  # (125000+130000+132000)/3 = 129000

    s114 = by_size["114"]
    assert s114.count == 2
    assert s114.min_price == 180000
    assert s114.avg_price == 185000


def test_summarize_empty():
    assert summarize_by_size([]) == {}


def test_top_n_lowest_returns_cheapest():
    listings = [
        L(article_id="a1", price=130000),
        L(article_id="a2", price=125000),
        L(article_id="a3", price=128000),
        L(article_id="a4", price=132000),
    ]
    top3 = top_n_lowest(listings, n=3)
    prices = [l.price_manwon for l in top3]
    assert prices == [125000, 128000, 130000]


def test_top_n_lowest_fewer_than_n():
    listings = [L(article_id="a1", price=130000)]
    assert len(top_n_lowest(listings, n=3)) == 1

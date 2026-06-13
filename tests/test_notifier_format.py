from src.models import Listing, Event, SizeSummary
from src.config import ApartmentConfig
from src.telegram_notifier import format_daily_summary, ComplexReport


def _listing(article_id="a1", complex_id="8692", price=125000, size="84"):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label=size,
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


def test_format_daily_summary_includes_complex_name_with_link():
    apt = ApartmentConfig(name="성복역현대홈타운", complex_id="8692", interested_sizes=(), active=True)
    report = ComplexReport(
        apartment=apt,
        listings_today=[_listing("a1"), _listing("a2", price=130000)],
        count_today=2,
        count_yesterday=2,
        size_summaries={"84": SizeSummary("84", 2, 125000, 127500, 130000)},
        new_listings=[],
        price_changes=[],
        top_lowest=[_listing("a1")],
    )

    text = format_daily_summary(
        date="2026-06-14", reports=[report],
        sheets_url="https://docs.google.com/spreadsheets/d/abc/edit",
    )

    assert "houseBOT" in text
    assert "2026-06-14" in text
    assert '<a href="https://new.land.naver.com/complexes/8692">성복역현대홈타운</a>' in text
    assert "84㎡" in text
    assert '<a href="https://docs.google.com/spreadsheets/d/abc/edit">' in text


def test_format_daily_summary_renders_new_and_price_changes():
    apt = ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True)
    new_l = _listing("a3", price=148000)
    price_change_event = Event(
        kind="PRICE_CHANGE", complex_id="8692", article_id="a1",
        detail="84㎡: 130000 → 125000 (-3.8%)",
        article_url="https://new.land.naver.com/complexes/8692?articleNo=a1",
    )
    report = ComplexReport(
        apartment=apt,
        listings_today=[_listing("a1"), new_l],
        count_today=2, count_yesterday=1,
        size_summaries={"84": SizeSummary("84", 2, 125000, 136500, 148000)},
        new_listings=[new_l],
        price_changes=[price_change_event],
        top_lowest=[_listing("a1")],
    )
    text = format_daily_summary("2026-06-14", [report], "https://x")

    assert "🆕" in text
    assert '<a href="' + new_l.article_url + '">' in text
    assert "📉" in text
    assert "-3.8%" in text


from src.telegram_notifier import format_light_check, format_error, ComplexChanges


def test_format_light_check_skipped_when_no_changes():
    """Caller should not call format_light_check if no changes; assert it raises."""
    import pytest
    with pytest.raises(ValueError, match="no changes"):
        format_light_check(time="12:30", complex_changes=[])


def test_format_light_check_renders_new_and_price():
    apt = ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True)
    new_l = _listing("a3", price=130000)
    price_event = Event(
        kind="PRICE_CHANGE", complex_id="8692", article_id="a1",
        detail="145㎡: 195000 → 188000 (-3.6%)",
        article_url="https://new.land.naver.com/complexes/8692?articleNo=a1",
    )
    changes = ComplexChanges(apartment=apt, new_listings=[new_l], price_changes=[price_event])
    text = format_light_check("12:30", [changes])

    assert "🔔" in text
    assert "12:30" in text
    assert "성복" in text
    assert "신규 매물 1건" in text
    assert "가격 변동 1건" in text
    assert "-3.6%" in text


def test_format_error_renders_message():
    text = format_error("네이버 API 구조 변경 감지\n단지: 성복 (8692)\n원인: 'dealPrice' 누락")
    assert "🚨" in text
    assert "성복" in text

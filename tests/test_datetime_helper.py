"""Test helper waktu (WIB <-> UTC)."""
from datetime import date, datetime, timezone
from app.utils.datetime_helper import build_utc_range_from_local_date

def test_build_utc_range_from_local_date():
    """Positive: 29 Sep WIB = 28 Sep 17:00 UTC s/d 29 Sep 17:00 UTC."""
    start_at, end_at = build_utc_range_from_local_date(date(2026, 9, 29), date(2026, 9, 29))
    assert start_at == datetime(2026, 9, 28, 17, 0, tzinfo=timezone.utc)
    assert end_at == datetime(2026, 9, 29, 17, 0, tzinfo=timezone.utc)

def test_build_utc_range_without_date():
    """Positive: ga ada tanggal -> ga ada batas."""
    assert build_utc_range_from_local_date() == (None, None)
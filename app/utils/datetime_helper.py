"""Helper waktu. Semua waktu di app pake UTC, pas ditampilin baru diubah ke WIB."""
from datetime import datetime, time, timedelta, timezone

# zona waktu tampilan: WIB (UTC+7). Indonesia ga pake DST jadi aman pake offset tetap
DISPLAY_TIMEZONE = timezone(timedelta(hours=7), "WIB")

def utc_now():
    """Waktu sekarang dalam UTC (ada info zona waktunya)."""
    return datetime.now(timezone.utc)

def to_utc_aware(value):
    """Pastiin datetime punya zona waktu UTC. Fungsi ini nyamain keduanya (Postgre + Sqlite) biar aman dibandingin."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def format_local_datetime(value, pattern="%d %b %Y, %H:%M"):
    """Format waktu buat ditampilin ke user dalam WIB, misal '25 Sep 2026, 14:30 WIB'."""
    if value is None:
        return "-"
    return to_utc_aware(value).astimezone(DISPLAY_TIMEZONE).strftime(pattern) + " WIB"

def build_utc_range_from_local_date(date_from=None, date_to=None):
    """Ubah rentang tanggal WIB (dari filter) jadi waktu UTC. date_to kehitung sampe akhir hari."""
    start_at = datetime.combine(date_from, time.min, DISPLAY_TIMEZONE).astimezone(timezone.utc) if date_from else None
    end_at = datetime.combine(date_to + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(timezone.utc) if date_to else None
    return start_at, end_at
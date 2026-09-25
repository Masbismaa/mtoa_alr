"""Helper waktu. Semua waktu di app pake UTC, pas ditampilin baru diubah ke WIB."""

from datetime import datetime, timedelta, timezone

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
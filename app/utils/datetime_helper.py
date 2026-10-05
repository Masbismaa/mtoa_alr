"""Helper waktu. Semua waktu di app pake UTC, pas ditampilin baru diubah ke WIB."""
from datetime import datetime, time, timedelta, timezone

# zona waktu tampilan: WIB (UTC+7). Indonesia ga pake DST jadi aman pake offset tetap
DISPLAY_TIMEZONE = timezone(timedelta(hours=7), "WIB")

# nama bulan Indonesia, dipake web & Excel biar tampilannya sama ("Okt", bukan "Oct")
MONTH_NAME_TUPLE = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

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

def to_local_time(value):
    """Waktu UTC jadi WIB. None tetep None."""
    if value is None:
        return None
    return to_utc_aware(value).astimezone(DISPLAY_TIMEZONE)

def format_local_datetime(value, pattern="%d %b %Y, %H:%M"):
    """Format waktu WIB buat ditampilin, misal '05 Okt 2026, 14:30 WIB'. %b otomatis jadi nama bulan Indonesia."""
    local_time = to_local_time(value)
    if local_time is None:
        return "-"
    month_pattern = pattern.replace("%b", MONTH_NAME_TUPLE[local_time.month - 1])
    return local_time.strftime(month_pattern) + " WIB"

def build_utc_range_from_local_date(date_from=None, date_to=None):
    """Ubah rentang tanggal WIB (dari filter) jadi waktu UTC. date_to kehitung sampe akhir hari."""
    start_at = datetime.combine(date_from, time.min, DISPLAY_TIMEZONE).astimezone(timezone.utc) if date_from else None
    end_at = datetime.combine(date_to + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(timezone.utc) if date_to else None
    return start_at, end_at

def format_time_ago(value):
    """Waktu relatif ala forum: 'Baru saja', '5 menit lalu', '3 jam lalu', lewat seminggu jadi tanggal."""
    if value is None:
        return "-"
    second_count = int((utc_now() - to_utc_aware(value)).total_seconds())
    if second_count < 60:
        return "Baru saja"
    if second_count < 3600:
        return f"{second_count // 60} menit lalu"
    if second_count < 86400:
        return f"{second_count // 3600} jam lalu"
    if second_count < 7 * 86400:
        return f"{second_count // 86400} hari lalu"
    return format_local_datetime(value)

"""Helper waktu. Semua waktu di app pake UTC biar ga bingung zona waktu."""

from datetime import datetime, timezone

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
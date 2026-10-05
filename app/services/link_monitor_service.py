"""Pengaturan dan eksekusi pemeriksaan status link otomatis."""
from datetime import timedelta

from app.extensions import db
from app.models import LinkMonitorSetting
from app.services.audit_service import log_audit
from app.utils.constants import AUDIT_ACTION_UPDATE, LINK_MONITOR_SETTING_ID
from app.utils.datetime_helper import to_utc_aware, utc_now


def get_monitor_settings():
    """Ambil pengaturan (cuma 1 baris), kalau belum ada dibikinin default."""
    settings = db.session.get(LinkMonitorSetting, LINK_MONITOR_SETTING_ID)
    if settings is None:
        settings = LinkMonitorSetting(id=LINK_MONITOR_SETTING_ID)
        db.session.add(settings)
        db.session.commit()
    return settings


def update_monitor_settings(user, data_dict):
    """Simpen pengaturan (data udah divalidasi form) + catat nilai lama vs baru di audit log."""
    settings = get_monitor_settings()
    old_data_dict = {"is_enabled": settings.is_enabled, "interval_minutes": settings.interval_minutes}
    settings.is_enabled = bool(data_dict["is_enabled"])
    settings.interval_minutes = data_dict["interval_minutes"]
    settings.updated_by_user_id = user.id
    log_audit(
        AUDIT_ACTION_UPDATE, "link_monitor_settings", entity_id=settings.id,
        old_data_dict=old_data_dict,
        new_data_dict={"is_enabled": settings.is_enabled, "interval_minutes": settings.interval_minutes},
        user=user,
    )
    db.session.commit()
    return settings


def is_monitor_due(settings):
    """True kalau monitoring aktif & interval sejak cek terakhir udah lewat."""
    if not settings.is_enabled or settings.last_run_at is None:
        return settings.is_enabled
    return to_utc_aware(settings.last_run_at) + timedelta(minutes=settings.interval_minutes) <= utc_now()


def run_monitor(force=False):
    """Jalankan pemeriksaan semua data jika sudah jatuh tempo, atau paksa dari panel admin."""
    settings = get_monitor_settings()
    if not force and not is_monitor_due(settings):
        return None

    from app.services.link_check_service import check_all_entry_status

    status_counter = check_all_entry_status()
    settings.last_run_at = utc_now()
    db.session.commit()
    return status_counter

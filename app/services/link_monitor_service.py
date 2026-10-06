"""Ringkasan dan eksekusi pemeriksaan status link yang dipicu admin."""
from collections import Counter

from app.extensions import db
from app.models import AccessEntry
from app.utils.constants import LINK_STATUS_DOWN, LINK_STATUS_UNKNOWN, LINK_STATUS_UP


def build_monitor_summary():
    """Ambil ringkasan hasil pemeriksaan terakhir untuk panel admin."""
    status_list = db.session.execute(db.select(AccessEntry.status)).scalars().all()
    status_counter = Counter(status_list)
    last_checked_at = db.session.scalar(db.select(db.func.max(AccessEntry.status_checked_at)))
    return {
        "total_count": len(status_list),
        "up_count": status_counter[LINK_STATUS_UP],
        "down_count": status_counter[LINK_STATUS_DOWN],
        "unknown_count": status_counter[LINK_STATUS_UNKNOWN],
        "last_checked_at": last_checked_at,
    }


def run_monitor():
    """Jalankan pemeriksaan semua data atas permintaan admin."""
    from app.services.link_check_service import check_all_entry_status
    return check_all_entry_status()

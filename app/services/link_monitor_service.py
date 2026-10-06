"""Ringkasan dan eksekusi pemeriksaan status link (dari tombol admin atau command check-links)."""
from collections import Counter
from app.extensions import db
from app.models import AccessEntry
from app.services.link_check_service import check_all_entry_status
from app.utils.constants import LINK_STATUS_DOWN, LINK_STATUS_UNKNOWN, LINK_STATUS_UP

def build_monitor_summary():
    """Ringkasan hasil pemeriksaan terakhir buat panel admin."""
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
    """Cek semua link sekarang. Dipake tombol admin & command check-links (Task Scheduler)."""
    return check_all_entry_status()

def build_run_summary_text(status_counter):
    """Hasil pemeriksaan jadi satu kalimat buat flash & output command."""
    return (
        f"Pemeriksaan selesai: {sum(status_counter.values())} data · {status_counter[LINK_STATUS_UP]} aktif · "
        f"{status_counter[LINK_STATUS_DOWN]} tidak aktif · {status_counter[LINK_STATUS_UNKNOWN]} belum dicek"
    )

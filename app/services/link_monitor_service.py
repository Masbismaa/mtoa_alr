"""Ringkasan dan eksekusi pemeriksaan status link (dari tombol admin atau command check-links)."""
from collections import Counter
from datetime import timedelta
import uuid
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import AccessEntry, LinkMonitorRun
from app.services.link_check_service import check_all_entry_status
from app.utils.constants import LINK_STATUS_DOWN, LINK_STATUS_UNKNOWN, LINK_STATUS_UP
from app.utils.datetime_helper import utc_now
from app.utils.exceptions import ValidationError, build_error

def build_monitor_summary():
    """Ringkasan hasil pemeriksaan terakhir buat panel admin."""
    status_counter = Counter(dict(db.session.execute(
        db.select(AccessEntry.status, db.func.count(AccessEntry.id)).group_by(AccessEntry.status)
    ).all()))
    last_checked_at = db.session.scalar(db.select(db.func.max(AccessEntry.status_checked_at)))
    return {
        "total_count": sum(status_counter.values()),
        "up_count": status_counter[LINK_STATUS_UP],
        "down_count": status_counter[LINK_STATUS_DOWN],
        "unknown_count": status_counter[LINK_STATUS_UNKNOWN],
        "last_checked_at": last_checked_at,
    }

def get_monitor_run():
    return db.session.get(LinkMonitorRun, 1, populate_existing=True)


def request_monitor_run():
    """Antrekan satu pemeriksaan; UPDATE bersyarat menolak klik/worker bersamaan."""
    if get_monitor_run() is None:
        db.session.add(LinkMonitorRun(id=1))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()  # Proses lain sudah membuat baris tunggalnya.
    token = uuid.uuid4().hex
    result = db.session.execute(db.update(LinkMonitorRun).where(
        LinkMonitorRun.id == 1, LinkMonitorRun.state.notin_(["queued", "running"]),
    ).values(token=token, state="queued", processed_count=0, total_count=0, updated_at=utc_now()))
    if result.rowcount != 1:
        db.session.rollback()
        raise ValidationError([build_error("monitor", "Pemeriksaan masih menunggu atau sedang berjalan")])
    db.session.commit()
    return token


def process_pending_monitor():
    """Hanya worker yang berhasil mengklaim token boleh menyimpan hasilnya."""
    job = get_monitor_run()
    if job is None or job.state != "queued":
        db.session.rollback()
        return None
    token = job.token
    claimed = db.session.execute(db.update(LinkMonitorRun).where(
        LinkMonitorRun.id == 1, LinkMonitorRun.token == token, LinkMonitorRun.state == "queued",
    ).values(state="running", updated_at=utc_now()))
    db.session.commit()
    if claimed.rowcount != 1:
        return None

    def progress(processed, total):
        changed = db.session.execute(db.update(LinkMonitorRun).where(
            LinkMonitorRun.id == 1, LinkMonitorRun.token == token, LinkMonitorRun.state == "running",
        ).values(processed_count=processed, total_count=total, updated_at=utc_now()))
        if changed.rowcount != 1:
            raise RuntimeError("Kepemilikan pemeriksaan sudah dicabut")

    try:
        counts = check_all_entry_status(progress_callback=progress)
        db.session.execute(db.update(LinkMonitorRun).where(
            LinkMonitorRun.id == 1, LinkMonitorRun.token == token, LinkMonitorRun.state == "running",
        ).values(state="completed", updated_at=utc_now()))
        db.session.commit()
        return counts
    except Exception:
        db.session.rollback()
        db.session.execute(db.update(LinkMonitorRun).where(
            LinkMonitorRun.id == 1, LinkMonitorRun.token == token, LinkMonitorRun.state == "running",
        ).values(state="failed", updated_at=utc_now()))
        db.session.commit()
        current_app.logger.error("Pemeriksaan link gagal; periksa worker dan koneksi jaringan")
        raise


def recover_stale_monitor():
    """Operator dapat mencabut run macet; hasil worker lama akan ditolak sebelum ditulis."""
    changed = db.session.execute(db.update(LinkMonitorRun).where(
        LinkMonitorRun.id == 1, LinkMonitorRun.state.in_(["queued", "running"]),
        LinkMonitorRun.updated_at < utc_now() - timedelta(minutes=5),
    ).values(state="failed", updated_at=utc_now()))
    db.session.commit()
    return changed.rowcount == 1


def run_monitor():
    """CLI memakai antrean dan kunci yang sama dengan tombol admin."""
    request_monitor_run()
    counts = process_pending_monitor()
    if counts is None:
        raise ValidationError([build_error("monitor", "Pemeriksaan sedang dikerjakan worker lain")])
    return counts

def build_run_summary_text(status_counter):
    """Hasil pemeriksaan jadi satu kalimat buat flash & output command."""
    return (
        f"Pemeriksaan selesai: {sum(status_counter.values())} data · {status_counter[LINK_STATUS_UP]} aktif · "
        f"{status_counter[LINK_STATUS_DOWN]} tidak aktif · {status_counter[LINK_STATUS_UNKNOWN]} belum dicek"
    )

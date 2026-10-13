"""Ringkasan dan eksekusi pemeriksaan status link (dari tombol admin atau command check-links)."""
from collections import Counter
from datetime import timedelta
import uuid
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import AccessEntry, LinkMonitorRun
from app.services.link_check_service import check_all_entry_status
from app.utils.constants import (
    LINK_STATUS_DOWN,
    LINK_STATUS_UNKNOWN,
    LINK_STATUS_UP,
    MONITOR_STALL_WARNING_SECONDS,
    MONITOR_WORKER_WAIT_WARNING_SECONDS,
)
from app.utils.datetime_helper import to_utc_aware, utc_now
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

# perintah yg ditampilin di peringatan (worker = proses terpisah yg ngerjain antrean, bukan bagian web)
WORKER_COMMAND = "python -m flask --app run monitor-worker"

def build_monitor_status():
    """Status pemeriksaan buat halaman Link Monitoring (render awal & polling JSON pake fungsi yg sama).

    is_active: masih nunggu / jalan (halaman perlu terus nanya status).
    warning: diisi kalau kemungkinan worker ga jalan (antrean ga diambil-ambil) atau berhenti di tengah jalan."""
    run = get_monitor_run()
    state = run.state if run else "idle"
    processed_count = run.processed_count if run else 0
    total_count = run.total_count if run else 0
    idle_seconds = (utc_now() - to_utc_aware(run.updated_at)).total_seconds() if run and run.updated_at else 0
    message_dict = {
        "idle": "No checks yet.",
        "queued": "Waiting for the check.",
        "running": f"Check running: {processed_count} of {total_count} links.",
        "completed": f"Check finished: {processed_count} links checked.",
        "failed": "The check stopped. Some results may already be updated; contact the server administrator.",
    }
    warning = None
    if state == "queued" and idle_seconds > MONITOR_WORKER_WAIT_WARNING_SECONDS:
        warning = f"The queue hasn't been picked up for more than {MONITOR_WORKER_WAIT_WARNING_SECONDS} seconds. The worker is probably not running."
    elif state == "running" and idle_seconds > MONITOR_STALL_WARNING_SECONDS:
        warning = f"No progress for more than {MONITOR_STALL_WARNING_SECONDS} seconds. The worker has probably stopped."
    return {
        "state": state,
        "is_active": state in ("queued", "running"),
        "processed_count": processed_count,
        "total_count": total_count,
        "percent": round(processed_count * 100 / total_count) if total_count else 0,
        "message": message_dict.get(state, message_dict["idle"]),
        "warning": warning,
        "worker_command": WORKER_COMMAND,
    }


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
        raise ValidationError([build_error("monitor", "A check is still waiting or running")])
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
        f"Check finished: {sum(status_counter.values())} links · {status_counter[LINK_STATUS_UP]} up · "
        f"{status_counter[LINK_STATUS_DOWN]} down · {status_counter[LINK_STATUS_UNKNOWN]} not checked"
    )

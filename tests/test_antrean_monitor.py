"""Antrean manual, klaim tunggal, progres batch, dan penolakan worker lama."""
from collections import Counter
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from app.extensions import db
from app.models import AccessEntry, LinkMonitorRun
from app.services import link_check_service, link_monitor_service
from app.utils.constants import LINK_STATUS_UP
from app.utils.datetime_helper import utc_now
from app.utils.exceptions import ValidationError


def test_admin_click_queues_without_network(admin_client, monkeypatch):
    check = MagicMock(side_effect=AssertionError("Request web tidak boleh menunggu jaringan"))
    monkeypatch.setattr(link_monitor_service, "check_all_entry_status", check)
    assert admin_client.post("/link-monitoring/run").status_code == 302
    assert link_monitor_service.get_monitor_run().state == "queued"
    assert not check.called


def test_second_request_rejected_until_worker_finishes(app, monkeypatch):
    link_monitor_service.request_monitor_run()
    with pytest.raises(ValidationError):
        link_monitor_service.request_monitor_run()
    def check(progress_callback):
        assert link_monitor_service.process_pending_monitor() is None
        progress_callback(3, 3)
        return Counter({LINK_STATUS_UP: 3})
    monkeypatch.setattr(link_monitor_service, "check_all_entry_status", check)
    counts = link_monitor_service.process_pending_monitor()
    assert counts[LINK_STATUS_UP] == 3
    run = link_monitor_service.get_monitor_run()
    assert (run.state, run.processed_count, run.total_count) == ("completed", 3, 3)
    assert link_monitor_service.process_pending_monitor() is None
    link_monitor_service.request_monitor_run()


def test_old_worker_cannot_write_after_recovery(app, monkeypatch):
    token = link_monitor_service.request_monitor_run()
    def check(progress_callback):
        db.session.execute(db.update(LinkMonitorRun).values(updated_at=utc_now() - timedelta(minutes=6)))
        db.session.commit()
        assert link_monitor_service.recover_stale_monitor()
        new_token = link_monitor_service.request_monitor_run()
        assert token != new_token
        progress_callback(1, 1)
    monkeypatch.setattr(link_monitor_service, "check_all_entry_status", check)
    with pytest.raises(RuntimeError, match="Kepemilikan"):
        link_monitor_service.process_pending_monitor()
    assert link_monitor_service.get_monitor_run().state == "queued"
    assert link_monitor_service.get_monitor_run().token != token


def test_monitor_saves_batches_without_loading_secrets(app, registered_user, category_dict, monkeypatch):
    for number in range(25):
        db.session.add(AccessEntry(user_id=registered_user.id, category_id=category_dict["Web"].id,
                                  title=f"Link {number}", url="https://example.test"))
    db.session.commit()
    monkeypatch.setattr(link_check_service, "check_target", lambda target, **kwargs:
                        link_check_service.LinkCheckResult(LINK_STATUS_UP, "HTTP 200"))
    progress = []
    result = link_check_service.check_all_entry_status(progress_callback=lambda done, total: progress.append((done, total)))
    assert result == Counter({LINK_STATUS_UP: 25})
    assert (20, 25) in progress and progress[-1] == (25, 25)
    assert db.session.scalar(db.select(db.func.count(AccessEntry.id)).where(AccessEntry.status == LINK_STATUS_UP)) == 25


def set_run_age(state, seconds_ago, processed=0, total=0):
    """Helper: bikin status antrean dgn umur tertentu (updated_at mundur sekian detik)."""
    if link_monitor_service.get_monitor_run() is None:
        db.session.add(LinkMonitorRun(id=1))
    db.session.execute(db.update(LinkMonitorRun).values(
        state=state, processed_count=processed, total_count=total, updated_at=utc_now() - timedelta(seconds=seconds_ago),
    ))
    db.session.commit()


def test_status_api_requires_login(client):
    """Negative (security): belum login -> 401 JSON (bukan redirect HTML), biar script halaman bisa baca alasannya."""
    response = client.get("/link-monitoring/status")
    assert (response.status_code, response.get_json()["is_success"]) == (401, False)


def test_status_api_requires_admin(logged_in_client):
    """Negative (security): status pemeriksaan cuma buat admin; user biasa -> 403 JSON."""
    response = logged_in_client.get("/link-monitoring/status")
    assert (response.status_code, response.get_json()["is_success"]) == (403, False)


def test_status_api_reports_progress(admin_client):
    """Positive: progres pemeriksaan kebaca dari API (dipake halaman buat update sendiri tanpa reload)."""
    set_run_age("running", 5, processed=3, total=12)
    data = admin_client.get("/link-monitoring/status").get_json()["data"]
    assert (data["state"], data["is_active"], data["percent"], data["warning"]) == ("running", True, 25, None)
    assert data["message"] == "Pemeriksaan berjalan: 3 dari 12 data."


@pytest.mark.parametrize(("state", "seconds_ago", "has_warning"), [
    ("queued", 10, False), ("queued", 61, True), ("running", 100, False), ("running", 121, True), ("completed", 999, False),
])
def test_worker_warning_only_when_queue_stuck(app, state, seconds_ago, has_warning):
    """Positive & negative: peringatan "worker kemungkinan tidak berjalan" cuma muncul kalau antrean ga diambil > 1 menit
    atau pemeriksaan ga maju > 2 menit."""
    set_run_age(state, seconds_ago, processed=1, total=5)
    assert (link_monitor_service.build_monitor_status()["warning"] is not None) == has_warning


def test_page_shows_worker_command_when_queue_stuck(admin_client):
    """Positive: halaman nampilin peringatan + perintah worker kalau antrean ga diambil, dan masang script polling."""
    set_run_age("queued", 120)
    html_text = admin_client.get("/link-monitoring/").get_data(as_text=True)
    assert "Worker kemungkinan tidak berjalan" in html_text
    assert "flask --app run monitor-worker" in html_text
    assert 'data-is-active="true"' in html_text
    assert "js/pages/link_monitoring.js" in html_text

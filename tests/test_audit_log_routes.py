"""Test halaman audit log (khusus admin, cuma bisa dibaca)."""
from app.extensions import db
from app.models import AuditLog
from app.services.access_entry_service import create_access_entry
from app.services.audit_service import log_audit
from app.utils.constants import AUDIT_ACTION_LOGIN_FAILED, AUDIT_ACTION_UPDATE, MASKED_VALUE, VISIBILITY_PRIVATE, VISIBILITY_PUBLIC

def create_entry(user, category, title, visibility):
    """Helper: bikin data link."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": "https://contoh.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": visibility,
    })

def get_entry_audit_log(entry):
    """Helper: audit log waktu data link dibuat."""
    query = db.select(AuditLog).filter_by(entity_type="access_entries", entity_id=str(entry.id))
    return db.session.execute(query).scalar_one()

def create_failed_login_log():
    """Helper: audit log login gagal dari orang luar."""
    return log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="penyusup@luar.com", is_commit=True)

def test_audit_logs_require_login(client):
    """Negative (security): belum login dilempar ke halaman login."""
    response = client.get("/audit-logs/")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_user_entry_cannot_open_audit_logs(logged_in_client):
    """Negative (RBAC): user biasa dapet 403."""
    assert logged_in_client.get("/audit-logs/").status_code == 403

def test_admin_can_open_audit_logs(admin_client, admin_user):
    """Positive: admin bisa buka, aktivitas daftar & login dia sendiri keliatan."""
    response = admin_client.get("/audit-logs/")
    html_text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert admin_user.email in html_text
    assert "audit-action-login" in html_text

def test_admin_sidebar_audit_menu_is_link(admin_client):
    """Positive: menu Audit Logs udah bisa diklik (bukan 'Segera' lagi)."""
    html_text = admin_client.get("/").get_data(as_text=True)
    assert 'href="/audit-logs/"' in html_text

def test_filter_by_action(admin_client):
    """Positive: filter aksi cuma nampilin aksi itu."""
    create_failed_login_log()
    assert "penyusup@luar.com" in admin_client.get("/audit-logs/?action=login_failed").get_data(as_text=True)
    assert "penyusup@luar.com" not in admin_client.get("/audit-logs/?action=logout").get_data(as_text=True)

def test_filter_by_keyword_and_date(admin_client):
    """Positive & negative: kata kunci ketemu, tapi di luar rentang tanggal ga muncul."""
    create_failed_login_log()
    assert "penyusup@luar.com" in admin_client.get("/audit-logs/?q=penyusup").get_data(as_text=True)
    assert "penyusup@luar.com" not in admin_client.get("/audit-logs/?q=penyusup&date_to=2000-01-01").get_data(as_text=True)

def test_invalid_filter_is_ignored(admin_client):
    """Negative: parameter ngawur ga bikin error."""
    response = admin_client.get("/audit-logs/?page=abc&action=hack&entity_type=%3Cscript%3E&date_from=kemarin")
    assert response.status_code == 200
    assert "<script>" not in response.get_data(as_text=True)

def test_detail_shows_changes(admin_client, admin_user, category_dict):
    """Positive: detail nampilin field & isinya."""
    entry = create_entry(admin_user, category_dict["Web"], "Portal HR", VISIBILITY_PUBLIC)
    response = admin_client.get(f"/audit-logs/{get_entry_audit_log(entry).id}")
    html_text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Portal HR" in html_text
    assert "has_access_note" in html_text

def test_detail_masks_sensitive_value(admin_client):
    """Negative (security): password ga pernah tampil apa adanya."""
    audit_log = log_audit(
        AUDIT_ACTION_UPDATE, "users", entity_id=1, actor_email="x@spindo.com",
        new_data_dict={"password": "RahasiaBanget123"}, is_commit=True,
    )
    html_text = admin_client.get(f"/audit-logs/{audit_log.id}").get_data(as_text=True)
    assert "RahasiaBanget123" not in html_text
    assert MASKED_VALUE in html_text

def test_detail_hides_private_data_of_other_user(admin_client, registered_user, category_dict):
    """Negative (security): isi data Private user lain ga keliatan, termasuk sama admin."""
    entry = create_entry(registered_user, category_dict["Web"], "VPN Rahasia", VISIBILITY_PRIVATE)
    response = admin_client.get(f"/audit-logs/{get_entry_audit_log(entry).id}")
    html_text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "VPN Rahasia" not in html_text
    assert "disembunyikan" in html_text

def test_detail_not_found(admin_client):
    """Negative: id ga ada -> 404."""
    assert admin_client.get("/audit-logs/999999").status_code == 404

def test_audit_log_is_read_only(admin_client):
    """Negative (security): ga ada jalan buat ubah/hapus audit log lewat web."""
    audit_log = create_failed_login_log()
    assert admin_client.post(f"/audit-logs/{audit_log.id}").status_code == 405
    assert admin_client.delete(f"/audit-logs/{audit_log.id}").status_code == 405
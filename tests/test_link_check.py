"""Test cek status link: aturan aktif/tidak aktif, tombol Cek Status, command check-links. Ga ada request beneran ke internet."""
import socket
import ssl
from urllib.error import URLError
from app.extensions import db
from app.services import link_check_service
from app.services.access_entry_service import create_access_entry
from app.services.link_check_service import LinkCheckResult, LinkCheckTarget, check_target
from app.utils.constants import LINK_STATUS_DOWN, LINK_STATUS_UNKNOWN, LINK_STATUS_UP, VISIBILITY_PRIVATE

def build_entry_dict(category, title, url, **override_dict):
    """Helper: data link contoh."""
    entry_dict = {
        "category_id": category.id, "title": title, "url": url,
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    entry_dict.update(override_dict)
    return entry_dict

def build_url_target(url):
    """Target cek yg cuma punya URL."""
    return LinkCheckTarget(1, url, None, None)

def fake_open_url(status_code):
    """open_url palsu yg langsung balikin kode HTTP tertentu."""
    return lambda url, ssl_context: status_code

def raise_error(error):
    """Fungsi palsu yg selalu lempar error tertentu."""
    def fake_function(*args, **kwargs):
        raise error
    return fake_function

def test_url_with_200_is_up(monkeypatch):
    """Positive: HTTP 200 -> Aktif."""
    monkeypatch.setattr(link_check_service, "open_url", fake_open_url(200))
    assert check_target(build_url_target("https://hr.spindo.com")) == LinkCheckResult(LINK_STATUS_UP, "HTTP 200")

def test_url_with_403_is_still_up(monkeypatch):
    """Positive: 403 (halaman login/forbidden) tetep dianggap aktif, server-nya ngejawab."""
    monkeypatch.setattr(link_check_service, "open_url", fake_open_url(403))
    assert check_target(build_url_target("https://sap.spindo.com")).status == LINK_STATUS_UP

def test_url_with_500_is_down(monkeypatch):
    """Negative: error 5xx -> Tidak aktif."""
    monkeypatch.setattr(link_check_service, "open_url", fake_open_url(503))
    assert check_target(build_url_target("https://hr.spindo.com")) == LinkCheckResult(LINK_STATUS_DOWN, "HTTP 503")

def test_url_refused_is_down(monkeypatch):
    """Negative: koneksi ditolak -> Tidak aktif + alasannya."""
    monkeypatch.setattr(link_check_service, "open_url", raise_error(URLError(ConnectionRefusedError())))
    assert check_target(build_url_target("https://hr.spindo.com")) == LinkCheckResult(LINK_STATUS_DOWN, "Koneksi ditolak")

def test_url_timeout_is_down(monkeypatch):
    """Negative: kelamaan ga dijawab -> Tidak aktif (Timeout)."""
    monkeypatch.setattr(link_check_service, "open_url", raise_error(URLError(TimeoutError())))
    result = check_target(build_url_target("https://hr.spindo.com"))
    assert result.status == LINK_STATUS_DOWN
    assert result.note.startswith("Timeout")

def test_url_with_invalid_cert_is_up_with_note(monkeypatch):
    """Edge: sertifikat self-signed -> dicoba ulang tanpa cek sertifikat, aktif + ada catatannya."""
    call_list = []
    def fake_open(url, ssl_context):
        call_list.append(ssl_context.verify_mode)
        if len(call_list) == 1:
            raise URLError(ssl.SSLCertVerificationError("self-signed"))
        return 200
    monkeypatch.setattr(link_check_service, "open_url", fake_open)
    result = check_target(build_url_target("https://intranet.spindo.local"))
    assert result == LinkCheckResult(LINK_STATUS_UP, "HTTP 200 · Sertifikat SSL tidak valid")
    assert call_list == [ssl.CERT_REQUIRED, ssl.CERT_NONE]

def test_url_with_other_scheme_not_checked(monkeypatch):
    """Negative: selain http/https ga dicek sama sekali."""
    monkeypatch.setattr(link_check_service, "open_url", raise_error(AssertionError("ga boleh kepanggil")))
    assert check_target(build_url_target("ftp://files.spindo.com")).status == LINK_STATUS_UNKNOWN

def test_address_port_open_is_up(monkeypatch):
    """Positive: port kebuka -> Aktif."""
    class FakeConnection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    monkeypatch.setattr(socket, "create_connection", lambda address_pair, timeout: FakeConnection())
    assert check_target(LinkCheckTarget(1, None, "10.0.0.2", 22)) == LinkCheckResult(LINK_STATUS_UP, "Port 22 terbuka")

def test_address_port_closed_is_down(monkeypatch):
    """Negative: port ketutup -> Tidak aktif."""
    monkeypatch.setattr(socket, "create_connection", raise_error(ConnectionRefusedError()))
    assert check_target(LinkCheckTarget(1, None, "10.0.0.2", 22)).status == LINK_STATUS_DOWN

def test_address_without_port_not_checked():
    """Edge: address tanpa port -> tetep Belum dicek (sengaja ga pake ping)."""
    assert check_target(LinkCheckTarget(1, None, "10.0.0.2", None)) == LinkCheckResult(
        LINK_STATUS_UNKNOWN, "Port kosong, tidak bisa dicek",
    )

def test_check_button_updates_status(logged_in_client, registered_user, category_dict, monkeypatch):
    """Positive: tombol Cek Status nyimpen status, alasan, & waktu cek, tapi 'Terakhir Diubah' ga ikut berubah."""
    monkeypatch.setattr(link_check_service, "check_target", lambda target: LinkCheckResult(LINK_STATUS_UP, "HTTP 200"))
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    old_updated_at = entry.updated_at
    response = logged_in_client.post(f"/entries/{entry.id}/check-status", follow_redirects=True)
    db.session.refresh(entry)
    assert entry.status == LINK_STATUS_UP
    assert entry.status_note == "HTTP 200"
    assert entry.status_checked_at is not None
    assert entry.updated_at == old_updated_at
    assert "Aktif" in response.get_data(as_text=True)

def test_check_button_requires_login(client, registered_user, category_dict):
    """Negative: belum login ga bisa ngecek."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    response = client.post(f"/entries/{entry.id}/check-status")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

def test_check_button_hidden_entry_is_404(logged_in_client, other_user, category_dict, monkeypatch):
    """Negative: private punya orang lain ga bisa dicek (404, sama kayak buka detailnya)."""
    monkeypatch.setattr(link_check_service, "check_target", raise_error(AssertionError("ga boleh kepanggil")))
    entry = create_access_entry(other_user, build_entry_dict(category_dict["Web"], "Private Orang", "https://orang.spindo.com"))
    assert logged_in_client.post(f"/entries/{entry.id}/check-status").status_code == 404

def test_check_button_get_not_allowed(logged_in_client, registered_user, category_dict):
    """Negative: cek status cuma lewat POST (biar ga kepicu dari link biasa)."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    assert logged_in_client.get(f"/entries/{entry.id}/check-status").status_code == 405

def test_detail_shows_check_button_and_note(logged_in_client, registered_user, category_dict, monkeypatch):
    """Positive: detail nampilin tombol Cek Status + alasan hasil cek terakhir."""
    monkeypatch.setattr(link_check_service, "check_target", lambda target: LinkCheckResult(LINK_STATUS_DOWN, "Koneksi ditolak"))
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    logged_in_client.post(f"/entries/{entry.id}/check-status")
    html_text = logged_in_client.get(f"/entries/{entry.id}").get_data(as_text=True)
    assert "Cek Status" in html_text
    assert "Koneksi ditolak" in html_text

def test_check_links_command(app, registered_user, category_dict, monkeypatch):
    """Positive: command check-links ngecek semua data + ngasih ringkasan."""
    monkeypatch.setattr(link_check_service, "check_target", lambda target: (
        LinkCheckResult(LINK_STATUS_UP, "HTTP 200") if target.url else LinkCheckResult(LINK_STATUS_UNKNOWN, "Port kosong, tidak bisa dicek")
    ))
    web_entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    network_entry = create_access_entry(registered_user, build_entry_dict(
        category_dict["Network"], "Switch Core", "", address="10.0.0.2", port="22",
    ))
    result = app.test_cli_runner().invoke(args=["check-links"])
    assert result.exit_code == 0
    assert "2 link dicek" in result.output
    db.session.refresh(web_entry)
    db.session.refresh(network_entry)
    assert web_entry.status == LINK_STATUS_UP
    assert network_entry.status_checked_at is not None
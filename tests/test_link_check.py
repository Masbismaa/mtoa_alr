"""Test cek status link otomatis: aturan aktif/tidak aktif, alamat terlarang, redirect, & command check-links. Ga ada koneksi beneran."""
import socket
import ssl
import pytest
from app.extensions import db
from app.security.link_target_guard import LinkTargetBlockedError, parse_check_url, resolve_safe_ip
from app.services import link_check_service
from app.services.access_entry_service import create_access_entry
from app.services.link_check_service import LinkCheckResult, LinkCheckTarget, check_target, save_check_result
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

def fake_dns(monkeypatch, ip_list):
    """getaddrinfo palsu: hostname apa aja dijawab pake daftar IP ini."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ip_list]
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

def fake_send_sequence(monkeypatch, response_list):
    """send_request palsu: tiap panggilan balikin isi response_list berurutan. Balikin list catatan panggilannya."""
    call_list = []
    def fake_send(parsed_url, pinned_ip, ssl_context):
        call_list.append((parsed_url, pinned_ip, ssl_context.verify_mode))
        response = response_list[len(call_list) - 1]
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(link_check_service, "send_request", fake_send)
    return call_list

def raise_error(error):
    """Fungsi palsu yg selalu lempar error tertentu."""
    def fake_function(*args, **kwargs):
        raise error
    return fake_function

@pytest.mark.parametrize("ip_text", ["127.0.0.1", "169.254.169.254", "224.0.0.1", "0.0.0.0", "::1", "::ffff:127.0.0.1"])
def test_forbidden_ip_blocked(ip_text):
    """Negative (SSRF): server sendiri, metadata cloud, multicast, dll selalu ditolak."""
    with pytest.raises(LinkTargetBlockedError):
        resolve_safe_ip(ip_text, 80)

def test_internal_and_public_ip_allowed():
    """Positive: IP internal kantor & IP publik boleh dicek."""
    assert resolve_safe_ip("10.10.1.5", 22) == "10.10.1.5"
    assert resolve_safe_ip("203.0.113.10", 443) == "203.0.113.10"

def test_hostname_resolving_to_loopback_blocked(monkeypatch):
    """Negative (SSRF): nama domain yg ternyata nunjuk ke 127.0.0.1 ditolak."""
    fake_dns(monkeypatch, ["127.0.0.1"])
    with pytest.raises(LinkTargetBlockedError, match="terlarang"):
        resolve_safe_ip("jebakan.contoh.com", 443)

def test_dns_with_one_bad_ip_blocked(monkeypatch):
    """Negative (DNS rebinding): satu dari beberapa IP hasil DNS terlarang -> semuanya ditolak."""
    fake_dns(monkeypatch, ["10.10.2.3", "169.254.169.254"])
    with pytest.raises(LinkTargetBlockedError):
        resolve_safe_ip("hr.spindo.local", 443)

@pytest.mark.parametrize("url", ["ftp://files.spindo.local", "http://admin:rahasia@hr.spindo.local", "http://", "http://hr.spindo.local:99999"])
def test_parse_check_url_rejects_bad_url(url):
    """Negative: skema selain http/https, URL berisi password, & format ngaco ditolak."""
    with pytest.raises(LinkTargetBlockedError):
        parse_check_url(url)

def test_url_with_200_is_up(monkeypatch):
    """Positive: HTTP 200 -> Aktif, koneksinya ke IP yg udah dicek."""
    call_list = fake_send_sequence(monkeypatch, [(200, None)])
    assert check_target(build_url_target("http://10.10.1.5/")) == LinkCheckResult(LINK_STATUS_UP, "HTTP 200")
    assert call_list[0][1] == "10.10.1.5"

def test_url_with_403_is_still_up(monkeypatch):
    """Positive: 403 (halaman login/forbidden) tetep dianggap aktif, server-nya ngejawab."""
    fake_send_sequence(monkeypatch, [(403, None)])
    assert check_target(build_url_target("https://10.10.1.5/")).status == LINK_STATUS_UP

def test_url_with_500_is_down(monkeypatch):
    """Negative: error 5xx -> Tidak aktif."""
    fake_send_sequence(monkeypatch, [(503, None)])
    assert check_target(build_url_target("http://10.10.1.5/")) == LinkCheckResult(LINK_STATUS_DOWN, "HTTP 503")

def test_url_refused_is_down(monkeypatch):
    """Negative: koneksi ditolak -> Tidak aktif + alasannya."""
    fake_send_sequence(monkeypatch, [ConnectionRefusedError()])
    assert check_target(build_url_target("http://10.10.1.5/")) == LinkCheckResult(LINK_STATUS_DOWN, "Koneksi ditolak")

def test_url_timeout_is_down(monkeypatch):
    """Negative: kelamaan ga dijawab -> Tidak aktif (Timeout)."""
    fake_send_sequence(monkeypatch, [TimeoutError()])
    assert check_target(build_url_target("http://10.10.1.5/")).note.startswith("Timeout")

def test_url_with_invalid_cert_is_up_with_note(monkeypatch):
    """Edge: sertifikat self-signed -> dicoba ulang tanpa cek sertifikat, aktif + ada catatannya."""
    call_list = fake_send_sequence(monkeypatch, [ssl.SSLCertVerificationError("self-signed"), (200, None)])
    result = check_target(build_url_target("https://10.10.1.5/"))
    assert result == LinkCheckResult(LINK_STATUS_UP, "HTTP 200 · Sertifikat SSL tidak valid")
    assert [call[2] for call in call_list] == [ssl.CERT_REQUIRED, ssl.CERT_NONE]

def test_forbidden_url_never_contacted(monkeypatch):
    """Negative (SSRF): link ke alamat terlarang -> Belum dicek + 'Diblokir', ga ada koneksi sama sekali."""
    call_list = fake_send_sequence(monkeypatch, [])
    for url in ("http://127.0.0.1:5432/", "http://169.254.169.254/latest/meta-data/"):
        result = check_target(build_url_target(url))
        assert result.status == LINK_STATUS_UNKNOWN
        assert result.note.startswith("Diblokir")
    assert call_list == []

def test_redirect_to_forbidden_target_not_followed(monkeypatch):
    """Negative (SSRF): redirect ke alamat terlarang ga diikutin, server asal tetep dihitung aktif."""
    call_list = fake_send_sequence(monkeypatch, [(302, "http://169.254.169.254/")])
    result = check_target(build_url_target("http://10.10.1.5/"))
    assert result.status == LINK_STATUS_UP
    assert "tidak diikuti" in result.note
    assert len(call_list) == 1

def test_redirect_to_safe_target_followed(monkeypatch):
    """Positive: redirect biasa diikutin, hasil akhirnya yg dipake."""
    call_list = fake_send_sequence(monkeypatch, [(302, "/login"), (200, None)])
    assert check_target(build_url_target("http://10.10.1.5/")) == LinkCheckResult(LINK_STATUS_UP, "HTTP 200")
    assert call_list[1][0].request_path == "/login"

def test_redirect_loop_stops(monkeypatch):
    """Edge: redirect muter terus -> berhenti setelah batasnya."""
    call_list = fake_send_sequence(monkeypatch, [(302, "/loop")] * 10)
    assert "redirect lebih dari" in check_target(build_url_target("http://10.10.1.5/loop")).note
    assert len(call_list) == 4

def test_address_port_open_is_up(monkeypatch):
    """Positive: port kebuka -> Aktif."""
    class FakeConnection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    monkeypatch.setattr(socket, "create_connection", lambda address_pair, timeout: FakeConnection())
    assert check_target(LinkCheckTarget(1, None, "10.10.0.2", 22)) == LinkCheckResult(LINK_STATUS_UP, "Port 22 terbuka")

def test_address_port_closed_is_down(monkeypatch):
    """Negative: port ketutup -> Tidak aktif."""
    monkeypatch.setattr(socket, "create_connection", raise_error(ConnectionRefusedError()))
    assert check_target(LinkCheckTarget(1, None, "10.10.0.2", 22)).status == LINK_STATUS_DOWN

def test_forbidden_address_never_contacted(monkeypatch):
    """Negative (SSRF): address ke server sendiri ga dikoneksi."""
    monkeypatch.setattr(socket, "create_connection", raise_error(AssertionError("ga boleh kepanggil")))
    assert check_target(LinkCheckTarget(1, None, "127.0.0.1", 5432)).status == LINK_STATUS_UNKNOWN

def test_address_without_port_not_checked():
    """Edge: address tanpa port -> tetep Belum dicek (sengaja ga pake ping)."""
    assert check_target(LinkCheckTarget(1, None, "10.10.0.2", None)) == LinkCheckResult(
        LINK_STATUS_UNKNOWN, "Port kosong, tidak bisa dicek",
    )

def test_save_result_keeps_updated_at(app, registered_user, category_dict):
    """Positive: hasil cek kesimpen, tapi 'Terakhir Diubah' ga ikut berubah."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    old_updated_at = entry.updated_at
    save_check_result(entry.id, LinkCheckResult(LINK_STATUS_UP, "HTTP 200"))
    db.session.commit()
    db.session.refresh(entry)
    assert (entry.status, entry.status_note) == (LINK_STATUS_UP, "HTTP 200")
    assert entry.status_checked_at is not None
    assert entry.updated_at == old_updated_at

def test_user_cannot_trigger_check(logged_in_client, registered_user, category_dict):
    """Negative: ga ada tombol/route cek manual, user ga bisa memicu cek lewat URL langsung."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    assert logged_in_client.post(f"/entries/{entry.id}/check-status").status_code == 404
    assert "Cek Status" not in logged_in_client.get(f"/entries/{entry.id}").get_data(as_text=True)

def test_check_links_command(app, registered_user, category_dict, monkeypatch):
    """Positive: command check-links ngecek semua data + ngasih ringkasan."""
    monkeypatch.setattr(link_check_service, "check_target", lambda target: (
        LinkCheckResult(LINK_STATUS_UP, "HTTP 200") if target.url else LinkCheckResult(LINK_STATUS_UNKNOWN, "Port kosong, tidak bisa dicek")
    ))
    web_entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(category_dict["Network"], "Switch Core", "", address="10.0.0.2", port="22"))
    result = app.test_cli_runner().invoke(args=["check-links"])
    assert result.exit_code == 0
    assert "2 link dicek" in result.output
    db.session.refresh(web_entry)
    assert web_entry.status == LINK_STATUS_UP
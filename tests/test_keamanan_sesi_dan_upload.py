"""Regresi replay cookie, pengiriman OTP, SSRF, kuota, dan pemindaian lampiran."""
import socket
import ssl
from unittest.mock import MagicMock

import pytest

from app import create_app
from app.extensions import db
from app.models import Attachment, OtpCode
from app.security.link_target_guard import LinkTargetBlockedError, resolve_safe_ip
from app.security.login_loader import load_user
from app.security.upload_scanner import scan_upload
from app.services import auth_service, notification_service
from app.services.attachment_service import enforce_upload_quota
from app.services.user_service import toggle_user_active
from app.utils.exceptions import AuthError, ValidationError


def test_replayed_cookie_rejected_after_logout(tmp_path, fixed_otp_code):
    # Tidak memakai fixture app yang menahan context: tiap request harus memuat ulang user.
    app = create_app("testing")
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    with app.app_context():
        db.create_all()
        auth_service.register_user("replay@spindo.com", "PasswordKuat123", "Replay", "ICT", "Staff")
    try:
        original = app.test_client()
        original.post("/auth/login", data={"email": "replay@spindo.com", "password": "PasswordKuat123"})
        original.post("/auth/otp", data={"otp_code": fixed_otp_code})
        stolen = app.test_client()
        stolen.set_cookie("session", original.get_cookie("session").value)
        assert stolen.get("/").status_code == 200
        assert original.post("/auth/logout").status_code == 302
        assert stolen.get("/").status_code == 302
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_old_session_not_revived_by_reactivation(app, admin_user, registered_user):
    old_id = registered_user.get_id()
    toggle_user_active(admin_user, registered_user)
    toggle_user_active(admin_user, registered_user)
    assert load_user(old_id) is None
    assert load_user(registered_user.get_id()) == registered_user
    assert load_user(str(registered_user.id)) is None


def test_failed_delivery_invalidates_otp(app, registered_user, monkeypatch):
    def fail_delivery(*args):
        raise OSError("smtp secret should not appear")
    monkeypatch.setattr(auth_service, "send_otp_code", fail_delivery)
    with pytest.raises(AuthError, match="belum bisa dikirim"):
        auth_service.start_otp_challenge(registered_user)
    assert db.session.scalar(db.select(OtpCode).order_by(OtpCode.id.desc()).limit(1)).is_used


def test_smtp_encrypts_before_authentication(app, registered_user, monkeypatch):
    app.config.update(OTP_DELIVERY_MODE="smtp", SMTP_HOST="mail.test", SMTP_FROM="otp@test.local",
                      SMTP_USERNAME="relay-user", SMTP_PASSWORD="dummy")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(notification_service.smtplib, "SMTP", MagicMock(return_value=connection))
    notification_service.send_otp_code(registered_user, "123456")
    methods = [call[0] for call in connection.method_calls]
    assert methods == ["ehlo", "starttls", "ehlo", "login", "send_message"]
    context = connection.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert connection.send_message.call_args.args[0]["To"] == registered_user.email


@pytest.mark.parametrize("ip", ["10.0.0.1", "192.168.1.1", "fc00::1", "100.100.100.200", "2002:7f00:1::"])
def test_non_public_targets_blocked_by_default(ip):
    with pytest.raises(LinkTargetBlockedError):
        resolve_safe_ip(ip, 80, allow_private=False)


def test_cgnat_blocked_even_in_intranet_mode():
    with pytest.raises(LinkTargetBlockedError):
        resolve_safe_ip("100.100.100.200", 80, allow_private=True)


def test_scanner_rejects_detection_and_unavailability(app, monkeypatch):
    app.config["UPLOAD_SCANNER_HOST"] = "scanner.test"
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.recv.return_value = b"stream: Eicar-Test-Signature FOUND\0"
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=connection))
    with pytest.raises(ValueError, match="ditolak"):
        scan_upload(b"dummy")
    monkeypatch.setattr(socket, "create_connection", MagicMock(side_effect=OSError()))
    with pytest.raises(ValueError, match="belum tersedia"):
        scan_upload(b"dummy")


def test_scanner_streams_file_and_requires_clean_response(app, monkeypatch):
    app.config["UPLOAD_SCANNER_HOST"] = "scanner.test"
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.recv.side_effect = [b"stream: ", b"OK\0"]
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=connection))
    scan_upload(b"abc")
    assert [call.args[0] for call in connection.sendall.call_args_list] == [
        b"zINSTREAM\0", b"\0\0\0\3abc", b"\0\0\0\0",
    ]


def test_quota_counts_previously_stored_files(app, registered_user, category_dict):
    from app.models import AccessEntry
    entry = AccessEntry(user_id=registered_user.id, category_id=category_dict["Web"].id, title="Quota")
    entry.attachment_list.append(Attachment(user_id=registered_user.id, original_filename="old.txt",
                                           stored_filename="old.txt", content_type="text/plain", file_size=8))
    db.session.add(entry)
    db.session.commit()
    app.config["UPLOAD_USER_QUOTA_BYTES"] = 10
    with pytest.raises(ValidationError):
        enforce_upload_quota(registered_user, [{"content_bytes": b"123"}])


def test_security_headers_and_no_cache(client):
    response = client.get("/auth/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "private, no-store"

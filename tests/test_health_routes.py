"""Unit test untuk route health check dan validasi konfigurasi aplikasi."""

import pytest

from app import create_app
from app.config import TestingConfig


@pytest.fixture(autouse=True)
def clear_readiness_cache():
    """Hasil /health/ready disimpen sebentar per proses: tiap test mulai tanpa hasil lama."""
    from app.routes import health_routes

    health_routes.readiness_cache.update(expires_at=0.0, response=None)


def test_health_check_returns_ok(client):
    """Positive: /health harus mengembalikan HTTP 200 dan status 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_unknown_route_returns_404(client):
    """Negative: URL yang tidak terdaftar harus mengembalikan HTTP 404."""
    response = client.get("/halaman-tidak-ada")
    assert response.status_code == 404


def test_create_app_without_secret_key_raises_error(monkeypatch):
    """Negative (security): aplikasi wajib menolak jalan jika SECRET_KEY kosong."""
    # Kosongkan SECRET_KEY sementara (otomatis dikembalikan setelah test selesai)
    monkeypatch.setattr(TestingConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError):
        create_app("testing")

def test_readiness_ok_when_services_up(client):
    """Positive: DB, penyimpanan rate limit, & folder upload nyambung -> 200 ready."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready", "checks": {
        "database": "ok", "limit_storage": "ok", "upload_folder": "ok",
    }}


def test_readiness_fails_when_database_down(client, monkeypatch):
    """Negative: DB putus -> 503 + nama yg gagal aja (detail error ga dibocorin), /health tetep 200 (proses hidup)."""
    from app.routes import health_routes

    def broken_database():
        raise RuntimeError("password=rahasia host=10.0.0.5")

    monkeypatch.setitem(health_routes.READINESS_CHECK_DICT, "database", broken_database)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["checks"]["database"] == "failed"
    assert "rahasia" not in response.get_data(as_text=True)
    assert client.get("/health").status_code == 200


def test_proxy_header_without_trusted_proxy_logs_warning_once(client, caplog):
    """Negative (temuan audit): aplikasi di belakang reverse proxy tapi TRUSTED_PROXY_COUNT=0 -> ada peringatan
    di log (sekali aja), biar ketauan kenapa semua user keliatan dari 1 IP."""
    with caplog.at_level("WARNING"):
        client.get("/health", headers={"X-Forwarded-For": "10.1.2.3"})
        client.get("/health", headers={"X-Forwarded-For": "10.1.2.4"})
    assert sum("TRUSTED_PROXY_COUNT" in record.getMessage() for record in caplog.records) == 1


def test_no_proxy_warning_for_direct_access(client, caplog):
    """Positive: akses langsung (tanpa header proxy) ga bikin peringatan."""
    with caplog.at_level("WARNING"):
        client.get("/health")
    assert not any("TRUSTED_PROXY_COUNT" in record.getMessage() for record in caplog.records)


def test_readiness_result_cached_briefly(client, monkeypatch):
    """Positive (temuan audit): dipanggil beruntun dalam 5 detik -> hasil disimpen, DB/Redis cuma dicek sekali."""
    from app.routes import health_routes

    call_list = []
    monkeypatch.setitem(health_routes.READINESS_CHECK_DICT, "database", lambda: call_list.append(1) or True)
    for _ in range(5):
        assert client.get("/health/ready").status_code == 200
    assert len(call_list) == 1


def test_readiness_reports_redis_down_as_503(monkeypatch):
    """Negative (temuan audit): Redis (penyimpanan rate limit) mati -> /health/ready tetep bisa ngelaporin 503
    + nama yg gagal, bukan error 500 (endpoint ini ga lewat rate limiter yg butuh Redis)."""
    from app.config import TestingConfig
    from app.routes import health_routes

    def broken_storage():
        raise ConnectionError("redis mati")

    monkeypatch.setattr(TestingConfig, "RATELIMIT_ENABLED", True)
    monkeypatch.setitem(health_routes.READINESS_CHECK_DICT, "limit_storage", broken_storage)
    response = create_app("testing").test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["checks"]["limit_storage"] == "failed"



@pytest.mark.parametrize("raw_value, is_secure", [(None, True), ("true", True), ("false", False), ("FALSE", False)])
def test_production_session_cookie_secure_from_env(raw_value, is_secure):
    """Positive: production default cookie HTTPS-only; QAS yg masih HTTP bisa matiin lewat SESSION_COOKIE_SECURE=false.
    Dicek di proses terpisah biar config modul test lain ga ikut keganti."""
    import os
    import subprocess
    import sys
    env = {key: value for key, value in os.environ.items() if key != "SESSION_COOKIE_SECURE"}
    if raw_value is not None:
        env["SESSION_COOKIE_SECURE"] = raw_value
    output = subprocess.run(
        [sys.executable, "-c", "from app.config import ProductionConfig as c; print(c.SESSION_COOKIE_SECURE)"],
        env=env, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert output == str(is_secure)

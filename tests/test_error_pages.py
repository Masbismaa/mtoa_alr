from app.extensions import db
from app.models import Category

def test_404_page_shows_not_found(client):
    response = client.get("/halaman-ngasal")
    html_text = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Tidak ditemukan" in html_text
    assert "Terlalu banyak percobaan" not in html_text

def test_405_page(client):
    """Negative: GET ke route yg cuma nerima POST -> halaman 405."""
    response = client.get("/auth/logout")
    assert response.status_code == 405
    assert "Aksi tidak diizinkan" in response.get_data(as_text=True)

def test_csrf_error_page(app, client):
    """Negative (security): form tanpa token CSRF -> halaman 400 yg jelas, bukan error mentah."""
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post("/auth/login", data={"email": "user@spindo.com", "password": "PasswordKuat123"})
    assert response.status_code == 400
    assert "Sesi form kedaluwarsa" in response.get_data(as_text=True)

def test_500_page_rolls_back_unsaved_data(app, client):
    """Negative: error server -> halaman 500, data yg setengah jalan ga ikut kesimpen."""
    app.config["PROPAGATE_EXCEPTIONS"] = False

    def broken_view():
        db.session.add(Category(name="Setengah Jalan"))
        raise RuntimeError("sengaja error buat test")

    app.add_url_rule("/test-error-500", "test_error_500", broken_view)
    response = client.get("/test-error-500")
    assert response.status_code == 500
    assert "Terjadi kesalahan" in response.get_data(as_text=True)
    assert db.session.execute(db.select(Category).filter_by(name="Setengah Jalan")).scalar_one_or_none() is None
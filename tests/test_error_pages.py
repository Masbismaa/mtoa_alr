from app.extensions import db
from app.models import Category

def test_404_page_shows_not_found(client):
    response = client.get("/halaman-ngasal")
    html_text = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Tidak ditemukan" in html_text
    assert "Terlalu banyak percobaan" not in html_text
"""Test format balasan JSON."""
from app.utils.response_formatter import error_response, success_response

def test_success_response_format(app):
    """format sukses lengkap & status code sesuai."""
    response, status_code = success_response(data={"id": 1}, message="Tersimpan", status_code=201)
    body_dict = response.get_json()
    assert status_code == 201
    assert body_dict["is_success"] is True
    assert body_dict["data"] == {"id": 1}
    assert body_dict["message"] == "Tersimpan"

def test_error_response_format(app):
    """format error bawa daftar error per field."""
    error_list = [{"field": "url", "message": "URL wajib http/https"}]
    response, status_code = error_response("Validasi gagal", 422, error_list)
    body_dict = response.get_json()
    assert status_code == 422
    assert body_dict["is_success"] is False
    assert body_dict["error_list"] == error_list

def test_error_response_default_error_list_is_empty(app):
    """kalau ga ada detail, error_list tetep list kosong (bukan None)."""
    response, _ = error_response("Gagal")
    assert response.get_json()["error_list"] == []
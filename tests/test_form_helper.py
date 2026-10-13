"""Test helper form bareng: baca isi form, tempel error ke field, sisanya dibalikin."""
from app.schemas.category_schema import CategoryForm
from app.utils.form_helper import attach_form_error_list

def test_attach_form_error_list(app):
    """Positive/Negative: error ber-field nempel ke field-nya, yg ga ada field-nya dibalikin."""
    with app.test_request_context(method="POST", data={"name": "SAP"}):
        form = CategoryForm()
        form.validate()
        leftover_list = attach_form_error_list(form, [
            {"field": "name", "message": "Nama sudah dipakai"},
            {"field": "attachments", "message": "File kebesaran"},
        ])
    assert form.name.errors[-1] == "Nama sudah dipakai"
    assert leftover_list == [{"field": "attachments", "message": "File kebesaran"}]

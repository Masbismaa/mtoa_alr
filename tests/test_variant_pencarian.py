"""Test variant Kriteria Pencarian (Save as Variant / Get Variant ala Select Screen SAP)."""
from app.extensions import db
from app.models import SelectionVariant
from app.utils.constants import SELECTION_VARIANT_MAX_COUNT


def save_variant(client, name, query_text, screen_path="/entries/"):
    return client.post("/settings/variants", data={"screen_path": screen_path, "name": name, "query_text": query_text})


def variant_list():
    return db.session.execute(db.select(SelectionVariant).order_by(SelectionVariant.id)).scalars().all()


def test_save_variant_then_it_shows_on_that_screen_only(logged_in_client):
    """Positive: variant kesimpen (tanpa nomor halaman & isian kosong), balik ke layar dgn kriteria itu,
    & muncul di menu Variant layar itu aja."""
    response = save_variant(logged_in_client, "Network Down", "run=1&status=down&title=&page=3")
    assert response.status_code == 302
    assert response.location.endswith("/entries/?run=1&status=down")
    assert [(variant.name, variant.query_text) for variant in variant_list()] == [("Network Down", "run=1&status=down")]
    assert "Network Down" in logged_in_client.get("/entries/").get_data(as_text=True)
    assert "Network Down" not in logged_in_client.get("/groups/").get_data(as_text=True)


def test_same_name_replaces_variant(logged_in_client):
    """Positive: simpen pake nama yg sama -> isinya ditimpa, ga dobel."""
    save_variant(logged_in_client, "Harian", "run=1&status=down")
    save_variant(logged_in_client, "Harian", "run=1&status=up")
    assert [variant.query_text for variant in variant_list()] == ["run=1&status=up"]


def test_variant_of_other_user_is_hidden_and_cannot_be_deleted(app, logged_in_client, other_user):
    """Negative (security): variant orang lain ga keliatan & ga bisa dihapus (dijawab "not found")."""
    db.session.add(SelectionVariant(user_id=other_user.id, screen_path="/entries/", name="Punya Orang", query_text="run=1"))
    db.session.commit()
    other_variant_id = variant_list()[0].id
    assert "Punya Orang" not in logged_in_client.get("/entries/").get_data(as_text=True)
    response = logged_in_client.post(f"/settings/variants/{other_variant_id}/delete", follow_redirects=True)
    assert "Variant not found" in response.get_data(as_text=True)
    assert len(variant_list()) == 1


def test_delete_own_variant(logged_in_client):
    """Positive: hapus variant sendiri -> balik ke layarnya."""
    save_variant(logged_in_client, "Sementara", "run=1")
    response = logged_in_client.post(f"/settings/variants/{variant_list()[0].id}/delete")
    assert response.status_code == 302 and response.location.endswith("/entries/")
    assert variant_list() == []


def test_variant_rejects_external_screen_and_empty_name(logged_in_client):
    """Negative (security): layar luar (open redirect) & nama kosong ditolak, ga ada yg kesimpen."""
    response = save_variant(logged_in_client, "Jahat", "run=1", screen_path="//evil.com/")
    assert response.status_code == 302 and "evil.com" not in response.location
    save_variant(logged_in_client, "  ", "run=1")
    assert variant_list() == []


def test_variant_limit_per_screen(logged_in_client):
    """Negative: maks variant per layar."""
    for index in range(SELECTION_VARIANT_MAX_COUNT + 1):
        save_variant(logged_in_client, f"V{index}", "run=1")
    assert len(variant_list()) == SELECTION_VARIANT_MAX_COUNT


def test_selection_screens_show_sap_function_key_hints(logged_in_client):
    """Positive: tombol toolbar & Execute bawa penanda tombol fungsi (dijalanin app_shell.js), status bar ada user & jam."""
    html_text = logged_in_client.get("/entries/").get_data(as_text=True)
    assert 'data-fkey="F8"' in html_text and 'data-fkey="F1"' in html_text and 'data-fkey="Shift+F3"' in html_text
    assert 'title="Logged-in user"' in html_text and "data-status-clock" in html_text

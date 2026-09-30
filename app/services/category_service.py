"""Logika kelola kategori (khusus admin): tambah, ubah, aktif/nonaktif, hapus."""
from app.extensions import db
from app.models import AccessEntry, Category
from app.services.audit_service import log_audit
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_UPDATE,
    DEFAULT_CATEGORY_NAME_SET,
    MAX_CATEGORY_DESCRIPTION_LENGTH,
    MAX_CATEGORY_NAME_LENGTH,
    MIN_CATEGORY_NAME_LENGTH,
)
from app.utils.exceptions import ValidationError, build_error
from app.utils.sanitizer import sanitize_text

AUDIT_CATEGORY = "categories"

def is_default_category(category):
    """Kategori bawaan (Web, Application, Network, General). Aturan form-nya nempel ke nama, jadi dikunci."""
    return category.name in DEFAULT_CATEGORY_NAME_SET

def build_category_audit_dict(category):
    """Data kategori buat audit log."""
    return {"name": category.name, "description": category.description, "is_active": category.is_active}

def find_category_by_name(name, exclude_category_id=None):
    """Cari kategori dgn nama sama (huruf besar/kecil dianggap sama)."""
    query = db.select(Category).where(db.func.lower(Category.name) == name.lower())
    if exclude_category_id is not None:
        query = query.where(Category.id != exclude_category_id)
    return db.session.execute(query.limit(1)).scalar_one_or_none()

def validate_category_data(data_dict, category=None):
    """Cek nama & deskripsi, balikin data bersih. Kategori bawaan ga boleh ganti nama."""
    clean_name = sanitize_text(data_dict.get("name"), max_length=MAX_CATEGORY_NAME_LENGTH) or ""
    clean_description = sanitize_text(data_dict.get("description"), max_length=MAX_CATEGORY_DESCRIPTION_LENGTH) or None

    if category is not None and is_default_category(category):
        if clean_name != category.name:
            raise ValidationError([build_error("name", "Nama kategori bawaan tidak bisa diubah")])
        return {"name": category.name, "description": clean_description}

    if len(clean_name) < MIN_CATEGORY_NAME_LENGTH:
        raise ValidationError([build_error("name", f"Nama kategori minimal {MIN_CATEGORY_NAME_LENGTH} karakter")])
    exclude_category_id = category.id if category is not None else None
    if find_category_by_name(clean_name, exclude_category_id) is not None:
        raise ValidationError([build_error("name", f'Kategori "{clean_name}" sudah ada')])
    return {"name": clean_name, "description": clean_description}

def count_entry_by_category():
    """Jumlah link per kategori: {category_id: jumlah}. Cuma angka, isi data Private tetep ga kebuka."""
    row_list = db.session.execute(
        db.select(AccessEntry.category_id, db.func.count(AccessEntry.id)).group_by(AccessEntry.category_id)
    ).all()
    return dict(row_list)

def count_category_entry(category_id):
    """Jumlah link di satu kategori."""
    return db.session.scalar(db.select(db.func.count(AccessEntry.id)).where(AccessEntry.category_id == category_id))

def list_category_summary():
    """Semua kategori (aktif & nonaktif) + jumlah link + bawaan atau bukan, buat tabel admin."""
    category_list = db.session.execute(db.select(Category).order_by(Category.id)).scalars().all()
    count_dict = count_entry_by_category()
    return [
        {
            "category": category,
            "entry_count": count_dict.get(category.id, 0),
            "is_default": is_default_category(category),
        }
        for category in category_list
    ]

def get_category(category_id):
    """Satu kategori, None kalau ga ada."""
    return db.session.get(Category, category_id)

def create_category(user, data_dict):
    """Tambah kategori baru, langsung aktif."""
    clean_dict = validate_category_data(data_dict)
    category = Category(**clean_dict, is_active=True)
    db.session.add(category)
    db.session.flush()
    log_audit(AUDIT_ACTION_CREATE, AUDIT_CATEGORY, entity_id=category.id, new_data_dict=build_category_audit_dict(category), user=user)
    db.session.commit()
    return category

def update_category(user, category, data_dict):
    """Ubah nama/deskripsi. Kategori bawaan cuma bisa ganti deskripsi."""
    clean_dict = validate_category_data(data_dict, category)
    old_data_dict = build_category_audit_dict(category)
    category.name = clean_dict["name"]
    category.description = clean_dict["description"]
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_CATEGORY, entity_id=category.id,
        old_data_dict=old_data_dict, new_data_dict=build_category_audit_dict(category), user=user,
    )
    db.session.commit()
    return category

def toggle_category_active(user, category):
    """Aktif <-> nonaktif. Nonaktif = ilang dari form tambah link, link lama tetep aman."""
    if is_default_category(category):
        raise ValidationError([build_error("is_active", "Kategori bawaan tidak bisa dinonaktifkan")])
    old_data_dict = build_category_audit_dict(category)
    category.is_active = not category.is_active
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_CATEGORY, entity_id=category.id,
        old_data_dict=old_data_dict, new_data_dict=build_category_audit_dict(category), user=user,
    )
    db.session.commit()
    return category

def delete_category(user, category):
    """Hapus kategori. Cuma boleh kalau bukan bawaan & belum dipake link sama sekali."""
    if is_default_category(category):
        raise ValidationError([build_error("category", "Kategori bawaan tidak bisa dihapus")])
    entry_count = count_category_entry(category.id)
    if entry_count > 0:
        raise ValidationError([build_error("category", f"Kategori masih dipakai {entry_count} link, nonaktifkan saja")])
    log_audit(AUDIT_ACTION_DELETE, AUDIT_CATEGORY, entity_id=category.id, old_data_dict=build_category_audit_dict(category), user=user)
    db.session.delete(category)
    db.session.commit()
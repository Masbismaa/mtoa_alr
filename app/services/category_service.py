"""Logika kategori bertingkat: pohon kategori, tambah/ubah/hapus, sama data tampilan forum."""
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import AccessEntry, Category
from app.security.access_policy import build_visible_entry_filter, has_permission
from app.services.audit_service import log_audit
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_UPDATE,
    CATEGORY_PATH_SEPARATOR,
    CATEGORY_STYLE_DICT,
    DEFAULT_CATEGORY_NAME_SET,
    DEFAULT_CATEGORY_STYLE,
    MAX_CATEGORY_DEPTH,
    MAX_CATEGORY_DESCRIPTION_LENGTH,
    MAX_CATEGORY_NAME_LENGTH,
    MIN_CATEGORY_NAME_LENGTH,
    PERMISSION_MANAGE_CATEGORIES,
)
from app.utils.exceptions import PermissionDeniedError, ValidationError, build_error
from app.utils.sanitizer import sanitize_text
from app.utils.datetime_helper import to_utc_aware

AUDIT_CATEGORY = "categories"

# POHON KATEGORI
def list_all_category():
    """Semua kategori sekali query. Tabelnya kecil, jadi pohonnya disusun di Python aja."""
    return db.session.execute(db.select(Category).order_by(Category.id)).scalars().all()

def build_child_dict(category_list):
    child_dict = {}
    for category in category_list:
        child_dict.setdefault(category.parent_id, []).append(category)
    for parent_id, child_list in child_dict.items():
        if parent_id is not None:
            child_list.sort(key=lambda category: category.name.lower())
    return child_dict

def walk_category_tree(child_dict, parent_id=None):
    for category in child_dict.get(parent_id, []):
        yield category
        yield from walk_category_tree(child_dict, category.id)

def collect_descendant_id_list(category_id, child_dict):
    """Id kategori ini + semua turunannya."""
    id_list = [category_id]
    for child in child_dict.get(category_id, []):
        id_list.extend(collect_descendant_id_list(child.id, child_dict))
    return id_list

def get_category_path_list(category):
    """Jalur dari kategori utama sampe kategori ini, misal [Web, SAP, Modul FI]."""
    path_list = []
    current_category = category
    while current_category is not None:
        path_list.append(current_category)
        current_category = current_category.parent
    return list(reversed(path_list))

def get_category_depth(category):
    """Tingkat kategori: 1 = utama, 4 = paling dalam."""
    return len(get_category_path_list(category))

def get_root_category(category):
    """Kategori utamanya. Aturan field form link ngikut ini."""
    return get_category_path_list(category)[0]

def build_category_label(category):
    """Nama lengkap, misal 'Web › SAP › Modul FI'."""
    if category is None:
        return "-"
    return CATEGORY_PATH_SEPARATOR.join(path_category.name for path_category in get_category_path_list(category))

def is_category_usable(category):
    """Bisa dipilih kalau dia & semua induknya aktif."""
    return all(path_category.is_active for path_category in get_category_path_list(category))

def get_category_style(category):
    """Ikon & warna ngikut kategori utamanya."""
    return CATEGORY_STYLE_DICT.get(get_root_category(category).name, DEFAULT_CATEGORY_STYLE)

def list_usable_category():
    """Kategori yg bisa dipilih di form & filter, urut kayak pohon."""
    child_dict = build_child_dict(list_all_category())
    return [category for category in walk_category_tree(child_dict) if is_category_usable(category)]

def get_category(category_id):
    """Satu kategori, None kalau ga ada."""
    return db.session.get(Category, category_id)

# HAK AKSES
def is_default_category(category):
    """Kategori utama bawaan (Web, Application, Network, General). Aturan form-nya nempel ke nama, jadi dikunci."""
    return category.parent_id is None and category.name in DEFAULT_CATEGORY_NAME_SET

def can_manage_category_master(user):
    """Boleh kelola semua kategori: admin, atau user yg dikasih akses kelola kategori."""
    return has_permission(user, PERMISSION_MANAGE_CATEGORIES)

def can_manage_category(user, category):
    """Pengelola kategori boleh semua. User lain cuma sub-kategori bikinannya sendiri."""
    return can_manage_category_master(user) or (category.parent_id is not None and category.user_id == user.id)

def can_add_sub_category(category):
    """Masih bisa ditambah sub kalau aktif & belum tingkat paling dalam."""
    return is_category_usable(category) and get_category_depth(category) < MAX_CATEGORY_DEPTH

# VALIDASI
def find_sibling_by_name(name, parent_id, exclude_category_id=None):
    """Cari saudara (induk sama) dgn nama sama, huruf besar/kecil dianggap sama."""
    parent_condition = Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
    query = db.select(Category).where(parent_condition, db.func.lower(Category.name) == name.lower())
    if exclude_category_id is not None:
        query = query.where(Category.id != exclude_category_id)
    return db.session.execute(query.limit(1)).scalar_one_or_none()

def validate_category_data(data_dict, category=None, parent=None):
    """Cek nama & deskripsi, balikin data bersih. Nama kategori bawaan ga boleh diganti."""
    clean_name = sanitize_text(data_dict.get("name"), max_length=MAX_CATEGORY_NAME_LENGTH) or ""
    clean_description = sanitize_text(data_dict.get("description"), max_length=MAX_CATEGORY_DESCRIPTION_LENGTH) or None

    if category is not None and is_default_category(category):
        if clean_name != category.name:
            raise ValidationError([build_error("name", "Nama kategori bawaan tidak bisa diubah")])
        return {"name": category.name, "description": clean_description}

    if len(clean_name) < MIN_CATEGORY_NAME_LENGTH:
        raise ValidationError([build_error("name", f"Nama kategori minimal {MIN_CATEGORY_NAME_LENGTH} karakter")])
    if category is not None:
        parent_id, exclude_category_id = category.parent_id, category.id
    else:
        parent_id, exclude_category_id = (parent.id if parent is not None else None), None
    if find_sibling_by_name(clean_name, parent_id, exclude_category_id) is not None:
        raise ValidationError([build_error("name", f'Kategori "{clean_name}" sudah ada di tingkat ini')])
    return {"name": clean_name, "description": clean_description}

def build_category_audit_dict(category):
    """Data kategori buat audit log."""
    return {
        "name": category.name,
        "parent_id": category.parent_id,
        "description": category.description,
        "is_active": category.is_active,
    }

# SIMPAN
def save_new_category(user, category):
    """Simpan kategori baru + catat audit."""
    db.session.add(category)
    db.session.flush()
    log_audit(AUDIT_ACTION_CREATE, AUDIT_CATEGORY, entity_id=category.id, new_data_dict=build_category_audit_dict(category), user=user)
    db.session.commit()
    return category

def create_category(user, data_dict):
    """Tambah kategori utama (route-nya khusus admin)."""
    clean_dict = validate_category_data(data_dict)
    return save_new_category(user, Category(**clean_dict, user_id=user.id, is_active=True))

def create_sub_category(user, parent, data_dict):
    """Tambah sub-kategori, semua user boleh. Maksimal 4 tingkat."""
    if not is_category_usable(parent):
        raise ValidationError([build_error("parent", "Kategori induknya lagi nonaktif")])
    if get_category_depth(parent) >= MAX_CATEGORY_DEPTH:
        raise ValidationError([build_error("parent", f"Kategori maksimal {MAX_CATEGORY_DEPTH} tingkat")])
    clean_dict = validate_category_data(data_dict, parent=parent)
    return save_new_category(user, Category(**clean_dict, parent_id=parent.id, user_id=user.id, is_active=True))

def update_category(user, category, data_dict):
    """Ubah nama/deskripsi. Kategori bawaan cuma bisa ganti deskripsi."""
    if not can_manage_category(user, category):
        raise PermissionDeniedError("Kamu tidak punya akses mengubah kategori ini")
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
    """Aktif <-> nonaktif (route-nya khusus admin). Nonaktif = dia & anak-anaknya ilang dari form."""
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

def count_category_entry(category_id):
    """Jumlah link langsung di satu kategori (semua visibilitas)."""
    return db.session.scalar(db.select(db.func.count(AccessEntry.id)).where(AccessEntry.category_id == category_id))

def count_child_category(category_id):
    """Jumlah sub langsung di bawah kategori ini."""
    return db.session.scalar(db.select(db.func.count(Category.id)).where(Category.parent_id == category_id))

def delete_category(user, category):
    """Hapus kategori. Cuma boleh kalau bukan bawaan, ga punya sub, & belum dipake link sama sekali."""
    if not can_manage_category(user, category):
        raise PermissionDeniedError("Kamu tidak punya akses menghapus kategori ini")
    if is_default_category(category):
        raise ValidationError([build_error("category", "Kategori bawaan tidak bisa dihapus")])
    if count_child_category(category.id) > 0:
        raise ValidationError([build_error("category", "Hapus dulu sub-kategori di dalamnya")])
    entry_count = count_category_entry(category.id)
    if entry_count > 0:
        raise ValidationError([build_error("category", f"Kategori masih dipakai {entry_count} link")])
    log_audit(AUDIT_ACTION_DELETE, AUDIT_CATEGORY, entity_id=category.id, old_data_dict=build_category_audit_dict(category), user=user)
    db.session.delete(category)
    db.session.commit()

# TAMPILAN
def count_entry_by_category(user=None):
    """{category_id: jumlah link}. Kalau user diisi, cuma link yg boleh dia liat yg kehitung."""
    query = db.select(AccessEntry.category_id, db.func.count(AccessEntry.id)).group_by(AccessEntry.category_id)
    if user is not None:
        query = query.where(build_visible_entry_filter(user))
    return dict(db.session.execute(query).all())

def get_latest_visible_entry(user, category_id_list):
    """Link terbaru yg boleh diliat user di kumpulan kategori ini."""
    return db.session.execute(
        db.select(AccessEntry)
        .options(joinedload(AccessEntry.owner))
        .where(build_visible_entry_filter(user), AccessEntry.category_id.in_(category_id_list))
        .order_by(AccessEntry.created_at.desc(), AccessEntry.id.desc())
        .limit(1)
    ).scalar_one_or_none()

def build_forum_row_list(user, parent=None):
    """Baris ala forum: kategori + sub-nya + jumlah link (termasuk turunannya) + link terbaru."""
    child_dict = build_child_dict(list_all_category())
    count_dict = count_entry_by_category(user)
    ranked = db.select(
        AccessEntry.id.label("entry_id"),
        db.func.row_number().over(partition_by=AccessEntry.category_id,
                                  order_by=(AccessEntry.created_at.desc(), AccessEntry.id.desc())).label("position"),
    ).where(build_visible_entry_filter(user)).subquery()
    latest_by_category = {entry.category_id: entry for entry in db.session.execute(
        db.select(AccessEntry).join(ranked, ranked.c.entry_id == AccessEntry.id)
        .where(ranked.c.position == 1).options(joinedload(AccessEntry.owner))
    ).scalars()}
    parent_id = parent.id if parent is not None else None
    row_list = []
    for category in child_dict.get(parent_id, []):
        if not category.is_active:
            continue
        descendant_id_list = collect_descendant_id_list(category.id, child_dict)
        entry_count = sum(count_dict.get(category_id, 0) for category_id in descendant_id_list)
        candidates = [latest_by_category[category_id] for category_id in descendant_id_list
                      if category_id in latest_by_category]
        row_list.append({
            "category": category,
            "style": get_category_style(category),
            "sub_category_list": [child for child in child_dict.get(category.id, []) if child.is_active],
            "entry_count": entry_count,
            "latest_entry": max(candidates, key=lambda entry: (to_utc_aware(entry.created_at), entry.id), default=None),
        })
    return row_list

def list_descendant_id(category):
    """Id kategori ini + semua turunannya (buat filter link)."""
    return collect_descendant_id_list(category.id, build_child_dict(list_all_category()))

def list_category_summary():
    """Semua kategori urut pohon + tingkat + jumlah link, buat tabel admin."""
    child_dict = build_child_dict(list_all_category())
    count_dict = count_entry_by_category()
    return [
        {
            "category": category,
            "depth": get_category_depth(category),
            "entry_count": count_dict.get(category.id, 0),
            "child_count": len(child_dict.get(category.id, [])),
            "is_default": is_default_category(category),
        }
        for category in walk_category_tree(child_dict)
    ]

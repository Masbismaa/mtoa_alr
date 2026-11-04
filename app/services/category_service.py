"""Logika kategori bertingkat: pohon kategori, tambah/ubah/hapus, sama data tampilan forum.
Kategori utama (4 bawaan) sama buat semua akun, sub-kategori di bawahnya milik pribadi pembuatnya."""
from flask import g, has_request_context
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import AccessEntry, Category
from app.security.access_policy import build_visible_entry_filter, is_admin
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
)
from app.utils.exceptions import PermissionDeniedError, ValidationError, build_error
from app.utils.sanitizer import sanitize_text
from app.utils.datetime_helper import to_utc_aware

AUDIT_CATEGORY = "categories"
# kunci cache kategori per request di flask.g
CATEGORY_CACHE_KEY = "category_dict"

# POHON KATEGORI
def query_all_category():
    """Semua kategori sekali query, urut id."""
    return db.session.execute(db.select(Category).order_by(Category.id)).scalars().all()

def list_all_category():
    """Semua kategori. Tabelnya kecil, jadi pohonnya disusun di Python aja. Di dalam request cuma query sekali."""
    category_dict = get_request_category_dict()
    return list(category_dict.values()) if category_dict is not None else query_all_category()

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

def get_request_category_dict():
    """Semua kategori {id: kategori}, sekali query per request. Disimpen di g biar objeknya ga kebuang
    (identity map SQLAlchemy cuma nyimpen referensi lemah, jadi tiap .parent bakal query ulang). Di luar request -> None."""
    if not has_request_context():
        return None
    if CATEGORY_CACHE_KEY not in g:
        g.setdefault(CATEGORY_CACHE_KEY, {category.id: category for category in query_all_category()})
    return g.get(CATEGORY_CACHE_KEY)

def clear_request_category_cache():
    """Buang cache kategori (dipanggil tiap awal request & abis kategori ditambah/dihapus)."""
    if has_request_context():
        g.pop(CATEGORY_CACHE_KEY, None)

def get_category_path_list(category):
    """Jalur dari kategori utama sampe kategori ini, misal [Web, SAP, Modul FI]."""
    category_dict = get_request_category_dict() or {}
    path_list = []
    current_category = category
    while current_category is not None:
        path_list.append(current_category)
        parent_id = current_category.parent_id
        # induk diambil dari cache, kalau ga ada (misal baru dibikin) baru lewat relasi
        current_category = category_dict.get(parent_id) or (current_category.parent if parent_id is not None else None)
    return list(reversed(path_list))

def get_category_depth(category):
    """Tingkat kategori: 1 = utama, 4 = paling dalam."""
    return len(get_category_path_list(category))

def get_root_category(category):
    """Kategori utamanya. Aturan field form link ngikut ini."""
    return get_category_path_list(category)[0]

def build_category_label(category, viewer=None):
    """Nama lengkap, misal 'Web › SAP › Modul FI'. viewer diisi & ini kategori pribadi orang lain -> cuma nama
    kategori bawaannya, atau "-" kalau kategori utamanya juga pribadi (nama kategori orang lain ga ditampilin)."""
    if category is None:
        return "-"
    if viewer is not None and not is_category_visible(viewer, category):
        root = get_root_category(category)
        return root.name if is_category_visible(viewer, root) else "-"
    return CATEGORY_PATH_SEPARATOR.join(path_category.name for path_category in get_category_path_list(category))

def is_category_usable(category):
    """Bisa dipilih kalau dia & semua induknya aktif."""
    return all(path_category.is_active for path_category in get_category_path_list(category))

def get_category_style(category):
    """Ikon & warna ngikut kategori utamanya."""
    return CATEGORY_STYLE_DICT.get(get_root_category(category).name, DEFAULT_CATEGORY_STYLE)

def is_category_visible(user, category):
    """4 kategori bawaan keliatan semua akun, kategori lain (utama maupun sub) cuma sama pembuatnya."""
    return is_default_category(category) or category.user_id == user.id

def list_usable_category(user):
    """Kategori yg bisa dipilih user di form & filter (4 kategori bawaan + kategori bikinannya), urut kayak pohon."""
    child_dict = build_child_dict([category for category in list_all_category() if is_category_visible(user, category)])
    return [category for category in walk_category_tree(child_dict) if is_category_usable(category)]

def get_category(category_id):
    """Satu kategori, None kalau ga ada."""
    return db.session.get(Category, category_id)

# HAK AKSES
def is_default_category(category):
    """Kategori utama bawaan (Web, Application, Network, General). Aturan form-nya nempel ke nama, jadi dikunci."""
    return category.parent_id is None and category.name in DEFAULT_CATEGORY_NAME_SET

def can_manage_category_master(user):
    """Boleh kelola semua kategori: admin aja."""
    return is_admin(user)

def can_manage_category(user, category):
    """Kategori bawaan: admin (cuma deskripsinya). Kategori lain cuma pembuatnya (admin juga ga bisa ngurus
    kategori pribadi orang lain)."""
    if is_default_category(category):
        return can_manage_category_master(user)
    return category.user_id == user.id

def can_add_sub_category(category):
    """Masih bisa ditambah sub kalau aktif & belum tingkat paling dalam."""
    return is_category_usable(category) and get_category_depth(category) < MAX_CATEGORY_DEPTH

# VALIDASI
def find_sibling_by_name(name, parent_id, owner_id, exclude_category_id=None):
    """Cari saudara (induk & pemilik sama) dgn nama sama, huruf besar/kecil dianggap sama.
    Kategori pribadi: akun lain boleh punya nama yg sama. Kategori utama juga ga boleh kembar sama kategori bawaan."""
    if parent_id is None:
        query = db.select(Category).where(
            Category.parent_id.is_(None), db.or_(Category.user_id == owner_id, Category.user_id.is_(None)),
        )
    else:
        query = db.select(Category).where(Category.parent_id == parent_id, Category.user_id == owner_id)
    query = query.where(db.func.lower(Category.name) == name.lower())
    if exclude_category_id is not None:
        query = query.where(Category.id != exclude_category_id)
    return db.session.execute(query.limit(1)).scalar_one_or_none()

def validate_category_data(data_dict, category=None, parent=None, owner_id=None):
    """Cek nama & deskripsi, balikin data bersih. Nama kategori bawaan ga boleh diganti.
    owner_id = pemilik sub-kategori baru (pas edit diambil dari kategorinya)."""
    clean_name = sanitize_text(data_dict.get("name"), max_length=MAX_CATEGORY_NAME_LENGTH) or ""
    clean_description = sanitize_text(data_dict.get("description"), max_length=MAX_CATEGORY_DESCRIPTION_LENGTH) or None

    if category is not None and is_default_category(category):
        if clean_name != category.name:
            raise ValidationError([build_error("name", "Built-in category names can't be changed")])
        return {"name": category.name, "description": clean_description}

    if len(clean_name) < MIN_CATEGORY_NAME_LENGTH:
        raise ValidationError([build_error("name", f"Category name must be at least {MIN_CATEGORY_NAME_LENGTH} characters")])
    if category is not None:
        parent_id, owner_id, exclude_category_id = category.parent_id, category.user_id, category.id
    else:
        parent_id, exclude_category_id = (parent.id if parent is not None else None), None
    if find_sibling_by_name(clean_name, parent_id, owner_id, exclude_category_id) is not None:
        raise ValidationError([build_error("name", f'Category "{clean_name}" already exists at this level')])
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
def commit_category_name(name):
    """Commit perubahan nama kategori. Kalau 2 request barengan bikin nama yg sama (lolos cek find_sibling_by_name
    dua-duanya), index unik di database nolak yg kalah -> dijadiin pesan validasi biasa, bukan error 500."""
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValidationError([build_error("name", f'Category "{name}" already exists at this level')]) from None

def save_new_category(user, category):
    """Simpan kategori baru + catat audit."""
    db.session.add(category)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        # induknya keburu dihapus orang lain (foreign key) vs nama kembar (index unik)
        if category.parent_id is not None and db.session.get(Category, category.parent_id) is None:
            raise ValidationError([build_error("name", "The parent category was just deleted")]) from None
        raise ValidationError([build_error("name", f'Category "{category.name}" already exists at this level')]) from None
    log_audit(AUDIT_ACTION_CREATE, AUDIT_CATEGORY, entity_id=category.id, new_data_dict=build_category_audit_dict(category), user=user)
    commit_category_name(category.name)
    clear_request_category_cache()
    return category

def create_category(user, data_dict):
    """Tambah kategori utama pribadi, semua user boleh. Cuma keliatan sama pembuatnya."""
    clean_dict = validate_category_data(data_dict, owner_id=user.id)
    return save_new_category(user, Category(**clean_dict, user_id=user.id, is_active=True))

def create_sub_category(user, parent, data_dict):
    """Tambah sub-kategori pribadi, semua user boleh, cuma di kategori bawaan / kategori bikinannya. Maksimal 4 tingkat."""
    if not is_category_visible(user, parent):
        raise PermissionDeniedError("You can only add sub-categories to your own categories")
    if not is_category_usable(parent):
        raise ValidationError([build_error("parent", "The parent category is inactive")])
    if get_category_depth(parent) >= MAX_CATEGORY_DEPTH:
        raise ValidationError([build_error("parent", f"Categories can be at most {MAX_CATEGORY_DEPTH} levels deep")])
    clean_dict = validate_category_data(data_dict, parent=parent, owner_id=user.id)
    return save_new_category(user, Category(**clean_dict, parent_id=parent.id, user_id=user.id, is_active=True))

def update_category(user, category, data_dict):
    """Ubah nama/deskripsi. Kategori bawaan cuma bisa ganti deskripsi."""
    if not can_manage_category(user, category):
        raise PermissionDeniedError("You don't have access to change this category")
    clean_dict = validate_category_data(data_dict, category)
    old_data_dict = build_category_audit_dict(category)
    category.name = clean_dict["name"]
    category.description = clean_dict["description"]
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_CATEGORY, entity_id=category.id,
        old_data_dict=old_data_dict, new_data_dict=build_category_audit_dict(category), user=user,
    )
    commit_category_name(category.name)
    return category

def toggle_category_active(user, category):
    """Aktif <-> nonaktif, cuma kategori yg user kelola. Nonaktif = dia & anak-anaknya ilang dari form."""
    if not can_manage_category(user, category):
        raise PermissionDeniedError("You don't have access to change this category")
    if is_default_category(category):
        raise ValidationError([build_error("is_active", "Built-in categories can't be deactivated")])
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

def list_subtree_category_id(category_id):
    """Id kategori ini + semua turunannya (induk duluan), langsung dari database, bukan cache request."""
    return collect_descendant_id_list(category_id, build_child_dict(query_all_category()))

def delete_category(user, category):
    """Hapus sub-kategori beserta sub di dalemnya, walau masih ada isinya: semua link di dalemnya dipindah ke induk
    sub yg dihapus, jadi ga ada link yg ilang. Kategori bawaan ga bisa dihapus, kategori utama lain cuma kalau kosong.
    Return jumlah link yg dipindah."""
    if not can_manage_category(user, category):
        raise PermissionDeniedError("You don't have access to delete this category")
    if is_default_category(category):
        raise ValidationError([build_error("category", "Built-in categories can't be deleted")])
    # baris dikunci dulu: hapus barengan -> yg kedua nunggu, terus dapet pesan ini (bukan audit hapus dobel).
    # Sub/link yg lagi ditambah barengan juga ketauan di bawah, karena turunannya diambil abis kunci kepegang
    is_still_there = db.session.execute(
        db.select(Category.id).where(Category.id == category.id).with_for_update()
    ).scalar_one_or_none() is not None
    if not is_still_there:
        db.session.rollback()
        raise ValidationError([build_error("category", "This category was already deleted")])
    subtree_id_list = list_subtree_category_id(category.id)
    if category.parent_id is None and (len(subtree_id_list) > 1 or count_category_entry(category.id) > 0):
        raise ValidationError([build_error("category", "A main category can only be deleted when it is empty")])
    moved_entry_id_list = db.session.execute(
        db.select(AccessEntry.id).where(AccessEntry.category_id.in_(subtree_id_list)).order_by(AccessEntry.id)
    ).scalars().all()
    if moved_entry_id_list:
        db.session.execute(
            db.update(AccessEntry).where(AccessEntry.id.in_(moved_entry_id_list)).values(category_id=category.parent_id)
        )
    # anak duluan biar foreign key ke induknya ga nolak
    for category_id in reversed(subtree_id_list):
        deleted_category = db.session.get(Category, category_id)
        new_data_dict = {"moved_entry_id_list": moved_entry_id_list} if category_id == category.id and moved_entry_id_list else None
        log_audit(AUDIT_ACTION_DELETE, AUDIT_CATEGORY, entity_id=category_id, old_data_dict=build_category_audit_dict(deleted_category),
                  new_data_dict=new_data_dict, user=user)
        db.session.delete(deleted_category)
        db.session.flush()
    try:
        db.session.commit()
    except IntegrityError:
        # sub-kategori / link baru masuk pas detik yg sama (database nolak karena foreign key)
        db.session.rollback()
        raise ValidationError([build_error("category", "The category just got a new link or sub-category. Reload and try again.")]) from None
    clear_request_category_cache()
    return len(moved_entry_id_list)

# TAMPILAN
def count_entry_by_category(user=None, category_id_list=None):
    """{category_id: jumlah link}. Kalau user diisi, cuma link yg boleh dia liat yg kehitung.
    category_id_list diisi = cuma kategori itu yg dihitung (hemat pas buka satu cabang)."""
    query = db.select(AccessEntry.category_id, db.func.count(AccessEntry.id)).group_by(AccessEntry.category_id)
    if user is not None:
        query = query.where(build_visible_entry_filter(user))
    if category_id_list is not None:
        query = query.where(AccessEntry.category_id.in_(category_id_list))
    return dict(db.session.execute(query).all())

def list_scope_category_id(user, category_id_list, is_include_sub=True):
    """Id kategori yg link-nya dianggap ada di kategori-kategori ini buat user (+ sub-nya kalau is_include_sub).
    Sub-kategori pribadi orang lain ga keliatan, jadi link (Public) di dalemnya dianggap ada langsung di induknya.
    Id yg ga ada dicuekin, hasilnya ga dobel."""
    category_list = list_all_category()
    category_dict = {category.id: category for category in category_list}
    child_dict = build_child_dict(category_list)
    selected_id_list = []
    for category_id in category_id_list:
        if category_id not in category_dict:
            continue
        descendant_id_list = collect_descendant_id_list(category_id, child_dict)
        if not is_include_sub:
            descendant_id_list = [category_id] + [
                descendant_id for descendant_id in descendant_id_list[1:]
                if not is_category_visible(user, category_dict[descendant_id])
            ]
        selected_id_list.extend(descendant_id for descendant_id in descendant_id_list if descendant_id not in selected_id_list)
    return selected_id_list

def build_forum_row_list(user, parent=None):
    """Baris ala forum: kategori + sub-nya + jumlah link (termasuk turunannya) + link terbaru.
    Barisnya cuma kategori yg keliatan user, hitungannya ikut link di sub-kategori orang lain yg boleh dia liat."""
    category_list = list_all_category()
    child_dict = build_child_dict(category_list)
    visible_child_dict = build_child_dict([category for category in category_list if is_category_visible(user, category)])
    # buka satu cabang -> cuma link di cabang itu yg dihitung & diranking (beranda: semua kategori emang ditampilin)
    scope_id_list = None
    if parent is not None:
        scope_id_list = [category_id for category_id in collect_descendant_id_list(parent.id, child_dict) if category_id != parent.id]
    count_dict = count_entry_by_category(user, scope_id_list)
    ranked_query = db.select(
        AccessEntry.id.label("entry_id"),
        db.func.row_number().over(partition_by=AccessEntry.category_id,
                                  order_by=(AccessEntry.created_at.desc(), AccessEntry.id.desc())).label("position"),
    ).where(build_visible_entry_filter(user))
    if scope_id_list is not None:
        ranked_query = ranked_query.where(AccessEntry.category_id.in_(scope_id_list))
    ranked = ranked_query.subquery()
    latest_by_category = {entry.category_id: entry for entry in db.session.execute(
        db.select(AccessEntry).join(ranked, ranked.c.entry_id == AccessEntry.id)
        .where(ranked.c.position == 1).options(joinedload(AccessEntry.owner))
    ).scalars()}
    parent_id = parent.id if parent is not None else None
    row_list = []
    for category in visible_child_dict.get(parent_id, []):
        if not category.is_active:
            continue
        descendant_id_list = collect_descendant_id_list(category.id, child_dict)
        entry_count = sum(count_dict.get(category_id, 0) for category_id in descendant_id_list)
        candidates = [latest_by_category[category_id] for category_id in descendant_id_list
                      if category_id in latest_by_category]
        row_list.append({
            "category": category,
            "style": get_category_style(category),
            "sub_category_list": [child for child in visible_child_dict.get(category.id, []) if child.is_active],
            "entry_count": entry_count,
            "latest_entry": max(candidates, key=lambda entry: (to_utc_aware(entry.created_at), entry.id), default=None),
            # tombol Delete di baris: cuma sub-kategori bikinan sendiri (kategori utama ga bisa dihapus)
            "can_delete": category.parent_id is not None and can_manage_category(user, category),
        })
    return row_list

def has_active_child_category(user, category):
    """Kategori ini punya sub aktif yg keliatan user (sama kayak isi daftar sub-kategori di halaman kategori)."""
    return any(
        child.is_active and is_category_visible(user, child)
        for child in build_child_dict(list_all_category()).get(category.id, [])
    )

def list_category_summary(user):
    """4 kategori bawaan + kategori bikinan user ini, urut pohon + tingkat + jumlah link yg boleh dia liat, buat tabel kelola."""
    child_dict = build_child_dict([category for category in list_all_category() if is_category_visible(user, category)])
    count_dict = count_entry_by_category(user)
    return [
        {
            "category": category,
            "depth": get_category_depth(category),
            "entry_count": count_dict.get(category.id, 0),
            "child_count": len(child_dict.get(category.id, [])),
            "is_default": is_default_category(category),
            "can_manage": can_manage_category(user, category),
        }
        for category in walk_category_tree(child_dict)
    ]

"""Service untuk mengisi data awal (seed) ke database."""

from app.extensions import db
from app.models import Category
from app.utils.constants import DEFAULT_CATEGORY_LIST


def seed_default_categories():
    """Menambahkan kategori default yang belum ada (aman dijalankan berkali-kali).

    Returns:
        Jumlah kategori baru yang ditambahkan.
    """
    # --- 1. Ambil semua nama kategori yang sudah ada dalam SATU query ---
    existing_name_set = set(db.session.execute(db.select(Category.name)).scalars().all())

    # --- 2. Siapkan hanya kategori yang belum ada (hindari duplikasi) ---
    new_category_list = [
        Category(name=category_dict["name"], description=category_dict["description"])
        for category_dict in DEFAULT_CATEGORY_LIST
        if category_dict["name"] not in existing_name_set
    ]

    # --- 3. Simpan sekaligus dalam satu transaksi ---
    if new_category_list:
        db.session.add_all(new_category_list)
        db.session.commit()

    return len(new_category_list)
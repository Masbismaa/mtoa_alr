"""Kategori utama selain 4 bawaan jadi milik pribadi pembuatnya: nama unik per pemilik, data lama dirapihin

Revision ID: e4a7c2d9b1f3
Revises: b6d2e8f4a1c9
Create Date: 2026-10-27 16:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "e4a7c2d9b1f3"
down_revision = "b6d2e8f4a1c9"
branch_labels = None
depends_on = None

MAX_NAME_LENGTH = 50
DEFAULT_CATEGORY_NAME_LIST = ["Web", "Application", "Network", "General"]
FALLBACK_CATEGORY_NAME = "General"


def build_unique_name(connection, parent_id, owner_id, name, category_id):
    """Nama yg belum dipake saudara (induk & pemilik sama), kembar dikasih akhiran " (2)", " (3)", ..."""
    owner_condition = "user_id IS NULL" if owner_id is None else "user_id = :owner_id"
    taken_set = set(connection.execute(
        sa.text(f"SELECT lower(name) FROM categories WHERE parent_id = :parent_id AND {owner_condition} AND id <> :id"),
        {"parent_id": parent_id, "owner_id": owner_id, "id": category_id},
    ).scalars())
    candidate, number = name, 2
    while candidate.lower() in taken_set:
        suffix = f" ({number})"
        candidate, number = name[:MAX_NAME_LENGTH - len(suffix)] + suffix, number + 1
    return candidate


def upgrade():
    # index lama (nama kategori utama unik di semua akun) diganti unik per pemilik
    op.drop_index("ix_categories_root_lower_name", table_name="categories")
    connection = op.get_bind()
    default_param_dict = {f"name_{index}": name for index, name in enumerate(DEFAULT_CATEGORY_NAME_LIST)}
    default_placeholder = ", ".join(f":{key}" for key in default_param_dict)
    root_list = connection.execute(sa.text(
        f"SELECT id, user_id FROM categories WHERE parent_id IS NULL AND name NOT IN ({default_placeholder})"
    ), default_param_dict).all()
    general_id = connection.execute(sa.text(
        "SELECT id FROM categories WHERE parent_id IS NULL AND name = :name ORDER BY id LIMIT 1"
    ), {"name": FALLBACK_CATEGORY_NAME}).scalar()

    # kategori utama lama sekarang cuma keliatan sama pembuatnya: sub & link punya akun lain di dalemnya
    # pindah ke General biar pemiliknya tetep bisa liat kategorinya (isi sub ikut pindah bareng sub-nya)
    for root in root_list:
        owner_condition = "" if root.user_id is None else " AND (user_id IS NULL OR user_id <> :owner_id)"
        param_dict = {"root_id": root.id, "owner_id": root.user_id}
        sub_list = connection.execute(sa.text(
            f"SELECT id, user_id, name FROM categories WHERE parent_id = :root_id{owner_condition}"
        ), param_dict).all()
        has_entry = connection.execute(sa.text(
            f"SELECT 1 FROM access_entries WHERE category_id = :root_id{owner_condition} LIMIT 1"
        ), param_dict).first() is not None
        if not sub_list and not has_entry:
            continue
        if general_id is None:
            raise RuntimeError("Kategori General ga ada: jalankan 'flask seed-categories' dulu, baru upgrade lagi")
        for sub in sub_list:
            name = build_unique_name(connection, general_id, sub.user_id, sub.name, sub.id)
            connection.execute(sa.text("UPDATE categories SET parent_id = :general_id, name = :name WHERE id = :id"),
                               {"general_id": general_id, "name": name, "id": sub.id})
        connection.execute(sa.text(
            f"UPDATE access_entries SET category_id = :general_id WHERE category_id = :root_id{owner_condition}"
        ), {**param_dict, "general_id": general_id})
        # kategori utama tanpa pemilik ga keliatan siapa pun lagi, isinya udah dipindah semua
        if root.user_id is None:
            connection.execute(sa.text("DELETE FROM categories WHERE id = :root_id"), param_dict)

    op.create_index(
        "ix_categories_root_owner_lower_name", "categories", [sa.text("coalesce(user_id, 0)"), sa.text("lower(name)")], unique=True,
        postgresql_where=sa.text("parent_id IS NULL"), sqlite_where=sa.text("parent_id IS NULL"),
    )


def downgrade():
    # data yg udah dipindah ga dibalikin. Gagal kalau ada 2 akun yg punya kategori utama dgn nama sama
    op.drop_index("ix_categories_root_owner_lower_name", table_name="categories")
    op.create_index(
        "ix_categories_root_lower_name", "categories", [sa.text("lower(name)")], unique=True,
        postgresql_where=sa.text("parent_id IS NULL"), sqlite_where=sa.text("parent_id IS NULL"),
    )

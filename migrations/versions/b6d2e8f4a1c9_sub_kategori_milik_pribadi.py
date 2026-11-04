"""Sub-kategori jadi milik pribadi pembuatnya: nama unik per induk & pemilik, data lama dirapihin

Revision ID: b6d2e8f4a1c9
Revises: d3b7f2a9c4e1
Create Date: 2026-10-27 13:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "b6d2e8f4a1c9"
down_revision = "d3b7f2a9c4e1"
branch_labels = None
depends_on = None

MAX_NAME_LENGTH = 50


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
    # index lama (unik per induk, semua akun) dibuang dulu: rapihin data di bawah bisa bikin nama kembar antar akun
    op.drop_index("ix_categories_parent_lower_name", table_name="categories")
    connection = op.get_bind()
    row_list = connection.execute(sa.text("SELECT id, parent_id, user_id, name FROM categories")).all()
    parent_of = {row.id: row.parent_id for row in row_list}
    owner_of = {row.id: row.user_id for row in row_list}

    def get_root_id(category_id):
        while parent_of[category_id] is not None:
            category_id = parent_of[category_id]
        return category_id

    def get_depth(category_id):
        depth = 1
        while parent_of[category_id] is not None:
            category_id, depth = parent_of[category_id], depth + 1
        return depth

    # 1. sub yg ditaruh di dalem sub punya akun lain -> pindah langsung ke kategori utamanya (induk diproses duluan)
    for row in sorted(row_list, key=lambda row: get_depth(row.id)):
        parent_id = parent_of[row.id]
        if parent_id is None or parent_of[parent_id] is None or owner_of[parent_id] == owner_of[row.id]:
            continue
        root_id = get_root_id(row.id)
        name = build_unique_name(connection, root_id, owner_of[row.id], row.name, row.id)
        connection.execute(sa.text("UPDATE categories SET parent_id = :root_id, name = :name WHERE id = :id"),
                           {"root_id": root_id, "name": name, "id": row.id})
        parent_of[row.id] = root_id

    # 2. link di sub punya akun lain (atau sub yg pembuatnya udah dihapus) -> pindah ke kategori utamanya
    for row in row_list:
        if parent_of[row.id] is None:
            continue
        owner_condition = "" if owner_of[row.id] is None else " AND user_id <> :owner_id"
        connection.execute(
            sa.text(f"UPDATE access_entries SET category_id = :root_id WHERE category_id = :id{owner_condition}"),
            {"root_id": get_root_id(row.id), "id": row.id, "owner_id": owner_of[row.id]},
        )

    op.create_index(
        "ix_categories_parent_owner_lower_name", "categories", ["parent_id", "user_id", sa.text("lower(name)")], unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL"), sqlite_where=sa.text("parent_id IS NOT NULL"),
    )


def downgrade():
    # data yg udah dipindah ga dibalikin. Gagal kalau ada 2 akun yg punya sub dgn nama sama di induk yg sama
    op.drop_index("ix_categories_parent_owner_lower_name", table_name="categories")
    op.create_index(
        "ix_categories_parent_lower_name", "categories", ["parent_id", sa.text("lower(name)")], unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL"), sqlite_where=sa.text("parent_id IS NOT NULL"),
    )

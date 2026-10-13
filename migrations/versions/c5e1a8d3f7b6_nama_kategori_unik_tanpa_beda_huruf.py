"""Nama kategori unik tanpa beda huruf besar/kecil (SAP = sap), sama kayak validasi aplikasi

Revision ID: c5e1a8d3f7b6
Revises: b4d9e2a7c1f3
Create Date: 2026-10-09 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "c5e1a8d3f7b6"
down_revision = "b4d9e2a7c1f3"
branch_labels = None
depends_on = None

def upgrade():
    # data lama yg udah kembar beda huruf (misal "SAP" & "sap" di induk yg sama) bikin index unik gagal dibuat.
    # Dicek duluan biar pesannya jelas: rapihin/ganti nama salah satunya, baru jalanin upgrade lagi
    # (mode --sql cuma nulis SQL, ga bisa baca data, jadi cek ini dilewatin)
    duplicate_list = [] if op.get_context().as_sql else op.get_bind().execute(sa.text(
        "SELECT parent_id, lower(name) AS lower_name, count(*) AS total FROM categories "
        "GROUP BY parent_id, lower(name) HAVING count(*) > 1"
    )).all()
    if duplicate_list:
        detail = "; ".join(f"induk {row.parent_id or '-'}: '{row.lower_name}' ({row.total}x)" for row in duplicate_list)
        raise RuntimeError(f"Ada nama kategori kembar beda huruf besar/kecil, ganti nama salah satunya dulu: {detail}")

    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.drop_constraint("uq_categories_parent_id", type_="unique")
    op.drop_index("ix_categories_root_name", table_name="categories")
    op.create_index(
        "ix_categories_parent_lower_name", "categories", ["parent_id", sa.text("lower(name)")], unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL"), sqlite_where=sa.text("parent_id IS NOT NULL"),
    )
    op.create_index(
        "ix_categories_root_lower_name", "categories", [sa.text("lower(name)")], unique=True,
        postgresql_where=sa.text("parent_id IS NULL"), sqlite_where=sa.text("parent_id IS NULL"),
    )

def downgrade():
    op.drop_index("ix_categories_root_lower_name", table_name="categories")
    op.drop_index("ix_categories_parent_lower_name", table_name="categories")
    op.create_index("ix_categories_root_name", "categories", ["name"], unique=True, postgresql_where=sa.text("parent_id IS NULL"))
    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_categories_parent_id", ["parent_id", "name"])

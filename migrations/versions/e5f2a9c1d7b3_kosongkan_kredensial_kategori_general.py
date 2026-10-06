"""Kosongkan username & access note di kategori General

Revision ID: e5f2a9c1d7b3
Revises: ca4f413837fb
Create Date: 2026-10-06 08:00:00.000000

"""
from alembic import op


revision = "e5f2a9c1d7b3"
down_revision = "ca4f413837fb"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        WITH RECURSIVE general_tree AS (
            SELECT id FROM categories WHERE parent_id IS NULL AND name = 'General'
            UNION ALL
            SELECT child.id FROM categories child JOIN general_tree parent ON child.parent_id = parent.id
        )
        UPDATE access_entries
        SET username = NULL, encrypted_access_note = NULL
        WHERE category_id IN (SELECT id FROM general_tree)
          AND (username IS NOT NULL OR encrypted_access_note IS NOT NULL)
    """)


def downgrade():
    pass

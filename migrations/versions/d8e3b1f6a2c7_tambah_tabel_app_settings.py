"""Tambah tabel app_settings: folder backup & lampiran bisa dipindah Admin dari menu Manage

Revision ID: d8e3b1f6a2c7
Revises: c5e8a1f4b9d2
Create Date: 2026-11-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "d8e3b1f6a2c7"
down_revision = "c5e8a1f4b9d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("app_settings")

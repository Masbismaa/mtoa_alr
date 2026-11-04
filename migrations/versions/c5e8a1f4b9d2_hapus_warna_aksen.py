"""Hapus kolom user_preferences.accent_color: pilihan warna aksen udah ga dipake

Revision ID: c5e8a1f4b9d2
Revises: a8c3e5f1d2b7
Create Date: 2026-10-29 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "c5e8a1f4b9d2"
down_revision = "a8c3e5f1d2b7"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("user_preferences", schema=None) as batch_op:
        batch_op.drop_column("accent_color")

def downgrade():
    with op.batch_alter_table("user_preferences", schema=None) as batch_op:
        batch_op.add_column(sa.Column("accent_color", sa.String(length=7), server_default="#0a6ed1", nullable=False))

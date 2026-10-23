"""Arsip link: tambah is_archived di access_entries

Revision ID: a1c4e7b2d9f3
Revises: f9c3a7e1b4d2
Create Date: 2026-10-16 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1c4e7b2d9f3"
down_revision = "f9c3a7e1b4d2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("access_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade():
    with op.batch_alter_table("access_entries", schema=None) as batch_op:
        batch_op.drop_column("is_archived")

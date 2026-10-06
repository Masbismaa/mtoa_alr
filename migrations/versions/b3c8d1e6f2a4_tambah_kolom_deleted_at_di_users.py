"""Tambah kolom deleted_at di users buat fitur hapus akun

Revision ID: b3c8d1e6f2a4
Revises: f51d8a9c4e72
Create Date: 2026-10-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "b3c8d1e6f2a4"
down_revision = "f51d8a9c4e72"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")

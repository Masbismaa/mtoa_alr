"""Tambah layout tabel ala ALV di preferensi user

Revision ID: d5e1f7a3b9c2
Revises: c4d2e8f1a9b5
Create Date: 2026-10-07 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "d5e1f7a3b9c2"
down_revision = "c4d2e8f1a9b5"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("user_preferences", schema=None) as batch_op:
        batch_op.add_column(sa.Column("table_layout", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))

def downgrade():
    with op.batch_alter_table("user_preferences", schema=None) as batch_op:
        batch_op.drop_column("table_layout")

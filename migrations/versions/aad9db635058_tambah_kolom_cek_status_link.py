"""Tambah kolom cek status link

Revision ID: c3d9e5f7a2b4
Revises: c7abce4829bd
Create Date: 2026-10-05 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c3d9e5f7a2b4'
down_revision = 'c2e8f4a6b1d3'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('access_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status_checked_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('status_note', sa.String(length=255), nullable=True))

def downgrade():
    with op.batch_alter_table('access_entries', schema=None) as batch_op:
        batch_op.drop_column('status_note')
        batch_op.drop_column('status_checked_at')

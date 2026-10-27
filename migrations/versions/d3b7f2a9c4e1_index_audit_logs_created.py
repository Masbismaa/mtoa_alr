"""Index audit_logs (created_at, id) buat urutan bawaan halaman Audit Logs

Revision ID: d3b7f2a9c4e1
Revises: c8f1d3a5b7e9
Create Date: 2026-10-23 14:00:00.000000

"""
from alembic import op

revision = "d3b7f2a9c4e1"
down_revision = "c8f1d3a5b7e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at", "id"], unique=False)


def downgrade():
    op.drop_index("ix_audit_logs_created", table_name="audit_logs")

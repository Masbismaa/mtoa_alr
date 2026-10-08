"""Antrean pemeriksaan manual dan indeks daftar terbaru.

Revision ID: f7b2c4d8e9a1
Revises: e6a1b9c3d7f2
"""
from alembic import op
import sqlalchemy as sa

revision = "f7b2c4d8e9a1"
down_revision = "e6a1b9c3d7f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "link_monitor_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(32), nullable=True),
        sa.Column("state", sa.String(16), nullable=False, server_default="idle"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_link_monitor_runs_single_monitor_run")),
        sa.CheckConstraint("state IN ('idle','queued','running','completed','failed')", name=op.f("ck_link_monitor_runs_monitor_state_valid")),
    )
    op.create_index("ix_access_entries_category_created", "access_entries", ["category_id", "created_at", "id"])
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at", "id"])


def downgrade():
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("ix_access_entries_category_created", table_name="access_entries")
    op.drop_table("link_monitor_runs")

"""hapus pengaturan monitor otomatis

Revision ID: f51d8a9c4e72
Revises: ca4f413837fb
Create Date: 2026-10-05 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f51d8a9c4e72"
down_revision = "e5f2a9c1d7b3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("link_monitor_settings")


def downgrade():
    op.create_table(
        "link_monitor_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_link_monitor_settings_single_row")),
        sa.CheckConstraint("interval_minutes BETWEEN 5 AND 1440", name=op.f("ck_link_monitor_settings_interval_valid")),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], name=op.f("fk_link_monitor_settings_updated_by_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_monitor_settings")),
    )

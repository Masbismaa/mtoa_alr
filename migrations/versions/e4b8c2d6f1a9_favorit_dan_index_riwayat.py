"""Favorit link (user_favorites) + index riwayat per data di audit_logs

Revision ID: e4b8c2d6f1a9
Revises: d7a3f1c9e2b5
Create Date: 2026-10-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "e4b8c2d6f1a9"
down_revision = "d7a3f1c9e2b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_entry_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["access_entry_id"], ["access_entries.id"], name=op.f("fk_user_favorites_access_entry_id_access_entries"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_favorites_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_favorites")),
        sa.UniqueConstraint("user_id", "access_entry_id", name=op.f("uq_user_favorites_user_id")),
    )
    op.create_index(op.f("ix_user_favorites_user_id"), "user_favorites", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_favorites_access_entry_id"), "user_favorites", ["access_entry_id"], unique=False)
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id", "id"], unique=False)


def downgrade():
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index(op.f("ix_user_favorites_access_entry_id"), table_name="user_favorites")
    op.drop_index(op.f("ix_user_favorites_user_id"), table_name="user_favorites")
    op.drop_table("user_favorites")

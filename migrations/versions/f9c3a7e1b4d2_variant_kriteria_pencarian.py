"""Variant Kriteria Pencarian (selection_variants)

Revision ID: f9c3a7e1b4d2
Revises: e4b8c2d6f1a9
Create Date: 2026-10-12 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f9c3a7e1b4d2"
down_revision = "e4b8c2d6f1a9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "selection_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("screen_path", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("query_text", sa.String(length=2000), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_selection_variants_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_selection_variants")),
        sa.UniqueConstraint("user_id", "screen_path", "name", name=op.f("uq_selection_variants_user_id")),
    )
    op.create_index(op.f("ix_selection_variants_user_id"), "selection_variants", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_selection_variants_user_id"), table_name="selection_variants")
    op.drop_table("selection_variants")

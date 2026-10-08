"""Tambah tabel user_notifications (notifikasi lonceng)

Revision ID: f2b7c9d4e6a1
Revises: f7b2c4d8e9a1
Create Date: 2026-10-08 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f2b7c9d4e6a1"
down_revision = "f7b2c4d8e9a1"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("user_notifications",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("message", sa.String(length=255), nullable=False),
    sa.Column("target_url", sa.String(length=255), nullable=True),
    sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_notifications_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_user_notifications"))
    )
    with op.batch_alter_table("user_notifications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_notifications_user_id"), ["user_id"], unique=False)

def downgrade():
    with op.batch_alter_table("user_notifications", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_notifications_user_id"))
    op.drop_table("user_notifications")

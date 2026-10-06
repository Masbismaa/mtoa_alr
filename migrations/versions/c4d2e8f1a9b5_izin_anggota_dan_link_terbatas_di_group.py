"""Izin tambah link per anggota dan link terbatas di group

Revision ID: c4d2e8f1a9b5
Revises: b3c8d1e6f2a4
Create Date: 2026-10-06 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "c4d2e8f1a9b5"
down_revision = "b3c8d1e6f2a4"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("group_members", schema=None) as batch_op:
        batch_op.add_column(sa.Column("can_add_entry", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    # anggota lama sebelumnya udah bisa nambah link, izinnya dipertahanin biar ga tiba-tiba ilang
    op.execute("UPDATE group_members SET can_add_entry = true WHERE role = 'member'")

    with op.batch_alter_table("group_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_restricted", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.create_table("group_entry_viewers",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("group_entry_id", sa.Integer(), nullable=False),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["group_entry_id"], ["group_entries.id"], name=op.f("fk_group_entry_viewers_group_entry_id_group_entries"), ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_group_entry_viewers_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_group_entry_viewers")),
    sa.UniqueConstraint("group_entry_id", "user_id", name=op.f("uq_group_entry_viewers_group_entry_id"))
    )
    with op.batch_alter_table("group_entry_viewers", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_group_entry_viewers_group_entry_id"), ["group_entry_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_group_entry_viewers_user_id"), ["user_id"], unique=False)

def downgrade():
    with op.batch_alter_table("group_entry_viewers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_group_entry_viewers_user_id"))
        batch_op.drop_index(batch_op.f("ix_group_entry_viewers_group_entry_id"))
    op.drop_table("group_entry_viewers")

    with op.batch_alter_table("group_entries", schema=None) as batch_op:
        batch_op.drop_column("is_restricted")

    with op.batch_alter_table("group_members", schema=None) as batch_op:
        batch_op.drop_column("can_add_entry")

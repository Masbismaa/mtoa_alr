"""Hapus tabel pending_registrations: akun sekarang dibikin admin + aktivasi lewat link email

Revision ID: a8c3e5f1d2b7
Revises: e4a7c2d9b1f3
Create Date: 2026-10-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a8c3e5f1d2b7"
down_revision = "e4a7c2d9b1f3"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("pending_registrations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pending_registrations_email"))
    op.drop_table("pending_registrations")

def downgrade():
    op.create_table("pending_registrations",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("email", sa.String(length=255), nullable=False),
    sa.Column("token_hash", sa.String(length=64), nullable=False),
    sa.Column("full_name", sa.String(length=150), nullable=False),
    sa.Column("department", sa.String(length=100), nullable=False),
    sa.Column("job_title", sa.String(length=100), nullable=False),
    sa.Column("password_hash", sa.String(length=255), nullable=False),
    sa.Column("code_hash", sa.String(length=64), nullable=False),
    sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_registrations")),
    sa.UniqueConstraint("token_hash", name=op.f("uq_pending_registrations_token_hash"))
    )
    with op.batch_alter_table("pending_registrations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pending_registrations_email"), ["email"], unique=False)

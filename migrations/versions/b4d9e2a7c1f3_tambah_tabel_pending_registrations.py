"""Tambah tabel pending_registrations (percobaan daftar yg nunggu verifikasi email)

Revision ID: b4d9e2a7c1f3
Revises: f2b7c9d4e6a1
Create Date: 2026-10-08 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "b4d9e2a7c1f3"
down_revision = "f2b7c9d4e6a1"
branch_labels = None
depends_on = None

def upgrade():
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

def downgrade():
    with op.batch_alter_table("pending_registrations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pending_registrations_email"))
    op.drop_table("pending_registrations")

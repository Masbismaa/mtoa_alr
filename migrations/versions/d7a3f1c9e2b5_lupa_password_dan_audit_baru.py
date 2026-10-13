"""Lupa password (otp_codes.purpose) + aksi audit baru: password_change, reveal, import

Revision ID: d7a3f1c9e2b5
Revises: c5e1a8d3f7b6
Create Date: 2026-10-12 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "d7a3f1c9e2b5"
down_revision = "c5e1a8d3f7b6"
branch_labels = None
depends_on = None

OLD_ACTION_SQL = "action IN ('create', 'update', 'delete', 'login', 'login_failed', 'logout', 'export')"
NEW_ACTION_SQL = (
    "action IN ('create', 'update', 'delete', 'login', 'login_failed', 'logout', 'export', "
    "'password_change', 'reveal', 'import')"
)


def upgrade():
    # OTP lama semuanya OTP login, jadi default 'login' langsung bener buat data yg udah ada
    with op.batch_alter_table("otp_codes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purpose", sa.String(length=20), nullable=False, server_default="login"))
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_audit_logs_action_valid"), type_="check")
        batch_op.create_check_constraint(op.f("ck_audit_logs_action_valid"), NEW_ACTION_SQL)


def downgrade():
    # catatan audit aksi baru yg udah ada bikin downgrade gagal (audit log ga boleh dihapus), itu disengaja
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_audit_logs_action_valid"), type_="check")
        batch_op.create_check_constraint(op.f("ck_audit_logs_action_valid"), OLD_ACTION_SQL)
    with op.batch_alter_table("otp_codes", schema=None) as batch_op:
        batch_op.drop_column("purpose")

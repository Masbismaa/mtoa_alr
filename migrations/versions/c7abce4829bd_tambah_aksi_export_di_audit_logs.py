"""Tambah aksi export di audit_logs

Revision ID: c2e8f4a6b1d3
Revises: b9d4e2f7a1c6
Create Date: 2026-10-02 09:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c2e8f4a6b1d3'
down_revision = 'b9d4e2f7a1c6'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_audit_logs_action_valid'), type_='check')
        batch_op.create_check_constraint(
            op.f('ck_audit_logs_action_valid'),
            "action IN ('create', 'update', 'delete', 'login', 'login_failed', 'logout', 'export')",
        )

def downgrade():
    # catatan export yg udah ada bikin downgrade gagal (audit log ga boleh dihapus), itu disengaja
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_audit_logs_action_valid'), type_='check')
        batch_op.create_check_constraint(
            op.f('ck_audit_logs_action_valid'),
            "action IN ('create', 'update', 'delete', 'login', 'login_failed', 'logout')",
        )
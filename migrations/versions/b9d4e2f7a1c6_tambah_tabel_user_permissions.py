"""Tambah tabel user_permissions (grant akses per user)

Revision ID: b9d4e2f7a1c6
Revises: 7c1e2f9a4b3d
Create Date: 2026-10-01 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b9d4e2f7a1c6'
down_revision = '7c1e2f9a4b3d'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('user_permissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('permission_key', sa.String(length=50), nullable=False),
    sa.Column('granted_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("permission_key IN ('manage_categories', 'view_audit_logs', 'edit_public_entries')", name=op.f('ck_user_permissions_permission_key_valid')),
    sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], name=op.f('fk_user_permissions_granted_by_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_permissions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_permissions')),
    sa.UniqueConstraint('user_id', 'permission_key', name=op.f('uq_user_permissions_user_id'))
    )
    with op.batch_alter_table('user_permissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_permissions_user_id'), ['user_id'], unique=False)

def downgrade():
    with op.batch_alter_table('user_permissions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_permissions_user_id'))
    op.drop_table('user_permissions')
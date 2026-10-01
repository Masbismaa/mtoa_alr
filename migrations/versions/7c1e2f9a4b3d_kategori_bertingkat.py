"""Kategori bertingkat: tambah parent_id & user_id di categories

Revision ID: 7c1e2f9a4b3d
Revises: ead5bf8bec03
Create Date: 2026-09-30 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7c1e2f9a4b3d'
down_revision = 'ead5bf8bec03'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        # nama sekarang cukup unik per induk, bukan unik se-tabel
        batch_op.drop_constraint('uq_categories_name', type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_categories_parent_id'), ['parent_id', 'name'])
        batch_op.create_index(batch_op.f('ix_categories_parent_id'), ['parent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_categories_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_categories_parent_id_categories'), 'categories', ['parent_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_categories_user_id_users'), 'users', ['user_id'], ['id'], ondelete='SET NULL')
    
    op.create_index('ix_categories_root_name', 'categories', ['name'], unique=True, postgresql_where=sa.text('parent_id IS NULL'))

def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_categories_root_name")
    # sub-kategori harus dihapus dulu, kalau nggak nama kembar bikin unique lama gagal dipasang
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_categories_user_id_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_categories_parent_id_categories'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_categories_user_id'))
        batch_op.drop_index(batch_op.f('ix_categories_parent_id'))
        batch_op.drop_constraint(batch_op.f('uq_categories_parent_id'), type_='unique')
        batch_op.create_unique_constraint('uq_categories_name', ['name'])
        batch_op.drop_column('user_id')
        batch_op.drop_column('parent_id')
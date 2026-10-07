"""Tambahkan versi sesi agar cookie lama dapat dicabut saat logout."""
from alembic import op
import sqlalchemy as sa

revision = "e6a1b9c3d7f2"
down_revision = "d5e1f7a3b9c2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("session_version")

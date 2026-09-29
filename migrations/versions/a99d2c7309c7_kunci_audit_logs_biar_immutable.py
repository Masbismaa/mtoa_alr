"""Kunci audit_logs biar immutable

Revision ID: a99d2c7309c7
Revises: d0d1a0871748
Create Date: 2026-09-24 13:37:49.074995

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a99d2c7309c7'
down_revision = 'd0d1a0871748'
branch_labels = None
depends_on = None

def upgrade():
    # fungsi yg selalu nolak, dipanggil sama trigger di bawah
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs bersifat immutable, tidak boleh diubah/dihapus';
        END;
        $$ LANGUAGE plpgsql;
    """)

    # tolak UPDATE & DELETE per baris
    op.execute("""
        CREATE TRIGGER trg_audit_logs_block_change
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_change();
    """)

    # tolak TRUNCATE (hapus semua sekaligus)
    op.execute("""
        CREATE TRIGGER trg_audit_logs_block_truncate
        BEFORE TRUNCATE ON audit_logs
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_audit_log_change();
    """)

def downgrade():
    # buka kunci (urutannya kebalikan dari upgrade)
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_block_truncate ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_block_change ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_change();")
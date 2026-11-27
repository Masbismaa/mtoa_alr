"""Access note jadi teks biasa: ALR ga nyimpen kredensial, jadi enkripsi Fernet dibuang

Revision ID: b3d7e2a9c4f1
Revises: c5e8a1f4b9d2
Create Date: 2026-11-27 10:00:00.000000

"""
import os

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken

revision = "b3d7e2a9c4f1"
down_revision = "c5e8a1f4b9d2"
branch_labels = None
depends_on = None

entry_table = sa.table(
    "access_entries",
    sa.column("id", sa.Integer),
    sa.column("access_note", sa.Text),
    sa.column("encrypted_access_note", sa.Text),
)

def get_fernet():
    """Kunci lama cuma dibutuhin sekali di sini. Ada data tapi ga ada kunci -> stop, biar data ga ilang."""
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key:
        raise RuntimeError("ENCRYPTION_KEY wajib ada di .env selama migrasi ini (buat buka access note lama)")
    return Fernet(encryption_key)

def read_note_dict(source_column):
    """{id: isi} semua baris yg kolomnya keisi."""
    return dict(op.get_bind().execute(
        sa.select(entry_table.c.id, source_column).where(source_column.is_not(None))
    ).all())

def write_note_dict(target_column_name, note_dict):
    connection = op.get_bind()
    for entry_id, note_text in note_dict.items():
        connection.execute(entry_table.update().where(entry_table.c.id == entry_id).values({target_column_name: note_text}))

def upgrade():
    # semua dibuka dulu sebelum tabel diubah: kunci kosong / salah -> gagal tanpa nyentuh apa-apa
    encrypted_dict = read_note_dict(entry_table.c.encrypted_access_note)
    plain_dict = {}
    if encrypted_dict:
        fernet = get_fernet()
        for entry_id, encrypted_text in encrypted_dict.items():
            try:
                plain_dict[entry_id] = fernet.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
            except InvalidToken as error:
                raise RuntimeError(f"Access note link id {entry_id} ga bisa dibuka pake ENCRYPTION_KEY ini") from error

    with op.batch_alter_table("access_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("access_note", sa.Text(), nullable=True))
    write_note_dict("access_note", plain_dict)
    with op.batch_alter_table("access_entries", schema=None) as batch_op:
        batch_op.drop_column("encrypted_access_note")

def downgrade():
    plain_dict = read_note_dict(entry_table.c.access_note)
    encrypted_dict = {}
    if plain_dict:
        fernet = get_fernet()
        encrypted_dict = {
            entry_id: fernet.encrypt(note_text.encode("utf-8")).decode("utf-8") for entry_id, note_text in plain_dict.items()
        }

    with op.batch_alter_table("access_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("encrypted_access_note", sa.Text(), nullable=True))
    write_note_dict("encrypted_access_note", encrypted_dict)
    with op.batch_alter_table("access_entries", schema=None) as batch_op:
        batch_op.drop_column("access_note")

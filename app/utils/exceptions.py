"""Exception custom biar error-nya jelas asalnya dari mana."""

class InvalidCredentialError(Exception):
    """Dilempar kalau data terenkripsi ga bisa dibuka (rusak / key-nya beda)."""

class ImmutableRecordError(Exception):
    """Dilempar kalau ada yg nyoba ubah/hapus data yg harusnya permanen (audit log)."""
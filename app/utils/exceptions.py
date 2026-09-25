"""Exception custom biar error-nya jelas asalnya dari mana."""
class InvalidCredentialError(Exception):
    """Dilempar kalau data terenkripsi ga bisa dibuka (rusak / key-nya beda)."""

class ImmutableRecordError(Exception):
    """Dilempar kalau ada yg nyoba ubah/hapus data yg harusnya permanen (audit log)."""

class AuthError(Exception):
    """Dilempar kalau register/login/OTP gagal. Pesannya aman buat ditampilin ke user."""

class ValidationError(Exception):
    """Dilempar kalau input ga valid. error_list isinya detail per field."""

    def __init__(self, error_list, message="Data tidak valid"):
        super().__init__(message)
        self.error_list = error_list

class PermissionDeniedError(Exception):
    """Dilempar kalau user nyoba ngubah/hapus data yg bukan haknya."""
"""Model ORM untuk tabel users (SR-02 Master User)."""

from sqlalchemy.orm import validates

from app.extensions import db
from app.models.base_model import TimestampMixin
from app.utils.constants import ROLE_LIST, ROLE_USER_ENTRY
from app.utils.sql_helper import build_sql_in_list


class User(TimestampMixin, db.Model):
    """Akun pengguna; username login memakai email korporat."""

    __tablename__ = "users"

    # --- Kolom identitas & profil ---
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)

    # --- Kolom hak akses ---
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER_ENTRY, server_default=ROLE_USER_ENTRY)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))

    # --- Relasi 1-1 ke preferensi tampilan; ikut terhapus jika user dihapus ---
    preference = db.relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # --- Constraint database: role hanya boleh nilai yang terdaftar di ROLE_LIST ---
    __table_args__ = (
        db.CheckConstraint(f"role IN ({build_sql_in_list(ROLE_LIST)})", name="role_valid"),
    )

    @validates("email")
    def normalize_email(self, key, value):
        """Merapikan email (hapus spasi & huruf kecil) agar tidak ada akun ganda."""
        return value.strip().lower()

    def __repr__(self):
        """Representasi singkat untuk debugging."""
        return f"<User {self.email}>"
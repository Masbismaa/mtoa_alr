"""Model ORM untuk tabel users."""
from flask_login import UserMixin
from sqlalchemy.orm import validates

from app.extensions import db
from app.models.base_model import TimestampMixin
from app.utils.constants import ROLE_LIST, ROLE_USER_ENTRY
from app.utils.sql_helper import build_sql_in_list
from app.utils.text_helper import normalize_email

class User(UserMixin, TimestampMixin, db.Model):
    """Akun pengguna; username login memakai email perusahaan."""

    __tablename__ = "users"

    # Kolom identitas & profil
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)

    # Kolom hak akses
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER_ENTRY, server_default=ROLE_USER_ENTRY)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))

    # hash argon2, bukan password asli
    password_hash = db.Column(db.String(255), nullable=False)
    # hitungan salah password berturut-turut, reset kalau login sukses
    failed_login_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    # kalau keisi & belum lewat, akun lagi dikunci
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # keisi = akun udah dihapus admin (datanya dianonimkan, barisnya tetep ada buat audit log)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relasi ke preferensi tampilan ikut terhapus jika user dihapus
    preference = db.relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # akses tambahan yg di-grant admin
    permission_list = db.relationship(
        "UserPermission",
        foreign_keys="UserPermission.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Constraint database: role hanya boleh nilai yang terdaftar di ROLE_LIST
    __table_args__ = (
        db.CheckConstraint(f"role IN ({build_sql_in_list(ROLE_LIST)})", name="role_valid"),
    )

    @validates("email")
    def validate_email(self, key, value):
        """Rapihin email sebelum disimpen (pake helper yg sama kayak service)."""
        return normalize_email(value)

    def __repr__(self):
        """Representasi singkat untuk debugging."""
        return f"<User {self.email}>"
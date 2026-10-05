"""Model ORM tabel user_permissions: akses tambahan yg di-grant admin ke user biasa."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin
from app.utils.constants import PERMISSION_LIST
from app.utils.sql_helper import build_sql_in_list

class UserPermission(CreatedAtMixin, db.Model):
    """Satu baris = satu akses buat satu user, misal Si A boleh kelola kategori."""

    __tablename__ = "user_permissions"

    id = db.Column(db.Integer, primary_key=True)
    # yg dapet akses. User dihapus -> aksesnya ikut kehapus
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_key = db.Column(db.String(50), nullable=False)
    # admin yg ngasih akses, dicatat biar jelas asal-usulnya
    granted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="permission_list")
    granted_by = db.relationship("User", foreign_keys=[granted_by_user_id])

    __table_args__ = (
        # satu akses cuma boleh dicatat sekali per user
        db.UniqueConstraint("user_id", "permission_key"),
        db.CheckConstraint(f"permission_key IN ({build_sql_in_list(PERMISSION_LIST)})", name="permission_key_valid"),
    )

    def __repr__(self):
        """Representasi singkat buat debugging."""
        return f"<UserPermission user={self.user_id} {self.permission_key}>"
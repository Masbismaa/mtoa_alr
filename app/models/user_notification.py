"""Model ORM tabel user_notifications: notifikasi lonceng per user."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin
from app.utils.constants import MAX_NOTIFICATION_MESSAGE_LENGTH

class UserNotification(CreatedAtMixin, db.Model):
    """Satu baris = satu pemberitahuan buat satu user, misal diundang ke group."""

    __tablename__ = "user_notifications"

    id = db.Column(db.Integer, primary_key=True)
    # penerima notifikasi. User dihapus -> notifikasinya ikut kehapus
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = db.Column(db.String(MAX_NOTIFICATION_MESSAGE_LENGTH), nullable=False)
    # tujuan pas notifikasi diklik, path di dalem ALR aja (boleh kosong)
    target_url = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))

    def __repr__(self):
        """Representasi singkat buat debugging."""
        return f"<UserNotification user={self.user_id} read={self.is_read}>"

"""Model ORM tabel otp_codes: OTP login yg lagi aktif/udah kepake."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin

class OtpCode(CreatedAtMixin, db.Model):
    """Satu baris = satu OTP yg pernah dikirim ke user."""
    __tablename__ = "otp_codes"

    id = db.Column(db.Integer, primary_key=True)
    # kalau user dihapus, OTP-nya ikut kehapus
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # hash OTP (64 karakter hex
    code_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    # udah berapa kali salah ketik OTP ini
    attempt_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    # kalau OTP udah kepake / hangus
    is_used = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))

    def __repr__(self):
        """Representasi singkat buat debugging (hash-nya sengaja ga ditampilin)."""
        return f"<OtpCode user_id={self.user_id} is_used={self.is_used}>"
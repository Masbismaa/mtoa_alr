"""Model ORM tabel pending_registrations: percobaan daftar yg nunggu kode verifikasi email."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin

class PendingRegistration(CreatedAtMixin, db.Model):
    """Satu baris = satu percobaan daftar. Akun di tabel users BARU dibikin setelah kode di baris ini bener.

    Kenapa ga langsung bikin user (belum aktif): dulu begitu, dan daftar ulang pake email yg sama bisa nimpa
    password percobaan sebelumnya -> pemilik email masukin kode, akunnya malah jadi pake password orang lain.
    Sekarang tiap percobaan punya baris + token sendiri (token cuma ada di session si pendaftar), jadi kode
    cuma berlaku buat percobaan itu dan percobaan orang lain ga bisa ngubahnya.
    """
    __tablename__ = "pending_registrations"

    id = db.Column(db.Integer, primary_key=True)
    # ga unique: beberapa orang boleh lagi nyoba daftar pake email yg sama, yg menang yg kodenya bener duluan
    email = db.Column(db.String(255), nullable=False, index=True)
    # sha256 token acak di session pendaftar (token aslinya ga disimpen di DB)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)

    # data akun yg bakal dibikin kalau kodenya bener (password udah di-hash argon2)
    full_name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # kode verifikasi (hash HMAC, sama kayak OTP login) + batasnya
    code_hash = db.Column(db.String(64), nullable=False)
    code_expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    attempt_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    # kapan kode terakhir dikirim (buat jeda kirim ulang)
    last_sent_at = db.Column(db.DateTime(timezone=True), nullable=False)

    def __repr__(self):
        """Representasi singkat buat debugging (hash & data diri sengaja ga ditampilin)."""
        return f"<PendingRegistration id={self.id}>"

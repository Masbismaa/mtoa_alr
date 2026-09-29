"""Model ORM untuk tabel categories (SR-01 Master Category)."""

from app.extensions import db
from app.models.base_model import TimestampMixin


class Category(TimestampMixin, db.Model):
    """Kategori link akses: Web, Application, Network, General."""

    __tablename__ = "categories"

    # --- Kolom data kategori ---
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)

    # --- Status aktif (kategori nonaktif tidak muncul di form input) ---
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))

    def __repr__(self):
        """Representasi singkat untuk debugging."""
        return f"<Category {self.name}>"
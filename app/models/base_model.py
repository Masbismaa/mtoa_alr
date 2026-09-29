"""Mixin kolom umum yang dipakai ulang oleh semua model (DRY)."""

from sqlalchemy import func

from app.extensions import db

class CreatedAtMixin:
    """Cuma kolom created_at. Dipake tabel yg datanya ga pernah diubah (audit log)."""

    # Waktu data dibuat diisi otomatis oleh database
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

class TimestampMixin(CreatedAtMixin):
    """Menambahkan kolom created_at dan updated_at ke model yang mewarisinya."""

    # Waktu data terakhir diubah diperbarui otomatis setiap update
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
"""Model ORM tabel access_entry_fields."""

from app.extensions import db
from app.models.base_model import TimestampMixin

class AccessEntryField(TimestampMixin, db.Model):
    """Satu field tambahan. Isinya HTML dari editor yg udah disanitasi."""
    __tablename__ = "access_entry_fields"

    id = db.Column(db.Integer, primary_key=True)
    # kalau data link-nya dihapus, field-nya ikut kehapus
    access_entry_id = db.Column(
        db.Integer,
        db.ForeignKey("access_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_label = db.Column(db.String(100), nullable=False)
    field_content = db.Column(db.Text, nullable=False)
    # urutan tampil (1, 2, 3, ...)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    access_entry = db.relationship("AccessEntry", back_populates="custom_field_list")

    def __repr__(self):
        """Representasi singkat buat debugging."""
        return f"<AccessEntryField {self.field_label}>"
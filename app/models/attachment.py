"""Model ORM tabel attachments."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin


class Attachment(CreatedAtMixin, db.Model):
    """Satu file lampiran. File aslinya di folder uploads, di sini cuma info-nya."""
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    access_entry_id = db.Column(
        db.Integer,
        db.ForeignKey("access_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # yg upload
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # nama asli cuma buat tampilan, nama di disk diacak (uuid)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(64), nullable=False, unique=True)
    content_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)

    access_entry = db.relationship("AccessEntry", back_populates="attachment_list")

    __table_args__ = (
        db.CheckConstraint("file_size > 0", name="file_size_positive"),
    )

    def __repr__(self):
        return f"<Attachment {self.original_filename}>"
"""Model tabel group_entry_viewers: anggota yg boleh liat link terbatas di group."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin

class GroupEntryViewer(CreatedAtMixin, db.Model):
    """Satu anggota yg dikasih izin liat satu link terbatas."""
    __tablename__ = "group_entry_viewers"
    id = db.Column(db.Integer, primary_key=True)
    group_entry_id = db.Column(db.Integer, db.ForeignKey("group_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_entry = db.relationship("GroupEntry", back_populates="viewer_list")
    user = db.relationship("User")
    __table_args__ = (
        db.UniqueConstraint("group_entry_id", "user_id"),
    )

    def __repr__(self):
        return f"<GroupEntryViewer entry={self.group_entry_id} user={self.user_id}>"

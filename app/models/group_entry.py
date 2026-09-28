"""Model tabel group_entries: link apa aja yg ada di group."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin

class GroupEntry(CreatedAtMixin, db.Model):
    """Satu link di satu group. user_id = yg nambahin."""
    __tablename__ = "group_entries"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    access_entry_id = db.Column(db.Integer, db.ForeignKey("access_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    group = db.relationship("Group", back_populates="group_entry_list")
    access_entry = db.relationship("AccessEntry", back_populates="group_entry_list")
    added_by = db.relationship("User")
    __table_args__ = (
        db.UniqueConstraint("group_id", "access_entry_id"),
    )

    def __repr__(self):
        return f"<GroupEntry group={self.group_id} entry={self.access_entry_id}>"
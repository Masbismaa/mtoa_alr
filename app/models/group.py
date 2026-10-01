"""Model tabel groups: workspace tim buat ngumpulin link."""
from app.extensions import db
from app.models.base_model import TimestampMixin

class Group(TimestampMixin, db.Model):
    """Satu group. user_id = pemilik (yg bikin)."""
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    owner = db.relationship("User")
    member_list = db.relationship(
        "GroupMember", back_populates="group", order_by="GroupMember.id", cascade="all, delete-orphan",
    )
    group_entry_list = db.relationship(
        "GroupEntry", back_populates="group", order_by="GroupEntry.id", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Group {self.name}>"
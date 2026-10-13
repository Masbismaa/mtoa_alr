"""Model tabel user_favorites: link yg ditandai bintang (favorit) sama satu user."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin

class UserFavorite(CreatedAtMixin, db.Model):
    """Satu user nandain satu link. Link-nya kehapus -> favoritnya ikut kehapus (cascade di AccessEntry)."""
    __tablename__ = "user_favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_entry_id = db.Column(db.Integer, db.ForeignKey("access_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    access_entry = db.relationship("AccessEntry", back_populates="favorite_list")
    __table_args__ = (
        db.UniqueConstraint("user_id", "access_entry_id"),
    )

    def __repr__(self):
        return f"<UserFavorite user={self.user_id} entry={self.access_entry_id}>"

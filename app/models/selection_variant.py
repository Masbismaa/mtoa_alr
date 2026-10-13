"""Model tabel selection_variants: Kriteria Pencarian yg disimpen user pake nama (Variant ala Select Screen SAP)."""
from app.extensions import db
from app.models.base_model import CreatedAtMixin

class SelectionVariant(CreatedAtMixin, db.Model):
    """Satu variant = isian Kriteria Pencarian (query string) di satu layar, punya satu user."""
    __tablename__ = "selection_variants"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # path layarnya, misal /entries/ atau /categories/5 (variant cuma muncul di layar yg sama)
    screen_path = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    query_text = db.Column(db.String(2000), nullable=False, default="", server_default="")
    __table_args__ = (
        db.UniqueConstraint("user_id", "screen_path", "name"),
    )

    def __repr__(self):
        return f"<SelectionVariant user={self.user_id} {self.screen_path} {self.name}>"

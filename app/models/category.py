# Model ORM untuk tabel categories. Bisa bertingkat: kategori utama + sampai 3 sub (level).
from app.extensions import db
from app.models.base_model import TimestampMixin

class Category(TimestampMixin, db.Model):
    # kategori utama: Web, Application, Network, General. Boleh ditambah sama admin. Bisa punya sub-kategori (maks 3 level)
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    # induknya, kosong kalau ini kategori utama
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    # pembuatnya, kosong buat kategori bawaan hasil seed. Kalau user-nya dihapus, kategorinya tetep ada
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    # kategori nonaktif (termasuk anak-anaknya) ga muncul di form & tampilan forum
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))

    parent = db.relationship("Category", remote_side=[id])
    creator = db.relationship("User")

    __table_args__ = (
        # nama boleh sama asal induknya beda (Web › SAP dan Application › SAP)
        db.UniqueConstraint("parent_id", "name"),
        # NULL dianggap beda sama database, jadi nama kategori utama dijaga pake index khusus
        db.Index(
            "ix_categories_root_name", "name", unique=True,
            postgresql_where=db.text("parent_id IS NULL"), sqlite_where=db.text("parent_id IS NULL"),
        ),
    )

    def __repr__(self):
        # representasi string buat debug
        return f"<Category {self.id} {self.name}>"
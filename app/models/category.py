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

    def __repr__(self):
        # representasi string buat debug
        return f"<Category {self.id} {self.name}>"

# Nama kategori unik per induk, huruf besar/kecil dianggap SAMA (SAP = sap), sama persis kayak aturan di
# category_service.find_sibling_by_name. Dijaga juga di database biar 2 request barengan ga bisa lolos dua-duanya.
# Nama boleh sama asal induknya beda (Web › SAP dan Application › SAP). Dibikin 2 index soalnya NULL (kategori utama)
# dianggap beda-beda sama database.
db.Index(
    "ix_categories_parent_lower_name", Category.parent_id, db.func.lower(Category.name), unique=True,
    postgresql_where=Category.parent_id.is_not(None), sqlite_where=Category.parent_id.is_not(None),
)
db.Index(
    "ix_categories_root_lower_name", db.func.lower(Category.name), unique=True,
    postgresql_where=Category.parent_id.is_(None), sqlite_where=Category.parent_id.is_(None),
)
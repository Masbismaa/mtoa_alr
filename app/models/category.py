# Model ORM untuk tabel categories. Bisa bertingkat: kategori utama + sampai 3 sub (level).
from app.extensions import db
from app.models.base_model import TimestampMixin

class Category(TimestampMixin, db.Model):
    # kategori utama bawaan sama buat semua akun; sub-kategori milik pribadi pembuatnya
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    # induknya, kosong kalau ini kategori utama
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    # pembuat = pemilik sub-kategori, kosong buat kategori bawaan hasil seed. Kalau user-nya dihapus, kategorinya tetep ada
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

# nama unik per induk & pemilik tanpa beda huruf (sama kayak find_sibling_by_name); 2 index karena NULL
db.Index(
    "ix_categories_parent_owner_lower_name", Category.parent_id, Category.user_id, db.func.lower(Category.name), unique=True,
    postgresql_where=Category.parent_id.is_not(None), sqlite_where=Category.parent_id.is_not(None),
)
# kategori utama unik per pemilik (bawaan dianggap pemilik 0)
db.Index(
    "ix_categories_root_owner_lower_name", db.func.coalesce(Category.user_id, 0), db.func.lower(Category.name), unique=True,
    postgresql_where=Category.parent_id.is_(None), sqlite_where=Category.parent_id.is_(None),
)
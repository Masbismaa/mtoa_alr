"""Model ORM tabel access_entries."""
from app.extensions import db
from app.models.base_model import TimestampMixin
from app.utils.constants import LINK_STATUS_LIST, LINK_STATUS_UNKNOWN, VISIBILITY_LIST, VISIBILITY_PRIVATE
from app.utils.sql_helper import build_sql_in_list

class AccessEntry(TimestampMixin, db.Model):
    """Data link akses ICT + petunjuk/kredensialnya."""

    __tablename__ = "access_entries"

    id = db.Column(db.Integer, primary_key=True)

    # pemilik data (created by) & kategori
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)

    # data utama
    title = db.Column(db.String(150), nullable=False)
    url = db.Column(db.String(2048), nullable=True, index=True)
    address = db.Column(db.String(255), nullable=True, index=True)
    port = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(150), nullable=True)

    # password / petunjuk akses, disimpen udah dienkripsi (Fernet)
    encrypted_access_note = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)

    # default private biar aman kalau lupa milih
    visibility = db.Column(db.String(10), nullable=False, default=VISIBILITY_PRIVATE, server_default=VISIBILITY_PRIVATE)
    # status link, diisi lewat tombol cek status
    status = db.Column(db.String(20), nullable=False, default=LINK_STATUS_UNKNOWN, server_default=LINK_STATUS_UNKNOWN)
    # kapan terakhir dicek + alasannya (misal "HTTP 200", "Timeout")
    status_checked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status_note = db.Column(db.String(255), nullable=True)

    # relasi
    owner = db.relationship("User")
    category = db.relationship("Category")
    custom_field_list = db.relationship(
        "AccessEntryField",
        back_populates="access_entry",
        order_by="AccessEntryField.sort_order",
        cascade="all, delete-orphan",
    )

    attachment_list = db.relationship(
        "Attachment",
        back_populates="access_entry",
        order_by="Attachment.id",
        cascade="all, delete-orphan",
    )

    group_entry_list = db.relationship(
        "GroupEntry",
        back_populates="access_entry",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.CheckConstraint(f"visibility IN ({build_sql_in_list(VISIBILITY_LIST)})", name="visibility_valid"),
        db.CheckConstraint(f"status IN ({build_sql_in_list(LINK_STATUS_LIST)})", name="status_valid"),
        db.CheckConstraint("port IS NULL OR (port >= 1 AND port <= 65535)", name="port_valid"),
    )

    def __repr__(self):
        """Representasi singkat buat debugging (kredensial sengaja ga ditampilin)."""
        return f"<AccessEntry {self.id} {self.title}>"
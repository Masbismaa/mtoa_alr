"""Model ORM tabel audit_logs (SR-15). Sekali ditulis, ga boleh diubah/dihapus."""

from sqlalchemy import event

from app.extensions import db
from app.models.base_model import CreatedAtMixin
from app.utils.constants import AUDIT_ACTION_LIST
from app.utils.exceptions import ImmutableRecordError
from app.utils.sql_helper import build_sql_in_list

class AuditLog(CreatedAtMixin, db.Model):
    """Catatan siapa ngapain, kapan, dari IP mana, data lama vs baru."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    # pelaku. user_id bisa kosong (misal login gagal), email disimpen juga sebagai snapshot
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    actor_email = db.Column(db.String(255), nullable=True)

    # aksi + data apa yg kena
    action = db.Column(db.String(30), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.String(50), nullable=True)

    # isi data sebelum & sesudah (field rahasia udah disamarin sama audit_service)
    old_data = db.Column(db.JSON, nullable=True)
    new_data = db.Column(db.JSON, nullable=True)

    # info koneksi
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # action cuma boleh yg ada di AUDIT_ACTION_LIST
    __table_args__ = (
        db.Index("ix_audit_logs_user_created", "user_id", "created_at", "id"),
        db.CheckConstraint(f"action IN ({build_sql_in_list(AUDIT_ACTION_LIST)})", name="action_valid"),
    )

    def __repr__(self):
        """Representasi singkat buat debugging."""
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"

# kunci lapis 1 (Python): tolak update & delete lewat ORM
# lapis 2 ada di trigger PostgreSQL (file migrasi)
@event.listens_for(AuditLog, "before_update")
def block_audit_log_update(mapper, connection, target):
    """Stop kalau ada kode yg nyoba ngubah audit log."""
    raise ImmutableRecordError("Audit log ga boleh diubah")

@event.listens_for(AuditLog, "before_delete")
def block_audit_log_delete(mapper, connection, target):
    """Stop kalau ada kode yg nyoba ngehapus audit log."""
    raise ImmutableRecordError("Audit log ga boleh dihapus")

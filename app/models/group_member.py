"""Model tabel group_members: siapa aja anggota group + status undangannya."""
from app.extensions import db
from app.models.base_model import TimestampMixin
from app.utils.constants import GROUP_MEMBER_STATUS_INVITED, GROUP_MEMBER_STATUS_LIST, GROUP_ROLE_LIST, GROUP_ROLE_MEMBER
from app.utils.sql_helper import build_sql_in_list

class GroupMember(TimestampMixin, db.Model):
    """Satu user di satu group. Status invited = belum nerima undangan."""
    __tablename__ = "group_members"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False, default=GROUP_ROLE_MEMBER, server_default=GROUP_ROLE_MEMBER)
    status = db.Column(db.String(10), nullable=False, default=GROUP_MEMBER_STATUS_INVITED, server_default=GROUP_MEMBER_STATUS_INVITED)
    # anggota baru cuma bisa liat, pemilik yg ngasih izin nambah link (pemilik sendiri selalu boleh)
    can_add_entry = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))
    group = db.relationship("Group", back_populates="member_list")
    user = db.relationship("User")
    __table_args__ = (
        db.UniqueConstraint("group_id", "user_id"),
        db.CheckConstraint(f"role IN ({build_sql_in_list(GROUP_ROLE_LIST)})", name="role_valid"),
        db.CheckConstraint(f"status IN ({build_sql_in_list(GROUP_MEMBER_STATUS_LIST)})", name="status_valid"),
    )

    def __repr__(self):
        return f"<GroupMember group={self.group_id} user={self.user_id} {self.status}>"
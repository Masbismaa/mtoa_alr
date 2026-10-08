"""Kumpulan model ORM, semua diimport di sini biar kebaca Flask-Migrate."""
from app.models.access_entry import AccessEntry
from app.models.access_entry_field import AccessEntryField
from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.group import Group
from app.models.group_entry import GroupEntry
from app.models.group_entry_viewer import GroupEntryViewer
from app.models.group_member import GroupMember
from app.models.otp_code import OtpCode
from app.models.user import User
from app.models.user_preference import UserPreference
from app.models.user_permission import UserPermission
from app.models.link_monitor_run import LinkMonitorRun
from app.models.user_notification import UserNotification
from app.extensions import db

# jumlah lampiran dihitung di SQL (buat tabel & export), biar ga perlu ngambil semua baris lampiran.
# deferred: cuma ikut query yg minta lewat undefer(AccessEntry.attachment_count).
# ditaruh di sini karena butuh dua model yg saling refer
AccessEntry.attachment_count = db.column_property(
    db.select(db.func.count(Attachment.id))
    .where(Attachment.access_entry_id == AccessEntry.id)
    .correlate_except(Attachment)
    .scalar_subquery(),
    deferred=True,
)

__all__ = [
    "AccessEntry", "AccessEntryField", "Attachment", "AuditLog", "Category",
    "Group", "GroupEntry", "GroupEntryViewer", "GroupMember", "OtpCode", "User", "UserPreference",
    "UserPermission", "LinkMonitorRun", "UserNotification"
]

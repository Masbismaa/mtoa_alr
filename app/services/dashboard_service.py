"""Isi halaman dashboard: angka ringkas (bisa diklik ke Link List), link yg perlu dicek, & aktivitas tim.
Semua angka ngikut hak akses user (data Private orang lain ga ikut kehitung / ga ditampilin)."""
from collections import namedtuple
from datetime import timedelta

from app.extensions import db
from app.models import AccessEntry, AuditLog, User, UserFavorite
from app.security.access_policy import build_visible_entry_filter, is_admin, is_private_audit_data
from app.services.access_entry_service import count_visible_entry_summary
from app.services.category_service import build_forum_row_list
from app.services.link_monitor_service import build_monitor_summary, get_monitor_run
from app.services.user_service import build_status_condition, build_user_summary
from app.services.group_service import (
    count_active_member,
    count_pending_invitation,
    count_visible_group_entries,
    list_user_group,
)
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_EXPORT,
    AUDIT_ACTION_IMPORT,
    AUDIT_ACTION_LOGIN_FAILED,
    AUDIT_ACTION_PASSWORD_CHANGE,
    AUDIT_ACTION_UPDATE,
    DASHBOARD_ACTIVITY_DAY_COUNT,
    DASHBOARD_ATTENTION_LIMIT,
    DASHBOARD_RECENT_ACTIVITY_LIMIT,
    DASHBOARD_TEAM_ACTIVITY_LIMIT,
    USER_STATUS_LOCKED,
    LINK_STATUS_DOWN,
    LINK_STATUS_UNKNOWN,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)
from app.utils.datetime_helper import to_local_time, utc_now

# AKTIVITAS TIM
# Kalimat per jenis aktivitas: (satu kali, beberapa kali). Yg ga ada di sini ga pernah tampil di dashboard
# (login/logout, preferensi tampilan, group: isinya urusan anggota group itu aja).
ActivityText = namedtuple("ActivityText", ["single", "plural", "is_admin_only"])
ACTIVITY_TEXT_DICT = {
    # boleh diliat semua user: cuma link Public & kategori (emang udah keliatan semua orang)
    (AUDIT_ACTION_CREATE, "access_entries"): ActivityText("added a public link", "added {count} public links", False),
    (AUDIT_ACTION_UPDATE, "access_entries"): ActivityText("updated a public link", "updated public links {count} times", False),
    (AUDIT_ACTION_DELETE, "access_entries"): ActivityText("deleted a public link", "deleted {count} public links", False),
    (AUDIT_ACTION_CREATE, "categories"): ActivityText("added a category", "added {count} categories", False),
    (AUDIT_ACTION_UPDATE, "categories"): ActivityText("changed a category", "changed {count} categories", False),
    (AUDIT_ACTION_DELETE, "categories"): ActivityText("deleted a category", "deleted {count} categories", False),
    # khusus admin: akun & keamanan. Isi datanya ga ditampilin, cuma siapa ngapain
    (AUDIT_ACTION_CREATE, "users"): ActivityText("joined ALR", "joined ALR", True),
    (AUDIT_ACTION_UPDATE, "users"): ActivityText("changed a user account", "changed user accounts {count} times", True),
    (AUDIT_ACTION_DELETE, "users"): ActivityText("deleted a user account", "deleted {count} user accounts", True),
    (AUDIT_ACTION_PASSWORD_CHANGE, "users"): ActivityText("changed their password", "changed their password {count} times", True),
    (AUDIT_ACTION_LOGIN_FAILED, "users"): ActivityText("failed to log in", "failed to log in {count} times", True),
    (AUDIT_ACTION_EXPORT, "access_entries"): ActivityText("exported links to Excel", "exported links to Excel {count} times", True),
    (AUDIT_ACTION_IMPORT, "access_entries"): ActivityText("imported links from Excel", "imported links from Excel {count} times", True),
}
# audit log yg dibaca buat feed dibatesin (feed cuma nampilin beberapa baris hasil gabungan)
ACTIVITY_SCAN_LIMIT = 300
# judul yg disebut per baris gabungan, sisanya cukup dihitung
ACTIVITY_TITLE_LIMIT = 3


def read_title(audit_log):
    """Judul link / nama kategori dari data audit (data baru dulu, kalau dihapus pake data lama)."""
    data_dict = audit_log.new_data or audit_log.old_data or {}
    return data_dict.get("title") or data_dict.get("name")


def find_public_entry_id_set(audit_log_list):
    """Id link yg SEKARANG masih Public dari daftar aktivitas link (yg udah diganti Private / dihapus ga ikut)."""
    id_list = {int(log.entity_id) for log in audit_log_list
               if log.entity_type == "access_entries" and (log.entity_id or "").isdigit()}
    if not id_list:
        return set()
    return set(db.session.execute(
        db.select(AccessEntry.id).where(AccessEntry.id.in_(id_list), AccessEntry.visibility == VISIBILITY_PUBLIC)
    ).scalars())


def is_shown_to_viewer(audit_log, activity_text, public_entry_id_set, is_viewer_admin):
    """Aktivitas ini boleh tampil ke yg lagi liat dashboard?"""
    if activity_text.is_admin_only:
        return is_viewer_admin
    if audit_log.entity_type != "access_entries":
        return True
    if is_private_audit_data(audit_log):
        return False
    # link: create/update cuma kalau link-nya sekarang masih Public; delete kalau pas dihapus dia Public
    if audit_log.action == AUDIT_ACTION_DELETE:
        return (audit_log.old_data or {}).get("visibility") == VISIBILITY_PUBLIC
    return (audit_log.entity_id or "").isdigit() and int(audit_log.entity_id) in public_entry_id_set


def build_actor_name_dict(audit_log_list):
    """user_id -> nama lengkap (akun yg dihapus otomatis kebaca "Deleted account")."""
    user_id_set = {log.user_id for log in audit_log_list if log.user_id}
    if not user_id_set:
        return {}
    return dict(db.session.execute(db.select(User.id, User.full_name).where(User.id.in_(user_id_set))).all())


def list_team_activity(viewer):
    """Aktivitas orang lain beberapa hari terakhir, dibikin kalimat & digabung biar ga spam:
    aktivitas yg sama dari orang yg sama di hari yg sama jadi SATU baris ("Budi added 5 public links").
    User biasa cuma liat yg emang Public; admin juga liat aktivitas akun & keamanan."""
    is_viewer_admin = is_admin(viewer)
    since = utc_now() - timedelta(days=DASHBOARD_ACTIVITY_DAY_COUNT)
    allowed_activity = db.or_(*[
        db.and_(AuditLog.action == action, AuditLog.entity_type == entity_type)
        for (action, entity_type), text in ACTIVITY_TEXT_DICT.items()
        if is_viewer_admin or not text.is_admin_only
    ])
    query = db.select(AuditLog).where(
        AuditLog.created_at >= since,
        db.or_(AuditLog.user_id.is_(None), AuditLog.user_id != viewer.id),
        allowed_activity,
    )
    if not is_viewer_admin:
        # Saring sebelum LIMIT: login/preferensi dan riwayat Private tidak memenuhi slot feed publik.
        public_ids = db.select(db.cast(AccessEntry.id, db.String)).where(AccessEntry.visibility == VISIBILITY_PUBLIC)
        query = query.where(db.or_(
            AuditLog.entity_type != "access_entries",
            db.and_(
                db.func.coalesce(AuditLog.old_data["visibility"].as_string(), "") != VISIBILITY_PRIVATE,
                db.func.coalesce(AuditLog.new_data["visibility"].as_string(), "") != VISIBILITY_PRIVATE,
                db.or_(
                    db.and_(AuditLog.action == AUDIT_ACTION_DELETE,
                            AuditLog.old_data["visibility"].as_string() == VISIBILITY_PUBLIC),
                    db.and_(AuditLog.action != AUDIT_ACTION_DELETE, AuditLog.entity_id.in_(public_ids)),
                ),
            ),
        ))
    audit_log_list = list(db.session.scalars(query.order_by(AuditLog.id.desc()).limit(ACTIVITY_SCAN_LIMIT)))
    public_entry_id_set = find_public_entry_id_set(audit_log_list)
    actor_name_dict = build_actor_name_dict(audit_log_list)

    group_dict = {}
    for log in audit_log_list:
        activity_text = ACTIVITY_TEXT_DICT[(log.action, log.entity_type)]
        if not is_shown_to_viewer(log, activity_text, public_entry_id_set, is_viewer_admin):
            if not is_viewer_admin:
                continue
            # Admin melihat ringkasan aksi saja; judul, URL, kredensial, dan isi riwayat Private tidak ditampilkan.
            activity_text = ActivityText(
                activity_text.single.replace("a public link", "a link"),
                activity_text.plural.replace("public links", "links"), True,
            )
        local_day = to_local_time(log.created_at).date()
        key = (log.user_id or log.actor_email, log.action, log.entity_type, local_day, activity_text.is_admin_only)
        if key not in group_dict:
            # urutannya terbaru dulu, jadi baris pertama yg ketemu = waktu terakhir aktivitas itu
            group_dict[key] = {
                "actor_name": actor_name_dict.get(log.user_id) or log.actor_email or "System",
                "activity_text": activity_text,
                "created_at": log.created_at,
                "count": 0,
                "title_list": [],
                "entry_id": None,
            }
        item = group_dict[key]
        item["count"] += 1
        title = read_title(log) if not activity_text.is_admin_only else None
        if title and title not in item["title_list"]:
            item["title_list"].append(title)
        if (item["count"] == 1 and not activity_text.is_admin_only
                and log.entity_type == "access_entries" and log.action != AUDIT_ACTION_DELETE):
            item["entry_id"] = int(log.entity_id) if (log.entity_id or "").isdigit() else None

    item_list = []
    for item in list(group_dict.values())[:DASHBOARD_TEAM_ACTIVITY_LIMIT]:
        activity_text = item["activity_text"]
        title_list = item["title_list"]
        item_list.append({
            "actor_name": item["actor_name"],
            "text": activity_text.single if item["count"] == 1 else activity_text.plural.format(count=item["count"]),
            "title_text": ", ".join(title_list[:ACTIVITY_TITLE_LIMIT]) + ("…" if len(title_list) > ACTIVITY_TITLE_LIMIT else ""),
            # cuma 1 link (masih Public) -> bisa diklik ke detail-nya
            "entry_id": item["entry_id"] if item["count"] == 1 else None,
            "created_at": item["created_at"],
            "is_admin_only": activity_text.is_admin_only,
        })
    return item_list


# ANGKA RINGKAS & YG PERLU DICEK

def count_visible_favorite(user):
    """Favorit yg link-nya masih boleh diliat."""
    return db.session.execute(
        db.select(db.func.count(UserFavorite.id))
        .join(AccessEntry, AccessEntry.id == UserFavorite.access_entry_id)
        .where(UserFavorite.user_id == user.id, build_visible_entry_filter(user))
    ).scalar()


def list_own_down_entry(user):
    """Link milik user yg hasil cek terakhirnya Down: yg paling perlu dibenerin pemiliknya."""
    return db.session.execute(
        db.select(AccessEntry)
        .where(AccessEntry.user_id == user.id, AccessEntry.status == LINK_STATUS_DOWN)
        .order_by(AccessEntry.status_checked_at.desc(), AccessEntry.id.desc())
        .limit(DASHBOARD_ATTENTION_LIMIT)
    ).scalars().all()


def list_recent_own_activity(user):
    """Aktivitas terakhir user sendiri (dari audit log)."""
    return db.session.execute(
        db.select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(DASHBOARD_RECENT_ACTIVITY_LIMIT)
    ).scalars().all()


# TAMPILAN PER PERAN
# admin: ringkasan sistem & tugas admin.
# User Entry (termasuk yg dikasih akses tambahan): data sendiri aja (+ panduan mulai kalau belum punya link).

def build_admin_panel():
    """Ringkasan sistem buat admin: akun, hasil cek link, antrean monitoring, akun yg lagi kekunci."""
    monitor_run = get_monitor_run()
    return {
        "user_summary": build_user_summary(),
        "monitor_summary": build_monitor_summary(),
        "monitor_state": monitor_run.state if monitor_run else "idle",
        "locked_user_list": db.session.execute(
            db.select(User).where(build_status_condition(USER_STATUS_LOCKED))
            .order_by(User.locked_until.desc()).limit(DASHBOARD_ATTENTION_LIMIT)
        ).scalars().all(),
    }


def build_dashboard_dict(user):
    """Semua data yg dibutuhin halaman dashboard dalam satu dict."""
    local_hour = to_local_time(utc_now()).hour
    greeting = "Good morning" if 5 <= local_hour < 12 else "Good afternoon" if 12 <= local_hour < 17 else "Good evening"
    summary_dict = count_visible_entry_summary(user)
    group_list = list_user_group(user)
    is_viewer_admin = is_admin(user)
    return {
        "greeting": greeting,
        "access_kind": "admin" if is_viewer_admin else "standard",
        "admin_panel": build_admin_panel() if is_viewer_admin else None,
        "summary": summary_dict,
        "own_count": summary_dict["own"],
        "favorite_count": count_visible_favorite(user),
        "down_count": summary_dict["status"].get(LINK_STATUS_DOWN, 0),
        "unknown_count": summary_dict["status"].get(LINK_STATUS_UNKNOWN, 0),
        "own_down_entry_list": list_own_down_entry(user),
        "team_activity_list": list_team_activity(user),
        "group_list": group_list,
        "group_entry_count_dict": count_visible_group_entries(user, group_list),
        "active_member_count_dict": count_active_member(group_list),
        "invitation_count": count_pending_invitation(user),
        "forum_row_list": build_forum_row_list(user),
        "recent_activity_list": list_recent_own_activity(user),
    }

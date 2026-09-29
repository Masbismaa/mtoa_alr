"""Angka & grafik buat halaman dashboard. Semua angka ngikut hak akses user (data Private orang lain ga ikut kehitung)."""
from datetime import timedelta
from app.extensions import db
from app.models import AccessEntry, Attachment, AuditLog
from app.security.access_policy import build_visible_entry_filter
from app.services.access_entry_service import count_visible_entry_summary, get_active_category_list
from app.services.group_service import list_pending_invitation, list_user_group
from app.utils.chart_helper import build_bar_list, build_sparkline, calculate_change_percent, calculate_percent
from app.utils.constants import DASHBOARD_CHART_DAY_COUNT, DASHBOARD_RECENT_ACTIVITY_LIMIT
from app.utils.datetime_helper import DISPLAY_TIMEZONE, to_utc_aware, utc_now


def build_local_date_list(day_count):
    """Tanggal (WIB) n hari terakhir, urut dari yg paling lama sampe hari ini."""
    today = utc_now().astimezone(DISPLAY_TIMEZONE).date()
    return [today - timedelta(days=offset) for offset in range(day_count - 1, -1, -1)]


def count_per_local_date(datetime_list, date_list):
    """Hitung jumlah kejadian per tanggal WIB (dihitung di Python biar sama di PostgreSQL & SQLite)."""
    count_dict = {local_date: 0 for local_date in date_list}
    for value in datetime_list:
        local_date = to_utc_aware(value).astimezone(DISPLAY_TIMEZONE).date()
        if local_date in count_dict:
            count_dict[local_date] += 1
    return [count_dict[local_date] for local_date in date_list]


def list_created_at_since(query, column, day_count):
    """Ambil waktu dibuat dalam n hari terakhir (+1 hari cadangan beda zona waktu)."""
    since = utc_now() - timedelta(days=day_count + 1)
    return db.session.execute(query.where(column >= since)).scalars().all()


def count_own_entry(user):
    """Jumlah link milik user sendiri."""
    return db.session.execute(db.select(db.func.count(AccessEntry.id)).where(AccessEntry.user_id == user.id)).scalar()


def count_visible_entry_with_attachment(user):
    """Jumlah link (yg boleh diliat) yg punya lampiran."""
    return db.session.execute(
        db.select(db.func.count(db.func.distinct(Attachment.access_entry_id)))
        .join(AccessEntry, AccessEntry.id == Attachment.access_entry_id)
        .where(build_visible_entry_filter(user))
    ).scalar()


def build_category_card_list(user, total_count):
    """Jumlah link per kategori aktif."""
    row_list = db.session.execute(
        db.select(AccessEntry.category_id, db.func.count(AccessEntry.id))
        .where(build_visible_entry_filter(user))
        .group_by(AccessEntry.category_id)
    ).all()
    count_by_category_dict = dict(row_list)
    return [
        {
            "id": category.id,
            "name": category.name,
            "count": count_by_category_dict.get(category.id, 0),
            "percent": calculate_percent(count_by_category_dict.get(category.id, 0), total_count),
        }
        for category in get_active_category_list()
    ]


def list_recent_own_activity(user):
    """Aktivitas terakhir user sendiri (dari audit log)."""
    return db.session.execute(
        db.select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(DASHBOARD_RECENT_ACTIVITY_LIMIT)
    ).scalars().all()


def build_dashboard_dict(user):
    """Semua data yg dibutuhin halaman dashboard dalam satu dict."""
    summary_dict = count_visible_entry_summary(user)
    total_count = summary_dict["total"]
    own_count = count_own_entry(user)
    attachment_entry_count = count_visible_entry_with_attachment(user)

    # link baru: 7 hari ini vs 7 hari sebelumnya
    two_week_date_list = build_local_date_list(DASHBOARD_CHART_DAY_COUNT * 2)
    entry_created_list = list_created_at_since(
        db.select(AccessEntry.created_at).where(build_visible_entry_filter(user)),
        AccessEntry.created_at, DASHBOARD_CHART_DAY_COUNT * 2,
    )
    two_week_count_list = count_per_local_date(entry_created_list, two_week_date_list)
    this_week_count_list = two_week_count_list[DASHBOARD_CHART_DAY_COUNT:]
    last_week_count_list = two_week_count_list[:DASHBOARD_CHART_DAY_COUNT]

    # aktivitas user sendiri 7 hari terakhir
    week_date_list = build_local_date_list(DASHBOARD_CHART_DAY_COUNT)
    activity_created_list = list_created_at_since(
        db.select(AuditLog.created_at).where(AuditLog.user_id == user.id),
        AuditLog.created_at, DASHBOARD_CHART_DAY_COUNT,
    )
    activity_count_list = count_per_local_date(activity_created_list, week_date_list)

    return {
        "summary": summary_dict,
        "own_count": own_count,
        "own_percent": calculate_percent(own_count, total_count),
        "attachment_entry_count": attachment_entry_count,
        "attachment_percent": calculate_percent(attachment_entry_count, total_count),
        "public_percent": calculate_percent(summary_dict["public"], total_count),
        "private_percent": calculate_percent(summary_dict["private"], total_count),
        "new_link_count": sum(this_week_count_list),
        "new_link_change_percent": calculate_change_percent(sum(this_week_count_list), sum(last_week_count_list)),
        "new_link_chart": build_sparkline(this_week_count_list),
        "trend_chart": build_sparkline(two_week_count_list),
        "activity_count": sum(activity_count_list),
        "activity_bar_list": build_bar_list(activity_count_list),
        "group_list": list_user_group(user),
        "invitation_count": len(list_pending_invitation(user)),
        "category_card_list": build_category_card_list(user, total_count),
        "recent_activity_list": list_recent_own_activity(user),
    }

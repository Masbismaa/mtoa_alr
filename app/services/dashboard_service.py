"""Angka & grafik buat halaman dashboard. Semua angka ngikut hak akses user (data Private orang lain ga ikut kehitung)."""
from datetime import timedelta
from app.extensions import db
from app.models import AccessEntry, Attachment, AuditLog
from app.security.access_policy import build_visible_entry_filter
from app.services.access_entry_service import count_visible_entry_summary
from app.services.category_service import build_forum_row_list
from app.services.group_service import count_visible_group_entries, list_pending_invitation, list_user_group
from app.utils.chart_helper import build_bar_list, build_sparkline, calculate_change_percent, calculate_percent
from app.utils.constants import DASHBOARD_CHART_DAY_COUNT, DASHBOARD_RECENT_ACTIVITY_LIMIT
from app.utils.datetime_helper import build_utc_range_from_local_date, to_local_time, utc_now


def build_local_date_list(day_count):
    """Tanggal (WIB) n hari terakhir, urut dari yg paling lama sampe hari ini."""
    today = to_local_time(utc_now()).date()
    return [today - timedelta(days=offset) for offset in range(day_count - 1, -1, -1)]


def count_per_local_date(datetime_list, date_list):
    """Hitung jumlah kejadian per tanggal WIB (dihitung di Python biar sama di PostgreSQL & SQLite)."""
    count_dict = {local_date: 0 for local_date in date_list}
    for value in datetime_list:
        local_date = to_local_time(value).date()
        if local_date in count_dict:
            count_dict[local_date] += 1
    return [count_dict[local_date] for local_date in date_list]


def count_created_by_local_date(column, condition, date_list):
    """Agregasi tanggal WIB di database; hanya jumlah per hari yang dikirim ke Python."""
    since, until = build_utc_range_from_local_date(date_list[0], date_list[-1])
    if db.engine.dialect.name == "postgresql":
        local_day = db.func.date(db.func.timezone("Asia/Jakarta", column))
    else:
        local_day = db.func.date(column, "+7 hours")
    counts = {str(day): count for day, count in db.session.execute(
        db.select(local_day, db.func.count()).where(condition, column >= since, column < until).group_by(local_day)
    )}
    return [counts.get(str(day), 0) for day in date_list]


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
    two_week_count_list = count_created_by_local_date(AccessEntry.created_at, build_visible_entry_filter(user), two_week_date_list)
    this_week_count_list = two_week_count_list[DASHBOARD_CHART_DAY_COUNT:]
    last_week_count_list = two_week_count_list[:DASHBOARD_CHART_DAY_COUNT]

    # aktivitas user sendiri 7 hari terakhir
    week_date_list = build_local_date_list(DASHBOARD_CHART_DAY_COUNT)
    activity_count_list = count_created_by_local_date(AuditLog.created_at, AuditLog.user_id == user.id, week_date_list)
    group_list = list_user_group(user)

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
        "group_list": group_list,
        "group_entry_count_dict": count_visible_group_entries(user, group_list),
        "invitation_count": len(list_pending_invitation(user)),
        "forum_row_list": build_forum_row_list(user),
        "recent_activity_list": list_recent_own_activity(user),
    }

"""Notifikasi lonceng: bikin, hitung yg belum dibaca, tandain dibaca."""
from app.extensions import db
from app.models import UserNotification
from app.utils.constants import MAX_NOTIFICATION_MESSAGE_LENGTH, NOTIFICATION_MENU_LIMIT

# alamat tujuan ditulis path biasa, soalnya service juga jalan di luar request (url_for ga bisa)
GROUP_LIST_PATH = "/groups/"

def build_group_path(group_id):
    """Path halaman detail group."""
    return f"{GROUP_LIST_PATH}{group_id}"

def add_notification(user_id, message, target_url=None):
    """Titip notifikasi ke session, commit-nya ikut aksi yg manggil (biar sekali jalan)."""
    notification = UserNotification(
        user_id=user_id, message=message[:MAX_NOTIFICATION_MESSAGE_LENGTH], target_url=target_url,
    )
    db.session.add(notification)
    return notification

def count_unread_notification(user):
    """Jumlah notifikasi yg belum dibaca, buat angka di lonceng."""
    return db.session.execute(
        db.select(db.func.count(UserNotification.id)).where(
            UserNotification.user_id == user.id, UserNotification.is_read.is_(False),
        )
    ).scalar()

def list_recent_notification(user, limit=NOTIFICATION_MENU_LIMIT):
    """Notifikasi terbaru buat isi menu lonceng."""
    return db.session.execute(
        db.select(UserNotification).where(UserNotification.user_id == user.id)
        .order_by(UserNotification.id.desc()).limit(limit)
    ).scalars().all()

def open_notification(user, notification_id):
    """Tandain satu notifikasi dibaca. Punya orang lain / ga ada -> None."""
    notification = db.session.execute(
        db.select(UserNotification).where(
            UserNotification.id == notification_id, UserNotification.user_id == user.id,
        )
    ).scalar_one_or_none()
    if notification is not None and not notification.is_read:
        notification.is_read = True
        db.session.commit()
    return notification

def mark_all_notification_read(user):
    """Tandain semua notifikasi user dibaca."""
    db.session.execute(
        db.update(UserNotification)
        .where(UserNotification.user_id == user.id, UserNotification.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()

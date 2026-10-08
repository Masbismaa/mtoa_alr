"""Ngasih tau Flask-Login cara ngambil user dari id yg disimpen di session."""
from app.extensions import db, login_manager
from app.models import User

@login_manager.user_loader
def load_user(user_id):
    """Ambil user dari DB. User nonaktif dianggap udah keluar."""
    try:
        raw_id, raw_version = user_id.split(":", 1)
        user_id, session_version = int(raw_id), int(raw_version)
    except (AttributeError, TypeError, ValueError):
        return None
    user = db.session.get(User, user_id)
    if user is None or not user.is_active or user.session_version != session_version:
        return None
    return user

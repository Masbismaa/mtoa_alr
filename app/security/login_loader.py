"""Ngasih tau Flask-Login cara ngambil user dari id yg disimpen di session."""
from app.extensions import db, login_manager
from app.models import User

@login_manager.user_loader
def load_user(user_id):
    """Ambil user dari DB. User nonaktif dianggap udah keluar."""
    user = db.session.get(User, int(user_id))
    if user is None or not user.is_active:
        return None
    return user
"""Decorator buat halaman yg cuma boleh dibuka role tertentu."""
from functools import wraps
from flask_login import current_user
from app.security.access_policy import is_admin
from app.utils.exceptions import PermissionDeniedError

def admin_required(view_function):
    """Halaman khusus admin, user biasa dapet 403. Pasang di bawah @login_required."""
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if not is_admin(current_user):
            raise PermissionDeniedError("Halaman ini khusus admin")
        return view_function(*args, **kwargs)
    return wrapper